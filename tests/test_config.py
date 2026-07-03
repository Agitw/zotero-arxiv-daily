"""Tests for repository-level runtime configuration."""


def test_openalex_journal_sources_keep_only_cas_q1_q2_journals(config):
    issns = set(config.source.openalex.issns)

    assert len(issns) == 30
    assert "1759-0876" in issns  # WIREs Computational Molecular Science
    assert "2662-8457" in issns  # Nature Computational Science
    assert "2056-7189" in issns  # npj Systems Biology and Applications
    assert "1476-9271" not in issns  # Computational Biology and Chemistry, CAS Q4
    assert "1432-881X" not in issns  # Theoretical Chemistry Accounts, CAS Q4
