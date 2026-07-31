"""Tests for BiorxivRetriever."""

import pytest
from omegaconf import open_dict

from zotero_arxiv_daily.retriever.biorxiv_retriever import BiorxivRetriever
from tests.canned_responses import SAMPLE_BIORXIV_API_RESPONSE


def test_biorxiv_retrieve(config, mock_biorxiv_api, monkeypatch):
    monkeypatch.setattr("zotero_arxiv_daily.retriever.base.sleep", lambda _: None)
    with open_dict(config.source):
        config.source.biorxiv = {"category": ["bioinformatics"]}
    retriever = BiorxivRetriever(config)
    papers = retriever.retrieve_papers()
    # Only latest date + matching category
    assert len(papers) == 1
    assert papers[0].title == "A biorxiv paper"


def test_biorxiv_selects_latest_matching_category_not_latest_overall(config, monkeypatch):
    import requests
    from types import SimpleNamespace

    response_body = {
        "messages": [{"status": "ok"}],
        "collection": [
            {
                "doi": "10.1101/2026.03.02.000001",
                "title": "Newest unrelated paper",
                "authors": "Unrelated, A.",
                "abstract": "A different field.",
                "date": "2026-03-03",
                "category": "genomics",
                "version": "1",
            },
            {
                "doi": "10.1101/2026.03.01.000001",
                "title": "Latest matching paper",
                "authors": "Relevant, A.",
                "abstract": "A relevant bioinformatics paper.",
                "date": "2026-03-02",
                "category": "bioinformatics",
                "version": "1",
            },
        ],
    }

    def _patched(url, **kw):
        resp = SimpleNamespace(status_code=200, raise_for_status=lambda: None)
        resp.json = lambda: response_body
        return resp

    monkeypatch.setattr(requests, "get", _patched)
    with open_dict(config.source):
        config.source.biorxiv = {"category": ["bioinformatics"]}

    papers = BiorxivRetriever(config).retrieve_papers()

    assert len(papers) == 1
    assert papers[0].title == "Latest matching paper"


def test_biorxiv_empty_response(config, monkeypatch):
    import requests
    from types import SimpleNamespace

    empty = {"messages": [{"status": "ok"}], "collection": []}

    def _patched(url, **kw):
        resp = SimpleNamespace(status_code=200, raise_for_status=lambda: None)
        resp.json = lambda: empty
        return resp

    monkeypatch.setattr(requests, "get", _patched)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.base.sleep", lambda _: None)

    with open_dict(config.source):
        config.source.biorxiv = {"category": ["bioinformatics"]}
    retriever = BiorxivRetriever(config)
    papers = retriever.retrieve_papers()
    assert papers == []


def test_biorxiv_convert_to_paper(config):
    with open_dict(config.source):
        config.source.biorxiv = {"category": ["bioinformatics"]}
    retriever = BiorxivRetriever(config)
    raw = SAMPLE_BIORXIV_API_RESPONSE["collection"][0]
    paper = retriever.convert_to_paper(raw)
    assert paper.title == "A biorxiv paper"
    assert paper.source == "biorxiv"
    assert "biorxiv.org" in paper.pdf_url
    assert paper.authors == ["Smith, J.", "Doe, A.", "Lee, K."]
    assert paper.venue == "bioRxiv: bioinformatics"
    assert paper.published_date == "2026-03-02"


def test_biorxiv_convert_to_paper_uses_corresponding_institution(config):
    with open_dict(config.source):
        config.source.biorxiv = {"category": ["bioinformatics"]}
    retriever = BiorxivRetriever(config)
    raw = {
        **SAMPLE_BIORXIV_API_RESPONSE["collection"][0],
        "author_corresponding_institution": "Institute of Genomics",
    }

    paper = retriever.convert_to_paper(raw)

    assert paper.affiliations == ["通讯单位：Institute of Genomics"]


def test_biorxiv_requires_category(config):
    with open_dict(config.source):
        config.source.biorxiv = {"category": None}
    with pytest.raises(ValueError, match="category must be specified"):
        BiorxivRetriever(config)
