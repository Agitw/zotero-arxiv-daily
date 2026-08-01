"""Tests for zotero_arxiv_daily.executor: normalize_path_patterns, filter_corpus, fetch_zotero_corpus, E2E."""

from datetime import datetime

import pytest
from omegaconf import OmegaConf

from zotero_arxiv_daily.executor import Executor, normalize_path_patterns
from zotero_arxiv_daily.protocol import CorpusPaper


# ---------------------------------------------------------------------------
# normalize_path_patterns — migrated from test_include_path.py
# ---------------------------------------------------------------------------


def test_normalize_path_patterns_rejects_single_string_for_include_path():
    with pytest.raises(TypeError, match="config.zotero.include_path must be a list"):
        normalize_path_patterns("2026/survey/**", "include_path")


def test_normalize_path_patterns_accepts_list_config_for_include_path():
    include_path = OmegaConf.create(["2026/survey/**", "2026/reading-group/**"])
    assert normalize_path_patterns(include_path, "include_path") == [
        "2026/survey/**",
        "2026/reading-group/**",
    ]


def test_normalize_path_patterns_rejects_single_string_for_ignore_path():
    with pytest.raises(TypeError, match="config.zotero.ignore_path must be a list"):
        normalize_path_patterns("archive/**", "ignore_path")


def test_normalize_path_patterns_accepts_list_config_for_ignore_path():
    ignore_path = OmegaConf.create(["archive/**", "2025/**"])
    assert normalize_path_patterns(ignore_path, "ignore_path") == ["archive/**", "2025/**"]


def test_normalize_path_patterns_accepts_empty_list():
    assert normalize_path_patterns([], "ignore_path") == []


def test_normalize_path_patterns_accepts_none():
    assert normalize_path_patterns(None, "include_path") is None


# ---------------------------------------------------------------------------
# filter_corpus — migrated from test_include_path.py
# ---------------------------------------------------------------------------


def _make_executor(include_patterns=None, ignore_patterns=None):
    executor = Executor.__new__(Executor)
    executor.include_path_patterns = normalize_path_patterns(include_patterns, "include_path") if include_patterns else None
    executor.ignore_path_patterns = normalize_path_patterns(ignore_patterns, "ignore_path") if ignore_patterns else None
    return executor


def test_filter_corpus_matches_any_path_against_any_pattern():
    executor = _make_executor(include_patterns=["2026/survey/**", "2026/reading-group/**"])
    corpus = [
        CorpusPaper(title="Survey Paper", abstract="", added_date=datetime(2026, 1, 1), paths=["2026/survey/topic-a", "archive/misc"]),
        CorpusPaper(title="Reading Group Paper", abstract="", added_date=datetime(2026, 1, 2), paths=["notes/inbox", "2026/reading-group/week-1"]),
        CorpusPaper(title="Excluded Paper", abstract="", added_date=datetime(2026, 1, 3), paths=["2025/other/topic"]),
    ]
    filtered = executor.filter_corpus(corpus)
    assert [p.title for p in filtered] == ["Survey Paper", "Reading Group Paper"]


def test_filter_corpus_excludes_papers_matching_ignore_path():
    executor = _make_executor(ignore_patterns=["archive/**", "2025/**"])
    corpus = [
        CorpusPaper(title="Active Paper", abstract="", added_date=datetime(2026, 1, 1), paths=["2026/survey/topic-a"]),
        CorpusPaper(title="Archived Paper", abstract="", added_date=datetime(2026, 1, 2), paths=["archive/misc"]),
        CorpusPaper(title="Old Paper", abstract="", added_date=datetime(2026, 1, 3), paths=["2025/other/topic"]),
    ]
    filtered = executor.filter_corpus(corpus)
    assert [p.title for p in filtered] == ["Active Paper"]


def test_filter_corpus_ignore_path_takes_precedence_over_include_path():
    executor = _make_executor(include_patterns=["2026/**"], ignore_patterns=["2026/ignore/**"])
    corpus = [
        CorpusPaper(title="Included Paper", abstract="", added_date=datetime(2026, 1, 1), paths=["2026/survey/topic-a"]),
        CorpusPaper(title="Ignored Paper", abstract="", added_date=datetime(2026, 1, 2), paths=["2026/ignore/topic-b"]),
    ]
    filtered = executor.filter_corpus(corpus)
    assert [p.title for p in filtered] == ["Included Paper"]


