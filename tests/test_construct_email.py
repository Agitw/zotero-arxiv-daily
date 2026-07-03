"""Tests for zotero_arxiv_daily.construct_email: render_email, get_stars, get_block_html."""

from zotero_arxiv_daily.construct_email import render_email, get_stars, get_block_html, get_empty_html
from tests.canned_responses import make_sample_paper


def test_render_email_with_papers():
    papers = [make_sample_paper(score=7.5, tldr="A great paper.", affiliations=["MIT"])]
    html = render_email(papers)
    assert "Sample Paper Title" in html
    assert "A great paper." in html
    assert "MIT" in html


def test_render_email_includes_publication_venue_and_date():
    paper = make_sample_paper(
        source="openalex",
        venue="Nature Computational Science",
        published_date="2026-07-02",
        score=8.2,
        tldr="A richer summary.",
    )
    html = render_email([paper])

    assert "Source:" in html
    assert "Nature Computational Science" in html
    assert "Date:" in html
    assert "2026-07-02" in html


def test_render_email_uses_chinese_tldr_label():
    paper = make_sample_paper(score=8.0, tldr="这篇论文提出了新的分子生成方法。")

    html = render_email([paper])

    assert "中文速览:" in html
    assert "TLDR:" not in html


def test_render_email_preserves_chinese_tldr_bullet_lines():
    paper = make_sample_paper(
        score=8.0,
        tldr="- 核心问题：解释深度学习理论。\n- 方法模型：统一近似、优化和泛化视角。",
    )

    html = render_email([paper])

    assert "- 核心问题：解释深度学习理论。<br>- 方法模型：统一近似、优化和泛化视角。" in html


def test_render_email_falls_back_to_paper_page_when_pdf_url_is_missing():
    paper = make_sample_paper(
        score=8.0,
        tldr="Summary",
        url="https://journal.example.org/article/123",
        pdf_url=None,
    )

    html = render_email([paper])

    assert 'href="https://journal.example.org/article/123"' in html
    assert ">期刊网页</a>" in html
    assert 'href="None"' not in html


def test_render_email_empty_list():
    html = render_email([])
    assert "No Papers Today" in html


def test_render_email_author_truncation():
    authors = [f"Author {i}" for i in range(10)]
    paper = make_sample_paper(authors=authors, score=7.0, tldr="ok")
    html = render_email([paper])
    assert "Author 0" in html
    assert "Author 1" in html
    assert "Author 2" in html
    assert "..." in html
    assert "Author 8" in html
    assert "Author 9" in html
    # Middle authors should be truncated
    assert "Author 5" not in html


def test_render_email_affiliation_truncation():
    affiliations = [f"Uni {i}" for i in range(8)]
    paper = make_sample_paper(affiliations=affiliations, score=7.0, tldr="ok")
    html = render_email([paper])
    assert "Uni 0" in html
    assert "Uni 4" in html
    assert "..." in html
    assert "Uni 7" not in html


def test_render_email_no_affiliations():
    paper = make_sample_paper(affiliations=None, score=7.0, tldr="ok")
    html = render_email([paper])
    assert "Unknown Affiliation" in html


def test_get_stars_low_score():
    assert get_stars(5.0) == ""
    assert get_stars(6.0) == ""


def test_get_stars_high_score():
    stars = get_stars(8.0)
    assert stars.count("full-star") == 5


def test_get_stars_mid_score():
    stars = get_stars(7.0)
    assert "star" in stars
    assert stars.count("full-star") + stars.count("half-star") > 0


def test_get_block_html_contains_all_fields():
    html = get_block_html("Title", "Auth", "3.5", "Summary", "http://pdf.url", "MIT")
    assert "Title" in html
    assert "Auth" in html
    assert "3.5" in html
    assert "Summary" in html
    assert "http://pdf.url" in html
    assert "MIT" in html


def test_get_empty_html():
    html = get_empty_html()
    assert "No Papers Today" in html
