"""Web research brief used by the writer, scout, and post kit."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""


class ResearchBrief(BaseModel):
    topic: str
    summary: str = ""
    facts: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)
    image_queries: list[str] = Field(default_factory=list)
    extracts: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)

    def spoken_pool(self) -> list[str]:
        pool: list[str] = []
        if self.summary:
            pool.append(self.summary)
        pool.extend(self.facts)
        pool.extend(self.extracts)
        pool.extend(self.quotes)
        return [item.strip() for item in pool if item and item.strip()]

    def visual_queries(self) -> list[str]:
        from app.services.visuals import visual_queries as build

        extra = list(self.image_queries) + list(self.people) + list(self.places)
        return build(self.topic, extra=extra)
