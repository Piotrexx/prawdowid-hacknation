"""Testy funkcji domykających wymagania: głos, archiwum, STIX, zgoda, brak /sources."""

import json

from app.core.audio import AudioError
from app.core.prompts import ImageReading
from app.schemas import Verdict
from tests.conftest import ADMIN, VACCINE_QUOTE, assessment, claim, extraction, passage_number

API = "/api/v1"
VACCINE_CLAIM = "Program szczepień ochronnych w Testowie rozpoczął się 1 marca."


def _confirm(provider):
    provider.extract = lambda user: extraction(claim(VACCINE_CLAIM))
    provider.assess = lambda user: assessment(
        Verdict.CONFIRMED,
        (passage_number(user, VACCINE_QUOTE), "supports", VACCINE_QUOTE),
    )


def test_sources_endpoint_is_gone(client):
    assert client.get(f"{API}/sources").status_code == 404


def test_consent_is_required_before_saving(make_client):
    client = make_client()
    client.cookies.clear()
    refused = client.post(f"{API}/checks", json={"text": VACCINE_CLAIM})
    assert refused.status_code == 428

    recorded = client.post(
        f"{API}/consent",
        json={"session_id": "nowa-sesja-0001", "policy_version": "2026-11-21", "accepted": True},
    )
    assert recorded.status_code == 200
    client.cookies.set("prawdowid_privacy_consent", "2026-11-21")
    client.cookies.set("prawdowid_session", "nowa-sesja-0001")
    allowed = client.post(f"{API}/checks", json={"text": VACCINE_CLAIM})
    assert allowed.status_code == 200


def test_audio_check_transcribes_locally_and_warns(client, provider, monkeypatch):
    _confirm(provider)
    monkeypatch.setattr(
        "app.core.pipeline.transcribe_audio",
        lambda data, settings: (
            f"{VACCINE_CLAIM} To jest nagranie głosowe.",
            {"model": "small", "język": "pl", "rozmiar": "10 kB"},
        ),
    )
    response = client.post(
        f"{API}/checks/audio",
        files={"file": ("nagranie.webm", b"\x1aE\xdf\xa3fake", "audio/webm")},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "completed"
    assert result["input"]["kind"] == "audio"
    assert result["input"]["text"].startswith(VACCINE_CLAIM)
    assert result["input"]["audio_metadata"]["model"] == "small"
    assert any(w["code"] == "audio_limits" for w in result["warnings"])


def test_audio_failure_is_a_technical_limitation(client, monkeypatch):
    def _fail(data, settings):
        raise AudioError("transcription_unavailable", "Brak modelu.")

    monkeypatch.setattr("app.core.pipeline.transcribe_audio", _fail)
    response = client.post(
        f"{API}/checks/audio",
        files={"file": ("nagranie.webm", b"audio", "audio/webm")},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "error"
    assert result["error_code"] == "transcription_unavailable"
    assert result["claims"] == []


def test_archive_roundtrip_and_session_scope(client, provider):
    _confirm(provider)
    result = client.post(f"{API}/checks", json={"text": VACCINE_CLAIM}).json()
    archived = client.post(f"{API}/archive", json={"check_id": result["id"]})
    assert archived.status_code == 200, archived.text
    row = archived.json()
    assert row["check_id"] == result["id"]
    assert row["excerpt"] and row["content_hash"] and row["retention_until"]

    fetched = client.get(f"{API}/archive/{row['id']}")
    assert fetched.status_code == 200 and fetched.json()["id"] == row["id"]

    listed = client.get(f"{API}/admin/archive", headers=ADMIN).json()
    assert [item["id"] for item in listed] == [row["id"]]

    assert client.delete(f"{API}/archive/{row['id']}").json() == {"deleted": True}
    assert client.get(f"{API}/archive/{row['id']}").status_code == 404


def test_stix_export_is_valid_bundle(client, provider):
    _confirm(provider)
    result = client.post(f"{API}/checks", json={"text": VACCINE_CLAIM}).json()
    response = client.get(f"{API}/admin/export/stix", headers=ADMIN)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/stix+json")
    bundle = json.loads(response.text)
    assert bundle["type"] == "bundle"
    types = {obj["type"] for obj in bundle["objects"]}
    assert {"identity", "note", "report"} <= types
    assert any(obj.get("x_prawdowid_check_id") == result["id"] for obj in bundle["objects"])


def test_image_metadata_still_works(client, provider):
    provider.reading = ImageReading(
        text=VACCINE_CLAIM, visible_dates=["1 marca"], description="zrzut ekranu", readable=True, injection_detected=False
    )
    _confirm(provider)
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (20, 10), "white").save(buffer, format="PNG")
    response = client.post(
        f"{API}/checks/image",
        files={"file": ("zrzut.png", buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["input"]["kind"] == "image"
