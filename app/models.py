from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SiteProfile(BaseModel):
    """A reusable recipe for one site: how to search + how to reach a download link."""

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = ""
    base: str = ""
    search_url: str = Field(min_length=1)
    result_selector: str = ""
    title_selector: str = ""
    artist_selector: str = ""
    detail_link_selector: str = ""
    download_selector: str = ""
    download_on: Literal["detail", "result"] = "detail"
    render: Literal["http", "js"] = "http"
    charset: str = ""
    enabled: bool = True
    notes: str = ""

    @field_validator("search_url")
    @classmethod
    def search_url_needs_placeholder(cls, value: str) -> str:
        if "{query}" not in value:
            raise ValueError("search_url باید شامل {query} باشد")
        return value


class SiteUpdate(SiteProfile):
    pass


class InferRequest(BaseModel):
    search_url: str = Field(min_length=1)
    detail_url: str = ""
    query_hint: str = ""


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: Literal["title", "lyrics"] = "title"
    site_ids: list[str] = Field(default_factory=list)
    limit_per_site: int = Field(default=4, ge=1, le=15)
    verify: bool = True


class TestRequest(BaseModel):
    query: str = Field(min_length=1)
    verify: bool = False


class ImportRequest(BaseModel):
    content: str = ""
    mode: Literal["merge", "replace"] = "merge"