def test_filter_corpus_no_filters_returns_all():
    executor = _make_executor()
    corpus = [
        CorpusPaper(title="Paper A", abstract="", added_date=datetime(2026, 1, 1), paths=["foo"]),
        CorpusPaper(title="Paper B", abstract="", added_date=datetime(2026, 1, 2), paths=["bar"]),
    ]
    filtered = executor.filter_corpus(corpus)
    assert filtered == corpus


# ---------------------------------------------------------------------------
# fetch_zotero_corpus
# ---------------------------------------------------------------------------


def test_fetch_zotero_corpus(config, monkeypatch):
    from tests.canned_responses import make_stub_zotero_client

    stub_zot = make_stub_zotero_client()
    monkeypatch.setattr("zotero_arxiv_daily.executor.zotero.Zotero", lambda *a, **kw: stub_zot)

    executor = Executor.__new__(Executor)
    executor.config = config
    corpus = executor.fetch_zotero_corpus()

    assert len(corpus) == 2
    assert corpus[0].title == "Stub Paper 1"
    assert "survey/topic-a" in corpus[0].paths[0]


def test_fetch_zotero_corpus_paper_with_zero_collections(config, monkeypatch):
    from tests.canned_responses import make_stub_zotero_client

    items = [
        {
            "data": {
                "title": "No Collection Paper",
                "abstractNote": "Abstract.",
                "dateAdded": "2026-03-01T00:00:00Z",
                "collections": [],
            }
        }
    ]
    stub_zot = make_stub_zotero_client(items=items)
    monkeypatch.setattr("zotero_arxiv_daily.executor.zotero.Zotero", lambda *a, **kw: stub_zot)

    executor = Executor.__new__(Executor)
    executor.config = config
    corpus = executor.fetch_zotero_corpus()

    assert len(corpus) == 1
    assert corpus[0].paths == []


def test_fetch_zotero_corpus_auto_uses_local_zotero_when_api_credentials_are_missing(config, monkeypatch):
    from omegaconf import open_dict

    local_corpus = [
        CorpusPaper(
            title="Local Paper",
            abstract="Local abstract.",
            added_date=datetime(2026, 7, 3, 8, 0, 0),
            paths=["local/library"],
        )
    ]
    with open_dict(config.zotero):
        config.zotero.source = "auto"
        config.zotero.user_id = ""
        config.zotero.api_key = ""
        config.zotero.local_sqlite_path = "C:/Users/WJH/Zotero/zotero.sqlite"

    monkeypatch.setattr("zotero_arxiv_daily.executor.fetch_local_zotero_corpus", lambda path: local_corpus)
    monkeypatch.setattr(
        "zotero_arxiv_daily.executor.zotero.Zotero",
        lambda *a, **kw: pytest.fail("API Zotero should not be used without credentials"),
    )

    executor = Executor.__new__(Executor)
    executor.config = config

    assert executor.fetch_zotero_corpus() == local_corpus


def test_fetch_zotero_corpus_auto_prefers_api_when_credentials_are_present(config, monkeypatch):
    from tests.canned_responses import make_stub_zotero_client
    from omegaconf import open_dict

    with open_dict(config.zotero):
        config.zotero.source = "auto"
        config.zotero.user_id = "123"
        config.zotero.api_key = "secret"

    monkeypatch.setattr(
        "zotero_arxiv_daily.executor.fetch_local_zotero_corpus",
        lambda path: pytest.fail("Local Zotero should not be used when API credentials exist"),
    )
    monkeypatch.setattr("zotero_arxiv_daily.executor.zotero.Zotero", lambda *a, **kw: make_stub_zotero_client())

    executor = Executor.__new__(Executor)
    executor.config = config

    assert [paper.title for paper in executor.fetch_zotero_corpus()] == ["Stub Paper 1", "Stub Paper 2"]


# ---------------------------------------------------------------------------
# E2E: Executor.run()
# ---------------------------------------------------------------------------


def test_run_writes_empty_funnel_when_zotero_corpus_is_empty(config, tmp_path):
    import json

    from omegaconf import open_dict

    funnel_path = tmp_path / "recommendation-funnel.json"
    with open_dict(config.executor):
        config.executor.recommendation_funnel_path = str(funnel_path)

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {}
    executor.fetch_zotero_corpus = lambda: []
    executor.filter_corpus = lambda corpus: corpus

    executor.run()

    report = json.loads(funnel_path.read_text(encoding="utf-8"))
    assert report["stage_totals"] == {"final": 0}


