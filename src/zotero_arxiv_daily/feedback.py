from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any

from loguru import logger

from .protocol import Paper


@dataclass
class FeedbackProfile:
    paper_feedback: dict[str, str] = field(default_factory=dict)
    positive_keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    preferred_venues: list[str] = field(default_factory=list)
    blocked_venues: list[str] = field(default_factory=list)


def load_feedback_profile(path: str | Path | None) -> FeedbackProfile:
    if not path:
        return FeedbackProfile()
    feedback_path = Path(path)
    if not feedback_path.exists():
        logger.info(f"Feedback profile not found at {feedback_path}; continuing without feedback")
        return FeedbackProfile()
    data = json.loads(feedback_path.read_text(encoding="utf-8"))
    return FeedbackProfile(
        paper_feedback=_string_dict(data.get("paper_feedback")),
        positive_keywords=_string_list(data.get("positive_keywords")),
        negative_keywords=_string_list(data.get("negative_keywords")),
        preferred_venues=_string_list(data.get("preferred_venues")),
        blocked_venues=_string_list(data.get("blocked_venues")),
    )


def apply_feedback(papers: list[Paper], feedback: FeedbackProfile | dict[str, Any] | None) -> list[Paper]:
    profile = _coerce_profile(feedback)
    adjusted = False
    for paper in papers:
        adjustment, reasons = _score_adjustment(paper, profile)
        if adjustment:
            adjusted = True
            paper.score = max(0.0, (paper.score or 0.0) + adjustment)
        if reasons:
            paper.recommendation_reason = _append_reason(paper.recommendation_reason, "；".join(reasons))
    if not adjusted:
        return papers
    return sorted(papers, key=lambda paper: paper.score or 0.0, reverse=True)


def _score_adjustment(paper: Paper, profile: FeedbackProfile) -> tuple[float, list[str]]:
    adjustment = 0.0
    reasons = []
    explicit_feedback = profile.paper_feedback.get(paper.url) or (
        profile.paper_feedback.get(paper.pdf_url) if paper.pdf_url else None
    )
    if explicit_feedback:
        normalized = explicit_feedback.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in {"important", "like", "liked", "save"}:
            adjustment += 3.0
            reasons.append("根据反馈显式标记为重要")
        elif normalized in {"not_interested", "dislike", "blocked", "hide"}:
            adjustment -= 5.0
            reasons.append("根据反馈显式标记为不感兴趣")
        elif normalized in {"read", "seen"}:
            adjustment -= 1.0
            reasons.append("根据反馈标记为已读，降低重复推送优先级")

    text = f"{paper.title}\n{paper.abstract}".lower()
    positive_hits = _matching_terms(text, profile.positive_keywords)
    if positive_hits:
        adjustment += min(2.5, 1.2 * len(positive_hits))
        reasons.append(f"命中反馈偏好关键词：{', '.join(positive_hits[:3])}")

    negative_hits = _matching_terms(text, profile.negative_keywords)
    if negative_hits:
        adjustment -= min(3.5, 1.5 * len(negative_hits))
        reasons.append(f"命中负反馈关键词：{', '.join(negative_hits[:3])}")

    venue = (paper.venue or "").lower()
    preferred_venue_hits = _matching_terms(venue, profile.preferred_venues)
    if preferred_venue_hits:
        adjustment += 1.0
        reasons.append(f"来自偏好期刊：{preferred_venue_hits[0]}")

    blocked_venue_hits = _matching_terms(venue, profile.blocked_venues)
    if blocked_venue_hits:
        adjustment -= 4.0
        reasons.append(f"来自负反馈期刊：{blocked_venue_hits[0]}")

    return adjustment, reasons


def _matching_terms(text: str, terms: list[str]) -> list[str]:
    matches = []
    for term in terms:
        needle = term.strip().lower()
        if needle and re.search(re.escape(needle), text):
            matches.append(term)
    return matches


def _append_reason(existing: str | None, addition: str) -> str:
    if not existing:
        return addition
    return f"{existing}；{addition}"


def _coerce_profile(feedback: FeedbackProfile | dict[str, Any] | None) -> FeedbackProfile:
    if feedback is None:
        return FeedbackProfile()
    if isinstance(feedback, FeedbackProfile):
        return feedback
    return FeedbackProfile(
        paper_feedback=_string_dict(feedback.get("paper_feedback")),
        positive_keywords=_string_list(feedback.get("positive_keywords")),
        negative_keywords=_string_list(feedback.get("negative_keywords")),
        preferred_venues=_string_list(feedback.get("preferred_venues")),
        blocked_venues=_string_list(feedback.get("blocked_venues")),
    )


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("feedback list fields must be lists")
    return [str(item) for item in value if str(item).strip()]


def _string_dict(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("paper_feedback must be an object")
    return {str(key): str(item) for key, item in value.items()}
