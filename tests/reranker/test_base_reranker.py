"""Tests for BaseReranker: scoring, sorting, time decay, unknown reranker."""

import numpy as np
import pytest

from zotero_arxiv_daily.reranker.base import BaseReranker, apply_venue_bonuses, get_reranker_cls
from tests.canned_responses import make_sample_paper, make_sample_corpus


class StubReranker(BaseReranker):
    """Reranker with a controlled similarity matrix for deterministic tests."""

    def __init__(self, sim_matrix: np.ndarray):
        self.config = None
        self._sim = sim_matrix

    def get_similarity_score(self, s1, s2):
        return self._sim


def test_rerank_scores_and_sorts():
    corpus = make_sample_corpus(3)
    papers = [make_sample_paper(title=f"Paper {i}") for i in range(2)]

    # Paper 1 has higher similarity to all corpus papers
    sim = np.array([
        [0.1, 0.1, 0.1],  # paper 0 — low
        [0.9, 0.9, 0.9],  # paper 1 — high
    ])
    reranker = StubReranker(sim)
    ranked = reranker.rerank(papers, corpus)
    assert ranked[0].title == "Paper 1"
    assert ranked[1].title == "Paper 0"
    assert ranked[0].score > ranked[1].score


def test_rerank_time_decay_weighting():
    corpus = make_sample_corpus(3)
    papers = [make_sample_paper(title="P")]

    # Only similar to the oldest paper (index 2 after reverse-sort by date)
    sim = np.array([[0.0, 0.0, 1.0]])
    reranker = StubReranker(sim)
    ranked_old = reranker.rerank(papers, corpus)
    score_old = ranked_old[0].score

    # Only similar to the newest paper (index 0 after reverse-sort by date)
    papers2 = [make_sample_paper(title="P")]
    sim2 = np.array([[1.0, 0.0, 0.0]])
    reranker2 = StubReranker(sim2)
    ranked_new = reranker2.rerank(papers2, corpus)
    score_new = ranked_new[0].score

    # Newest corpus paper gets higher time-decay weight, so score should be higher
    assert score_new > score_old


def test_rerank_single_candidate_single_corpus():
    corpus = make_sample_corpus(1)
    papers = [make_sample_paper()]
    sim = np.array([[0.5]])
    reranker = StubReranker(sim)
    ranked = reranker.rerank(papers, corpus)
    assert len(ranked) == 1
    assert ranked[0].score is not None


def test_get_reranker_cls_unknown():
    with pytest.raises(ValueError, match="not found"):
        get_reranker_cls("nonexistent_reranker_xyz")


def test_apply_venue_bonuses_requires_successful_relevant_deepseek_score_and_resorts():
    ordinary = make_sample_paper(title="Ordinary", venue="Ordinary Journal", score=7.5)
    high_impact = make_sample_paper(
        title="High impact",
        venue="Nature Machine Intelligence",
        score=7.0,
        deepseek_score=6.0,
        score_source="deepseek",
    )

    ranked = apply_venue_bonuses(
        [ordinary, high_impact],
        {"Nature Machine Intelligence": 0.8},
    )

    assert ranked == [high_impact, ordinary]
    assert high_impact.score == pytest.approx(7.8)
    assert ordinary.score == 7.5
    assert "Nature Machine Intelligence +0.80" in high_impact.recommendation_reason


def test_apply_venue_bonuses_rejects_low_scoring_or_fallback_papers():
    low_relevance = make_sample_paper(
        title="Low relevance",
        venue="Nature Machine Intelligence",
        score=7.0,
        deepseek_score=5.9,
        score_source="deepseek",
    )
    fallback = make_sample_paper(
        title="Fallback",
        venue="Nature Machine Intelligence",
        score=8.0,
        deepseek_score=None,
        score_source="embedding_fallback",
    )

    ranked = apply_venue_bonuses(
        [fallback, low_relevance],
        {"Nature Machine Intelligence": 0.8},
    )

    assert ranked == [fallback, low_relevance]
    assert low_relevance.score == 7.0
    assert fallback.score == 8.0


def test_apply_venue_bonuses_prefers_issn_over_journal_name_fallback():
    paper = make_sample_paper(
        venue="Publisher display name",
        venue_issns=["2522-5839"],
        score=4.0,
        deepseek_score=8.0,
        score_source="deepseek",
    )

    apply_venue_bonuses(
        [paper],
        {
            "2522-5839": 0.8,
            "Publisher display name": 0.3,
        },
    )

    assert paper.score == pytest.approx(4.8)
    assert "Publisher display name +0.80" in paper.recommendation_reason


def test_apply_venue_bonuses_can_lower_peripheral_journal_priority():
    peripheral = make_sample_paper(
        title="Peripheral",
        venue="BMC Genomics",
        venue_issns=["1471-2164"],
        score=8.0,
        score_source="embedding_fallback",
    )
    core = make_sample_paper(title="Core", score=7.8)

    ranked = apply_venue_bonuses([peripheral, core], {"1471-2164": -0.3})

    assert ranked == [core, peripheral]
    assert peripheral.score == pytest.approx(7.7)
    assert peripheral.venue_bonus == pytest.approx(-0.3)
