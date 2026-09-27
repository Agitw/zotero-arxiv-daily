"""Replay the external source failures observed in September Actions runs."""

import json
from types import SimpleNamespace

import arxiv
import feedparser
import pytest
import requests
from omegaconf import open_dict

from tests.canned_responses import (
    SAMPLE_BIORXIV_API_RESPONSE,
    make_sample_corpus,
    make_sample_paper,
)
from zotero_arxiv_daily.executor import Executor
from zotero_arxiv_daily.protocol import Paper
from zotero_arxiv_daily.retriever.arxiv_retriever import ArxivRetriever
from zotero_arxiv_daily.retriever.biorxiv_retriever import BiorxivRetriever
from zotero_arxiv_daily.retriever.medrxiv_retriever import MedrxivRetriever
from zotero_arxiv_daily.retriever.base import SourceRetrievalError


@pytest.mark.parametrize("status", [406, 503])
def test_arxiv_api_failure_preserves_rss_papers(config, monkeypatch, status):
    feed = feedparser.parse("tests/retriever/arxiv_rss_example.xml")
    monkeypatch.setattr("feedparser.parse", lambda *args, **kwargs: feed)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.arxiv_retriever.sleep", lambda _: None)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.base.sleep", lambda _: None)

    class FailedClient:
        def __init__(self, **kwargs):
            pass

        def results(self, search):
            raise arxiv.HTTPError("https://export.arxiv.org/api/query", 0, status)

    monkeypatch.setattr(arxiv, "Client", FailedClient)
    papers = ArxivRetriever(config).retrieve_papers()

    assert [paper.title for paper in papers] == [
        "Neural Architecture Search for Efficient Transformers",
        "Reward Shaping in Multi-Agent Reinforcement Learning",
    ]
    assert papers[0].abstract == "We propose a neural architecture search method for efficient transformers."
    assert papers[0].authors == ["Alice Smith", "Bob Jones"]
    assert papers[0].published_date.startswith("2025-08-20")
    assert papers[0].url == "https://arxiv.org/abs/2508.14001v1"
    assert papers[0].pdf_url == "https://arxiv.org/pdf/2508.14001v1"


@pytest.mark.parametrize("retriever_cls", [BiorxivRetriever, MedrxivRetriever])
def test_biorxiv_invalid_json_is_retried(config, monkeypatch, retriever_cls):
    bad_response = requests.Response()
    bad_response.status_code = 200
    bad_response._content = b"<html>temporarily unavailable</html>"
    good_response = SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: SAMPLE_BIORXIV_API_RESPONSE,
    )
    responses = iter([bad_response, good_response])
    calls = []

    def get(url, **kwargs):
        calls.append(kwargs)
        return next(responses)

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.biorxiv_retriever.sleep", lambda _: None)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.base.sleep", lambda _: None)
    with open_dict(config.source):
        config.source[retriever_cls.name] = {"category": ["bioinformatics"]}

    papers = retriever_cls(config).retrieve_papers()

    assert [paper.title for paper in papers] == ["A biorxiv paper"]
    assert len(calls) == 2
    assert all(call["timeout"] == (10, 60) for call in calls)


def test_one_failed_source_still_delivers_other_sources(config, tmp_path, monkeypatch):
    funnel_path = tmp_path / "funnel.json"
    with open_dict(config.executor):
        config.executor.recommendation_funnel_path = str(funnel_path)
        config.executor.feedback_path = None
    selected = make_sample_paper(source="openalex", score=8.0)
    calls = []

    def fail():
        raise requests.JSONDecodeError("Expecting value", "", 0)

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {
        "biorxiv": SimpleNamespace(retrieve_papers=fail),
        "openalex": SimpleNamespace(retrieve_papers=lambda: [selected]),
    }
    executor.reranker = SimpleNamespace(rerank=lambda papers, corpus: papers)
    executor.openai_client = object()
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(1)
    executor.filter_corpus = lambda corpus: corpus
    monkeypatch.setattr(Paper, "generate_tldr", lambda *args: "summary")
    monkeypatch.setattr(Paper, "generate_affiliations", lambda *args: [])
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda *args: calls.append("sent"))

    executor.run()

    assert calls == ["sent"]
    report = json.loads(funnel_path.read_text(encoding="utf-8"))
    assert report["sources"]["biorxiv"]["status"] == "failed"
    assert report["sources"]["openalex"]["status"] == "success"
    assert report["stage_totals"]["emailed"] == 1
    assert "failure" not in report


