"""Tests for repository-level runtime configuration."""

from pathlib import Path

from omegaconf import OmegaConf


def test_openalex_journal_sources_keep_curated_high_impact_journals(config):
    issns = set(config.source.openalex.issns)

    assert config.source.openalex.days == 14
    assert config.source.openalex.max_results == 3000
    assert len(issns) == 31
    assert "2522-5839" in issns  # Nature Machine Intelligence
    assert "1759-0876" in issns  # WIREs Computational Molecular Science
    assert "2662-8457" in issns  # Nature Computational Science
    assert "2056-7189" in issns  # npj Systems Biology and Applications
    assert "1476-9271" not in issns  # Computational Biology and Chemistry, CAS Q4
    assert "1432-881X" not in issns  # Theoretical Chemistry Accounts, CAS Q4


def test_high_impact_journal_bonuses_are_configured(config):
    bonuses = config.reranker.venue_bonuses

    assert bonuses["2522-5839"] == 0.8  # Nature Machine Intelligence
    assert bonuses["1548-7091"] == 0.8  # Nature Methods
    assert bonuses["1087-0156"] == 0.8  # Nature Biotechnology
    assert bonuses["2662-8457"] == 0.6  # Nature Computational Science
    assert config.reranker.venue_bonus_min_deepseek_score == 6.0
    hybrid = config.reranker.hybrid_llm
    assert hybrid.llm_candidate_num == 100
    assert hybrid.llm_global_candidate_num == 70
    assert hybrid.llm_high_impact_candidate_num == 30
    assert hybrid.llm_high_impact_min_score == 0.20
    assert hybrid.evidence_per_candidate == 5
    assert hybrid.max_evidence_abstract_chars == 500
    assert hybrid.deepseek_score_weight == 0.7


def test_runtime_config_enables_recommendation_history_and_funnel():
    custom = OmegaConf.load(Path(__file__).parent.parent / "config" / "custom.yaml")

    assert custom.executor.recommendation_history_path == ".cache/recommendation-history.json"
    assert custom.executor.recommendation_history_days == 60
    assert custom.executor.recommendation_funnel_path == "outputs/recommendation-funnel.json"


def test_base_config_uses_bounded_deepseek_budgets():
    base = OmegaConf.load(Path(__file__).parent.parent / "config" / "base.yaml")

    assert base.llm.generation_kwargs.max_tokens == 768
    assert base.llm.affiliation_generation_kwargs.max_tokens == 128
    hybrid = base.reranker.hybrid_llm
    assert hybrid.llm_candidate_num == 100
    assert hybrid.llm_global_candidate_num == 70
    assert hybrid.llm_high_impact_candidate_num == 30
    assert hybrid.evidence_per_candidate == 5
    assert hybrid.candidate_batch_size == 10
    assert hybrid.max_abstract_chars == 700
    assert hybrid.max_evidence_abstract_chars == 500
    assert hybrid.generation_kwargs.max_tokens == 128