def test_run_records_pipeline_failure_in_funnel_and_reraises(config, tmp_path):
    import json

    from omegaconf import open_dict

    funnel_path = tmp_path / "recommendation-funnel.json"
    with open_dict(config.executor):
        config.executor.recommendation_funnel_path = str(funnel_path)

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.fetch_zotero_corpus = lambda: (_ for _ in ()).throw(RuntimeError("Zotero unavailable"))

    with pytest.raises(RuntimeError, match="Zotero unavailable"):
        executor.run()

    report = json.loads(funnel_path.read_text(encoding="utf-8"))
    assert report["failure"] == {
        "type": "RuntimeError",
        "message": "Zotero unavailable",
    }


def test_run_end_to_end(config, monkeypatch):
    """Full pipeline: Zotero fetch -> filter -> retrieve -> rerank -> TLDR -> email."""
    import smtplib

    from omegaconf import open_dict

    from tests.canned_responses import (
        make_sample_corpus,
        make_sample_paper,
        make_stub_openai_client,
        make_stub_smtp,
        make_stub_zotero_client,
    )

    # Config: source=["arxiv"], reranker="api", send_empty=false
    with open_dict(config):
        config.executor.source = ["arxiv"]
        config.executor.reranker = "api"
        config.executor.send_empty = False

    # 1. Stub pyzotero
    stub_zot = make_stub_zotero_client()
    monkeypatch.setattr("zotero_arxiv_daily.executor.zotero.Zotero", lambda *a, **kw: stub_zot)

    # 2. Stub OpenAI (for reranker + TLDR/affiliations)
    stub_client = make_stub_openai_client()
    monkeypatch.setattr("zotero_arxiv_daily.executor.OpenAI", lambda **kw: stub_client)
    monkeypatch.setattr("zotero_arxiv_daily.reranker.api.OpenAI", lambda **kw: stub_client)
    retrieved = [
        make_sample_paper(title="E2E Paper 1", score=None),
        make_sample_paper(title="E2E Paper 2", score=None),
    ]

    # Import to register the arxiv retriever
    import zotero_arxiv_daily.retriever.arxiv_retriever  # noqa: F401

    from zotero_arxiv_daily.retriever.base import registered_retrievers

    monkeypatch.setattr(
        registered_retrievers["arxiv"],
        "retrieve_papers",
        lambda self: retrieved,
    )

    # 4. Stub SMTP
    sent = []
    monkeypatch.setattr(smtplib, "SMTP", make_stub_smtp(sent))

    # 5. Stub sleep (reranker/retriever)
    monkeypatch.setattr("zotero_arxiv_daily.retriever.base.sleep", lambda _: None)

    # 6. Run
    executor = Executor(config)
    executor.run()

    # Assertions
    assert len(sent) == 1, "Email should have been sent"
    _, _, email_body = sent[0]
    assert "text/html" in email_body


def test_run_no_papers_send_empty_false(config, monkeypatch):
    """When no papers are found and send_empty=false, no email is sent."""
    import smtplib

    from omegaconf import open_dict

    from tests.canned_responses import make_stub_openai_client, make_stub_smtp, make_stub_zotero_client

    with open_dict(config):
        config.executor.source = ["arxiv"]
        config.executor.reranker = "api"
        config.executor.send_empty = False

    stub_zot = make_stub_zotero_client()
    monkeypatch.setattr("zotero_arxiv_daily.executor.zotero.Zotero", lambda *a, **kw: stub_zot)

    stub_client = make_stub_openai_client()
    monkeypatch.setattr("zotero_arxiv_daily.executor.OpenAI", lambda **kw: stub_client)
    monkeypatch.setattr("zotero_arxiv_daily.reranker.api.OpenAI", lambda **kw: stub_client)

    import zotero_arxiv_daily.retriever.arxiv_retriever  # noqa: F401

    from zotero_arxiv_daily.retriever.base import registered_retrievers

    monkeypatch.setattr(registered_retrievers["arxiv"], "retrieve_papers", lambda self: [])

    sent = []
    monkeypatch.setattr(smtplib, "SMTP", make_stub_smtp(sent))
    monkeypatch.setattr("zotero_arxiv_daily.retriever.base.sleep", lambda _: None)

    executor = Executor(config)
    executor.run()

    assert len(sent) == 0, "No email should be sent when no papers and send_empty=false"


