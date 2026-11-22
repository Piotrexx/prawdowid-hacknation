"""Weryfikacja zdjęcia: odwrotne wyszukiwanie (Yandex, TinEye) -> pobranie kopii -> porównanie lokalne -> ocena.

Zasada: zdjęcie zmanipulowane różni się w tym samym miejscu od większości swoich kopii w sieci,
a oryginał różni się co najwyżej od pojedynczych kopii (np. ze znakiem wodnym lub podpisem).
Model językowy nie bierze w tym udziału: ocena wynika wprost z porównania obrazów.
"""

import asyncio
import hashlib
import io
import json
import logging
import math
import time
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import Settings
from app.core import image_compare
from app.core.image_compare import Relation
from app.core.image_provenance import Provenance, inspect_file
from app.core.image_search import SUPPORTED_ENGINES, EngineResult, FoundImage, search_all
from app.schemas import (
    VERDICT_LABELS,
    AiAssessment,
    AiSignal,
    CheckMeta,
    CheckResponse,
    CheckStatus,
    EngineStatus,
    ImageAnalysis,
    ImageMatch,
    ImageRegion,
    InputInfo,
    SourceRef,
    Verdict,
    Warning,
)
from app.security.urlfetch import fetch_image
from app.store.db import Store

log = logging.getLogger("image_check")

_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "MPO"}
_MAX_PIXELS = 40_000_000
_QUERY_MAX_SIDE = 1600
_DOWNLOAD_CONCURRENCY = 5
_DOWNLOAD_BUDGET_S = 20.0
_ARCHIVAL_AFTER_DAYS = 365
_EDITING_SOFTWARE = ("photoshop", "gimp", "lightroom", "affinity", "pixelmator", "snapseed", "picsart", "canva", "facetune")
_NOT_A_VERDICT = "To problem techniczny, a nie wynik sprawdzenia."
_RELATION_LABELS = {
    "identical": "ta sama wersja",
    "locally_modified": "różni się fragmentem",
    "different_version": "inna obróbka lub kadr",
}
_ENGINE_NAMES = {"yandex": "Yandex", "tineye": "TinEye", "bing": "Bing"}
# Generatory obrazów upowszechniły się w 2022 r. (DALL·E 2, Midjourney, Stable Diffusion).
_GENERATIVE_AI_ERA = date(2022, 1, 1)
_CACHE_VERSION = "image-v3"

Search = Callable[[bytes, list[str], float], Awaitable[list[EngineResult]]]
Download = Callable[[str], Awaitable[bytes]]


def _copies(n: int) -> str:
    """Biernik: 1 kopię, 2–4 kopie, 5+ kopii (z wyjątkiem 12–14)."""
    if n == 1:
        return "1 kopię"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} kopie"
    return f"{n} kopii"


class ImageInputError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ImageInspection:
    """Wynik analizy samego obrazu, bez zapisu sprawdzenia.

    Pipeline tekstowy dokłada te dane do wspólnej odpowiedzi; `ImageCheckService.check`
    zamienia je w samodzielne `CheckResponse` i dopiero wtedy zapisuje je w bazie.
    """

    analysis: ImageAnalysis | None = None
    warnings: list[Warning] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)
    verdict: Verdict | None = None
    confidence: float | None = None
    justification: str | None = None
    limitations: list[str] = field(default_factory=list)
    stages: dict[str, int] = field(default_factory=dict)
    duration_ms: int = 0
    error_code: str | None = None
    error_message: str | None = None

    @property
    def failed(self) -> bool:
        return self.error_code is not None


def open_image(data: bytes) -> Image.Image:
    """Dekoduje obraz z limitem pikseli (ochrona przed "bombami dekompresyjnymi")."""
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in _ALLOWED_FORMATS:
            raise ImageInputError("image_unsupported", "Obsługiwane są zdjęcia JPEG, PNG, WebP i GIF.")
        if img.width * img.height > _MAX_PIXELS:
            raise ImageInputError("image_too_large", "Zdjęcie ma zbyt dużą rozdzielczość.")
        img.load()
    except ImageInputError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageInputError("image_invalid", "Nie udało się odczytać tego pliku jako zdjęcia.") from exc
    return img


