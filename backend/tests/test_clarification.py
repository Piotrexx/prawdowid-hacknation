"""Doprecyzowanie: system dopytuje, gdy nie wie, co sprawdzić, a odpowiedź wraca jako kontekst."""

import pytest

from app.llm.base import LLMUnavailable, Usage
from app.schemas import ClarifyingQuestion, ClarityCheck, KeywordExtraction, VerdictLabel
from app.security.ratelimit import RateLimiter

API = "/api/v1"
VAGUE = "Słyszałem, że on znowu to zrobił w tym mieście, czy to prawda?"

ASK = ClarityCheck(
    needs_clarification=True,
    questions=[
        ClarifyingQuestion(text="O kim jest ta wiadomość?"),
        ClarifyingQuestion(text="Które twierdzenie sprawdzić?", options=["podwyżka cen", "zamknięcie szkoły", " "]),
    ],
    missing=["kto", "miejsce"],
)
CLEAR = ClarityCheck()
KEYWORDS = KeywordExtraction(keywords=["Kowalski", "Gdańsk"], main_topic="Prezydent Gdańska", summary="Twierdzenie.")


class Bielik:
    """Tylko słowa kluczowe."""

    name = "openai_compatible"
    model = "bielik:4.5b-instruct"

    def __init__(self, fail: Exception | None = None):
        self.prompts: list[str] = []
        self.fail = fail

    async def structured(self, *, system, user, schema, effort="medium", images=None):
        assert schema is KeywordExtraction
        self.prompts.append(user)
        if self.fail:
            raise self.fail
        return KEYWORDS, Usage(100, 20, 1)


class MainModel:
    """Główny model (DeepSeek): ocena doprecyzowania według scenariusza oraz werdykt."""

    name = "openai_compatible"
    model = "deepseek-flash"

    def __init__(self, *clarity: ClarityCheck | Exception):
        self.clarity = list(clarity) or [CLEAR]
        self.clarity_prompts: list[str] = []
        self.verdict_prompts: list[str] = []

    async def structured(self, *, system, user, schema, effort="medium", images=None):
        if schema is ClarityCheck:
            self.clarity_prompts.append(user)
            response = self.clarity.pop(0) if len(self.clarity) > 1 else self.clarity[0]
            if isinstance(response, Exception):
                raise response
            return response, Usage(300, 50, 1)
        self.verdict_prompts.append(user)
        return schema(verdict=VerdictLabel.FAKE, confidence=0.8, justification="Uzasadnienie."), Usage(500, 100, 1)


@pytest.fixture
def make_client(make_client):
    # Wspólna fabryka ustawia limiter na None, a zależność limitu zakłada, że istnieje.
    def factory(**overrides):
        client = make_client(**overrides)
        client.app.state.limiter = RateLimiter(1000)
        return client

    return factory


@pytest.fixture
def client(make_client):
    return make_client()


def _client(make_client, main: MainModel, bielik: Bielik | None = None):
    return make_client(provider=main, bielik_provider=bielik or Bielik())


def test_short_text_asks_without_calling_models(make_client):
    main, bielik = MainModel(), Bielik()
    client = _client(make_client, main, bielik)

    data = client.post(f"{API}/checks", json={"text": "szczepionki"}).json()

    assert data["status"] == "needs_clarification"
    assert data["verdict"] is None
    assert data["input"]["kind"] == "text"
    assert data["clarification"]["round"] == 1
    assert data["clarification"]["max_rounds"] == 2
    assert len(data["clarification"]["questions"]) == 1
    assert bielik.prompts == [] and main.clarity_prompts == [] and main.verdict_prompts == []


def test_main_model_asks_and_no_verdict_is_given(make_client):
    main = MainModel(ASK)
    client = _client(make_client, main)

    data = client.post(f"{API}/checks", json={"text": VAGUE}).json()

    assert data["status"] == "needs_clarification"
    assert data["verdict"] is None
    questions = data["clarification"]["questions"]
    assert [q["text"] for q in questions] == ["O kim jest ta wiadomość?", "Które twierdzenie sprawdzić?"]
    assert questions[1]["options"] == ["podwyżka cen", "zamknięcie szkoły"]
    assert data["clarification"]["missing"] == ["kto", "miejsce"]
    assert "O kim jest ta wiadomość?" in data["status_message"]
    assert main.verdict_prompts == []


def test_clear_text_goes_straight_to_verdict(make_client):
    main = MainModel(CLEAR)
    data = _client(make_client, main).post(f"{API}/checks", json={"text": VAGUE}).json()

    assert data["status"] == "completed"
    assert data["clarification"] is None
    assert data["keywords"] == ["Kowalski", "Gdańsk"]