def test_run_no_papers_send_empty_true(config, monkeypatch):
    """When no papers are found and send_empty=true, empty email is sent."""
    import smtplib

    from omegaconf import open_dict

    from tests.canned_responses import make_stub_openai_client, make_stub_smtp, make_stub_zotero_client

    with open_dict(config):
        config.executor.source = ["arxiv"]
        config.executor.reranker = "api"
        config.executor.send_empty = True

    stub_zot = make_stub_zotero_client()
    monkeypatch.setattr("zotero_arxiv_daily.executor.zotero.Zotero", lambda *a, **kw: stub_zot)

    stub_client = make_stub_openai_client()
    monkeypatch.setattr("zotero_arxiv_daily.executor.OpenAI", lambda **kw: stub_client)
    monkeypatch.setattr("zotero_arxiv_daily.reranker.api.OpenAI", lambda **kw: stub_client)

    import zotero_arxiv_daily.retriever.arxiv_retriever  # noqa: F401

    from zotero_arxiv_daily.retriever.base import registered_retrievers

    monkeypatch.setattr(registered_retrievers["arxiv"], "retrieve_papers", lambda self: [])

    sent = []
    monkeypatch.setattr(smtplib, "SMTP", make_stub_smtp(sent))
    monkeypatch.setattr("zotero_arxiv_daily.retriever.base.sleep", lambda _: None)

    executor = Executor(config)
    executor.run()

    assert len(sent) == 1, "Email should be sent even with no papers when send_empty=true"
    _, _, body = sent[0]
    assert "text/html" in body


def test_run_limits_rerank_candidates_and_summarizes_final_top_papers(config, monkeypatch):
    from omegaconf import open_dict

    from tests.canned_responses import make_sample_corpus, make_sample_paper
    from zotero_arxiv_daily.protocol import Paper

    with open_dict(config):
        config.executor.rerank_candidate_num = 50
        config.executor.max_paper_num = 20
        config.executor.send_empty = False

    all_candidates = [make_sample_paper(title=f"Paper {i}") for i in range(60)]
    seen_by_reranker = []
    summarized = []

    class StubRetriever:
        def retrieve_papers(self):
            return all_candidates

    class StubReranker:
        def rerank(self, papers, corpus):
            seen_by_reranker.extend(papers)
            for score, paper in enumerate(reversed(papers)):
                paper.score = float(score)
            return list(reversed(papers))

    def fake_tldr(self, openai_client, llm_params):
        summarized.append(self.title)
        self.tldr = "summary"
        return self.tldr

    monkeypatch.setattr(Paper, "generate_tldr", fake_tldr)
    monkeypatch.setattr(Paper, "generate_affiliations", lambda self, openai_client, llm_params: [])
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda config, email_content: None)

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {"arxiv": StubRetriever()}
    executor.reranker = StubReranker()
    executor.openai_client = object()
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(3)
    executor.filter_corpus = lambda corpus: corpus

    executor.run()

    assert len(seen_by_reranker) == 50
    assert [paper.title for paper in seen_by_reranker[:2]] == ["Paper 0", "Paper 1"]
    assert len(summarized) == 20
    assert summarized[0] == "Paper 49"
    assert summarized[-1] == "Paper 30"


