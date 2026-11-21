from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from app.schemas import SourceType


class CatalogSource(BaseModel):
    id: str
    name: str
    publisher: str
    homepage: str
    source_type: SourceType
    tier: int
    language: str
    license: str
    storage: Literal["full_text", "excerpt", "structured"]
    qualification: str
    update_policy: str
    enabled: bool = True
    disabled_reason: str | None = None
    connector: str | None = None
    params: dict[str, Any] = {}


class Catalog(BaseModel):
    rules: list[str]
    sources: list[CatalogSource]

    def by_id(self) -> dict[str, CatalogSource]:
        return {s.id: s for s in self.sources}


class Document(BaseModel):
    """Rekord korpusu. `text` to jedyna treść, z której wolno cytować."""

    id: str
    source_id: str
    title: str
    publisher: str
    url: str
    language: str
    source_type: SourceType
    tier: int
    license: str
    published_at: date | None = None
    retrieved_at: datetime
    text: str
    claim_reviewed: str | None = None
    rating: str | None = None
    appearance_urls: list[str] = []


@lru_cache
def load_catalog(path: Path) -> Catalog:
    return Catalog.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
