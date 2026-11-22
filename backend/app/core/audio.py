"""Lokalna transkrypcja nagrań (faster-whisper). Dźwięk nie jest zapisywany."""

from __future__ import annotations

import logging
import os
import tempfile
import threading

# faster-whisper >= 1.1 calls av.open(..., metadata_errors="ignore") but PyAV 19.x
# does not yet expose that kwarg. Strip it silently until PyAV adds support.
try:
    import av as _av

    _av_open_orig = _av.open

    def _av_open_compat(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _av_open_orig(*args, **kwargs)

    _av.open = _av_open_compat
except ImportError:
    pass

from app.config import Settings

log = logging.getLogger("audio")

_model = None
_model_key: tuple[str, str, str] | None = None
_lock = threading.Lock()


class AudioError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _get_model(settings: Settings):
    global _model, _model_key
    key = (settings.whisper_model, settings.whisper_device, settings.whisper_compute_type)
    if _model is not None and _model_key == key:
        return _model
    with _lock:
        if _model is not None and _model_key == key:
            return _model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - zależy od instalacji
            raise AudioError(
                "transcription_unavailable",
                "Moduł transkrypcji nie jest zainstalowany na serwerze.",
            ) from exc
        try:
            _model = WhisperModel(
                settings.whisper_model,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
                download_root=settings.whisper_cache_dir,
            )
            _model_key = key
        except Exception as exc:  # pragma: no cover - model może być niedostępny
            log.warning("nie udało się wczytać modelu Whisper: %s", exc)
            raise AudioError(
                "transcription_unavailable",
                "Model transkrypcji jest chwilowo niedostępny.",
            ) from exc
    return _model


def transcribe_audio(data: bytes, settings: Settings) -> tuple[str, dict[str, str]]:
    """Zwraca (tekst, metadane). Nie zapisuje nagrania trwale."""
    if not data:
        raise AudioError("audio_empty", "Nagranie jest puste.")
    if len(data) > settings.audio_max_bytes:
        raise AudioError(
            "audio_too_large",
            f"Nagranie jest za duże. Maksymalny rozmiar to {settings.audio_max_bytes // 1_000_000} MB.",
        )
    model = _get_model(settings)
    suffix = ".webm"
    path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(data)
            path = handle.name
        segments, info = model.transcribe(
            path,
            language="pl",
            vad_filter=True,
            beam_size=5,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        metadata = {
            "model": settings.whisper_model,
            "język": getattr(info, "language", "pl") or "pl",
            "rozmiar": f"{len(data) / 1000:.0f} kB",
            "przetwarzanie": "lokalnie na serwerze usługi",
        }
        if info and getattr(info, "duration", None):
            metadata["czas"] = f"{float(info.duration):.1f} s"
        if info and getattr(info, "duration", 0) and float(info.duration) > settings.audio_max_seconds:
            raise AudioError(
                "audio_too_long",
                f"Nagranie jest za długie. Maksymalny czas to {settings.audio_max_seconds} s.",
            )
        return text, metadata
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:  # pragma: no cover - plik mógł już zniknąć
                pass