def test_filter_recent_papers_keeps_only_shanghai_today_and_previous_day():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from tests.canned_responses import make_sample_paper
    from zotero_arxiv_daily.executor import filter_recent_papers

    now = datetime(2026, 8, 1, 5, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    papers = [
        make_sample_paper(title="Today", published_date="2026-08-01"),
        make_sample_paper(title="Yesterday", published_date="2026-07-31"),
        make_sample_paper(title="Too old", published_date="2026-07-30"),
        make_sample_paper(title="Future", published_date="2026-08-02"),
        make_sample_paper(title="Missing date", published_date=None),
    ]

    filtered = filter_recent_papers(papers, now=now)

    assert [paper.title for paper in filtered] == ["Today", "Yesterday"]


def test_run_includes_every_successful_deepseek_eight_plus_paper_after_top_limit(
    config, monkeypatch
):
    from omegaconf import open_dict

    from tests.canned_responses import make_sample_corpus, make_sample_paper
    from zotero_arxiv_daily.protocol import Paper

    with open_dict(config):
        config.executor.max_paper_num = 30
        config.executor.include_all_deepseek_score_at_least = 8.0
        config.executor.send_empty = False
        config.executor.feedback_path = None

    candidates = [make_sample_paper(title=f"Paper {i}", venue=None) for i in range(35)]
    candidates[30].deepseek_score = 8.0
    candidates[30].score_source = "deepseek"
    candidates[31].deepseek_score = 7.9
    candidates[31].score_source = "deepseek"
    candidates[32].deepseek_score = None
    candidates[32].score_source = "embedding_fallback"
    candidates[34].deepseek_score = 8.5
    candidates[34].score_source = "deepseek"
    summarized = []

    class StubRetriever:
        def retrieve_papers(self):
            return candidates

    class StubReranker:
        def rerank(self, papers, corpus):
            for index, paper in enumerate(papers):
                paper.score = float(len(papers) - index)
            return papers

    def fake_tldr(self, openai_client, llm_params):
        summarized.append(self.title)
        self.tldr = "summary"
        return self.tldr

    monkeypatch.setattr(Paper, "generate_tldr", fake_tldr)
    monkeypatch.setattr(Paper, "generate_affiliations", lambda self, client, params: [])
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda config, content: None)

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {"arxiv": StubRetriever()}
    executor.reranker = StubReranker()
    executor.openai_client = object()
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(3)
    executor.filter_corpus = lambda corpus: corpus

    executor.run()

    assert summarized == [
        *[f"Paper {index}" for index in range(30)],
        "Paper 30",
        "Paper 34",
    ]


def test_run_filters_recommendation_history_and_records_only_emailed_papers(config, tmp_path, monkeypatch):
    import json

    from omegaconf import open_dict

    from tests.canned_responses import make_sample_corpus, make_sample_paper
    from zotero_arxiv_daily.protocol import Paper
    from zotero_arxiv_daily.recommendation_history import RecommendationHistory

    history_path = tmp_path / "recommendation-history.json"
    funnel_path = tmp_path / "recommendation-funnel.json"
    already_sent = make_sample_paper(title="Already sent", doi="10.1000/already-sent")
    selected = make_sample_paper(title="Selected", doi="10.1000/selected")
    below_cutoff = make_sample_paper(title="Below cutoff", doi="10.1000/below-cutoff")
    RecommendationHistory(history_path).record([already_sent])
    with open_dict(config.executor):
        config.executor.recommendation_history_path = str(history_path)
        config.executor.recommendation_history_days = 60
        config.executor.recommendation_funnel_path = str(funnel_path)
        config.executor.max_paper_num = 1
        config.executor.feedback_path = None

    seen_by_reranker = []

    class StubRetriever:
        def retrieve_papers(self):
            return [already_sent, selected, below_cutoff]

    class StubReranker:
        def rerank(self, papers, corpus):
            seen_by_reranker.extend(papers)
            selected.score = 9.0
            selected.llm_selection_reason = "global"
            selected.llm_scoring_attempted = True
            selected.llm_scoring_succeeded = True
            selected.score_source = "deepseek"
            selected.deepseek_score = 8.0
            below_cutoff.score = 8.0
            below_cutoff.llm_selection_reason = "venue_reserve"
            below_cutoff.llm_scoring_attempted = True
            below_cutoff.llm_scoring_succeeded = False
            below_cutoff.score_source = "embedding_fallback"
            return [selected, below_cutoff]

    monkeypatch.setattr(Paper, "generate_tldr", lambda self, client, params: "summary")
    monkeypatch.setattr(Paper, "generate_affiliations", lambda self, client, params: [])
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda config, content: None)

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {"openalex": StubRetriever()}
    executor.reranker = StubReranker()
    executor.openai_client = object()
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(1)
    executor.filter_corpus = lambda corpus: corpus

    executor.run()

    assert seen_by_reranker == [selected, below_cutoff]
    persisted = RecommendationHistory(history_path)
    assert persisted.filter_unseen([selected]) == []
    assert persisted.filter_unseen([below_cutoff]) == [below_cutoff]
    report = json.loads(funnel_path.read_text(encoding="utf-8"))
    assert report["stage_totals"] == {
        "retrieved": 3,
        "date_filtered": 3,
        "unseen": 2,
        "rerank_candidates": 2,
        "semantic_ranked": 2,
        "llm_selected": 2,
        "llm_attempted": 2,
        "llm_scored": 1,
        "llm_fallback": 1,
        "venue_bonus_ranked": 2,
        "feedback_ranked": 2,
        "final": 1,
        "emailed": 1,
    }


