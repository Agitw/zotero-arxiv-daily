"""Structured observability for the recommendation pipeline."""

from datetime import UTC, datetime
import json
from pathlib import Path

from loguru import logger

from .protocol import Paper
from .recommendation_history import paper_identity


class RecommendationFunnel:
    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        self.generated_at = datetime.now(UTC).isoformat()
        self.stage_totals: dict[str, int] = {}
        self.venues: dict[str, dict] = {}
        self._papers: dict[str, dict] = {}
        self.failure: dict[str, str] | None = None
        self.llm_batches: list[dict] = []
        self.sources: dict[str, dict] = {}
        self.llm_usage: dict[str, int] = {
            "batch_count": 0,
            "successful_batches": 0,
            "fallback_batches": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def observe(self, stage: str, papers: list[Paper]) -> None:
        self.stage_totals[stage] = len(papers)
        venue_counts: dict[str, int] = {}
        for rank, paper in enumerate(papers, start=1):
            venue_key = self._venue_key(paper)
            venue_counts[venue_key] = venue_counts.get(venue_key, 0) + 1
            venue = self.venues.setdefault(
                venue_key,
                {
                    "venue": paper.venue,
                    "issns": list(paper.venue_issns or []),
                    "source": paper.source,
                    "stages": {},
                },
            )
            venue["stages"][stage] = venue["stages"].get(stage, 0) + 1

            paper_key = paper_identity(paper)
            tracked = self._papers.setdefault(
                paper_key,
                {
                    "key": paper_key,
                    "title": paper.title,
                    "source": paper.source,
                    "venue": paper.venue,
                    "venue_issns": list(paper.venue_issns or []),
                    "llm_selection_reason": paper.llm_selection_reason,
                    "embedding_score": paper.embedding_score,
                    "deepseek_score": paper.deepseek_score,
                    "score_source": paper.score_source,
                    "llm_scoring_attempted": paper.llm_scoring_attempted,
                    "llm_scoring_succeeded": paper.llm_scoring_succeeded,
                    "venue_bonus": paper.venue_bonus,
                    "stages": {},
                },
            )
            tracked["llm_selection_reason"] = paper.llm_selection_reason
            tracked["embedding_score"] = paper.embedding_score
            tracked["deepseek_score"] = paper.deepseek_score
            tracked["score_source"] = paper.score_source
            tracked["llm_scoring_attempted"] = paper.llm_scoring_attempted
            tracked["llm_scoring_succeeded"] = paper.llm_scoring_succeeded
            tracked["venue_bonus"] = paper.venue_bonus
            tracked["stages"][stage] = {
                "rank": rank,
                "score": float(paper.score) if paper.score is not None else None,
            }

        logger.info(
            f"Recommendation funnel {stage}: {len(papers)} papers across {len(venue_counts)} venues"
        )
        self.write()

    def record_failure(self, error: Exception) -> None:
        self.failure = {
            "type": type(error).__name__,
            "message": str(error),
        }
        logger.error(f"Recommendation pipeline failed: {type(error).__name__}: {error}")
        self.write()

    def record_source(
        self,
        source: str,
        count: int,
        *,
        error: Exception | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        result = {
            "status": "failed" if error else ("degraded" if warnings else "success"),
            "paper_count": count,
            "warnings": list(warnings or []),
        }
        if error is not None:
            result["error"] = {"type": type(error).__name__, "message": str(error)}
        self.sources[source] = result
        self.write()

    def record_llm_batches(self, batches: list[dict]) -> None:
        self.llm_batches = [dict(batch) for batch in batches]
        self.llm_usage = {
            "batch_count": len(batches),
            "successful_batches": sum(batch.get("status") == "success" for batch in batches),
            "fallback_batches": sum(batch.get("status") == "fallback" for batch in batches),
            "prompt_tokens": sum(int(batch.get("prompt_tokens") or 0) for batch in batches),
            "completion_tokens": sum(int(batch.get("completion_tokens") or 0) for batch in batches),
            "total_tokens": sum(int(batch.get("total_tokens") or 0) for batch in batches),
        }
        self.write()

    def as_dict(self) -> dict:
        report = {
            "generated_at": self.generated_at,
            "stage_totals": self.stage_totals,
            "venues": self.venues,
            "papers": list(self._papers.values()),
            "llm_batches": self.llm_batches,
            "llm_usage": self.llm_usage,
            "sources": self.sources,
        }
        if self.failure is not None:
            report["failure"] = self.failure
        return report

    def write(self) -> bool:
        if self.path is None:
            return False
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(self.as_dict(), ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        except OSError as exc:
            logger.warning(f"Could not save recommendation funnel to {self.path}: {exc}")
            return False
        return True

    @staticmethod
    def _venue_key(paper: Paper) -> str:
        if paper.venue_issns:
            return f"issn:{paper.venue_issns[0].strip().upper()}"
        if paper.venue:
            return f"venue:{paper.venue.strip().casefold()}"
        return f"source:{paper.source.strip().casefold()}"
