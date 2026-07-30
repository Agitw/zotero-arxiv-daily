"""Tests for durable recommendation history."""

from datetime import UTC, datetime, timedelta

from tests.canned_responses import make_sample_paper
from zotero_arxiv_daily.recommendation_history import RecommendationHistory


def test_recorded_papers_are_filtered_after_reload_until_retention_expires(tmp_path):
    history_path = tmp_path / "recommendation-history.json"
    sent_at = datetime(2026, 7, 30, tzinfo=UTC)
    paper = make_sample_paper(
        url="https://publisher.example/paper",
        doi="https://doi.org/10.1000/EXAMPLE",
    )

    RecommendationHistory(history_path, retention_days=60, now=sent_at).record([paper])

    active = RecommendationHistory(
        history_path,
        retention_days=60,
        now=sent_at + timedelta(days=59),
    )
    expired = RecommendationHistory(
        history_path,
        retention_days=60,
        now=sent_at + timedelta(days=61),
    )

    assert active.filter_unseen([paper]) == []
    assert expired.filter_unseen([paper]) == [paper]
