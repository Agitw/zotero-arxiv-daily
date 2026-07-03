"""Tests for feedback-based recommendation adjustments."""

import json

from tests.canned_responses import make_sample_paper
from zotero_arxiv_daily.feedback import apply_feedback, load_feedback_profile


def test_load_feedback_profile_returns_empty_profile_when_path_is_missing(tmp_path):
    profile = load_feedback_profile(tmp_path / "missing.json")

    assert profile.paper_feedback == {}
    assert profile.positive_keywords == []
    assert profile.negative_keywords == []


def test_apply_feedback_boosts_preferred_topics_and_penalizes_disliked_topics():
    protein = make_sample_paper(
        title="Protein design with diffusion models",
        abstract="A model for enzyme engineering.",
        score=7.0,
    )
    clinical = make_sample_paper(
        title="Clinical trial recruitment dashboard",
        abstract="Hospital workflow analytics.",
        score=8.0,
    )

    ranked = apply_feedback(
        [clinical, protein],
        {
            "positive_keywords": ["protein design", "enzyme"],
            "negative_keywords": ["clinical trial"],
        },
    )

    assert ranked[0] == protein
    assert protein.score > 8.0
    assert clinical.score < 8.0
    assert "反馈偏好" in protein.recommendation_reason
    assert "负反馈" in clinical.recommendation_reason


def test_apply_feedback_uses_explicit_paper_feedback_by_url():
    important = make_sample_paper(
        title="Important paper",
        url="https://journal.example.org/important",
        score=6.0,
    )
    ignored = make_sample_paper(
        title="Ignored paper",
        url="https://journal.example.org/ignored",
        score=9.0,
    )

    ranked = apply_feedback(
        [ignored, important],
        {
            "paper_feedback": {
                "https://journal.example.org/important": "important",
                "https://journal.example.org/ignored": "not_interested",
            }
        },
    )

    assert ranked == [important, ignored]
    assert "显式标记为重要" in important.recommendation_reason
    assert "显式标记为不感兴趣" in ignored.recommendation_reason


def test_load_feedback_profile_reads_json_file(tmp_path):
    path = tmp_path / "feedback.json"
    path.write_text(
        json.dumps(
            {
                "positive_keywords": ["protein design"],
                "paper_feedback": {"https://example.org/a": "read"},
            }
        ),
        encoding="utf-8",
    )

    profile = load_feedback_profile(path)

    assert profile.positive_keywords == ["protein design"]
    assert profile.paper_feedback == {"https://example.org/a": "read"}
