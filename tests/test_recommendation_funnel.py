"""Tests for the structured recommendation funnel report."""

import json

from tests.canned_responses import make_sample_paper
from zotero_arxiv_daily.recommendation_funnel import RecommendationFunnel


def test_funnel_report_tracks_venue_counts_selection_reason_and_rank_changes(tmp_path):
    report_path = tmp_path / "recommendation-funnel.json"
    paper = make_sample_paper(
        title="High-impact candidate",
        venue="Nature Machine Intelligence",
        venue_issns=["2522-5839"],
        doi="10.1000/high-impact",
        score=6.4,
        llm_selection_reason="venue_reserve",
        embedding_score=6.0,
        deepseek_score=6.6,
        score_source="deepseek",
        llm_scoring_attempted=True,
        llm_scoring_succeeded=True,
    )
    funnel = RecommendationFunnel(report_path)

    funnel.observe("semantic_ranked", [paper])
    funnel.record_llm_batches(
        [
            {
                "status": "success",
                "candidate_count": 1,
                "duration_seconds": 0.25,
                "prompt_tokens": 1200,
                "completion_tokens": 42,
                "total_tokens": 1242,
            }
        ]
    )
    paper.score = 9.6
    funnel.observe("venue_bonus_ranked", [paper])

    report = json.loads(report_path.read_text(encoding="utf-8"))
    venue = report["venues"]["issn:2522-5839"]
    tracked_paper = report["papers"][0]
    assert report["stage_totals"] == {"semantic_ranked": 1, "venue_bonus_ranked": 1}
    assert venue["stages"] == {"semantic_ranked": 1, "venue_bonus_ranked": 1}
    assert tracked_paper["llm_selection_reason"] == "venue_reserve"
    assert tracked_paper["embedding_score"] == 6.0
    assert tracked_paper["deepseek_score"] == 6.6
    assert tracked_paper["score_source"] == "deepseek"
    assert tracked_paper["llm_scoring_attempted"] is True
    assert tracked_paper["llm_scoring_succeeded"] is True
    assert tracked_paper["stages"]["semantic_ranked"] == {"rank": 1, "score": 6.4}
    assert tracked_paper["stages"]["venue_bonus_ranked"] == {"rank": 1, "score": 9.6}
    assert report["llm_batches"][0]["total_tokens"] == 1242
    assert report["llm_usage"] == {
        "batch_count": 1,
        "completion_tokens": 42,
        "fallback_batches": 0,
        "prompt_tokens": 1200,
        "successful_batches": 1,
        "total_tokens": 1242,
    }
