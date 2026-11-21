"""Katalog źródeł ingestu. Jedyne miejsce, które decyduje, co trafia do korpusu.

Metadane są w kodzie (a nie w pliku YAML), bo to one uzasadniają kwalifikację
źródła, jego licencję i poziom zaufania. Dokumenty są pobierane na bieżąco i
zapisywane w PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VOIVODESHIPS = [
    "dolnoslaskie",
    "kujawsko-pomorskie",
    "lubelskie",
    "lubuskie",
    "lodzkie",
    "malopolskie",
    "mazowieckie",
    "opolskie",
    "podkarpackie",
    "podlaskie",
    "pomorskie",
    "slaskie",
    "swietokrzyskie",
    "warminsko-mazurskie",
    "wielkopolskie",
    "zachodniopomorskie",
]


@dataclass(frozen=True)
class SourceSpec:
    key: str
    name: str
    url: str
    adapter: str
    publisher: str
    source_type: str = "official"
    tier: int = 1
    license: str = ""
    storage: str = "excerpt"
    qualification: str = ""
    update_policy: str = ""
    max_items: int = 10
    params: dict = field(default_factory=dict)


SOURCES: list[SourceSpec] = [
    # --- źródła urzędowe (poziom 1) ---
    SourceSpec(
        key="rcb-raport-dobowy",
        name="Rządowe Centrum Bezpieczeństwa – raport dobowy",
        url="https://www.gov.pl/web/rcb/raport-dobowy3",
        adapter="single_page_daily",
        publisher="Rządowe Centrum Bezpieczeństwa",
        source_type="official",
        tier=1,
        license="Materiały urzędowe – nie są przedmiotem prawa autorskiego (art. 4 pr. aut.)",
        storage="full_text",
        qualification="Źródło pierwotne: oficjalny raport dobowy RCB.",
        update_policy="Codziennie; nowy raport na stronie.",
    ),
    SourceSpec(
        key="gov-ostrzezenia",
        name="Gov.pl – system ostrzeżeń (RSO)",
        url="https://www.gov.pl/web/gov/ostrzezenia",
        adapter="rso_api",
        publisher="Rządowe Centrum Bezpieczeństwa",
        source_type="official",
        tier=1,
        license="Materiały urzędowe – nie są przedmiotem prawa autorskiego (art. 4 pr. aut.)",
        storage="structured",
        qualification="Źródło pierwotne: publiczne API Regionalnego Systemu Ostrzegania.",
        update_policy="Co godzinę; API RSO wszystkich województw.",
        params={
            "api_template": "https://www.gov.pl/api/data/proxy/rso/komunikatyxml/{voivodeship}/wszystkie/0?_format=json",
            "voivodeships": VOIVODESHIPS,
        },
    ),
    SourceSpec(
        key="imgw-meteo",
        name="IMGW – ostrzeżenia meteorologiczne",
        url="https://meteo.imgw.pl/",
        adapter="imgw_json",
        publisher="IMGW-PIB",
        source_type="official",
        tier=1,
        license="Dane publiczne IMGW-PIB – przechowujemy tytuł, treść ostrzeżenia i link",
        storage="full_text",
        qualification="Źródło pierwotne: państwowa służba hydrologiczno-meteorologiczna.",
        update_policy="Co godzinę; publiczne API ostrzeżeń.",
        params={"api_url": "https://danepubliczne.imgw.pl/api/data/warningsmeteo", "kind": "meteo"},
    ),
    SourceSpec(
        key="imgw-hydro",
        name="IMGW – sytuacja hydrologiczna",
        url="https://hydro.imgw.pl/",
        adapter="imgw_hydro_snapshot",
        publisher="IMGW-PIB",
        source_type="official",
        tier=1,
        license="Dane publiczne IMGW-PIB – przechowujemy tytuł, treść i link",
        storage="full_text",
        qualification="Źródło pierwotne: państwowa służba hydrologiczno-meteorologiczna.",
        update_policy="Co godzinę; publiczne API stanów wód.",
        params={"api_url": "https://danepubliczne.imgw.pl/api/data/hydro"},
    ),
    SourceSpec(
        key="cert-polska",
        name="CERT Polska – komunikaty",
        url="https://moje.cert.pl/komunikaty/",
        adapter="html_links",
        publisher="NASK – CERT Polska",
        source_type="official",
        tier=1,
        license="Prawa zastrzeżone – przechowujemy tylko tytuł, zajawkę i link",
        storage="excerpt",
        qualification="Zespół CSIRT poziomu krajowego (ustawa o KSC).",
        update_policy="Codziennie; lista komunikatów.",
        params={"link_regex": r"/komunikaty/\d{4}/\d+/[^/]+/?$"},
    ),
    SourceSpec(
        key="gddkia",
        name="GDDKiA – aktualności (gov.pl)",
        url="https://www.gov.pl/web/gddkia/aktualnosci",
        adapter="govpl_list",
        publisher="Generalna Dyrekcja Dróg Krajowych i Autostrad",
        source_type="official",
        tier=1,
        license="Materiały urzędowe – nie są przedmiotem prawa autorskiego (art. 4 pr. aut.)",
        storage="full_text",
        qualification="Źródło pierwotne: państwowy zarządca dróg krajowych.",
        update_policy="Codziennie; lista aktualności.",
    ),
    SourceSpec(
        key="kgpsp",
        name="Komenda Główna PSP – aktualności",
        url="https://www.gov.pl/web/kgpsp/aktualnosci",
        adapter="govpl_list",
        publisher="Komenda Główna Państwowej Straży Pożarnej",
        source_type="official",
        tier=1,
        license="Materiały urzędowe – nie są przedmiotem prawa autorskiego (art. 4 pr. aut.)",
        storage="full_text",
        qualification="Źródło pierwotne: państwowa straż pożarna.",
        update_policy="Codziennie; lista aktualności.",
    ),
    SourceSpec(
        key="policja",
        name="Policja – aktualności",
        url="https://policja.pl/pol/aktualnosci",
        adapter="html_links",
        publisher="Policja",
        source_type="official",
        tier=1,
        license="Prawa zastrzeżone – przechowujemy tylko tytuł, zajawkę i link",
        storage="excerpt",
        qualification="Źródło pierwotne: Policja.",
        update_policy="Codziennie; lista aktualności.",
        params={"link_regex": r"/pol/aktualnosci/\d+,[^/]+\.html$"},
    ),
    SourceSpec(
        key="gis",
        name="GIS – ostrzeżenia",
        url="https://www.gov.pl/web/gis/ostrzezenia",
        adapter="govpl_list",
        publisher="Główny Inspektorat Sanitarny",
        source_type="official",
        tier=1,
        license="Materiały urzędowe – nie są przedmiotem prawa autorskiego (art. 4 pr. aut.)",
        storage="full_text",
        qualification="Źródło pierwotne: państwowa inspekcja sanitarna.",
        update_policy="Codziennie; lista ostrzeżeń.",
    ),
    SourceSpec(
        key="paa",
        name="Państwowa Agencja Atomistyki – aktualności",
        url="https://www.gov.pl/web/paa/aktualnosci",
        adapter="govpl_list",
        publisher="Państwowa Agencja Atomistyki",
        source_type="official",
        tier=1,
        license="Materiały urzędowe – nie są przedmiotem prawa autorskiego (art. 4 pr. aut.)",
        storage="full_text",
        qualification="Źródło pierwotne: państwowy dozór jądrowy.",
        update_policy="Codziennie; lista aktualności.",
    ),
    SourceSpec(
        key="msz-gov-pl",
        name="MSZ – aktualności i oświadczenia",
        url="https://www.gov.pl/web/dyplomacja/aktualnosci",
        adapter="govpl_list",
        publisher="Ministerstwo Spraw Zagranicznych RP",
        source_type="official",
        tier=1,
        license="CC BY-SA 4.0 (stopka serwisu gov.pl)",
        storage="full_text",
        qualification="Źródło pierwotne: oficjalny serwis ministra właściwego do spraw zagranicznych.",
        update_policy="Codziennie; nowe pozycje z listy aktualności.",
        params={"listing": "https://www.gov.pl/web/dyplomacja/aktualnosci", "pages": 6},
    ),
    # --- źródła prawne (poziom 1) ---
    SourceSpec(
        key="sejm-eli",
        name="Dziennik Ustaw (API ELI Sejmu RP)",
        url="https://isap.sejm.gov.pl",
        adapter="sejm_eli",
        publisher="Kancelaria Sejmu RP",
        source_type="legal",
        tier=1,
        license="Materiały urzędowe – nie są przedmiotem prawa autorskiego (art. 4 pr. aut.)",
        storage="structured",
        qualification="Źródło pierwotne: urzędowy rejestr aktów prawnych.",
        update_policy="Codziennie; nowe pozycje bieżącego rocznika.",
        params={
            "publisher": "DU",
            "year": 2026,
            "limit": 80,
            "types": ["Ustawa", "Umowa międzynarodowa", "Oświadczenie rządowe"],
        },
    ),
    # --- fact-checking (poziom 2) ---
    SourceSpec(
        key="konkret24",
        name="Konkret24",
        url="https://konkret24.tvn24.pl",
        adapter="rss",
        publisher="TVN24 – Konkret24",
        source_type="factcheck",
        tier=2,
        license="Prawa zastrzeżone (TVN) – przechowujemy tylko tytuł, zajawkę i link",
        storage="excerpt",
        qualification="Redakcja fact-checkingowa deklarująca standardy IFCN.",
        update_policy="Co godzinę; kanał RSS.",
        max_items=40,
        params={"feed": "https://konkret24.tvn24.pl/najnowsze.xml", "max_items": 40},
    ),
    SourceSpec(
        key="pravda-rss",
        name="Pravda – artykuły",
        url="https://pravda.org.pl",
        adapter="rss",
        publisher="Stowarzyszenie Pravda",
        source_type="factcheck",
        tier=2,
        license="Prawa zastrzeżone – przechowujemy tylko tytuł, zajawkę i link",
        storage="excerpt",
        qualification="Organizacja fact-checkingowa deklarująca standardy IFCN/EFCSN.",
        update_policy="Codziennie; kanał RSS.",
        max_items=30,
        params={"feed": "https://pravda.org.pl/feed/", "max_items": 30},
    ),
    SourceSpec(
        key="pravda-claimreview",
        name="Pravda – zweryfikowane twierdzenia (ClaimReview)",
        url="https://pravda.org.pl",
        adapter="claimreview",
        publisher="Stowarzyszenie Pravda",
        source_type="factcheck",
        tier=2,
        license="Dane strukturalne ClaimReview – twierdzenie, ocena i link",
        storage="structured",
        qualification="Korpus zweryfikowanych twierdzeń (schema.org/ClaimReview).",
        update_policy="Codziennie; publiczny kanał Fact Check Tools.",
        max_items=220,
        params={"domain": "pravda.org.pl", "max_items": 220},
    ),
    SourceSpec(
        key="fakenews-pl",
        name="FakeNews.pl",
        url="https://fakenews.pl",
        adapter="rss",
        publisher="Fundacja „Przeciwdziałamy Dezinformacji”",
        source_type="factcheck",
        tier=2,
        license="Prawa zastrzeżone – przechowujemy tylko tytuł, zajawkę i link",
        storage="excerpt",
        qualification="Organizacja fact-checkingowa deklarująca standardy EFCSN.",
        update_policy="Codziennie; kanał RSS.",
        max_items=20,
        params={"feed": "https://fakenews.pl/feed/", "max_items": 20},
    ),
    # --- media (poziom 3, wyłącznie kontekst) ---
    SourceSpec(
        key="osw",
        name="Ośrodek Studiów Wschodnich – analizy",
        url="https://www.osw.waw.pl",
        adapter="rss",
        publisher="Ośrodek Studiów Wschodnich im. Marka Karpia",
        source_type="official",
        tier=1,
        license="Do potwierdzenia w nocie prawnej serwisu – przechowujemy tylko tytuł, zajawkę i link",
        storage="excerpt",
        qualification="Państwowa instytucja analityczna; analizy eksperckie, nie dokumenty urzędowe.",
        update_policy="Codziennie; kanał RSS.",
        max_items=30,
        params={"feed": "https://www.osw.waw.pl/pl/rss.xml", "max_items": 30},
    ),
    SourceSpec(
        key="rzeczpospolita",
        name="Rzeczpospolita",
        url="https://www.rp.pl",
        adapter="rss",
        publisher="Gremi Media – Rzeczpospolita",
        source_type="media",
        tier=3,
        license="Prawa zastrzeżone – przechowujemy tylko tytuł, zajawkę i link",
        storage="excerpt",
        qualification="Ogólnopolski dziennik; wiarygodne źródło wtórne, wyłącznie jako kontekst.",
        update_policy="Co godzinę; kanał RSS.",
        max_items=30,
        params={"feed": "https://www.rp.pl/rss_main", "max_items": 30},
    ),
]


def get_sources(only: list[str] | None = None) -> list[SourceSpec]:
    if not only:
        return list(SOURCES)
    wanted = {key.strip() for key in only if key.strip()}
    known = {spec.key for spec in SOURCES}
    unknown = wanted - known
    if unknown:
        raise ValueError(f"Nieznane źródła: {', '.join(sorted(unknown))}")
    return [spec for spec in SOURCES if spec.key in wanted]


def source_names() -> dict[str, str]:
    return {spec.key: spec.name for spec in SOURCES}
