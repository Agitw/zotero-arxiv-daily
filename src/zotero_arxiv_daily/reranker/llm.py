import json
import re

import numpy as np
from loguru import logger
from openai import OpenAI
from omegaconf import OmegaConf

from .base import BaseReranker, register_reranker
from ..protocol import CorpusPaper, Paper


def _as_plain_dict(value) -> dict:
    if value is None:
        return {}
    if OmegaConf.is_config(value):
        return OmegaConf.to_container(value, resolve=True) or {}
    return dict(value)


def _extract_scores(content: str, expected: int) -> list[float]:
    candidates = [content]
    object_match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    array_match = re.search(r"\[.*\]", content, flags=re.DOTALL)
    if object_match:
        candidates.append(object_match.group(0))
    if array_match:
        candidates.append(array_match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        scores = parsed.get("scores") if isinstance(parsed, dict) else parsed
        if not isinstance(scores, list):
            continue
        if len(scores) != expected:
            continue
        return [min(1.0, max(0.0, float(score))) for score in scores]

    raise ValueError(f"Expected JSON scores array of length {expected}")


@register_reranker("llm")
class LlmReranker(BaseReranker):
    def __init__(self, config):
        super().__init__(config)
        self.client = OpenAI(api_key=config.llm.api.key, base_url=config.llm.api.base_url)
        self.llm_config = config.reranker.get("llm", {})

    def rerank(self, candidates: list[Paper], corpus: list[CorpusPaper]) -> list[Paper]:
        corpus = sorted(corpus, key=lambda paper: paper.added_date, reverse=True)
        max_corpus_papers = self.llm_config.get("max_corpus_papers")
        if max_corpus_papers is not None:
            corpus = corpus[: int(max_corpus_papers)]

        candidate_batch_size = int(self.llm_config.get("candidate_batch_size") or 5)
        corpus_batch_size = int(self.llm_config.get("corpus_batch_size") or len(corpus) or 1)
        for start in range(0, len(candidates), candidate_batch_size):
            batch = candidates[start : start + candidate_batch_size]
            scores = np.zeros(len(batch), dtype=float)
            for corpus_start in range(0, len(corpus), corpus_batch_size):
                corpus_chunk = corpus[corpus_start : corpus_start + corpus_batch_size]
                chunk_scores = self._score_candidate_batch(batch, corpus_chunk)
                scores = np.maximum(scores, np.array(chunk_scores, dtype=float))
            for paper, score in zip(batch, scores):
                paper.score = score * 10
        return sorted(candidates, key=lambda paper: paper.score or 0.0, reverse=True)

    def get_similarity_score(self, s1: list[str], s2: list[str]) -> np.ndarray:
        batch_size = int(self.llm_config.get("batch_size") or 8)
        max_corpus_papers = self.llm_config.get("max_corpus_papers")
        compare_count = len(s2)
        if max_corpus_papers is not None:
            compare_count = min(compare_count, int(max_corpus_papers))

        sim = np.zeros((len(s1), len(s2)), dtype=float)
        for candidate_idx, candidate_abstract in enumerate(s1):
            for start in range(0, compare_count, batch_size):
                batch = s2[start : start + batch_size]
                sim[candidate_idx, start : start + len(batch)] = self._score_batch(
                    candidate_abstract,
                    batch,
                )
        return sim

    def _score_candidate_batch(
        self,
        candidates: list[Paper],
        corpus: list[CorpusPaper],
    ) -> list[float]:
        prompt = self._build_candidate_batch_prompt(candidates, corpus)
        params = self._chat_params()

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You rank new scientific papers against a user's Zotero library. "
                            "Return JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                **params,
            )
            content = response.choices[0].message.content or ""
            return _extract_scores(content, len(candidates))
        except Exception as exc:
            logger.warning(f"LLM candidate matching failed for one batch: {exc}")
            return [0.0] * len(candidates)

    def _score_batch(self, candidate_abstract: str, corpus_abstracts: list[str]) -> list[float]:
        prompt = self._build_prompt(candidate_abstract, corpus_abstracts)
        params = self._chat_params()

        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You compare scientific abstracts for topical and methodological relevance. "
                            "Return JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                **params,
            )
            content = response.choices[0].message.content or ""
            return _extract_scores(content, len(corpus_abstracts))
        except Exception as exc:
            logger.warning(f"LLM abstract matching failed for one batch: {exc}")
            return [0.0] * len(corpus_abstracts)

    def _chat_params(self) -> dict:
        params = _as_plain_dict(self.config.llm.get("generation_kwargs"))
        params.update(_as_plain_dict(self.llm_config.get("generation_kwargs")))
        params["model"] = self.llm_config.get("model") or params.get("model")
        params.setdefault("temperature", 0)
        return params

    def _trim(self, text: str) -> str:
        max_chars = int(self.llm_config.get("max_abstract_chars") or 1200)
        return text[:max_chars]

    def _format_corpus_profile(self, corpus: list[CorpusPaper]) -> str:
        return "\n\n".join(
            f"{idx}. Title: {paper.title}\nAbstract: {self._trim(paper.abstract)}"
            for idx, paper in enumerate(corpus, start=1)
        )

    def _build_candidate_batch_prompt(
        self,
        candidates: list[Paper],
        corpus: list[CorpusPaper],
    ) -> str:
        candidate_text = "\n\n".join(
            f"{idx}. Title: {paper.title}\nAbstract: {self._trim(paper.abstract)}"
            for idx, paper in enumerate(candidates, start=1)
        )
        corpus_profile = self._format_corpus_profile(corpus)
        return (
            "Score each candidate paper from 0.0 to 1.0 for relevance to this chunk of the user's Zotero library.\n"
            "Prioritize overlap in research problem, biological system, method family, and likely usefulness "
            "to the user's recent library papers. Penalize broad field-only overlap.\n"
            "Return exactly this JSON shape and no other text: {\"scores\": [0.0, 0.0]}\n\n"
            f"Zotero library chunk, newest first:\n{corpus_profile}\n\n"
            f"Candidate papers to score, in order:\n{candidate_text}"
        )

    @staticmethod
    def _build_prompt(candidate_abstract: str, corpus_abstracts: list[str]) -> str:
        references = "\n\n".join(
            f"{idx}. {abstract}" for idx, abstract in enumerate(corpus_abstracts, start=1)
        )
        return (
            "Score how relevant the candidate paper abstract is to each Zotero reference abstract.\n"
            "Use 1.0 for the same research problem, method family, or biological system; "
            "use 0.0 for unrelated work; use intermediate values for partial overlap.\n"
            "Return exactly this JSON shape and no other text: {\"scores\": [0.0, 0.0]}\n\n"
            f"Candidate abstract:\n{candidate_abstract}\n\n"
            f"Zotero reference abstracts:\n{references}"
        )
