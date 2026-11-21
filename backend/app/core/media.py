"""Przygotowanie obrazu: walidacja, odczyt metadanych, usunięcie EXIF przed wysłaniem do modelu."""

import io

from PIL import Image, UnidentifiedImageError

_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
_MAX_EDGE = 2000
_EXIF_IFD = 0x8769
_GPS_IFD = 0x8825
_TAGS = {"data_w_metadanych": 306, "oprogramowanie": 305, "producent_urzadzenia": 271, "model_urzadzenia": 272}
_DATETIME_ORIGINAL = 36867


class ImageError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def prepare_image(data: bytes, max_bytes: int) -> tuple[bytes, str, dict[str, str]]:
    """Zwraca (obraz bez metadanych, typ MIME, czytelne metadane do pokazania użytkownikowi)."""
    if len(data) > max_bytes:
        raise ImageError("image_too_large", f"Obraz jest za duży. Maksymalny rozmiar to {max_bytes // 1_000_000} MB.")
    try:
        Image.open(io.BytesIO(data)).verify()
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageError("image_invalid", "Nie udało się otworzyć tego pliku jako obrazu.") from exc
    if image.format not in _FORMATS:
        raise ImageError("image_unsupported", "Obsługujemy obrazy PNG, JPEG i WebP.")

    exif = image.getexif()
    metadata = {"format": image.format, "wymiary": f"{image.width}×{image.height}"}
    for label, tag in _TAGS.items():
        if exif.get(tag):
            metadata[label] = str(exif[tag])[:80]
    original = exif.get_ifd(_EXIF_IFD).get(_DATETIME_ORIGINAL)
    if original:
        metadata["data_wykonania"] = str(original)[:40]
    if exif.get_ifd(_GPS_IFD):
        metadata["lokalizacja_gps"] = "obecna w pliku (nie zapisujemy jej i nie wysyłamy do modelu)"
    if len(metadata) == 2:
        metadata["metadane"] = "brak (typowe dla zrzutów ekranu i plików z komunikatorów)"

    # Ponowne zakodowanie usuwa EXIF (w tym GPS), zanim obraz opuści serwer.
    output_format = "PNG" if image.format == "PNG" else "JPEG"
    clean = image.convert("RGB") if output_format == "JPEG" else image.copy()
    clean.thumbnail((_MAX_EDGE, _MAX_EDGE))
    buffer = io.BytesIO()
    clean.save(buffer, format=output_format, quality=90)
    return buffer.getvalue(), _FORMATS[output_format], metadata
