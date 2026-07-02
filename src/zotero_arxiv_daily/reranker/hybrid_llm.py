import hashlib
import json
from pathlib import Path

import numpy as np
from loguru import logger
from openai import OpenAI
from omegaconf import OmegaConf

from .base import BaseReranker, register_reranker
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

        candidate_batch_size = int(self.hybrid_config.get("candidate_batch_size") or 5)
        for start in range(0, len(candidates), candidate_batch_size):
            batch = candidates[start : start + candidate_batch_size]
            batch_evidence = []
            for candidate_idx in range(start, start + len(batch)):
                evidence_indices = np.argsort(sim[candidate_idx])[::-1][:evidence_per_candidate]
                batch_evidence.append([corpus[idx] for idx in evidence_indices])
            scores = self._score_candidate_batch(batch, batch_evidence)
            for paper, score in zip(batch, scores):
                paper.score = score * 10
        return sorted(candidates, key=lambda paper: paper.score or 0.0, reverse=True)

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
        response = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You rank new scientific papers against the most relevant evidence "
                        "retrieved from a user's Zotero library. Return JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            **params,
        )
        content = response.choices[0].message.content or ""
        return _extract_scores(content, len(candidates))

    def _chat_params(self) -> dict:
        params = _as_plain_dict(self.config.llm.get("generation_kwargs"))
        params.update(_as_plain_dict(self.hybrid_config.get("generation_kwargs")))
        params["model"] = self.hybrid_config.get("model") or params.get("model")
        params.setdefault("temperature", 0)
        return params

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
