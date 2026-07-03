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
        rate_limited = False
        for issn_batch in self._issn_batches():
            cursor = "*"
            while cursor and len(works) < max_results:
                filters = [
                    f"from_publication_date:{from_date.isoformat()}",
                    f"to_publication_date:{until_date.isoformat()}",
                    "type:article",
                    "has_abstract:true",
                    f"locations.source.issn:{'|'.join(issn_batch)}",
                ]
                params = {
                    "filter": ",".join(filters),
                    "sort": "publication_date:desc",
                    "per-page": per_page,
                    "cursor": cursor,
                }
                if mailto:
                    params["mailto"] = mailto
                try:
                    response = self._get_with_retries(params)
                except requests.HTTPError as exc:
                    if self._status_code(exc) == 429:
                        logger.warning("OpenAlex rate limit reached; skipping remaining OpenAlex retrieval")
                        rate_limited = True
                        break
                    raise
                result = response.json()
                works.extend(result.get("results", []))
                cursor = result.get("meta", {}).get("next_cursor")
                if not cursor:
                    break
                sleep(1)
            if rate_limited:
                break

        seen = set()
        unique_works = []
        for work in works:
            key = work.get("doi") or work.get("id")
            if key in seen:
                continue
            seen.add(key)
            unique_works.append(work)
        return unique_works

    def _issn_batches(self) -> list[list[str]]:
        batch_size = int(self.retriever_config.get("issn_batch_size") or 50)
        issns = list(self.retriever_config.issns)
        return [issns[start : start + batch_size] for start in range(0, len(issns), batch_size)]

    def _get_with_retries(self, params: dict[str, Any]):
        attempts = max(1, int(self.retriever_config.get("request_retry_attempts") or 2))
        for attempt in range(attempts):
            response = requests.get(self.api_url, params=params, timeout=(10, 60))
            try:
                response.raise_for_status()
                return response
            except requests.HTTPError as exc:
                if attempt == attempts - 1 or not self._is_retryable_status(self._status_code(exc)):
                    raise
                delay = self._retry_delay_seconds(response, attempt)
                logger.warning(
                    f"OpenAlex request failed with HTTP {self._status_code(exc)}; retrying in {delay:.1f}s"
                )
                sleep(delay)
        raise RuntimeError("unreachable")

    @staticmethod
    def _status_code(exc: requests.HTTPError) -> int | None:
        response = getattr(exc, "response", None)
        return getattr(response, "status_code", None)

    @staticmethod
    def _is_retryable_status(status_code: int | None) -> bool:
        return status_code in {429, 500, 502, 503, 504}

    def _retry_delay_seconds(self, response, attempt: int) -> float:
        default_delay = float(self.retriever_config.get("request_retry_initial_seconds") or 10)
        max_delay = float(self.retriever_config.get("request_retry_max_seconds") or 60)
        retry_after = None
        try:
            retry_after = response.headers.get("retry-after")
        except AttributeError:
            retry_after = None
        try:
            delay = float(retry_after) if retry_after is not None else default_delay * (2 ** attempt)
        except (TypeError, ValueError):
            delay = default_delay * (2 ** attempt)
        return min(delay, max_delay)

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