def test_run_applies_feedback_profile_before_summarizing_top_papers(config, tmp_path, monkeypatch):
    import json

    from omegaconf import open_dict

    from tests.canned_responses import make_sample_corpus, make_sample_paper
    from zotero_arxiv_daily.protocol import Paper

    feedback_path = tmp_path / "feedback.json"
    feedback_path.write_text(
        json.dumps(
            {
                "positive_keywords": ["protein design"],
                "negative_keywords": ["clinical trial"],
            }
        ),
        encoding="utf-8",
    )
    with open_dict(config):
        config.executor.max_paper_num = 2
        config.executor.send_empty = False
        config.executor.feedback_path = str(feedback_path)

    disliked = make_sample_paper(
        title="Clinical trial dashboard",
        abstract="Clinical trial recruitment analytics.",
        score=None,
    )
    preferred = make_sample_paper(
        title="Protein design model",
        abstract="Protein design for enzymes.",
        score=None,
    )
    summarized = []

    class StubRetriever:
        def retrieve_papers(self):
            return [disliked, preferred]

    class StubReranker:
        def rerank(self, papers, corpus):
            disliked.score = 9.0
            preferred.score = 7.0
            return [disliked, preferred]

    def fake_tldr(self, openai_client, llm_params):
        summarized.append(self.title)
        self.tldr = "summary"
        return self.tldr

    monkeypatch.setattr(Paper, "generate_tldr", fake_tldr)
    monkeypatch.setattr(Paper, "generate_affiliations", lambda self, openai_client, llm_params: [])
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda config, email_content: None)

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {"arxiv": StubRetriever()}
    executor.reranker = StubReranker()
    executor.openai_client = object()
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(3)
    executor.filter_corpus = lambda corpus: corpus

    executor.run()

    assert summarized == ["Protein design model", "Clinical trial dashboard"]
    assert "反馈偏好" in preferred.recommendation_reason
    assert "负反馈" in disliked.recommendation_reason


def test_run_merges_github_issue_feedback_before_summarizing_top_papers(config, monkeypatch):
    from omegaconf import open_dict

    from tests.canned_responses import make_sample_corpus, make_sample_paper
    from zotero_arxiv_daily.feedback import FeedbackProfile
    from zotero_arxiv_daily.protocol import Paper

    with open_dict(config):
        config.executor.max_paper_num = 2
        config.executor.send_empty = False
        config.executor.feedback_github_repository = "Agitw/zotero-arxiv-daily"
        config.executor.feedback_github_token = "github-token"

    disliked = make_sample_paper(
        title="Clinical trial dashboard",
        url="https://journal.example.org/disliked",
        score=None,
    )
    preferred = make_sample_paper(
        title="Protein design model",
        url="https://journal.example.org/preferred",
        score=None,
    )
    summarized = []

    class StubRetriever:
        def retrieve_papers(self):
            return [disliked, preferred]

    class StubReranker:
        def rerank(self, papers, corpus):
            disliked.score = 9.0
            preferred.score = 7.0
            return [disliked, preferred]

    def fake_tldr(self, openai_client, llm_params):
        summarized.append(self.title)
        self.tldr = "summary"
        return self.tldr

    monkeypatch.setattr(Paper, "generate_tldr", fake_tldr)
    monkeypatch.setattr(Paper, "generate_affiliations", lambda self, openai_client, llm_params: [])
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda config, email_content: None)
    monkeypatch.setattr(
        "zotero_arxiv_daily.executor.fetch_github_issue_feedback",
        lambda repository, token: FeedbackProfile(
            paper_feedback={
                "https://journal.example.org/disliked": "not_interested",
                "https://journal.example.org/preferred": "important",
            }
        ),
    )

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {"arxiv": StubRetriever()}
    executor.reranker = StubReranker()
    executor.openai_client = object()
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(3)
    executor.filter_corpus = lambda corpus: corpus

    executor.run()

    assert summarized == ["Protein design model", "Clinical trial dashboard"]


