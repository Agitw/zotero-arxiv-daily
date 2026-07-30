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


def test_high_impact_journal_weights_are_configured(config):
    weights = config.reranker.venue_weights

    assert weights["2522-5839"] == 1.5  # Nature Machine Intelligence
    assert weights["1548-7091"] == 1.5  # Nature Methods
    assert weights["1087-0156"] == 1.5  # Nature Biotechnology
    assert weights["2662-8457"] == 1.4  # Nature Computational Science
    hybrid = config.reranker.hybrid_llm
    assert hybrid.llm_candidate_num == 60
    assert hybrid.llm_global_candidate_num == 50
    assert hybrid.llm_high_impact_candidate_num == 10
    assert hybrid.llm_high_impact_min_score == 0.20


def test_runtime_config_enables_recommendation_history_and_funnel():
    custom = OmegaConf.load(Path(__file__).parent.parent / "config" / "custom.yaml")

    assert custom.executor.recommendation_history_path == ".cache/recommendation-history.json"
    assert custom.executor.recommendation_history_days == 60
    assert custom.executor.recommendation_funnel_path == "outputs/recommendation-funnel.json"