def test_arxiv_keeps_successful_batch_and_stops_api_after_failure(config, monkeypatch):
    entries = [
        feedparser.FeedParserDict(
            id=f"oai:arXiv.org:2609.{index:05d}v1",
            title=f"Paper {index}",
            summary=f"arXiv:2609.{index:05d}v1 Announce Type: new\nAbstract: Abstract {index}",
            author="Test Author", published="2026-09-26T00:00:00-04:00",
            arxiv_announce_type="new",
        )
        for index in range(45)
    ]
    feed = feedparser.FeedParserDict(feed={"title": "cs.AI updates"}, entries=entries)
    monkeypatch.setattr(feedparser, "parse", lambda *args: feed)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.arxiv_retriever.sleep", lambda _: None)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.base.sleep", lambda _: None)
    calls = []
    first_batch = [make_sample_paper(title=f"API paper {index}") for index in range(20)]

    class Client:
        def __init__(self, **kwargs):
            pass

        def results(self, search):
            calls.append(search.id_list)
            if len(calls) == 1:
                return iter(first_batch)
            raise arxiv.HTTPError("https://export.arxiv.org/api/query", 0, 406)

    monkeypatch.setattr(arxiv, "Client", Client)
    retriever = ArxivRetriever(config)
    papers = retriever.retrieve_papers()

    assert len(calls) == 2
    assert papers[:20] == first_batch
    assert [paper.title for paper in papers[20:]] == [f"Paper {index}" for index in range(20, 45)]
    assert len(retriever.retrieval_warnings) == 1


@pytest.mark.parametrize("body", [b"", b"<html>unavailable</html>", b'{"messages": [{"status": "error"}]}'])
def test_biorxiv_persistent_bad_response_is_a_bounded_source_failure(config, monkeypatch, body):
    response = requests.Response()
    response.status_code = 200
    response._content = body
    calls = []

    def get(url, **kwargs):
        calls.append(kwargs)
        return response

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.biorxiv_retriever.sleep", lambda _: None)
    with open_dict(config.source):
        config.source.biorxiv = {"category": ["bioinformatics"]}

    with pytest.raises(SourceRetrievalError, match="after 3 attempts"):
        BiorxivRetriever(config).retrieve_papers()

    assert len(calls) == 3


def test_all_sources_failed_does_not_report_empty_success(config, tmp_path, monkeypatch):
    funnel_path = tmp_path / "funnel.json"
    with open_dict(config.executor):
        config.executor.recommendation_funnel_path = str(funnel_path)
        config.executor.send_empty = True
    calls = []

    def fail():
        calls.append("retrieved")
        raise requests.Timeout("source unavailable")

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {name: SimpleNamespace(retrieve_papers=fail) for name in ["biorxiv", "openalex"]}
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(1)
    executor.filter_corpus = lambda corpus: corpus
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda *args: pytest.fail("Must not send an empty success email"))

    with pytest.raises(SourceRetrievalError, match="All paper sources failed"):
        executor.run()

    assert calls == ["retrieved", "retrieved"]
    report = json.loads(funnel_path.read_text(encoding="utf-8"))
    assert report["failure"]["type"] == "SourceRetrievalError"
    assert all(source["status"] == "failed" for source in report["sources"].values())


def test_programming_error_is_not_hidden_as_a_source_outage(config):
    def fail():
        raise TypeError("broken implementation")

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {"arxiv": SimpleNamespace(retrieve_papers=fail)}
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(1)
    executor.filter_corpus = lambda corpus: corpus

    with pytest.raises(TypeError, match="broken implementation"):
        executor.run()
