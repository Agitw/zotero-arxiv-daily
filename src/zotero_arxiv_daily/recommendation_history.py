"""Durable identities for papers that were successfully recommended."""

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path

from loguru import logger

from .protocol import Paper


def paper_identity(paper: Paper) -> str:
    if paper.doi:
        doi = paper.doi.strip().casefold()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if doi.startswith(prefix):
                doi = doi[len(prefix) :]
                break
        if doi:
            return f"doi:{doi}"
    if paper.external_id:
        return f"external:{paper.external_id.strip().casefold()}"
    if paper.url:
        return f"url:{paper.url.strip().rstrip('/').casefold()}"
    normalized_title = " ".join(paper.title.split()).casefold()
    digest = hashlib.sha256(normalized_title.encode("utf-8")).hexdigest()
    return f"title:{digest}"


class RecommendationHistory:
    def __init__(
        self,
        path: str | Path,
        retention_days: int = 60,
        now: datetime | None = None,
    ):
        self.path = Path(path)
        self.retention_days = max(0, int(retention_days))
        self.now = now or datetime.now(UTC)
        if self.now.tzinfo is None:
            self.now = self.now.replace(tzinfo=UTC)
        self.entries = self._load_entries()

    def filter_unseen(self, papers: list[Paper]) -> list[Paper]:
        active_entries = self._active_entries()
        return [paper for paper in papers if self.paper_key(paper) not in active_entries]

    def record(self, papers: list[Paper]) -> bool:
        entries = self._active_entries()
        recorded_at = self.now.astimezone(UTC).isoformat()
        for paper in papers:
            entries[self.paper_key(paper)] = recorded_at
        payload = {"version": 1, "papers": entries}
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        except OSError as exc:
            logger.warning(f"Could not save recommendation history to {self.path}: {exc}")
            return False
        self.entries = entries
        return True

    @staticmethod
    def paper_key(paper: Paper) -> str:
        return paper_identity(paper)

    def _load_entries(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            papers = payload.get("papers", {})
            if not isinstance(papers, dict):
                raise TypeError("papers must be an object")
            return {str(key): str(value) for key, value in papers.items()}
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.warning(f"Could not load recommendation history from {self.path}: {exc}")
            return {}

    def _active_entries(self) -> dict[str, str]:
        cutoff = self.now - timedelta(days=self.retention_days)
        active = {}
        for key, value in self.entries.items():
            try:
                recorded_at = datetime.fromisoformat(value)
                if recorded_at.tzinfo is None:
                    recorded_at = recorded_at.replace(tzinfo=UTC)
            except ValueError:
                continue
            if recorded_at >= cutoff:
                active[key] = value
        return active
