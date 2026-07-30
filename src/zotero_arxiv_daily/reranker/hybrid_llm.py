import hashlib
import json
import time
from pathlib import Path

import numpy as np
from loguru import logger
from openai import OpenAI
from omegaconf import OmegaConf

from .base import BaseReranker, get_venue_weight, register_reranker
from .llm import _as_plain_dict, _extract_scores
from ..protocol import CorpusPaper, Paper


class LocalEmbeddingClient:
    def __init__(self, model: str, encode_kwargs: dict):
        from sentence_transformers import SentenceTransformer

        self.encoder = SentenceTransformer(model, trust_remote_code=True)
        self.encode_kwargs = encode_kwargs

    def encode(self, texts: list[str]) -> list[list[float]]:
        try:
            return self.encoder.encode(texts, **self.encode_kwargs, show_progress_bar=True).tolist()
        except TypeError as exc:
            if "unexpected keyword argument 'task'" not in str(exc):
                raise
            fallback_kwargs = dict(self.encode_kwargs)
            fallback_kwargs.pop("task", None)
            return self.encoder.encode(texts, **fallback_kwargs, show_progress_bar=True).tolist()


@register_reranker("hybrid_llm")
class HybridLlmReranker(BaseReranker):
    def __init__(self, config):
        super().__init__(config)
        self.hybrid_config = config.reranker.get("hybrid_llm", {})
        self.client = None
        self.embedding_client = self._make_embedding_client()
        self.llm_scoring_disabled = False

    @staticmethod
    def corpus_key(paper: CorpusPaper) -> str:
        payload = "\n".join(
            [
                paper.title,
                paper.abstract,
                paper.added_date.isoformat(),
                *paper.paths,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def rerank(self, candidates: list[Paper], corpus: list[CorpusPaper]) -> list[Paper]:
        corpus = sorted(corpus, key=lambda paper: paper.added_date, reverse=True)
        corpus_embeddings = self.prepare_corpus_embeddings(corpus)
        candidate_embeddings = np.array(self.embedding_client.encode([paper.abstract for paper in candidates]))
        corpus_embedding_array = np.array(corpus_embeddings)
        sim = self._cosine_similarity(candidate_embeddings, corpus_embedding_array)
        evidence_per_candidate = int(self.hybrid_config.get("evidence_per_candidate") or 20)
        evidence_indices_by_candidate = [
            np.argsort(sim[candidate_idx])[::-1][:evidence_per_candidate]
            for candidate_idx in range(len(candidates))
        ]
        embedding_scores = [
            float(np.clip(np.mean(sim[candidate_idx][evidence_indices]), 0.0, 1.0))
            for candidate_idx, evidence_indices in enumerate(evidence_indices_by_candidate)
        ]
        for candidate_idx, (paper, score) in enumerate(zip(candidates, embedding_scores)):
            paper.score = score * 10
            evidence = [corpus[idx] for idx in evidence_indices_by_candidate[candidate_idx]]
            paper.matched_zotero_titles = [item.title for item in evidence[:3] if item.title]
            paper.recommendation_reason = self._build_recommendation_reason(
                paper.matched_zotero_titles,
                score,
            )

        llm_candidate_indices = self.select_llm_candidate_indices(candidates, embedding_scores)
        if len(llm_candidate_indices) < len(candidates):
            logger.info(
                f"DeepSeek scoring limited to top {len(llm_candidate_indices)} "
                f"of {len(candidates)} embedding-ranked candidates"
            )

        candidate_batch_size = int(self.hybrid_config.get("candidate_batch_size") or 5)
        for start in range(0, len(llm_candidate_indices), candidate_batch_size):
            batch_indices = llm_candidate_indices[start : start + candidate_batch_size]
            batch = [candidates[idx] for idx in batch_indices]
            batch_evidence = []
            batch_embedding_scores = []
            for candidate_idx in batch_indices:
                evidence_indices = evidence_indices_by_candidate[candidate_idx]
                batch_evidence.append([corpus[idx] for idx in evidence_indices])
                batch_embedding_scores.append(embedding_scores[candidate_idx])
            if self.llm_scoring_disabled:
                scores = batch_embedding_scores
            else:
                try:
                    scores = self._score_candidate_batch(batch, batch_evidence)
                except Exception as exc:
                    if not self._is_recoverable_llm_scoring_error(exc):
                        raise
                    self.llm_scoring_disabled = True
                    logger.warning(
                        f"DeepSeek scoring failed; using embedding scores for this run: {exc}"
                    )
                    scores = batch_embedding_scores
            for paper, score in zip(batch, scores):
                paper.score = score * 10
        return sorted(candidates, key=lambda paper: paper.score or 0.0, reverse=True)

    def select_llm_candidate_indices(
        self,
        candidates: list[Paper],
        embedding_scores: list[float],
    ) -> list[int]:
        for paper in candidates:
            paper.llm_selection_reason = None
        llm_candidate_num = self.hybrid_config.get("llm_candidate_num")
        if llm_candidate_num is None:
            selected = list(range(len(embedding_scores)))
            for idx in selected:
                candidates[idx].llm_selection_reason = "global"
            return selected
        limit = max(0, int(llm_candidate_num))
        ranked = sorted(
            range(len(embedding_scores)),
            key=lambda idx: (-embedding_scores[idx], idx),
        )
        if limit >= len(ranked):
            for idx in ranked:
                candidates[idx].llm_selection_reason = "global"
            return ranked

        global_config = self.hybrid_config.get("llm_global_candidate_num")
        global_limit = limit if global_config is None else min(limit, max(0, int(global_config)))
        reserve_limit = max(0, int(self.hybrid_config.get("llm_high_impact_candidate_num") or 0))
        minimum_score = float(self.hybrid_config.get("llm_high_impact_min_score") or 0.0)
        venue_weights = self.config.reranker.get("venue_weights")

        selected = ranked[:global_limit]
        selected_set = set(selected)
        for idx in selected:
            candidates[idx].llm_selection_reason = "global"

        reserve_candidates = [
            idx
            for idx in ranked
            if idx not in selected_set
            and np.isfinite(embedding_scores[idx])
            and embedding_scores[idx] >= minimum_score
            and get_venue_weight(candidates[idx], venue_weights) > 1.0
        ][:reserve_limit]
        for idx in reserve_candidates:
            selected.append(idx)
            selected_set.add(idx)
            candidates[idx].llm_selection_reason = "venue_reserve"

        for idx in ranked:
            if len(selected) >= limit:
                break
            if idx in selected_set:
                continue
            selected.append(idx)
            selected_set.add(idx)
            candidates[idx].llm_selection_reason = "global_fill"

        return sorted(selected, key=lambda idx: (-embedding_scores[idx], idx))

    def get_similarity_score(self, s1: list[str], s2: list[str]) -> np.ndarray:
        s1_embeddings = np.array(self.embedding_client.encode(s1))
        s2_embeddings = np.array(self.embedding_client.encode(s2))
        return self._cosine_similarity(s1_embeddings, s2_embeddings)

    def _make_embedding_client(self):
        encode_kwargs = _as_plain_dict(self.hybrid_config.get("encode_kwargs"))
        return LocalEmbeddingClient(self.hybrid_config.embedding_model, encode_kwargs)

    def prepare_corpus_embeddings(self, corpus: list[CorpusPaper]) -> list[list[float]]:
        corpus = sorted(corpus, key=lambda paper: paper.added_date, reverse=True)
        return self._load_or_build_corpus_embeddings(corpus)

    def _load_or_build_corpus_embeddings(self, corpus: list[CorpusPaper]) -> list[list[float]]:
        cache_path = Path(str(self.hybrid_config.cache_path))
        expected_keys = [self.corpus_key(paper) for paper in corpus]
        embeddings_by_key = {}
        if cache_path.exists():
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            if cache.get("model") == self.hybrid_config.embedding_model:
                entries = cache.get("entries", [])
                embeddings_by_key = {entry["key"]: entry["embedding"] for entry in entries}
                if all(key in embeddings_by_key for key in expected_keys):
                    return [embeddings_by_key[key] for key in expected_keys]

        missing = [
            (key, paper)
            for key, paper in zip(expected_keys, corpus)
            if key not in embeddings_by_key
        ]
        batch_size = int(self.hybrid_config.get("cache_build_batch_size") or 128)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        for start in range(0, len(missing), batch_size):
            batch = missing[start : start + batch_size]
            logger.info(
                f"Encoding Zotero corpus embeddings {start + 1}-{start + len(batch)} of {len(missing)} missing papers"
            )
            embeddings = self.embedding_client.encode([paper.abstract for _, paper in batch])
            for (key, _), embedding in zip(batch, embeddings):
                embeddings_by_key[key] = embedding
            self._write_corpus_cache(cache_path, expected_keys, embeddings_by_key)
        return [embeddings_by_key[key] for key in expected_keys]

    def _write_corpus_cache(self, cache_path: Path, expected_keys: list[str], embeddings_by_key: dict[str, list[float]]) -> None:
        cache_path.write_text(
            json.dumps(
                {
                    "model": self.hybrid_config.embedding_model,
                    "entries": [
                        {"key": key, "embedding": embeddings_by_key[key]}
                        for key in expected_keys
                        if key in embeddings_by_key
                    ],
                }
            ),
            encoding="utf-8",
        )

    def _score_candidate_batch(
        self,
        candidates: list[Paper],
        evidence_by_candidate: list[list[CorpusPaper]],
    ) -> list[float]:
        prompt = self._build_prompt(candidates, evidence_by_candidate)
        params = self._chat_params()
        if self.client is None:
            self.client = OpenAI(api_key=self.config.llm.api.key, base_url=self.config.llm.api.base_url)
        messages = [
            {
                "role": "system",
                "content": (
                    "You rank new scientific papers against the most relevant evidence "
                    "retrieved from a user's Zotero library. Return JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        response = self._create_chat_completion_with_retry(messages, params)
        content = response.choices[0].message.content or ""
        return _extract_scores(content, len(candidates))

    def _create_chat_completion_with_retry(self, messages: list[dict], params: dict):
        attempts = int(self.hybrid_config.get("llm_retry_attempts") or 3)
        for attempt in range(attempts):
            try:
                return self.client.chat.completions.create(messages=messages, **params)
            except Exception as exc:
                if attempt == attempts - 1 or not self._is_retryable_llm_error(exc):
                    raise
                delay = self._retry_delay_seconds(exc, attempt)
                logger.warning(
                    f"DeepSeek scoring failed with retryable error ({exc}); retrying in {delay:.1f}s"
                )
                time.sleep(delay)
        raise RuntimeError("unreachable")

    @staticmethod
    def _is_retryable_llm_error(exc: Exception) -> bool:
        if getattr(exc, "status_code", None) in {408, 409, 429, 500, 502, 503, 504}:
            return True
        return exc.__class__.__name__ in {"APIConnectionError", "APITimeoutError"}

    def _is_recoverable_llm_scoring_error(self, exc: Exception) -> bool:
        return isinstance(exc, ValueError) or self._is_retryable_llm_error(exc)

    def _retry_delay_seconds(self, exc: Exception, attempt: int) -> float:
        default_delay = float(self.hybrid_config.get("llm_retry_initial_seconds") or 10)
        max_delay = float(self.hybrid_config.get("llm_retry_max_seconds") or 60)
        response = getattr(exc, "response", None)
        retry_after = None
        if response is not None:
            try:
                retry_after = response.headers.get("retry-after")
            except AttributeError:
                retry_after = None
            if retry_after is None:
                try:
                    retry_after = response.json().get("retry_after")
                except Exception:
                    retry_after = None
        try:
            delay = float(retry_after) if retry_after is not None else default_delay * (2 ** attempt)
        except (TypeError, ValueError):
            delay = default_delay * (2 ** attempt)
        return min(delay, max_delay)

    def _chat_params(self) -> dict:
        params = _as_plain_dict(self.config.llm.get("generation_kwargs"))
        params.update(_as_plain_dict(self.hybrid_config.get("generation_kwargs")))
        params["model"] = self.hybrid_config.get("model") or params.get("model")
        params.setdefault("temperature", 0)
        if self.hybrid_config.get("llm_timeout_seconds") is not None:
            params.setdefault("timeout", float(self.hybrid_config.llm_timeout_seconds))
        return params

    @staticmethod
    def _build_recommendation_reason(matched_titles: list[str] | None, embedding_score: float) -> str:
        if matched_titles:
            quoted_titles = "、".join(f"《{title}》" for title in matched_titles[:3])
            return (
                f"与 Zotero 文献 {quoted_titles} 的摘要相似度较高；"
                f"先用全库 embedding 召回相关证据，再结合精排评分推荐。"
            )
        return (
            f"基于 Zotero 全库摘要相似度进行推荐；"
            f"当前 embedding 相似度为 {embedding_score:.2f}。"
        )

    def _trim(self, text: str) -> str:
        max_chars = int(self.hybrid_config.get("max_abstract_chars") or 1200)
        return text[:max_chars]

    def _build_prompt(
        self,
        candidates: list[Paper],
        evidence_by_candidate: list[list[CorpusPaper]],
    ) -> str:
        sections = []
        for idx, (candidate, evidence) in enumerate(zip(candidates, evidence_by_candidate), start=1):
            evidence_text = "\n".join(
                f"- {paper.title}: {self._trim(paper.abstract)}"
                for paper in evidence
            )
            sections.append(
                f"{idx}. Candidate title: {candidate.title}\n"
                f"Candidate abstract: {self._trim(candidate.abstract)}\n"
                f"Most relevant Zotero evidence:\n{evidence_text}"
            )
        return (
            "Score each candidate paper from 0.0 to 1.0 for relevance to the user's Zotero library.\n"
            "Use the retrieved Zotero evidence. Penalize broad field-only overlap.\n"
            "Return exactly this JSON shape and no other text: {\"scores\": [0.0, 0.0]}\n\n"
            + "\n\n".join(sections)
        )

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
        b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
        return np.dot(a_norm, b_norm.T)
