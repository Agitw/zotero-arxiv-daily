from abc import ABC, abstractmethod
from collections.abc import Mapping
from omegaconf import DictConfig
from ..protocol import Paper, CorpusPaper
import numpy as np
from typing import Type


def get_venue_bonus(
    paper: Paper,
    venue_bonuses: Mapping[str, float] | None,
) -> float:
    if not venue_bonuses:
        return 0.0
    normalized_bonuses = {
        str(key).strip().casefold(): float(bonus)
        for key, bonus in venue_bonuses.items()
    }
    issn_bonuses = [
        normalized_bonuses[issn.strip().casefold()]
        for issn in paper.venue_issns or []
        if issn.strip().casefold() in normalized_bonuses
    ]
    if issn_bonuses:
        return max(issn_bonuses)
    venue = (paper.venue or "").strip().casefold()
    return normalized_bonuses.get(venue, 0.0)


def apply_venue_bonuses(
    papers: list[Paper],
    venue_bonuses: Mapping[str, float] | None,
    minimum_deepseek_score: float = 6.0,
) -> list[Paper]:
    """Add a capped journal bonus only after a sufficiently relevant DeepSeek score."""
    if not venue_bonuses:
        return papers

    adjusted = False
    for paper in papers:
        paper.venue_bonus = 0.0
        if paper.score_source != "deepseek":
            continue
        if paper.deepseek_score is None or paper.deepseek_score < minimum_deepseek_score:
            continue
        venue = (paper.venue or "").strip()
        bonus = get_venue_bonus(paper, venue_bonuses)
        if bonus <= 0.0:
            continue
        paper.score = (paper.score or 0.0) + bonus
        paper.venue_bonus = bonus
        reason = f"高影响力期刊加分：{venue} +{bonus:.2f}"
        paper.recommendation_reason = (
            f"{paper.recommendation_reason}；{reason}"
            if paper.recommendation_reason
            else reason
        )
        adjusted = True
    if not adjusted:
        return papers
    return sorted(papers, key=lambda paper: paper.score or 0.0, reverse=True)


class BaseReranker(ABC):
    def __init__(self, config:DictConfig):
        self.config = config

    def rerank(self, candidates:list[Paper], corpus:list[CorpusPaper]) -> list[Paper]:
        corpus = sorted(corpus,key=lambda x: x.added_date,reverse=True)
        time_decay_weight = 1 / (1 + np.log10(np.arange(len(corpus)) + 1))
        time_decay_weight: np.ndarray = time_decay_weight / time_decay_weight.sum()
        sim = self.get_similarity_score([c.abstract for c in candidates], [c.abstract for c in corpus])
        assert sim.shape == (len(candidates), len(corpus))
        scores = (sim * time_decay_weight).sum(axis=1) * 10 # [n_candidate]
        for s,c in zip(scores,candidates):
            c.score = s
        candidates = sorted(candidates,key=lambda x: x.score,reverse=True)
        return candidates
    
    @abstractmethod
    def get_similarity_score(self, s1:list[str], s2:list[str]) -> np.ndarray:
        raise NotImplementedError

registered_rerankers = {}

def register_reranker(name:str):
    def decorator(cls):
        registered_rerankers[name] = cls
        return cls
    return decorator

def get_reranker_cls(name:str) -> Type[BaseReranker]:
    if name not in registered_rerankers:
        raise ValueError(f"Reranker {name} not found")
    return registered_rerankers[name]
