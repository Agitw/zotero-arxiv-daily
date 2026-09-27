"""Tests for zotero_arxiv_daily.protocol: Paper.generate_tldr, Paper.generate_affiliations."""

import pytest
from types import SimpleNamespace

from tests.canned_responses import make_sample_paper, make_stub_openai_client


@pytest.fixture()
def llm_params():
    return {
        "language": "English",
        "generation_kwargs": {"model": "gpt-4o-mini", "max_tokens": 768},
        "affiliation_generation_kwargs": {"max_tokens": 128},
    }


# ---------------------------------------------------------------------------
# generate_tldr
# ---------------------------------------------------------------------------


def test_tldr_returns_response(llm_params):
    client = make_stub_openai_client()
    paper = make_sample_paper()
    result = paper.generate_tldr(client, llm_params)
    assert "研究问题：Widget stability is poorly understood." in result
    assert "解决思路：The study combines modeling and experiments." in result
    assert "核心方法：A constrained graph model is introduced." in result
    assert "关键结果：The abstract reports improved stability." in result
    assert "主要结论：The method supports robust widget design." in result
    assert paper.tldr == result


def test_tldr_without_abstract_or_fulltext(llm_params):
    client = make_stub_openai_client()
    paper = make_sample_paper(abstract="", full_text=None)
    result = paper.generate_tldr(client, llm_params)
    assert "Failed to generate TLDR" in result


def test_tldr_falls_back_to_abstract_excerpt_on_error(llm_params):
    paper = make_sample_paper()

    # Client whose create() raises
    from types import SimpleNamespace

    broken_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("API down")))
        )
    )
    result = paper.generate_tldr(broken_client, llm_params)
    assert "摘要原文" in result
    assert paper.abstract in result
    assert "摘要未说明" not in result


def test_tldr_uses_title_and_abstract_but_not_full_text(llm_params):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return make_stub_openai_client().chat.completions.create(**kwargs)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    paper = make_sample_paper(
        title="Visible title",
        abstract="Visible abstract",
        full_text="SECRET FULL TEXT MUST NOT BE SENT",
    )

    paper.generate_tldr(client, llm_params)

    request_text = str(calls[0]["messages"])
    assert "Visible title" in request_text
    assert "Visible abstract" in request_text
    assert "SECRET FULL TEXT MUST NOT BE SENT" not in request_text
    assert calls[0]["max_tokens"] == 768


def test_tldr_prompt_requests_richer_scientific_summary(llm_params):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Detailed TLDR"))]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    paper = make_sample_paper()
    paper.generate_tldr(client, llm_params)

    request_text = str(calls[0]["messages"])
    assert "problem" in request_text.lower()
    assert "method" in request_text.lower()
    assert "result" in request_text.lower()
    assert "conclusion" in request_text.lower()


def test_tldr_prompt_explicitly_requests_chinese_output(llm_params):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="中文摘要"))]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    paper = make_sample_paper()
    llm_params = {
        **llm_params,
        "language": "Chinese",
    }
    paper.generate_tldr(client, llm_params)

    request_text = str(calls[0]["messages"])
    assert "中文" in request_text
    assert "研究问题" in request_text
    assert "解决思路" in request_text
    assert "核心方法" in request_text
    assert "关键结果" in request_text
    assert "主要结论" in request_text


def test_chinese_tldr_prompt_requests_research_reading_structure(llm_params):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"research_problem":"问题"}'))]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    paper = make_sample_paper()
    llm_params = {
        **llm_params,
        "language": "Chinese",
    }

    paper.generate_tldr(client, llm_params)

    request_text = str(calls[0]["messages"])
    assert "摘要未说明" not in request_text
    assert "不得根据常识补全" in request_text


def test_chinese_tldr_preserves_useful_prose_when_json_is_unavailable(llm_params):
    calls = []
    responses = ["Deep learning has outgrown any single mathematical explanation."]

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=responses.pop(0)))]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    paper = make_sample_paper()
    llm_params = {
        **llm_params,
        "language": "Chinese",
    }

    result = paper.generate_tldr(client, llm_params)

    assert len(calls) == 1
    assert "Deep learning has outgrown any single mathematical explanation." in result
    assert "摘要未说明" not in result


def test_tldr_does_not_fill_missing_sections_with_repeated_placeholders(llm_params):
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(
                        content='{"research_problem":"How do protein variants affect function?",'
                                '"key_results":"摘要未说明"}'
                    ))]
                )
            )
        )
    )
    paper = make_sample_paper(abstract="We predict protein variant effects from sequence and structure.")

    result = paper.generate_tldr(client, llm_params)

    assert "How do protein variants affect function?" in result
    assert paper.abstract in result
    assert "摘要未说明" not in result


def test_tldr_uses_original_abstract_when_every_model_field_is_missing(llm_params):
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=(
                        '{"research_problem":"摘要未说明",'
                        '"solution_approach":"摘要未说明"}'
                    )))]
                )
            )
        )
    )
    paper = make_sample_paper(
        abstract="We model protein conformational ensembles to predict variant effects."
    )

    result = paper.generate_tldr(client, llm_params)

    assert "摘要原文" in result
    assert paper.abstract in result
    assert "摘要未说明" not in result


# ---------------------------------------------------------------------------
# generate_affiliations
# ---------------------------------------------------------------------------


def test_affiliations_returns_parsed_list(llm_params):
    client = make_stub_openai_client()
    paper = make_sample_paper()
    result = paper.generate_affiliations(client, llm_params)
    assert isinstance(result, list)
    assert result == [
        "第一单位：TsingHua University",
        "通讯单位：Peking University",
    ]


def test_affiliations_none_without_fulltext(llm_params):
    client = make_stub_openai_client()
    paper = make_sample_paper(full_text=None)
    result = paper.generate_affiliations(client, llm_params)
    assert result is None


def test_affiliations_preserve_retriever_metadata_without_calling_llm(llm_params):
    metadata = ["第一单位：Institute A", "通讯单位：Institute B"]
    paper = make_sample_paper(full_text=None, affiliations=metadata)
    broken_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kw: (_ for _ in ()).throw(AssertionError("LLM must not be called"))
            )
        )
    )

    result = paper.generate_affiliations(broken_client, llm_params)

    assert result == metadata
    assert paper.affiliations == metadata


def test_affiliations_deduplicates(llm_params):
    """The stub returns two distinct affiliations, so no dedup needed.
    But confirm the set() dedup in the code doesn't break anything.
    """
    client = make_stub_openai_client()
    paper = make_sample_paper()
    result = paper.generate_affiliations(client, llm_params)
    assert len(result) == len(set(result))


def test_affiliations_uses_a_128_token_budget(llm_params):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"first_affiliation":"Institute A",'
                            '"corresponding_affiliations":["Institute B"]}'
                        )
                    )
                )
            ]
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    make_sample_paper().generate_affiliations(client, llm_params)

    assert calls[0]["max_tokens"] == 128


def test_affiliations_malformed_llm_output(llm_params):
    """LLM returns affiliations without JSON brackets. Should fall back gracefully."""
    from types import SimpleNamespace

    def create_no_brackets(**kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="TsingHua University, Peking University"),
                )
            ]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_no_brackets)
        )
    )
    paper = make_sample_paper()
    result = paper.generate_affiliations(client, llm_params)
    # re.search for [...] will fail -> AttributeError -> caught -> returns None
    assert result is None


def test_affiliations_error_returns_none(llm_params):
    from types import SimpleNamespace

    broken_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))
        )
    )
    paper = make_sample_paper()
    result = paper.generate_affiliations(broken_client, llm_params)
    assert result is None
    assert paper.affiliations is None
