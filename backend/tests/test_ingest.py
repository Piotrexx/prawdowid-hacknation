"""Testy adapterów ingestu i idempotencji zapisu (bez sieci)."""

from datetime import datetime

from app.ingest import adapters
from app.ingest.registry import SourceSpec
from app.retrieval.corpus import CorpusStore

GOVPL_HTML = """
<article>
  <div class="art-prev">
    <ul>
      <li>
        <div class="event"><span class="date">18.11.2026</span></div>
        <div class="title"><a href="/web/gis/ostrzezenie-publiczne-1">Ostrzeżenie publiczne 1</a></div>
      </li>
      <li>
        <div class="event"><span class="date">17.11.2026</span></div>
        <div class="title"><a href="/web/gis/ostrzezenie-publiczne-2">Ostrzeżenie publiczne 2</a></div>
      </li>
    </ul>
  </div>
</article>
"""


def _spec(**overrides) -> SourceSpec:
    base = {
        "key": "test",
        "name": "Test",
        "url": "https://www.gov.pl/web/test/aktualnosci",
        "adapter": "govpl_list",
        "publisher": "Test",
    }
    base.update(overrides)
    return SourceSpec(**base)


def test_govpl_list_parses_articles_and_dates():
    documents = adapters.govpl_list(GOVPL_HTML, _spec(), limit=10)
    assert [document.title for document in documents] == ["Ostrzeżenie publiczne 1", "Ostrzeżenie publiczne 2"]
    assert documents[0].url == "https://www.gov.pl/web/gis/ostrzezenie-publiczne-1"
    assert documents[0].published_at == datetime(2026, 11, 18)
    assert documents[0].fetch_content is True


def test_html_links_filters_by_pattern():
    html = """
    <a href="/komunikaty/subskrybuj/">Subskrybuj</a>
    <a href="/komunikaty/2026/218/falszywe-informacje/">Fałszywe informacje</a>
    <a href="/komunikaty/2026/217/podatnosc/">Krytyczna podatność</a>
    """
    spec = _spec(
        key="cert",
        url="https://moje.cert.pl/komunikaty/",
        adapter="html_links",
        params={"link_regex": r"/komunikaty/\d{4}/\d+/[^/]+/?$"},
    )
    documents = adapters.html_links(html, spec, 10, spec.params["link_regex"])
    assert len(documents) == 2
    assert documents[0].url == "https://moje.cert.pl/komunikaty/2026/218/falszywe-informacje/"
    assert documents[0].fetch_content is True


def test_rso_documents_sorts_alarm_first_and_skips_expired():
    payload = {
        "newses": [
            {
                "id": 1,
                "title": "Susza",
                "content": "Niskie przepływy",
                "rso_alarm": "0",
                "valid_from": "2026-11-01 10:00:00",
                "valid_to": "2030-01-01 10:00:00",
            },
            {
                "id": 2,
                "title": "Wezbranie",
                "content": "Wysokie stany wód",
                "rso_alarm": "2",
                "valid_from": "2026-11-20 10:00:00",
                "valid_to": "2030-01-01 10:00:00",
            },
            {
                "id": 3,
                "title": "Stare",
                "content": "Nieaktualne",
                "rso_alarm": "0",
                "valid_from": "2020-01-01 10:00:00",
                "valid_to": "2020-01-02 10:00:00",
            },
        ]
    }
    spec = _spec(key="rso", url="https://www.gov.pl/web/gov/ostrzezenia", adapter="rso_api")
    documents = adapters.rso_documents([payload], spec, limit=10)
    assert [document.title for document in documents] == ["Wezbranie", "Susza"]
    assert documents[0].url.endswith("#rso-2")


def test_imgw_documents_builds_titles_and_excerpts():
    payload = [
        {
            "id": "Sk1",
            "nazwa_zdarzenia": "Oblodzenie",
            "stopien": "1",
            "tresc": "Mokre nawierzchnie mogą ulegać oblodzeniu.",
            "komentarz": "Brak.",
            "biuro": "Biuro Prognoz w Warszawie",
            "opublikowano": "2026-11-21 12:00:00",
        }
    ]
    spec = _spec(key="imgw", url="https://meteo.imgw.pl/", adapter="imgw_json", params={"kind": "meteo"})
    documents = adapters.imgw_documents(payload, spec, limit=10)
    assert documents[0].title == "Oblodzenie – stopień 1"
    assert "Mokre nawierzchnie" in documents[0].excerpt
    assert documents[0].published_at == datetime(2026, 11, 21, 12, 0)


def test_rbc_daily_snapshot_has_unique_date_url():
    html = """
    <article>
      <h2>Raport dobowy</h2>
      <div class="editor-content">
        <p><strong>21 listopada 2026 r.</strong></p>
        <p>Ostrzeżenia meteorologiczne: brak.</p>
      </div>
    </article>
    """
    spec = _spec(
        key="rcb",
        url="https://www.gov.pl/web/rcb/raport-dobowy3",
        adapter="single_page_daily",
    )
    documents = adapters.single_page_daily(html, spec, limit=10)
    assert len(documents) == 1
    assert documents[0].url == "https://www.gov.pl/web/rcb/raport-dobowy3#2026-11-21"
    assert "Raport dobowy" in documents[0].title


def test_corpus_upsert_is_idempotent(db_engine):
    corpus = CorpusStore(db_engine)
    kwargs = {
        "source_key": "gis",
        "publisher": "GIS",
        "title": "Ostrzeżenie publiczne",
        "excerpt": "Fragment ostrzeżenia o produktach.",
        "url": "https://example.org/a",
        "published_at": datetime(2026, 11, 18),
        "content_hash": "hash-1",
        "embedding": [0.1] * 384,
        "embedding_model": "fake",
    }
    first = corpus.upsert_article(**kwargs)
    second = corpus.upsert_article(**kwargs)
    assert first.status == "created"
    assert second.status == "unchanged"
    assert corpus.count() == 1

    kwargs["content_hash"] = "hash-2"
    third = corpus.upsert_article(**kwargs)
    assert third.status == "updated"
    assert corpus.count() == 1


def test_corpus_backfills_missing_embedding(db_engine):
    corpus = CorpusStore(db_engine)
    kwargs = {
        "source_key": "gis",
        "publisher": "GIS",
        "title": "Ostrzeżenie bez wektora",
        "excerpt": "Fragment.",
        "url": "https://example.org/no-vector",
        "published_at": None,
        "content_hash": "hash-1",
        "embedding": None,
        "embedding_model": None,
    }
    first = corpus.upsert_article(**kwargs)
    assert first.status == "created"
    assert corpus.get_index_state(kwargs["url"]) == ("hash-1", False)

    backfilled = corpus.upsert_article(**{**kwargs, "embedding": [0.2] * 384, "embedding_model": "fake"})
    assert backfilled.status == "updated"
    assert corpus.get_index_state(kwargs["url"]) == ("hash-1", True)
