"""Katalog źródeł ingestu. Jedyne miejsce, które decyduje, co trafia do korpusu."""

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
    source_type: str = "urzędowe"
    max_items: int = 10
    params: dict = field(default_factory=dict)


SOURCES: list[SourceSpec] = [
    SourceSpec(
        key="rcb-raport-dobowy",
        name="Rządowe Centrum Bezpieczeństwa – raport dobowy",
        url="https://www.gov.pl/web/rcb/raport-dobowy3",
        adapter="single_page_daily",
        publisher="Rządowe Centrum Bezpieczeństwa",
    ),
    SourceSpec(
        key="gov-ostrzezenia",
        name="Gov.pl – system ostrzeżeń (RSO)",
        url="https://www.gov.pl/web/gov/ostrzezenia",
        adapter="rso_api",
        publisher="Rządowe Centrum Bezpieczeństwa",
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
        params={
            "api_url": "https://danepubliczne.imgw.pl/api/data/warningsmeteo",
            "kind": "meteo",
        },
    ),
    SourceSpec(
        key="imgw-hydro",
        name="IMGW – sytuacja hydrologiczna",
        url="https://hydro.imgw.pl/",
        adapter="imgw_hydro_snapshot",
        publisher="IMGW-PIB",
        params={
            "api_url": "https://danepubliczne.imgw.pl/api/data/hydro",
        },
    ),
    SourceSpec(
        key="cert-polska",
        name="CERT Polska – komunikaty",
        url="https://moje.cert.pl/komunikaty/",
        adapter="html_links",
        publisher="CERT Polska",
        params={"link_regex": r"/komunikaty/\d{4}/\d+/[^/]+/?$"},
    ),
    SourceSpec(
        key="gddkia",
        name="GDDKiA – aktualności (gov.pl)",
        url="https://www.gov.pl/web/gddkia/aktualnosci",
        adapter="govpl_list",
        publisher="Generalna Dyrekcja Dróg Krajowych i Autostrad",
    ),
    SourceSpec(
        key="kgpsp",
        name="Komenda Główna PSP – aktualności",
        url="https://www.gov.pl/web/kgpsp/aktualnosci",
        adapter="govpl_list",
        publisher="Komenda Główna Państwowej Straży Pożarnej",
    ),
    SourceSpec(
        key="policja",
        name="Policja – aktualności",
        url="https://policja.pl/pol/aktualnosci",
        adapter="html_links",
        publisher="Policja",
        params={"link_regex": r"/pol/aktualnosci/\d+,[^/]+\.html$"},
    ),
    SourceSpec(
        key="gis",
        name="GIS – ostrzeżenia",
        url="https://www.gov.pl/web/gis/ostrzezenia",
        adapter="govpl_list",
        publisher="Główny Inspektorat Sanitarny",
    ),
    SourceSpec(
        key="paa",
        name="Państwowa Agencja Atomistyki – aktualności",
        url="https://www.gov.pl/web/paa/aktualnosci",
        adapter="govpl_list",
        publisher="Państwowa Agencja Atomistyki",
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
