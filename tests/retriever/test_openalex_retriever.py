"""Tests for OpenAlexRetriever."""

from types import SimpleNamespace

from omegaconf import open_dict

from zotero_arxiv_daily.retriever.openalex_retriever import OpenAlexRetriever


def test_openalex_retriever_returns_articles_with_reconstructed_abstract(config, monkeypatch):
    response_body = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "title": "A computational biology paper",
                "authorships": [
                    {"author": {"display_name": "Alice"}},
                    {"author": {"display_name": "Bob"}},
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
                    "source": {"display_name": "Nature Computational Science"},
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
    assert papers[0].pdf_url == "https://example.org/paper.pdf"
    assert papers[0].venue == "Nature Computational Science"
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
