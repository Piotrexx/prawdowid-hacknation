"""Ślady generowania przez AI zapisane w samym pliku.

Trzy źródła, od najpewniejszego:
1. C2PA (Content Credentials) – podpisany manifest; OpenAI, Adobe Firefly, Microsoft i część aparatów
   zapisują w nim `digitalSourceType`.
2. IPTC `DigitalSourceType` w XMP – ten sam słownik, ale bez podpisu.
3. Parametry generatorów – Stable Diffusion (A1111), ComfyUI, InvokeAI, NovelAI zapisują prompt
   i ustawienia w metadanych PNG/EXIF; nazwy generatorów sprawdzamy tylko w polach "programu",
   nigdy w opisach (np. "firefly" w opisie zdjęcia świetlika to nie Adobe Firefly).

Brak śladów niczego nie dowodzi: media społecznościowe i zrzuty ekranu usuwają metadane.
"""

import io
import json
import logging
import re
from dataclasses import dataclass, field

from PIL import Image

log = logging.getLogger("image_provenance")

_GENERATED = "trainedAlgorithmicMedia"
_EDITED = "compositeWithTrainedAlgorithmicMedia"
_SOURCE_TYPE = re.compile(rb"digitalsourcetype/(\w+)", re.IGNORECASE)
_XMP_PACKET = re.compile(rb"<x:xmpmeta.*?</x:xmpmeta>", re.DOTALL)
_CREATOR_TOOL = re.compile(rb"CreatorTool(?:=\"|>)([^\"<]{1,200})")
_MIME = {"JPEG": "image/jpeg", "MPO": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}
_C2PA_SIGNED_STATES = {"valid", "trusted"}
_C2PA_CREDENTIAL_ONLY = {"signingCredential.untrusted", "signingCredential.expired"}
# Fragment nazwy w polu "program" -> nazwa do wyświetlenia.
_GENERATOR_NAMES = {
    "midjourney": "Midjourney",
    "dall-e": "DALL·E",
    "dall·e": "DALL·E",
    "openai": "OpenAI",
    "firefly": "Adobe Firefly",
    "stable diffusion": "Stable Diffusion",
    "stablediffusion": "Stable Diffusion",
    "comfyui": "ComfyUI",
    "automatic1111": "Stable Diffusion (A1111)",
    "invokeai": "InvokeAI",
    "novelai": "NovelAI",
    "ideogram": "Ideogram",
    "leonardo.ai": "Leonardo.Ai",
    "nightcafe": "NightCafe",
}
# Klucze tekstowe PNG, które zapisują wyłącznie generatory obrazów.
_GENERATOR_PNG_KEYS = {
    "parameters": "Stable Diffusion (A1111)",
    "workflow": "ComfyUI",
    "prompt": "ComfyUI",
    "invokeai_metadata": "InvokeAI",
    "sd-metadata": "InvokeAI",
    "dream": "InvokeAI",
}


@dataclass
class Signal:
    source: str  # c2pa | iptc | generator_metadata
    kind: str  # ai_generated | ai_edited
    detail: str
    generator: str | None = None
    signed: bool = False


@dataclass
class Provenance:
    signals: list[Signal] = field(default_factory=list)
    content_credentials: str | None = None

    @property
    def kind(self) -> str | None:
        kinds = {s.kind for s in self.signals}
        return "ai_generated" if "ai_generated" in kinds else ("ai_edited" if kinds else None)


def _kind(source_type: str) -> str | None:
    lowered = source_type.lower()
    if lowered == _GENERATED.lower():
        return "ai_generated"
    if lowered == _EDITED.lower():
        return "ai_edited"
    return None


def _known_generator(text: str | None) -> str | None:
    lowered = (text or "").lower()
    return next((name for needle, name in _GENERATOR_NAMES.items() if needle in lowered), None)


def _agent_name(agent) -> str | None:
    if isinstance(agent, dict):
        agent = agent.get("name")
    return str(agent).strip()[:100] if agent else None


def _c2pa_integrity(store: dict) -> tuple[bool, str]:
    """Czy treść pliku zgadza się z podpisem, i opis stanu po polsku.

    Wygasły lub niezaufany certyfikat (np. testowy albo próbka sprzed lat) nie oznacza zmiany pliku,
    więc nie traktujemy go jak naruszenia; zmianę pliku zgłaszają dopiero niezgodne skróty (hash).
    """
    if str(store.get("validation_state") or "").lower() in _C2PA_SIGNED_STATES:
        return True, "podpis nienaruszony"
    failures = ((store.get("validation_results") or {}).get("activeManifest") or {}).get("failure")
    codes = {str(f.get("code", "")) for f in (failures if failures is not None else store.get("validation_status") or [])}
    if any("mismatch" in code for code in codes):
        return False, "podpis nie zgadza się z treścią – plik zmieniono po podpisaniu"
    if codes and codes <= _C2PA_CREDENTIAL_ONLY:
        note = "certyfikat podpisu wygasł" if "signingCredential.expired" in codes else "certyfikat spoza listy zaufanych"
        return True, f"treść zgodna z podpisem ({note})"
    return False, "podpis nie przeszedł weryfikacji" + (f" ({', '.join(sorted(codes))})" if codes else "")


