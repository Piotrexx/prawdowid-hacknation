"""Doprecyzowanie: gdy nie wiadomo, które twierdzenie sprawdzić, system pyta, a odpowiedzi wracają jako kontekst."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import CONSENT_COOKIE, SESSION_COOKIE
from app.main import build_state, create_app
from app.retrieval.corpus import CorpusStore
from app.schemas import ClarifyingQuestion
from app.store.db import Store
from tests.conftest import TEST_SESSION, claim, extraction, seed_corpus

API = "/api/v1"
VAGUE = "Słyszałem, że on znowu podniósł te opłaty w naszym mieście, czy to prawda?"
QUESTIONS = [
    ClarifyingQuestion(text="Kto miał podnieść opłaty?"),
    ClarifyingQuestion(text="O jakie opłaty chodzi?", options=["za wodę", "za śmieci", " "]),
]


def asking(*, questions=QUESTIONS, missing=("kto", "jakie opłaty"), claims=()):
    result = extraction(*claims, status="needs_clarification", message=questions[0].text if questions else "")
    result.questions = list(questions)
    result.missing = list(missing)
    return result


def answered_ok(user: str):
    if "Odpowiedź:" in user:
        return extraction(claim("Prezydent Warszawy podniósł ceny biletów komunikacji miejskiej od stycznia 2026."))
    return asking()


@pytest.fixture
def make_ask_client(settings, provider):
    # Wspólna fabryka nie podaje modelu słów kluczowych, a bez niego wstępny filtr odrzuca każdą treść.
    def factory(session: str = TEST_SESSION) -> TestClient:
        app = create_app(with_lifespan=False)
        corpus = CorpusStore(Store(settings.database_url).engine)
        seed_corpus(corpus)
        build_state(app, settings, provider=provider, bielik_provider=provider, embedder=None, corpus=corpus)
        app.state.store.record_consent(session, settings.privacy_policy_version, True)
        client = TestClient(app)
        client.cookies.set(SESSION_COOKIE, session)
        client.cookies.set(CONSENT_COOKIE, settings.privacy_policy_version)
        return client

    return factory


@pytest.fixture
def client(make_ask_client) -> TestClient:
    return make_ask_client()


def post(client, body, status=200):
    response = client.post(f"{API}/checks", json=body)
    assert response.status_code == status, response.text
    return response.json()


def extract_calls(provider):
    return [(system, user) for name, system, user in provider.calls if name == "Extraction"]


def test_vague_message_gets_questions_not_a_verdict(client, provider):
    provider.extract = lambda user: asking()

    data = post(client, {"text": VAGUE})

    assert data["status"] == "needs_clarification"
    assert data["verdict"] is None and data["claims"] == []
    questions = data["clarification"]["questions"]
    assert [q["text"] for q in questions] == ["Kto miał podnieść opłaty?", "O jakie opłaty chodzi?"]
    assert questions[1]["options"] == ["za wodę", "za śmieci"]
    assert data["clarification"]["missing"] == ["kto", "jakie opłaty"]
    assert (data["clarification"]["round"], data["clarification"]["max_rounds"]) == (1, 2)
    assert "1. Kto miał podnieść opłaty?" in data["status_message"]
    assert not any(name == "ClaimAssessment" for name, _, _ in provider.calls)


def test_model_message_becomes_the_question_when_it_gives_no_list(client, provider):
    provider.extract = lambda user: extraction(status="needs_clarification", message="O którą informację chodzi?")

    data = post(client, {"text": "czy to prawda?"})

    assert [q["text"] for q in data["clarification"]["questions"]] == ["O którą informację chodzi?"]


def test_answer_continues_the_original_check(client, provider):
    provider.extract = answered_ok
    asked = post(client, {"text": VAGUE})

    data = post(client, {"text": "Prezydent Warszawy, bilety od stycznia", "parent_check_id": asked["id"]})

    assert data["status"] == "completed"
    assert data["parent_check_id"] == asked["id"]
    assert data["input"]["text"] == VAGUE
    assert data["clarification"]["questions"] == []
    assert data["clarification"]["history"] == [
        {"questions": ["Kto miał podnieść opłaty?", "O jakie opłaty chodzi?"], "answer": "Prezydent Warszawy, bilety od stycznia"}
    ]
    system, user = extract_calls(provider)[-1]
    assert "Doprecyzowanie od użytkownika:" in user and "Odpowiedź: Prezydent Warszawy" in user
    assert "Nie używaj" not in system


def test_answers_are_masked_like_any_other_input(client, provider):
    provider.extract = answered_ok
    asked = post(client, {"text": VAGUE})

    data = post(client, {"text": "Napisał mi o tym jan.kowalski@example.com", "parent_check_id": asked["id"]})

    assert "jan.kowalski@example.com" not in extract_calls(provider)[-1][1]
    assert any(w["code"] == "pii_masked" for w in data["warnings"])


def test_stops_asking_after_max_rounds(client, provider):
    provider.extract = lambda user: asking()
    first = post(client, {"text": VAGUE})
    second = post(client, {"text": "nie wiem", "parent_check_id": first["id"]})
    assert second["clarification"]["round"] == 2

    third = post(client, {"text": "naprawdę nie wiem", "parent_check_id": second["id"]})

    system, _ = extract_calls(provider)[-1]
    assert "Nie używaj" in system
    assert third["status"] == "needs_clarification"
    assert third["clarification"]["questions"] == []
    assert len(third["clarification"]["history"]) == 2
    assert "Mimo doprecyzowania" in third["status_message"]
    post(client, {"text": "jeszcze raz", "parent_check_id": third["id"]}, status=409)


def test_after_max_rounds_claims_are_checked_with_a_note(client, provider):
    provider.extract = lambda user: asking() if user.count("Odpowiedź:") < 2 else asking(
        claims=[claim("Opłaty za wodę w Warszawie wzrosły.")]
    )
    first = post(client, {"text": VAGUE})
    second = post(client, {"text": "nie wiem", "parent_check_id": first["id"]})

    third = post(client, {"text": "chyba za wodę", "parent_check_id": second["id"]})

    assert third["status"] == "completed"
    assert len(third["claims"]) == 1
    assert any("Mimo doprecyzowania" in note for note in third["limitations"])


def test_answer_to_a_page_fetches_the_page_again(client, provider, mock_fetch_page):
    provider.extract = answered_ok
    asked = post(client, {"url": "https://example.org/artykul"})

    data = post(client, {"text": "chodzi o ceny", "parent_check_id": asked["id"]})

    assert data["status"] == "completed"
    assert (data["input"]["kind"], data["input"]["url"]) == ("url", "https://example.org/artykul")


def test_replies_to_unknown_foreign_or_finished_checks_are_rejected(client, make_ask_client, provider):
    provider.extract = lambda user: asking()
    asked = post(client, {"text": VAGUE})
    stranger = make_ask_client(session="inna-sesja-0002")
    provider.extract = lambda user: extraction(claim("Twierdzenie testowe."))
    done = post(client, {"text": "Most w Testowie zawalił się podczas powodzi."})

    post(client, {"text": "x", "parent_check_id": "0" * 32}, status=404)
    post(stranger, {"text": "x", "parent_check_id": asked["id"]}, status=404)
    post(client, {"text": "x", "parent_check_id": done["id"]}, status=409)


@pytest.mark.parametrize(
    "body",
    [
        {"parent_check_id": "a" * 32},
        {"parent_check_id": "a" * 32, "text": "   "},
        {"parent_check_id": "a" * 32, "text": "x", "url": "https://example.org"},
        {"parent_check_id": "nie-hex", "text": "x"},
    ],
)
def test_invalid_replies(client, body):
    post(client, body, status=422)