def test_answer_continues_the_original_check(make_client):
    main, bielik = MainModel(ASK, CLEAR), Bielik()
    client = _client(make_client, main, bielik)
    asked = client.post(f"{API}/checks", json={"text": VAGUE}).json()

    data = client.post(
        f"{API}/checks", json={"text": "Prezydent Gdańska, chodzi o podwyżkę cen", "parent_check_id": asked["id"]}
    ).json()

    assert data["status"] == "completed"
    assert data["verdict"] == "fake_news"
    assert data["parent_check_id"] == asked["id"]
    assert data["input"]["text"] == VAGUE
    history = data["clarification"]["history"]
    assert history == [
        {"questions": ["O kim jest ta wiadomość?", "Które twierdzenie sprawdzić?"], "answer": "Prezydent Gdańska, chodzi o podwyżkę cen"}
    ]
    assert data["clarification"]["questions"] == []
    # Słowa kluczowe z pierwszej rundy mogły zostać anulowane po pytaniu, więc bierzemy ostatnie.
    for prompt in (main.clarity_prompts[1], bielik.prompts[-1], main.verdict_prompts[0]):
        assert "Odpowiedź: Prezydent Gdańska" in prompt


def test_stops_asking_after_max_rounds(make_client):
    client = _client(make_client, MainModel(ASK))
    first = client.post(f"{API}/checks", json={"text": VAGUE}).json()
    second = client.post(f"{API}/checks", json={"text": "nie wiem", "parent_check_id": first["id"]}).json()
    assert second["status"] == "needs_clarification"
    assert second["clarification"]["round"] == 2

    third = client.post(f"{API}/checks", json={"text": "naprawdę nie wiem", "parent_check_id": second["id"]}).json()

    assert third["status"] == "completed"
    assert len(third["clarification"]["history"]) == 2
    assert any("Mimo doprecyzowania" in note for note in third["limitations"])


def test_failed_clarity_check_does_not_block_the_check(make_client):
    data = _client(make_client, MainModel(LLMUnavailable("brak połączenia"))).post(
        f"{API}/checks", json={"text": VAGUE}
    ).json()

    assert data["status"] == "completed"
    assert data["verdict"] == "fake_news"


def test_question_wins_over_failed_keywords(make_client):
    data = _client(make_client, MainModel(ASK), Bielik(fail=LLMUnavailable("brak"))).post(
        f"{API}/checks", json={"text": VAGUE}
    ).json()

    assert data["status"] == "needs_clarification"


def test_clarification_model_off_never_asks(make_client, settings):
    settings.clarification_model = "off"
    main = MainModel(ASK)
    data = _client(make_client, main).post(f"{API}/checks", json={"text": VAGUE}).json()

    assert data["status"] == "completed"
    assert main.clarity_prompts == []


def test_clarification_by_bielik(make_client, settings):
    settings.clarification_model = "bielik"

    class AskingBielik(Bielik):
        async def structured(self, *, system, user, schema, effort="medium", images=None):
            if schema is ClarityCheck:
                return ASK, Usage(100, 20, 1)
            return await super().structured(system=system, user=user, schema=schema)

    main = MainModel(CLEAR)
    data = _client(make_client, main, AskingBielik()).post(f"{API}/checks", json={"text": VAGUE}).json()

    assert data["status"] == "needs_clarification"
    assert main.clarity_prompts == []


def test_answer_to_url_check_refetches_the_article(make_client):
    client = _client(make_client, MainModel(ASK, CLEAR))
    asked = client.post(f"{API}/checks", json={"url": "https://example.org/artykul"}).json()

    data = client.post(f"{API}/checks", json={"text": "chodzi o ceny", "parent_check_id": asked["id"]}).json()

    assert data["status"] == "completed"
    assert data["input"]["kind"] == "url"
    assert data["input"]["url"] == "https://example.org/artykul"


def test_reply_to_unknown_or_finished_check_is_rejected(make_client):
    client = _client(make_client, MainModel(CLEAR))
    done = client.post(f"{API}/checks", json={"text": VAGUE}).json()
    assert done["status"] == "completed"

    assert client.post(f"{API}/checks", json={"text": "x", "parent_check_id": "0" * 32}).status_code == 404
    assert client.post(f"{API}/checks", json={"text": "x", "parent_check_id": done["id"]}).status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"url": "https://example.org", "text": "oba naraz"},
        {"parent_check_id": "a" * 32},
        {"parent_check_id": "a" * 32, "text": "x", "url": "https://example.org"},
        {"parent_check_id": "nie-hex", "text": "x"},
    ],
)
def test_invalid_requests(client, body):
    assert client.post(f"{API}/checks", json=body).status_code == 422
