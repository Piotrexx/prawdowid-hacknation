"""Testy weryfikacji zdjęć – bez sieci: syntetyczne obrazy, wstrzyknięte wyszukiwanie i pobieranie."""

import asyncio
import io
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter, PngImagePlugin

from app.config import Settings
from app.core import image_compare
from app.core.image_check import ImageCheckService, _copies
from app.core.image_compare import Relation
from app.core.image_provenance import Provenance, _c2pa_integrity, inspect_file
from app.core.image_search import EngineResult, FoundImage
from app.core.prompts import Extraction, ImageReading
from app.schemas import AiAssessment, AiSignal, CheckStatus, ClarifyingQuestion, ImageAnalysis, Verdict
from app.store.db import Store


def _scene(seed: int = 7, size: tuple[int, int] = (800, 600)) -> Image.Image:
    """Teksturowana scena z wieloma punktami charakterystycznymi dla SIFT."""
    rng = np.random.default_rng(seed)
    w, h = size
    noise = rng.integers(0, 255, (h // 8, w // 8, 3), dtype=np.uint8)
    img = Image.fromarray(noise).resize(size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(2))
    draw = ImageDraw.Draw(img)
    for _ in range(40):
        x, y = int(rng.integers(0, w - 60)), int(rng.integers(0, h - 60))
        r = int(rng.integers(10, 50))
        color = tuple(int(v) for v in rng.integers(0, 255, 3))
        if rng.random() < 0.5:
            draw.rectangle([x, y, x + r, y + r], fill=color)
        else:
            draw.ellipse([x, y, x + r, y + r], fill=color)
    return img


def _jpeg(img: Image.Image, quality: int = 88) -> bytes:
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, "JPEG", quality=quality)
    return buffer.getvalue()


def _copy(img: Image.Image, scale: float, quality: int, crop: float = 0.0) -> bytes:
    """Kopia "z innej strony": przeskalowana, ponownie skompresowana, lekko przycięta."""
    w, h = img.size
    dx, dy = int(w * crop), int(h * crop)
    out = img.crop((dx, dy, w - dx, h - dy))
    out = out.resize((int(out.width * scale), int(out.height * scale)), Image.LANCZOS)
    return _jpeg(out, quality)


def _edited(img: Image.Image) -> Image.Image:
    out = img.copy()
    w, h = out.size
    ImageDraw.Draw(out).ellipse([w * 0.06, h * 0.06, w * 0.28, h * 0.3], fill=(250, 245, 230))
    return out


ORIGINAL = _scene()
COPIES = [_copy(ORIGINAL, 0.7, 80), _copy(ORIGINAL, 0.5, 75, 0.03), _copy(ORIGINAL, 1.0, 92), _copy(ORIGINAL, 0.6, 70, 0.05)]


def _prepared(data: bytes) -> np.ndarray:
    return image_compare.prepare(Image.open(io.BytesIO(data)).convert("RGB"))


def _service(
    settings: Settings,
    copies: list[bytes] | None = None,
    *,
    results: list[EngineResult] | None = None,
    first_seen: date | None = None,
):
    copies = COPIES if copies is None else copies
    store = {f"https://img.example/{i}.jpg": body for i, body in enumerate(copies)}
    calls = {"search": 0}

    async def search(data, engines, timeout):
        calls["search"] += 1
        if results is not None:
            return results
        found = [
            FoundImage(
                engine="tineye" if i % 2 else "yandex",
                page_url=f"https://news{i}.example/artykul",
                image_url=url,
                thumbnail_url=None,
                title=f"Artykuł {i}",
                domain=f"news{i}.example",
                first_seen=first_seen,
            )
            for i, url in enumerate(store)
        ]
        return [
            EngineResult("yandex", True, [f for f in found if f.engine == "yandex"], 120),
            EngineResult("tineye", True, [f for f in found if f.engine == "tineye"], 10),
        ]

    async def download(url):
        return store[url]

    service = ImageCheckService(settings, Store(settings.database_url), search=search, download=download)
    return service, calls


# --- porównanie obrazów ---


def test_compare_identical_copy_despite_rescale_and_crop():
    query = _prepared(_jpeg(ORIGINAL))
    for body in COPIES:
        assert image_compare.compare(query, _prepared(body)).relation == Relation.IDENTICAL


def test_compare_finds_local_edit_in_the_right_place():
    result = image_compare.compare(_prepared(_jpeg(_edited(ORIGINAL))), _prepared(COPIES[0]))
    assert result.relation == Relation.LOCALLY_MODIFIED
    assert result.hot_cells and all(i <= 2 and j <= 2 for i, j in result.hot_cells)


def test_compare_unrelated_image_is_not_comparable():
    other = _prepared(_jpeg(_scene(seed=99)))
    assert image_compare.compare(_prepared(_jpeg(ORIGINAL)), other).relation == Relation.NOT_COMPARABLE


# --- usługa ---


def test_edited_image_is_flagged_with_changed_region(settings):
    service, _ = _service(settings)
    response = asyncio.run(service.check(_jpeg(_edited(ORIGINAL)), None))
    analysis = response.image_analysis
    assert response.status == CheckStatus.COMPLETED
    assert response.verdict == Verdict.FALSE
    assert analysis.assessment == "manipulation_suspected"
    assert analysis.changed_regions and all(r.x < 0.4 and r.y < 0.4 for r in analysis.changed_regions)
    assert response.warnings[0].code == "image_manipulation"


def test_original_image_is_consistent_with_copies(settings):
    service, _ = _service(settings)
    response = asyncio.run(service.check(_jpeg(ORIGINAL), None))
    assert response.verdict == Verdict.CONFIRMED
    assert response.image_analysis.assessment == "consistent_with_copies"
    assert response.image_analysis.identical == len(COPIES)
    assert {s.source_type for s in response.source_articles} == {"reverse_image"}


def test_no_matches_is_uncertain(settings):
    service, _ = _service(settings, results=[EngineResult("yandex", True, [], 0), EngineResult("tineye", True, [], 0)])
    response = asyncio.run(service.check(_jpeg(ORIGINAL), None))
    assert response.verdict == Verdict.INSUFFICIENT
    assert response.image_analysis.assessment == "no_matches"


def test_all_engines_down_is_an_error_not_a_verdict(settings):
    down = [EngineResult("yandex", False, [], error="captcha"), EngineResult("tineye", False, [], error="timeout")]
    service, _ = _service(settings, results=down)
    response = asyncio.run(service.check(_jpeg(ORIGINAL), None))
    assert response.status == CheckStatus.ERROR
    assert response.error_code == "image_search_unavailable"
    assert response.verdict is None


def test_one_engine_down_adds_warning(settings):
    service, _ = _service(settings)
    partial = asyncio.run(service._search(b"", [], 1))[:1] + [EngineResult("tineye", False, [], error="timeout")]
    service, _ = _service(settings, results=partial)
    response = asyncio.run(service.check(_jpeg(ORIGINAL), None))
    assert response.status == CheckStatus.COMPLETED
    assert "retrieval_degraded" in {w.code for w in response.warnings}


def test_invalid_file_is_rejected(settings):
    service, calls = _service(settings)
    response = asyncio.run(service.check(b"to nie jest obraz", None))
    assert response.status == CheckStatus.ERROR
    assert response.error_code == "image_invalid"
    assert calls["search"] == 0


def test_huge_resolution_is_rejected(settings):
    buffer = io.BytesIO()
    Image.new("1", (7000, 6000)).save(buffer, "PNG")
    service, calls = _service(settings)
    response = asyncio.run(service.check(buffer.getvalue(), None))
    assert response.error_code == "image_too_large"
    assert calls["search"] == 0


def test_same_image_is_served_from_cache(settings):
    service, calls = _service(settings)
    data = _jpeg(ORIGINAL)
    first = asyncio.run(service.check(data, None))
    second = asyncio.run(service.check(data, None))
    assert calls["search"] == 1
    assert second.meta.cached and second.verdict == first.verdict


def test_polish_plural():
    assert [_copies(n) for n in (1, 2, 5, 12, 22, 25)] == ["1 kopię", "2 kopie", "5 kopii", "12 kopii", "22 kopie", "25 kopii"]


# --- ślady AI w metadanych ---

FIXTURES = Path(__file__).parent / "fixtures"
NO_RESULTS = [EngineResult("yandex", True, [], 0), EngineResult("tineye", True, [], 0)]


def _provenance(data: bytes):
    return inspect_file(data, Image.open(io.BytesIO(data)))


def _png(**text: str) -> bytes:
    info = PngImagePlugin.PngInfo()
    for key, value in text.items():
        info.add_text(key, value)
    buffer = io.BytesIO()
    _scene().save(buffer, "PNG", pnginfo=info)
    return buffer.getvalue()


def _jpeg_with_xmp(xmp: bytes) -> bytes:
    buffer = io.BytesIO()
    _scene().save(buffer, "JPEG", xmp=xmp)
    return buffer.getvalue()


_MIDJOURNEY_XMP = (
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF><rdf:Description xmp:CreatorTool="Midjourney" '
    b'Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"/>'
    b"</rdf:RDF></x:xmpmeta>"
)


def test_c2pa_ai_generated_with_intact_signature():
    found = _provenance((FIXTURES / "c2pa_ai.jpg").read_bytes())
    assert found.kind == "ai_generated"
    assert found.signals[0].source == "c2pa" and found.signals[0].signed
    assert found.signals[0].generator == "TestGen AI"


def test_c2pa_ai_edit_and_camera_capture():
    assert _provenance((FIXTURES / "c2pa_ai_edit.jpg").read_bytes()).kind == "ai_edited"
    camera = _provenance((FIXTURES / "c2pa_camera.jpg").read_bytes())
    assert camera.kind is None
    assert "TestCamera" in camera.content_credentials and "nienaruszony" in camera.content_credentials


def test_c2pa_file_changed_after_signing_has_invalid_signature():
    data = bytearray((FIXTURES / "c2pa_ai.jpg").read_bytes())
    data[-200] ^= 0xFF
    found = _provenance(bytes(data))
    assert found.kind == "ai_generated" and not found.signals[0].signed
    assert "zmieniono po podpisaniu" in found.content_credentials


@pytest.mark.parametrize(
    ("store", "intact", "phrase"),
    [
        ({"validation_state": "Valid"}, True, "nienaruszony"),
        (
            {"validation_state": "Invalid", "validation_status": [{"code": "signingCredential.expired"}, {"code": "signingCredential.untrusted"}]},
            True,
            "wygasł",
        ),
        (
            {"validation_state": "Invalid", "validation_status": [{"code": "assertion.dataHash.mismatch"}]},
            False,
            "zmieniono po podpisaniu",
        ),
    ],
)
def test_c2pa_expired_certificate_is_not_reported_as_tampering(store, intact, phrase):
    signed, status = _c2pa_integrity(store)
    assert signed is intact and phrase in status


@pytest.mark.parametrize(
    ("data", "generator"),
    [
        (_png(parameters="a cat, Steps: 20, Sampler: Euler a, CFG scale: 7"), "Stable Diffusion (A1111)"),
        (_png(prompt='{"3": {"class_type": "KSampler"}}', workflow='{"nodes": []}'), "ComfyUI"),
        (_jpeg_with_xmp(_MIDJOURNEY_XMP), "Midjourney"),
    ],
)
def test_generator_metadata_is_detected(data, generator):
    found = _provenance(data)
    assert found.kind == "ai_generated"
    assert found.signals[0].generator == generator


@pytest.mark.parametrize(
    "data",
    [
        _png(prompt="zdjęcie z wakacji"),  # zwykły opis w polu "prompt"
        _png(Description="A firefly at night", Software="GIMP 2.10"),  # "firefly" w opisie, nie w programie
        _jpeg(ORIGINAL),
    ],
)
def test_ordinary_files_have_no_ai_signals(data):
    assert _provenance(data).kind is None


def test_ai_metadata_overrides_copy_comparison(settings):
    service, _ = _service(settings, results=NO_RESULTS)
    response = asyncio.run(service.check((FIXTURES / "c2pa_ai.jpg").read_bytes(), None))
    assert response.verdict == Verdict.FALSE
    assert response.confidence == 0.95
    assert response.image_analysis.ai.result == "ai_generated"
    assert response.warnings[0].code == "ai_generated"
    assert "Content Credentials" in response.justification


def test_unsigned_ai_metadata_has_lower_confidence(settings):
    service, _ = _service(settings, results=NO_RESULTS)
    response = asyncio.run(service.check(_jpeg_with_xmp(_MIDJOURNEY_XMP), None))
    assert response.verdict == Verdict.FALSE
    assert response.confidence == 0.85


def test_ai_edit_downgrades_consistent_copies_to_uncertain():
    analysis = ImageAnalysis(
        assessment="consistent_with_copies",
        sha256="0" * 64,
        width=10,
        height=10,
        compared=4,
        identical=4,
        ai=AiAssessment(
            result="ai_edited",
            signals=[AiSignal(source="c2pa", kind="ai_edited", detail="Content Credentials (C2PA): obraz edytowany z użyciem AI", signed=True)],
        ),
    )
    plain = analysis.model_copy(update={"ai": AiAssessment(result="no_signals")})
    assert ImageCheckService._verdict(plain)[0] == Verdict.CONFIRMED
    verdict, confidence, text = ImageCheckService._verdict(analysis)
    assert verdict == Verdict.INSUFFICIENT and confidence == 0.5
    assert text.startswith("Content Credentials (C2PA): obraz edytowany")


def test_ai_edit_warning_comes_first(settings):
    service, _ = _service(settings, results=NO_RESULTS)
    response = asyncio.run(service.check((FIXTURES / "c2pa_ai_edit.jpg").read_bytes(), None))
    assert response.image_analysis.ai.result == "ai_edited"
    assert response.warnings[0].code == "ai_edited"


def test_camera_credentials_are_reported_as_information(settings):
    service, _ = _service(settings, results=NO_RESULTS)
    response = asyncio.run(service.check((FIXTURES / "c2pa_camera.jpg").read_bytes(), None))
    assert response.image_analysis.ai.result == "no_signals"
    assert "content_credentials" in {w.code for w in response.warnings}


def test_copies_online_before_2022_make_ai_unlikely(settings):
    service, _ = _service(settings, first_seen=date(2019, 5, 1))
    response = asyncio.run(service.check(_jpeg(ORIGINAL), None))
    assert response.image_analysis.ai.result == "predates_generative_ai"
    assert response.verdict == Verdict.CONFIRMED
    assert "przed upowszechnieniem generatorów" in response.justification


def test_dates_of_lookalike_images_are_ignored(settings):
    """Inna twarz z generatora sprzed 2022 nie może dać sygnału "zdjęcie starsze niż generatory AI"."""
    service, _ = _service(settings)
    lookalike = FoundImage("tineye", "https://faces.example/1", "https://faces.example/1.jpg", None, None, "faces.example", date(2019, 1, 1))
    same = FoundImage("tineye", "https://news.example/1", "https://news.example/1.jpg", None, None, "news.example", date(2024, 3, 1))
    comparisons = {
        0: image_compare.Comparison(Relation.DIFFERENT_VERSION, median_diff=15.0),
        1: image_compare.Comparison(Relation.IDENTICAL, median_diff=0.5),
    }
    results = [EngineResult("tineye", True, [lookalike, same], 2)]
    analysis = service._analyse("0" * 64, ORIGINAL, {}, Provenance(), results, [lookalike, same], comparisons)
    assert analysis.earliest_seen == date(2024, 3, 1)
    assert analysis.ai.result == "no_signals"


def test_recent_copies_give_no_ai_signal(settings):
    service, _ = _service(settings, first_seen=date(2024, 5, 1))
    response = asyncio.run(service.check(_jpeg(ORIGINAL), None))
    assert response.image_analysis.ai.result == "no_signals"


# --- endpoint ---


@pytest.fixture
def image_service(settings):
    service, calls = _service(settings)
    return service, calls


@pytest.fixture
def image_client(make_client, image_service, provider):
    service, _ = image_service
    provider.reading = ImageReading(
        text="Most w Testowie został zamknięty na czas remontu.",
        visible_dates=[],
        description="zrzut ekranu artykułu",
        readable=True,
        injection_detected=False,
    )
    return make_client(image_checks=service)


def test_endpoint_merges_ocr_with_image_analysis(image_client):
    reply = image_client.post(
        "/api/v1/checks/image",
        files={"file": ("zdjecie.jpg", _jpeg(_edited(ORIGINAL)), "image/jpeg")},
    )
    assert reply.status_code == 200
    body = reply.json()
    # Ten sam obraz przechodzi OCR (twierdzenia) i analizę manipulacji w jednej odpowiedzi.
    assert body["input"]["kind"] == "image"
    assert body["claims"]
    assert body["verdict"] == "falszywe"
    assert body["image_analysis"]["assessment"] == "manipulation_suspected"
    assert body["image_analysis"]["changed_regions"]
    assert "image_manipulation" in {w["code"] for w in body["warnings"]}
    assert image_client.get(f"/api/v1/checks/{body['id']}").status_code == 200


def test_endpoint_keeps_user_comment_apart_from_ocr(image_client):
    reply = image_client.post(
        "/api/v1/checks/image",
        files={"file": ("zdjecie.jpg", _jpeg(ORIGINAL), "image/jpeg")},
        data={"comment": "  Dostałem to od sąsiada, tel. 600 700 800. Czy to prawda?  "},
    )
    assert reply.status_code == 200
    body = reply.json()
    assert body["input"]["kind"] == "image"
    assert "Czy to prawda?" in body["input"]["comment"]
    assert "600 700 800" not in body["input"]["comment"]
    assert "Czy to prawda?" not in body["input"]["text"]


def test_photo_without_text_is_judged_by_the_image_alone(make_client, image_service, provider):
    service, _ = image_service
    provider.reading = ImageReading(
        text="", visible_dates=[], description="zdjęcie mostu", readable=False, injection_detected=False
    )
    client = make_client(image_checks=service)
    body = client.post(
        "/api/v1/checks/image", files={"file": ("zdjecie.jpg", _jpeg(_edited(ORIGINAL)), "image/jpeg")}
    ).json()
    # Brak tekstu nie kończy się pytaniem o kontekst: wynik to analiza samego zdjęcia.
    assert body["status"] == "completed"
    assert body["clarification"] is None
    assert body["claims"] == []
    assert body["verdict"] == "falszywe"
    assert body["image_analysis"]["assessment"] == "manipulation_suspected"


def test_image_never_asks_clarifying_questions(make_client, image_service, provider):
    service, _ = image_service
    provider.reading = ImageReading(
        text="Zobaczcie, co się stało!", visible_dates=[], description="wpis", readable=True, injection_detected=False
    )
    provider.extract = lambda user: Extraction(
        input_status="needs_clarification", message="Kto?", claims=[], injection_detected=False,
        questions=[ClarifyingQuestion(text="Kto?")],
    )
    client = make_client(image_checks=service)
    body = client.post(
        "/api/v1/checks/image", files={"file": ("zdjecie.jpg", _jpeg(ORIGINAL), "image/jpeg")}
    ).json()
    assert body["status"] == "completed"
    assert body["clarification"] is None
    assert body["image_analysis"] is not None
    extract_system = next(system for name, system, _ in provider.calls if name == "Extraction")
    assert "nie używaj \"needs_clarification\"" in extract_system


def test_endpoint_survives_image_search_failure(make_client, settings, provider):
    down = [
        EngineResult("yandex", False, [], error="captcha"),
        EngineResult("tineye", False, [], error="timeout"),
    ]
    service, _ = _service(settings, results=down)
    provider.reading = ImageReading(
        text="Most w Testowie został zamknięty na czas remontu.",
        visible_dates=[],
        description="zrzut ekranu artykułu",
        readable=True,
        injection_detected=False,
    )
    client = make_client(image_checks=service)
    reply = client.post(
        "/api/v1/checks/image",
        files={"file": ("zdjecie.jpg", _jpeg(ORIGINAL), "image/jpeg")},
    )
    body = reply.json()
    # Awaria wyszukiwarek obrazów nie jest werdyktem o treści ani błędem sprawdzenia.
    assert reply.status_code == 200
    assert body["status"] == "completed"
    assert body["claims"]
    assert body["image_analysis"] is None
    assert "image_analysis_unavailable" in {w["code"] for w in body["warnings"]}


def test_endpoint_rejects_too_large_file(make_client, image_service):
    service, _ = image_service
    client = make_client(image_checks=service, image_max_bytes=1_000_000)
    reply = client.post("/api/v1/checks/image", files={"file": ("duze.jpg", b"0" * 1_000_001, "image/jpeg")})
    body = reply.json()
    # Za duży plik to techniczne ograniczenie wejścia, nie werdykt.
    assert reply.status_code == 200
    assert body["status"] == "error"
    assert body["error_code"] == "image_too_large"


def test_endpoint_rejects_bad_session_id(image_client):
    reply = image_client.post(
        "/api/v1/checks/image",
        files={"file": ("a.jpg", _jpeg(ORIGINAL), "image/jpeg")},
        data={"session_id": "zła sesja!"},
    )
    assert reply.status_code == 422