def _c2pa(data: bytes, mime: str, out: Provenance) -> None:
    import c2pa

    try:
        reader = c2pa.Reader.try_create(mime, io.BytesIO(data))
        if reader is None:
            return
        store = json.loads(reader.json())
    except Exception as exc:  # uszkodzony lub nieobsługiwany manifest
        log.info("nie odczytano C2PA: %s", exc)
        return

    signed, status = _c2pa_integrity(store)
    manifests = store.get("manifests") or {}
    active = manifests.get(store.get("active_manifest") or "") or {}
    issuer = (active.get("signature_info") or {}).get("issuer")
    generators = [g.get("name") for g in active.get("claim_generator_info") or [] if g.get("name")]
    tool = generators[0] if generators else active.get("claim_generator")
    out.content_credentials = ", ".join(p for p in (tool, f"wystawca: {issuer}" if issuer else None, status) if p)

    # Ślady AI mogą być też w składnikach (np. obraz z Firefly później edytowany w Photoshopie).
    for manifest in manifests.values():
        for assertion in manifest.get("assertions") or []:
            if not str(assertion.get("label", "")).startswith("c2pa.actions"):
                continue
            for action in (assertion.get("data") or {}).get("actions") or []:
                kind = _kind(str(action.get("digitalSourceType", "")).rsplit("/", 1)[-1])
                if not kind:
                    continue
                agent = _agent_name(action.get("softwareAgent")) or tool
                verb = "wygenerowany przez AI" if kind == "ai_generated" else "edytowany z użyciem AI"
                out.signals.append(
                    Signal(
                        source="c2pa",
                        kind=kind,
                        generator=agent,
                        signed=signed,
                        detail=f"Content Credentials (C2PA): obraz {verb}"
                        + (f" – {agent}" if agent else "")
                        + (f", podpisał: {issuer}" if issuer else "")
                        + ("" if signed else " (podpis nieważny)"),
                    )
                )


def _xmp(data: bytes, img: Image.Image, out: Provenance) -> None:
    packets = _XMP_PACKET.findall(data)
    extra = img.info.get("xmp") or img.info.get("XML:com.adobe.xmp")
    if extra:
        packets.append(extra if isinstance(extra, bytes) else str(extra).encode())
    for packet in packets:
        tool = next((t.decode(errors="replace") for t in _CREATOR_TOOL.findall(packet)), None)
        for raw in _SOURCE_TYPE.findall(packet):
            kind = _kind(raw.decode(errors="replace"))
            if kind:
                verb = "wygenerowany przez AI" if kind == "ai_generated" else "edytowany z użyciem AI"
                out.signals.append(
                    Signal(
                        source="iptc",
                        kind=kind,
                        generator=_known_generator(tool) or tool,
                        detail=f"Metadane IPTC: obraz {verb}" + (f" ({tool})" if tool else "") + " – bez podpisu cyfrowego",
                    )
                )
                return
        if generator := _known_generator(tool):
            out.signals.append(
                Signal(source="generator_metadata", kind="ai_generated", generator=generator, detail=f"Program w metadanych XMP: {tool}")
            )
            return


def _generator_fields(img: Image.Image, out: Provenance) -> None:
    texts = {str(k).lower(): str(v) for k, v in img.info.items() if isinstance(v, str | bytes) and k != "xmp"}
    for key, generator in _GENERATOR_PNG_KEYS.items():
        value = texts.get(key, "")
        # "prompt" bywa też zwykłym opisem – liczy się tylko JSON węzłów ComfyUI lub ustawienia A1111.
        if value and (key != "prompt" or value.lstrip().startswith("{")) and (key != "parameters" or "Steps:" in value):
            out.signals.append(
                Signal(source="generator_metadata", kind="ai_generated", generator=generator, detail=f"Parametry generowania zapisane w pliku ({generator})")
            )
            return

    try:
        exif = img.getexif()
        software = str(exif.get(305) or "")
        comment = exif.get_ifd(0x8769).get(0x9286)  # UserComment – tu A1111 zapisuje parametry w JPEG
    except Exception:
        software, comment = "", None
    comment_text = comment.decode("utf-8", errors="ignore") if isinstance(comment, bytes) else str(comment or "")
    if "Steps:" in comment_text and "Sampler:" in comment_text:
        out.signals.append(
            Signal(source="generator_metadata", kind="ai_generated", generator="Stable Diffusion", detail="Parametry generowania Stable Diffusion w EXIF")
        )
        return
    for candidate in (software, texts.get("software", "")):
        if generator := _known_generator(candidate):
            out.signals.append(
                Signal(source="generator_metadata", kind="ai_generated", generator=generator, detail=f"Program w metadanych: {candidate.strip()[:100]}")
            )
            return


def inspect_file(data: bytes, img: Image.Image) -> Provenance:
    """`img` to obraz otwarty z `data` (przed konwersją – z oryginalnymi metadanymi)."""
    out = Provenance()
    mime = _MIME.get(img.format or "")
    if mime:
        _c2pa(data, mime, out)
    _xmp(data, img, out)
    _generator_fields(img, out)
    return out