def _read_exif(img: Image.Image) -> dict[str, str]:
    """Tylko pola przydatne do oceny. Lokalizacji GPS celowo nie odczytujemy ani nie zapisujemy."""
    try:
        exif = img.getexif()
        fields = {
            "software": exif.get(305),
            "datetime": exif.get(306),
            "camera": " ".join(str(v).strip() for v in (exif.get(271), exif.get(272)) if v),
            "datetime_original": exif.get_ifd(0x8769).get(36867),
        }
    except Exception:
        return {}
    return {k: str(v).strip()[:100] for k, v in fields.items() if v and str(v).strip()}


def _rgb(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        return background
    return img.convert("RGB")


def _prepare_query(data: bytes) -> tuple[Image.Image, dict[str, str], Provenance, bytes]:
    """Zwraca zdjęcie do porównań, EXIF, ślady AI z metadanych i kopię JPEG bez metadanych dla wyszukiwarek."""
    original = open_image(data)
    exif = _read_exif(original)
    provenance = inspect_file(data, original)
    img = _rgb(original)
    upload = img.copy()
    upload.thumbnail((_QUERY_MAX_SIDE, _QUERY_MAX_SIDE))
    buffer = io.BytesIO()
    upload.save(buffer, "JPEG", quality=90)
    return img, exif, provenance, buffer.getvalue()


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def _pick_candidates(results: list[EngineResult], limit: int) -> list[FoundImage]:
    """Na przemian z każdego silnika, bez duplikatów, żeby żaden silnik nie zdominował porównania."""
    queues = [list(r.found) for r in results if r.ok]
    picked: list[FoundImage] = []
    seen: set[str] = set()
    while len(picked) < limit and any(queues):
        for queue in queues:
            if not queue or len(picked) >= limit:
                continue
            item = queue.pop(0)
            key = item.image_url or item.page_url
            if key not in seen:
                seen.add(key)
                picked.append(item)
    return picked


class ImageCheckService:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        *,
        search: Search = search_all,
        download: Download | None = None,
    ):
        self._settings = settings
        self._store = store
        self._search = search
        self._download = download or (
            lambda url: fetch_image(url, settings, settings.image_candidate_max_bytes)
        )

    async def check(self, data: bytes, session_id: str | None) -> CheckResponse:
        """Samodzielne sprawdzenie zdjęcia: pełna odpowiedź, zapisana w bazie."""
        started = time.perf_counter()
        check_id = uuid.uuid4().hex
        digest = hashlib.sha256(data).hexdigest()
        cache_key = hashlib.sha256(f"{_CACHE_VERSION}|{digest}|{self._settings.image_search_engines}".encode()).hexdigest()

        cached = self._store.find_cached(
            cache_key, datetime.now(UTC) - timedelta(hours=self._settings.image_cache_hours)
        )
        if cached is not None:
            # Te same bajty sprawdzone niedawno: nie odpytujemy wyszukiwarek ponownie (limity, captcha).
            return cached.model_copy(update={"meta": cached.meta.model_copy(update={"cached": True})})

        inspection = await self._inspect(data, digest, started)
        if inspection.failed:
            response = self._error(
                check_id,
                started,
                inspection.error_code or "internal_error",
                inspection.error_message or f"Nie udało się sprawdzić zdjęcia. {_NOT_A_VERDICT}",
            )
        else:
            response = self._completed(check_id, inspection)

        self._store.save_check(response, session_id, cache_key if response.status == CheckStatus.COMPLETED else None)
        self._log(check_id, response, inspection)
        return response

    async def inspect(self, data: bytes) -> ImageInspection:
        """Analiza obrazu bez zapisu sprawdzenia – dla pipeline'u, który zapisuje jedną odpowiedź."""
        started = time.perf_counter()
        return await self._inspect(data, hashlib.sha256(data).hexdigest(), started)

    async def _inspect(self, data: bytes, digest: str, started: float) -> ImageInspection:
        stages: dict[str, int] = {}

        def mark(stage: str, since: float) -> float:
            now = time.perf_counter()
            stages[stage] = int((now - since) * 1000)
            return now

        try:
            query_img, exif, provenance, upload = await asyncio.to_thread(_prepare_query, data)
            engines = [e for e in self._settings.image_engine_list if e in SUPPORTED_ENGINES]
            t = time.perf_counter()
            results = await self._search(upload, engines, self._settings.image_search_timeout_s)
            t = mark("search", t)

            if results and not any(r.ok for r in results):
                details = "; ".join(f"{_ENGINE_NAMES.get(r.engine, r.engine)}: {r.error}" for r in results)
                raise ImageInputError(
                    "image_search_unavailable",
                    f"Żadna wyszukiwarka obrazów nie odpowiedziała ({details}). {_NOT_A_VERDICT} Spróbuj ponownie za chwilę.",
                )

            candidates = _pick_candidates(results, self._settings.image_compare_max_candidates)
            downloaded = await self._download_all(candidates)
            t = mark("download", t)
            comparisons = await asyncio.to_thread(self._compare_all, query_img, downloaded)
            mark("compare", t)

            analysis = self._analyse(digest, query_img, exif, provenance, results, candidates, comparisons)
        except ImageInputError as exc:
            return ImageInspection(
                error_code=exc.code,
                error_message=exc.message,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception:
            log.exception("nieoczekiwany błąd analizy zdjęcia")
            return ImageInspection(
                error_code="internal_error",
                error_message=f"Wystąpił nieoczekiwany błąd. {_NOT_A_VERDICT} Spróbuj ponownie.",
                duration_ms=int((time.perf_counter() - started) * 1000),
            )

        warnings, sources, verdict, confidence, justification, limitations = self._assemble(analysis, results)
        return ImageInspection(
            analysis=analysis,
            warnings=warnings,
            sources=sources,
            verdict=verdict,
            confidence=confidence,
            justification=justification,
            limitations=limitations,
            stages=stages,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    @staticmethod
    def _log(check_id: str, response: CheckResponse, inspection: ImageInspection) -> None:
        analysis = inspection.analysis
        log.info(
            json.dumps(
                {
                    "check_id": check_id,
                    "kind": "image",
                    "status": response.status.value,
                    "error_code": response.error_code,
                    "assessment": analysis.assessment if analysis else None,
                    "ai": analysis.ai.result if analysis and analysis.ai else None,
                    "verdict": response.verdict.value if response.verdict else None,
                    "confidence": response.confidence,
                    "compared": analysis.compared if analysis else 0,
                    "engines": {e.engine: e.ok for e in analysis.engines} if analysis else {},
                    "duration_ms": response.meta.duration_ms,
                    "stages_ms": response.meta.stages_ms,
                }
            )
        )

    async def _download_all(self, candidates: list[FoundImage]) -> dict[int, bytes]:
        semaphore = asyncio.Semaphore(_DOWNLOAD_CONCURRENCY)

        async def one(index: int, item: FoundImage) -> tuple[int, bytes | None]:
            async with semaphore:
                # Najpierw pełny obraz ze strony źródłowej, a gdy się nie da – miniatura z wyszukiwarki.
                for url in (item.image_url, item.thumbnail_url):
                    if not url:
                        continue
                    try:
                        return index, await self._download(url)
                    except Exception as exc:  # każdy błąd pobrania (SSRF, typ, rozmiar, sieć) = pomijamy kopię
                        log.debug("nie pobrano %s: %s", url, exc)
                return index, None

        tasks = [asyncio.create_task(one(i, item)) for i, item in enumerate(candidates)]
        done, pending = await asyncio.wait(tasks, timeout=_DOWNLOAD_BUDGET_S) if tasks else (set(), set())
        for task in pending:
            task.cancel()
        return {index: body for index, body in (task.result() for task in done) if body is not None}

    @staticmethod
    def _compare_all(query_img: Image.Image, downloaded: dict[int, bytes]) -> dict[int, image_compare.Comparison]:
        query = image_compare.prepare(query_img)
        out: dict[int, image_compare.Comparison] = {}
        for index, body in downloaded.items():
            try:
                candidate = image_compare.prepare(_rgb(open_image(body)))
            except ImageInputError:
                out[index] = image_compare.Comparison(Relation.NOT_COMPARABLE)
                continue
            out[index] = image_compare.compare(query, candidate)
        return out

    def _analyse(
        self,
        digest: str,
        query_img: Image.Image,
        exif: dict[str, str],
        provenance: Provenance,
        results: list[EngineResult],
        candidates: list[FoundImage],
        comparisons: dict[int, image_compare.Comparison],
    ) -> ImageAnalysis:
        matches: list[ImageMatch] = []
        aligned: list[tuple[FoundImage, image_compare.Comparison]] = []
        picked = {id(item) for item in candidates}
        for index, item in enumerate(candidates):
            comparison = comparisons.get(index)
            relation = comparison.relation.value if comparison else "not_downloaded"
            matches.append(self._match(item, relation, comparison.median_diff if comparison else None))
            if comparison and comparison.relation in (Relation.IDENTICAL, Relation.LOCALLY_MODIFIED):
                aligned.append((item, comparison))
        for result in results:
            for item in result.found:
                if id(item) not in picked:
                    matches.append(self._match(item, "not_downloaded", None))

        relations = Counter(c.relation for c in comparisons.values())
        consensus: list[tuple[int, int]] = []
        if len(aligned) >= 2:
            votes = Counter(cell for _, c in aligned for cell in c.hot_cells)
            needed = max(2, math.ceil(0.6 * len(aligned)))
            consensus = sorted(cell for cell, count in votes.items() if count >= needed)

        identical = relations[Relation.IDENTICAL]
        if consensus:
            assessment = "manipulation_suspected"
        elif identical:
            # Pojedyncze kopie mogą mieć własne podpisy czy znaki wodne; liczy się brak różnicy wspólnej
            # dla kopii i co najmniej jedna kopia zgodna w całości.
            assessment = "consistent_with_copies"
        elif any(r.total for r in results):
            assessment = "insufficient_copies"
        else:
            assessment = "no_matches"

        # Daty tylko z kopii tego samego zdjęcia. "Inna wersja" bywa innym zdjęciem o podobnym układzie
        # (np. inna twarz z generatora – wszystkie mają oczy w tym samym miejscu), więc jej data nic nie mówi.
        related_dates = [item.first_seen for item, _ in aligned if item.first_seen]
        earliest = min(related_dates) if related_dates else None
        ai_result = provenance.kind or (
            "predates_generative_ai" if earliest and earliest < _GENERATIVE_AI_ERA else "no_signals"
        )
        size = 1 / image_compare.GRID
        return ImageAnalysis(
            assessment=assessment,
            sha256=digest,
            width=query_img.width,
            height=query_img.height,
            engines=[EngineStatus(engine=r.engine, ok=r.ok, results=r.total, error=r.error) for r in results],
            matches_found=sum(r.total for r in results),
            compared=len(aligned),
            identical=identical,
            locally_modified=relations[Relation.LOCALLY_MODIFIED],
            different_versions=relations[Relation.DIFFERENT_VERSION],
            earliest_seen=earliest,
            changed_regions=[ImageRegion(x=j * size, y=i * size, width=size, height=size) for i, j in consensus],
            exif=exif,
            ai=AiAssessment(
                result=ai_result,
                signals=[AiSignal(**vars(signal)) for signal in provenance.signals],
                content_credentials=provenance.content_credentials,
            ),
            matches=matches,
        )

    @staticmethod
    def _match(item: FoundImage, relation: str, difference: float | None) -> ImageMatch:
        return ImageMatch(
            engine=item.engine,
            page_url=item.page_url,
            image_url=item.image_url,
            thumbnail_url=item.thumbnail_url,
            title=item.title,
            domain=item.domain,
            first_seen=item.first_seen,
            relation=relation,
            difference=round(difference, 3) if difference is not None else None,
        )

    def _assemble(
        self, analysis: ImageAnalysis, results: list[EngineResult]
    ) -> tuple[list[Warning], list[SourceRef], Verdict, float, str, list[str]]:
        warnings: list[Warning] = []
        failed = [r for r in results if not r.ok]
        if failed:
            names = ", ".join(_ENGINE_NAMES.get(r.engine, r.engine) for r in failed)
            warnings.append(
                Warning(code="retrieval_degraded", message=f"Nie odpowiedziała część wyszukiwarek ({names}). Wynik opiera się na pozostałych.")
            )
        old = analysis.earliest_seen and analysis.earliest_seen < date.today() - timedelta(days=_ARCHIVAL_AFTER_DAYS)
        if old:
            warnings.append(
                Warning(
                    code="archival_material",
                    message=f"To zdjęcie krąży w sieci co najmniej od {analysis.earliest_seen:%d.%m.%Y}. "
                    "Jeśli jest przedstawiane jako aktualne, może być użyte poza kontekstem.",
                )
            )
        software = analysis.exif.get("software", "")
        if any(name in software.lower() for name in _EDITING_SOFTWARE):
            warnings.append(
                Warning(
                    code="image_edit_software",
                    message=f"Metadane pliku wskazują na program do edycji ({software}). Sama obróbka nie oznacza manipulacji.",
                )
            )

        verdict, confidence, justification = self._verdict(analysis)
        ai = analysis.ai
        generators = ", ".join(sorted({s.generator for s in ai.signals if s.generator})) if ai else ""
        if ai and ai.result == "ai_generated":
            warnings.insert(
                0,
                Warning(
                    code="ai_generated",
                    message="Metadane pliku wskazują, że obraz został wygenerowany przez AI"
                    + (f" ({generators})." if generators else "."),
                ),
            )
        elif ai and ai.result == "ai_edited":
            warnings.insert(
                0,
                Warning(
                    code="ai_edited",
                    message="Metadane pliku wskazują, że obraz był edytowany z użyciem AI"
                    + (f" ({generators})." if generators else ".")
                    + " Część obrazu mogła zostać wygenerowana.",
                ),
            )
        elif ai and ai.content_credentials:
            warnings.append(
                Warning(code="content_credentials", message=f"Plik ma Content Credentials (C2PA): {ai.content_credentials}.")
            )
        if analysis.assessment == "manipulation_suspected":
            warnings.insert(
                0,
                Warning(
                    code="image_manipulation",
                    message="Fragment tego zdjęcia wygląda inaczej niż na większości kopii znalezionych w sieci.",
                ),
            )

        engine_names = ", ".join(_ENGINE_NAMES.get(r.engine, r.engine) for r in results)
        limitations = [
            f"Zdjęcie (bez metadanych EXIF) zostało wysłane do zewnętrznych wyszukiwarek obrazów: {engine_names}.",
            "Porównanie wykrywa doklejone, usunięte lub zmienione fragmenty względem kopii w sieci; "
            "nie oceni zdjęć, których nie ma w indeksach wyszukiwarek.",
            "Obrazy z AI rozpoznajemy po metadanych (C2PA, IPTC, parametry generatorów) i dacie najstarszej kopii. "
            "Media społecznościowe i zrzuty ekranu usuwają metadane, więc brak śladów nie wyklucza obrazu z AI.",
            "Różnica w jednym miejscu może też oznaczać, że to kopie w sieci mają dodany podpis lub znak wodny.",
            "Nawet niezmienione zdjęcie może zostać użyte w fałszywym kontekście – sprawdź, skąd pochodzi i kiedy powstało.",
        ]
        return warnings, self._sources(analysis), verdict, confidence, justification, limitations

    def _completed(self, check_id: str, inspection: ImageInspection) -> CheckResponse:
        analysis = inspection.analysis
        assert analysis is not None  # wywoływane tylko dla udanej analizy
        return CheckResponse(
            id=check_id,
            created_at=datetime.now(UTC),
            channel="web",
            status=CheckStatus.COMPLETED,
            input=InputInfo(
                kind="image",
                text=f"Zdjęcie {analysis.width}×{analysis.height} px",
                url="",
                title="Przesłane zdjęcie",
            ),
            verdict=inspection.verdict,
            verdict_label=VERDICT_LABELS[inspection.verdict] if inspection.verdict else None,
            confidence=inspection.confidence,
            justification=inspection.justification,
            main_topic="Weryfikacja zdjęcia",
            source_articles=inspection.sources,
            limitations=inspection.limitations,
            warnings=inspection.warnings,
            image_analysis=analysis,
            meta=CheckMeta(
                duration_ms=inspection.duration_ms,
                stages_ms=inspection.stages,
                processing_location=self._settings.processing_location,
            ),
        )

    @classmethod
    def _verdict(cls, a: ImageAnalysis) -> tuple[Verdict, float, str]:
        """Ślady AI w metadanych są mocniejsze niż porównanie z kopiami, więc nadpisują jego werdykt."""
        verdict, confidence, text = cls._copy_verdict(a)
        ai = a.ai
        if ai is None:
            return verdict, confidence, text
        lead = "; ".join(s.detail for s in ai.signals)
        if ai.result == "ai_generated":
            signed = any(s.signed for s in ai.signals if s.kind == "ai_generated")
            return (
                Verdict.FALSE,
                0.95 if signed else 0.85,
                f"{lead}. To obraz z generatora AI, a nie zdjęcie rzeczywistej sceny. "
                f"Porównanie z kopiami w sieci: {_lower_first(text)}",
            )
        if ai.result == "ai_edited":
            if verdict == Verdict.CONFIRMED:
                verdict, confidence = Verdict.INSUFFICIENT, 0.5
            return (
                verdict,
                confidence,
                f"{lead}. Część obrazu mogła zostać wygenerowana lub zmieniona przez AI. "
                f"Porównanie z kopiami w sieci: {_lower_first(text)}",
            )
        if ai.result == "predates_generative_ai":
            text += (
                f" Zdjęcie było w sieci już {a.earliest_seen:%d.%m.%Y}, czyli przed upowszechnieniem generatorów "
                "obrazów AI (2022), więc raczej nie zostało przez nie wygenerowane."
            )
        return verdict, confidence, text

    @staticmethod
    def _copy_verdict(a: ImageAnalysis) -> tuple[Verdict, float, str]:
        seen = f" Najstarsza znaleziona kopia pochodzi z {a.earliest_seen:%d.%m.%Y}." if a.earliest_seen else ""
        if a.assessment == "manipulation_suspected":
            confidence = min(0.8, 0.45 + 0.07 * a.locally_modified)
            return (
                Verdict.FALSE,
                round(confidence, 2),
                f"Przesłana wersja różni się w tym samym miejscu od {a.locally_modified} z {a.compared} "
                f"porównanych kopii tego zdjęcia w sieci ({len(a.changed_regions)} z {image_compare.GRID ** 2} fragmentów). "
                f"To typowy ślad doklejenia, usunięcia lub podmiany elementu.{seen}",
            )
        if a.assessment == "consistent_with_copies":
            confidence = min(0.8, 0.4 + 0.06 * a.compared + 0.04 * a.identical)
            other = a.compared - a.identical
            others = f" Pozostałe {other} różnią się w różnych miejscach, co wskazuje na zmiany w samych kopiach (np. podpisy, znaki wodne)." if other else ""
            return (
                Verdict.CONFIRMED,
                round(confidence, 2),
                f"Porównano {_copies(a.compared)} tego zdjęcia z sieci; {a.identical} zgadza się z przesłaną wersją w całości.{others} "
                f"Nie widać fragmentu, który różniłby się od większości kopii, więc brak śladów doklejenia lub usunięcia elementów.{seen} "
                "To nie potwierdza opisu, z jakim zdjęcie jest udostępniane.",
            )
        if a.assessment == "insufficient_copies":
            return (
                Verdict.INSUFFICIENT,
                0.3,
                "Wyszukiwarki znalazły podobne obrazy, ale za mało kopii tego samego zdjęcia, "
                f"by rzetelnie porównać szczegóły (porównano: {a.compared}, inna obróbka lub kadr: {a.different_versions}).{seen}",
            )
        return (
            Verdict.INSUFFICIENT,
            0.2,
            "Nie znaleziono tego zdjęcia w sieci. Może być nowe, prywatne, mocno przerobione albo wygenerowane – "
            "brak kopii nie pozwala ocenić, czy zostało zmienione.",
        )

    @staticmethod
    def _sources(analysis: ImageAnalysis) -> list[SourceRef]:
        compared = [m for m in analysis.matches if m.relation in _RELATION_LABELS]
        return [
            SourceRef(
                doc_id=f"img-{index}",
                title=m.title or m.domain or m.page_url,
                publisher=m.domain or "",
                url=m.page_url,
                published_at=m.first_seen,
                source_type="reverse_image",
                source_name=_ENGINE_NAMES.get(m.engine, m.engine),
                rating=_RELATION_LABELS[m.relation],
            )
            for index, m in enumerate(compared)
        ]

    def _error(self, check_id: str, started: float, code: str, message: str) -> CheckResponse:
        return CheckResponse(
            id=check_id,
            created_at=datetime.now(UTC),
            channel="web",
            status=CheckStatus.ERROR,
            status_message=message,
            error_code=code,
            input=InputInfo(kind="image", text="", url="", title="Przesłane zdjęcie"),
            meta=CheckMeta(
                duration_ms=int((time.perf_counter() - started) * 1000),
                processing_location=self._settings.processing_location,
            ),
        )
