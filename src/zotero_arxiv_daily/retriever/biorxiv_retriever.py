from datetime import datetime
from time import sleep
from typing import Any
from zoneinfo import ZoneInfo

import requests
from loguru import logger

from .base import BaseRetriever, SourceRetrievalError, register_retriever
from ..protocol import Paper, format_affiliations
from ..publication_window import earliest_allowed_publication_date


SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")

@register_retriever("biorxiv")
class BiorxivRetriever(BaseRetriever):
    server = "biorxiv"

    def __init__(self, config):
        super().__init__(config)
        if self.retriever_config.category is None:
            raise ValueError(f"category must be specified for {self.name}")

    def _retrieve_raw_papers(self) -> list[dict[str, Any]]:
        local_today = datetime.now(SHANGHAI_TIMEZONE).date()
        earliest_date = earliest_allowed_publication_date(local_today)
        lookback_days = max(2, (local_today - earliest_date).days)
        api_url = f"https://api.biorxiv.org/details/{self.server}/{lookback_days}d"
        retry_num = 3
        delay_time = 10
        for i in range(retry_num):
            try:
                response = requests.get(api_url, timeout=(10, 60))
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict) or not isinstance(result.get("collection"), list):
                    raise ValueError(f"{self.server_label()} API response has no collection list")
                break
            except (requests.RequestException, ValueError) as e:
                if i == retry_num - 1:
                    raise SourceRetrievalError(
                        f"{self.server_label()} retrieval failed after {retry_num} attempts: "
                        f"{type(e).__name__}: {e}"
                    ) from e
                else:
                    wait = delay_time * (i + 1)
                    logger.warning(f"{self.server_label()} retrieval failed: {type(e).__name__}: {e}. Retry in {wait} seconds.")
                    sleep(wait)
        collection = result['collection']
        if len(collection) == 0:
            logger.warning(f"No paper found. API Message: {result.get('messages')}")
            return []
        categories = [c.lower() for c in self.retriever_config.category]
        collection = [c for c in collection if c['category'].lower() in categories]
        if len(collection) == 0:
            return []
        all_dates = set(c['date'] for c in collection)
        latest_date = sorted(all_dates)[-1]
        collection = [c for c in collection if c['date'] == latest_date]
        if self.config.executor.debug:
            collection = collection[:10]
        return collection


    def convert_to_paper(self, raw_paper:dict[str, Any]) -> Paper | None:
        title = raw_paper['title']
        authors = [a.strip() for a in raw_paper['authors'].split(';')]
        abstract = raw_paper['abstract']
        pdf_url = f"https://www.{self.server}.org/content/{raw_paper['doi']}v{raw_paper['version']}.full.pdf"
        full_text = None # biorxiv forbids scraping its pdf
        corresponding_institution = raw_paper.get("author_corresponding_institution")
        return Paper(
            source=self.name,
            title=title,
            authors=authors,
            abstract=abstract,
            url=pdf_url,
            pdf_url=pdf_url,
            full_text=full_text,
            affiliations=format_affiliations(None, [corresponding_institution]),
            venue=f"{self.server_label()}: {raw_paper.get('category', 'unknown')}",
            published_date=raw_paper.get("date"),
        )

    def server_label(self) -> str:
        return {"biorxiv": "bioRxiv", "medrxiv": "medRxiv"}.get(self.server, self.server)
