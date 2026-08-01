"""Tests for OpenAlexRetriever."""

from types import SimpleNamespace

import requests
from omegaconf import open_dict

from zotero_arxiv_daily.retriever.openalex_retriever import OpenAlexRetriever


def test_openalex_retriever_returns_articles_with_reconstructed_abstract(config, monkeypatch):
    response_body = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "title": "A computational biology paper",
                "authorships": [
                    {
                        "author": {"display_name": "Alice"},
                        "institutions": [{"display_name": "Institute A"}],
                        "is_corresponding": False,
                    },
                    {
                        "author": {"display_name": "Bob"},
                        "institutions": [{"display_name": "Institute B"}],
                        "is_corresponding": True,
                    },
                ],
                "abstract_inverted_index": {
                    "Protein": [0],
                    "dynamics": [1],
                    "prediction": [2],
                },
                "doi": "https://doi.org/10.0000/example",
                "publication_date": "2026-07-02",
                "primary_location": {
                    "landing_page_url": "https://example.org/paper",
                    "pdf_url": "https://example.org/paper.pdf",
                    "source": {
                        "display_name": "Nature Computational Science",
                        "issn_l": "2662-8457",
                        "issn": ["2662-8457", "2662-8465"],
                    },
                },
            }
        ],
        "meta": {"next_cursor": None},
    }
    calls = []

    def _get(url, params=None, timeout=None):
        calls.append((url, params, timeout))
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: response_body,
        )

    monkeypatch.setattr("zotero_arxiv_daily.retriever.openalex_retriever.requests.get", _get)
    with open_dict(config.source):
        config.source.openalex = {
            "issns": ["1549-9618"],
            "days": 1,
            "per_page": 25,
            "mailto": "test@example.com",
        }

    papers = OpenAlexRetriever(config).retrieve_papers()

    assert len(papers) == 1
    assert papers[0].title == "A computational biology paper"
    assert papers[0].abstract == "Protein dynamics prediction"
    assert papers[0].authors == ["Alice", "Bob"]
    assert papers[0].affiliations == [
        "第一单位：Institute A",
        "通讯单位：Institute B",
    ]
    assert papers[0].pdf_url == "https://example.org/paper.pdf"
    assert papers[0].venue == "Nature Computational Science"
    assert papers[0].venue_issns == ["2662-8457", "2662-8465"]
    assert papers[0].doi == "https://doi.org/10.0000/example"
    assert papers[0].external_id == "https://openalex.org/W123"
    assert papers[0].published_date == "2026-07-02"
    assert calls[0][1]["filter"].startswith("from_publication_date:")
    assert "locations.source.issn:1549-9618" in calls[0][1]["filter"]


def test_openalex_retriever_does_not_sleep_between_local_conversions(config, monkeypatch):
    response_body = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "title": "A computational biology paper",
                "authorships": [],
                "abstract_inverted_index": {"Protein": [0]},
                "primary_location": {},
            }
        ],
        "meta": {"next_cursor": None},
    }
    sleep_calls = []

    monkeypatch.setattr(
        "zotero_arxiv_daily.retriever.openalex_retriever.requests.get",
        lambda *args, **kwargs: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: response_body,
        ),
    )
    monkeypatch.setattr("zotero_arxiv_daily.retriever.base.sleep", lambda seconds: sleep_calls.append(seconds))
    with open_dict(config.source):
        config.source.openalex = {
            "issns": ["1549-9618"],
            "days": 1,
            "per_page": 25,
            "mailto": "test@example.com",
        }

    OpenAlexRetriever(config).retrieve_papers()

    assert sleep_calls == []


def test_openalex_retriever_batches_multiple_issns_in_one_request(config, monkeypatch):
    calls = []

    def _get(url, params=None, timeout=None):
        calls.append((url, params, timeout))
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"results": [], "meta": {"next_cursor": None}},
        )

    monkeypatch.setattr("zotero_arxiv_daily.retriever.openalex_retriever.requests.get", _get)
    with open_dict(config.source):
        config.source.openalex = {
            "issns": ["1549-9618", "1549-9596", "1758-2946"],
            "days": 1,
            "per_page": 25,
        }

    OpenAlexRetriever(config).retrieve_papers()

    assert len(calls) == 1
    assert "locations.source.issn:1549-9618|1549-9596|1758-2946" in calls[0][1]["filter"]


def test_openalex_retriever_uses_shanghai_calendar_date_for_window(config, monkeypatch):
    from datetime import UTC, datetime

    calls = []
    instant = datetime(2026, 7, 31, 16, 30, tzinfo=UTC)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    def _get(url, params=None, timeout=None):
        calls.append(params)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"results": [], "meta": {"next_cursor": None}},
        )

    monkeypatch.setattr("zotero_arxiv_daily.retriever.openalex_retriever.datetime", FrozenDateTime)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.openalex_retriever.requests.get", _get)
    with open_dict(config.source):
        config.source.openalex = {"issns": ["1549-9618"], "days": 1, "per_page": 25}

    OpenAlexRetriever(config).retrieve_papers()

    assert "to_publication_date:2026-08-01" in calls[0]["filter"]


def test_openalex_retriever_skips_openalex_when_rate_limited(config, monkeypatch):
    def _get(url, params=None, timeout=None):
        response = SimpleNamespace(status_code=429, headers={})
        error = requests.HTTPError("429 Client Error: Too Many Requests")
        error.response = response
        return SimpleNamespace(
            status_code=429,
            headers={},
            raise_for_status=lambda: (_ for _ in ()).throw(error),
        )

    monkeypatch.setattr("zotero_arxiv_daily.retriever.openalex_retriever.requests.get", _get)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.openalex_retriever.sleep", lambda seconds: None)
    with open_dict(config.source):
        config.source.openalex = {
            "issns": ["1549-9618"],
            "days": 1,
            "per_page": 25,
            "request_retry_attempts": 1,
        }

    papers = OpenAlexRetriever(config).retrieve_papers()

    assert papers == []
