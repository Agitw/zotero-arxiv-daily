"""Tests for repository-level runtime configuration."""


def test_openalex_journal_sources_cover_broad_computational_chemistry_and_biology(config):
    issns = set(config.source.openalex.issns)

    assert len(issns) >= 50
    assert "1759-0876" in issns  # WIREs Computational Molecular Science
    assert "1476-9271" in issns  # Computational Biology and Chemistry
    assert "2662-8457" in issns  # Nature Computational Science
    assert "2056-7189" in issns  # npj Systems Biology and Applications
