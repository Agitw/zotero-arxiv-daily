"""Tests for repository-level runtime configuration."""


def test_openalex_journal_sources_keep_curated_high_impact_journals(config):
    issns = set(config.source.openalex.issns)

    assert len(issns) == 31
    assert "2522-5839" in issns  # Nature Machine Intelligence
    assert "1759-0876" in issns  # WIREs Computational Molecular Science
    assert "2662-8457" in issns  # Nature Computational Science
    assert "2056-7189" in issns  # npj Systems Biology and Applications
    assert "1476-9271" not in issns  # Computational Biology and Chemistry, CAS Q4
    assert "1432-881X" not in issns  # Theoretical Chemistry Accounts, CAS Q4


def test_high_impact_journal_weights_are_configured(config):
    weights = config.reranker.venue_weights

    assert weights["Nature Machine Intelligence"] == 1.5
    assert weights["Nature Methods"] == 1.5
    assert weights["Nature Biotechnology"] == 1.5
    assert weights["Nature Computational Science"] == 1.4
