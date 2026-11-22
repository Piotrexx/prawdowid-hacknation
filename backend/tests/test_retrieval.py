"""Testy wyszukiwania semantycznego: budowa zapytania, rerank i pgvector."""

from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.retrieval.corpus import CorpusDocument, CorpusStore
from app.retrieval.embeddings import FakeEmbedder
from app.retrieval.service import RetrievalService
from tests.conftest import TEST_DATABASE_URL

DIM = 384


def _vector(first: float, second: float = 0.0) -> list[float]:
    vector = [0.0] * DIM
    vector[0] = first
    vector[1] = second
    return vector


def _document(**overrides) -> CorpusDocument:
    base = {
        "doc_id": "1",
        "source_key": "gis",
        "publisher": "GIS",
        "title": "Ostrzeżenie publiczne",
        "excerpt": "Treść ostrzeżenia.",
        "url": "https://example.org/1",
        "published_at": datetime.now(UTC),
        "similarity": 0.9,
    }
    base.update(overrides)
    return CorpusDocument(**base)


def test_build_query_contains_topic_summary_and_keywords():
    query = RetrievalService.build_query(
        keywords=["powódź", "Warszawa"],
        main_topic="Powódź w Warszawie",
        summary="Woda przerwała wał.",
    )
    assert "Powódź w Warszawie" in query
    assert "Woda przerwała wał" in query
    assert "powódź; Warszawa" in query


def test_rerank_requires_keyword_or_high_similarity():
    documents = [
        _document(doc_id="1", url="https://example.org/1", similarity=0.95, title="Inny temat", excerpt="Sport"),
        _document(doc_id="2", url="https://example.org/2", similarity=0.80, title="Powódź w Warszawie", excerpt="Alert"),
        _document(doc_id="3", url="https://example.org/3", similarity=0.55, title="Powódź", excerpt="Alert"),
    ]
    ranked = RetrievalService._rerank(
        documents,
        keywords=["powódź", "Warszawa"],
        min_similarity=0.58,
        strong_similarity=0.82,
        max_per_source=2,
        top_k=6,
    )
    urls = [item.document.url for item in ranked]
    assert "https://example.org/3" not in urls  # poniżej progu podobieństwa
    assert "https://example.org/2" in urls
    assert "https://example.org/1" in urls  # bardzo wysokie podobieństwo


def test_rerank_caps_per_source_and_total():
    documents = [
        _document(
            doc_id=str(index),
            url=f"https://example.org/{index}",
            source_key="gis",
            similarity=0.99 - index * 0.001,
            title="Powódź",
            excerpt="Alert powodziowy",
        )
        for index in range(5)
    ]
    ranked = RetrievalService._rerank(
        documents,
        keywords=["powódź"],
        min_similarity=0.58,
        strong_similarity=0.82,
        max_per_source=2,
        top_k=3,
    )
    assert len(ranked) == 2
    assert {item.document.source_key for item in ranked} == {"gis"}


async def test_pgvector_search_filters_age_and_excludes_url(db_engine):
    corpus = CorpusStore(db_engine)
    now = datetime.now(UTC)
    rows = [
        ("gis", "https://example.org/new-1", "Powódź w Warszawie", _vector(1.0), now),
        ("gis", "https://example.org/new-2", "Powódź w Krakowie", _vector(0.99, 0.01), now),
        ("imgw", "https://example.org/new-3", "Ostrzeżenie hydrologiczne", _vector(0.98, 0.02), now),
        ("gis", "https://example.org/old", "Stara powódź", _vector(1.0), now - timedelta(days=300)),
    ]
    for index, (source, url, title, vector, published) in enumerate(rows):
        corpus.upsert_article(
            source_key=source,
            publisher=source.upper(),
            title=title,
            excerpt=f"{title}. Alert powodziowy.",
            url=url,
            published_at=published,
            content_hash=f"hash-{index}",
            embedding=vector,
            embedding_model="fake",
        )

    settings = Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        embedding_backend="none",
        retrieval_top_k=6,
        retrieval_candidates=20,
        retrieval_min_similarity=0.58,
        retrieval_strong_similarity=0.82,
        retrieval_max_age_days=90,
        retrieval_max_per_source=2,
    )
    embedder = FakeEmbedder(dim=DIM, mapping={"Powódź": _vector(1.0)})
    service = RetrievalService(settings, corpus, embedder)

    related = await service.find_related(
        keywords=["powódź"],
        main_topic="Powódź",
        summary="Alert powodziowy.",
        exclude_url="https://example.org/new-1",
    )
    urls = [item.document.url for item in related]
    assert "https://example.org/old" not in urls
    assert "https://example.org/new-1" not in urls
    assert "https://example.org/new-2" in urls
    assert len(related) <= 3


async def test_find_related_returns_empty_without_keywords(db_engine):
    settings = Settings(_env_file=None, database_url=TEST_DATABASE_URL, embedding_backend="none")
    service = RetrievalService(settings, CorpusStore(db_engine), FakeEmbedder(dim=DIM))
    assert await service.find_related(keywords=[], main_topic="Temat", summary="") == []


def test_format_context_marks_materials_as_context():
    from app.retrieval.service import RelatedArticle

    assert RetrievalService.format_context([]) == ""

    article = RelatedArticle(
        document=_document(title="Powódź", excerpt="Woda sięga mostu."),
        score=0.9,
        keyword_overlap=0.5,
    )
    text = RetrievalService.format_context([article])
    assert "kontekst, NIE dowód" in text
    assert "Powódź" in text
    assert "https://example.org/1" in text