def test_run_still_generates_tldr_when_reranker_disables_llm_scoring(config, monkeypatch):
    from omegaconf import open_dict

    from tests.canned_responses import make_sample_corpus, make_sample_paper
    from zotero_arxiv_daily.protocol import Paper

    with open_dict(config):
        config.llm.language = "English"
        config.executor.max_paper_num = 2
        config.executor.send_empty = False

    candidates = [
        make_sample_paper(
            title="Paper 1",
            abstract="Abstract 1",
            affiliations=["第一单位：Institute A"],
        ),
        make_sample_paper(title="Paper 2", abstract="Abstract 2"),
    ]

    class StubRetriever:
        def retrieve_papers(self):
            return candidates

    class LlmUnavailableReranker:
        llm_scoring_disabled = True

        def rerank(self, papers, corpus):
            for score, paper in enumerate(papers, start=1):
                paper.score = float(score)
            return papers

    def fake_tldr(self, openai_client, llm_params):
        self.tldr = self.abstract
        return self.tldr

    monkeypatch.setattr(Paper, "generate_tldr", fake_tldr)
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda config, email_content: None)

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {"arxiv": StubRetriever()}
    executor.reranker = LlmUnavailableReranker()
    executor.openai_client = object()
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(3)
    executor.filter_corpus = lambda corpus: corpus

    executor.run()

    assert [paper.tldr for paper in candidates] == ["Abstract 1", "Abstract 2"]
    assert [paper.affiliations for paper in candidates] == [["第一单位：Institute A"], None]


def test_run_uses_chinese_tldr_fallback_when_reranker_disables_llm_scoring(config, monkeypatch):
    from omegaconf import open_dict

    from tests.canned_responses import make_sample_corpus, make_sample_paper
    from zotero_arxiv_daily.protocol import Paper

    with open_dict(config):
        config.llm.language = "Chinese"
        config.executor.max_paper_num = 1
        config.executor.send_empty = False

    candidate = make_sample_paper(
        title="English Paper",
        abstract="Deep learning has outgrown any single mathematical explanation.",
    )

    class StubRetriever:
        def retrieve_papers(self):
            return [candidate]

    class LlmUnavailableReranker:
        llm_scoring_disabled = True

        def rerank(self, papers, corpus):
            papers[0].score = 8.0
            return papers

    def fake_tldr(self, openai_client, llm_params):
        self.tldr = "- 核心问题：预测冷启动蛋白质相互作用。\n- 方法模型：利用多模态知识图谱学习蛋白质表示。"
        return self.tldr

    monkeypatch.setattr(Paper, "generate_tldr", fake_tldr)
    monkeypatch.setattr("zotero_arxiv_daily.executor.send_email", lambda config, email_content: None)

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {"arxiv": StubRetriever()}
    executor.reranker = LlmUnavailableReranker()
    executor.openai_client = object()
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(3)
    executor.filter_corpus = lambda corpus: corpus

    executor.run()

    assert "核心问题" in candidate.tldr
    assert "预测冷启动蛋白质相互作用" in candidate.tldr
    assert "Deep learning has outgrown" not in candidate.tldr
    assert candidate.affiliations is None


def test_run_can_write_email_preview_and_skip_smtp(config, tmp_path, monkeypatch):
    from omegaconf import open_dict

    from tests.canned_responses import make_sample_corpus, make_sample_paper

    preview_path = tmp_path / "preview.html"
    with open_dict(config):
        config.executor.max_paper_num = 1
        config.executor.skip_email = True
        config.executor.email_preview_path = str(preview_path)

    candidate = make_sample_paper(title="Preview Paper", abstract="Preview abstract")

    class StubRetriever:
        def retrieve_papers(self):
            return [candidate]

    class StubReranker:
        def rerank(self, papers, corpus):
            papers[0].score = 9.0
            return papers

    monkeypatch.setattr(
        "zotero_arxiv_daily.executor.send_email",
        lambda config, email_content: pytest.fail("SMTP should be skipped"),
    )

    executor = Executor.__new__(Executor)
    executor.config = config
    executor.retrievers = {"arxiv": StubRetriever()}
    executor.reranker = StubReranker()
    executor.openai_client = object()
    executor.fetch_zotero_corpus = lambda: make_sample_corpus(3)
    executor.filter_corpus = lambda corpus: corpus

    executor.run()

    assert preview_path.exists()
    assert "Preview Paper" in preview_path.read_text(encoding="utf-8")
