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
    )
    funnel = RecommendationFunnel(report_path)

    funnel.observe("semantic_ranked", [paper])
    paper.score = 9.6
    funnel.observe("weighted_ranked", [paper])

    report = json.loads(report_path.read_text(encoding="utf-8"))
    venue = report["venues"]["issn:2522-5839"]
    tracked_paper = report["papers"][0]
    assert report["stage_totals"] == {"semantic_ranked": 1, "weighted_ranked": 1}
    assert venue["stages"] == {"semantic_ranked": 1, "weighted_ranked": 1}
    assert tracked_paper["llm_selection_reason"] == "venue_reserve"
    assert tracked_paper["stages"]["semantic_ranked"] == {"rank": 1, "score": 6.4}
    assert tracked_paper["stages"]["weighted_ranked"] == {"rank": 1, "score": 9.6}
