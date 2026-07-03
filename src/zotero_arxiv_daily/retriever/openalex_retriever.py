from datetime import UTC, datetime, timedelta
from time import sleep
from typing import Any

import requests
from loguru import logger

from .base import BaseRetriever, register_retriever
from ..protocol import Paper


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    words_by_position = {}
    for word, positions in inverted_index.items():
        for position in positions:
            words_by_position[position] = word
    return " ".join(words_by_position[position] for position in sorted(words_by_position))


@register_retriever("openalex")
class OpenAlexRetriever(BaseRetriever):
    api_url = "https://api.openalex.org/works"
    conversion_delay_seconds = 0

    def __init__(self, config):
        super().__init__(config)
        if not self.retriever_config.get("issns"):
            raise ValueError("issns must be specified for openalex.")

    def _retrieve_raw_papers(self) -> list[dict[str, Any]]:
        days = int(self.retriever_config.get("days") or 1)
        until_date = datetime.now(UTC).date()
        from_date = until_date - timedelta(days=days)
        per_page = int(self.retriever_config.get("per_page") or 200)
        max_results = int(self.retriever_config.get("max_results") or 500)
        mailto = self.retriever_config.get("mailto")

        works = []
        for issn in self.retriever_config.issns:
            cursor = "*"
            while cursor and len(works) < max_results:
                filters = [
                    f"from_publication_date:{from_date.isoformat()}",
                    f"to_publication_date:{until_date.isoformat()}",
                    "type:article",
                    "has_abstract:true",
                    f"locations.source.issn:{issn}",
                ]
                params = {
                    "filter": ",".join(filters),
                    "sort": "publication_date:desc",
                    "per-page": per_page,
                    "cursor": cursor,
                }
                if mailto:
                    params["mailto"] = mailto
                response = requests.get(self.api_url, params=params, timeout=(10, 60))
                response.raise_for_status()
                result = response.json()
                works.extend(result.get("results", []))
                cursor = result.get("meta", {}).get("next_cursor")
                if not cursor:
                    break
                sleep(1)

        seen = set()
        unique_works = []
        for work in works:
            key = work.get("doi") or work.get("id")
            if key in seen:
                continue
            seen.add(key)
            unique_works.append(work)
        return unique_works

    def convert_to_paper(self, raw_paper: dict[str, Any]) -> Paper | None:
        abstract = reconstruct_abstract(raw_paper.get("abstract_inverted_index"))
        if not abstract:
            logger.warning(f"Skipping OpenAlex work without abstract: {raw_paper.get('id')}")
            return None
        primary_location = raw_paper.get("primary_location") or {}
        authors = [
            authorship.get("author", {}).get("display_name", "")
            for authorship in raw_paper.get("authorships", [])
        ]
        authors = [author for author in authors if author]
        url = primary_location.get("landing_page_url") or raw_paper.get("doi") or raw_paper.get("id")
        venue = (primary_location.get("source") or {}).get("display_name")
        return Paper(
            source=self.name,
            title=raw_paper.get("title") or "",
            authors=authors,
            abstract=abstract,
            url=url,
            pdf_url=primary_location.get("pdf_url"),
            full_text=None,
            venue=venue,
            published_date=raw_paper.get("publication_date"),
        )
