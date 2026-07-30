"""Tests for cached hybrid LLM reranking."""

import json
from types import SimpleNamespace

import pytest
from omegaconf import open_dict

from tests.canned_responses import make_sample_corpus, make_sample_paper
from zotero_arxiv_daily.reranker.hybrid_llm import HybridLlmReranker


class FakeEmbeddingClient:
    def __init__(self, vectors_by_text: dict[str, list[float]]):
        self.vectors_by_text = vectors_by_text
        self.encoded_texts: list[str] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.encoded_texts.extend(texts)
        return [self.vectors_by_text[text] for text in texts]


def _make_chat_client(response: str):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=response))]
        )

    return SimpleNamespace(
        calls=calls,
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )


class RetryableChatError(Exception):
    status_code = 502


def _make_flaky_chat_client(response: str):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RetryableChatError("temporary upstream failure")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=response))]
        )

    return SimpleNamespace(
        calls=calls,
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )


def _make_failing_chat_client():
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        raise RetryableChatError("temporary upstream failure")

    return SimpleNamespace(
        calls=calls,
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )


def _enable_hybrid(config, cache_path):
    with open_dict(config.executor):
        config.executor.reranker = "hybrid_llm"
    with open_dict(config.reranker):
        config.reranker.hybrid_llm = {
            "model": "deepseek-v4-flash",
            "embedding_provider": "fake",
            "embedding_model": "fake-embedding-model",
            "cache_path": str(cache_path),
            "cache_build_batch_size": 1,
            "evidence_per_candidate": 2,
            "candidate_batch_size": 5,
            "max_abstract_chars": 1200,
        }
    return config


def test_hybrid_llm_reranker_uses_cached_corpus_embeddings_for_deepseek_evidence(config, tmp_path, monkeypatch):
    corpus = make_sample_corpus(3)
    candidates = [
        make_sample_paper(title="Candidate", abstract="candidate abstract"),
    ]
    cache_path = tmp_path / "zotero-corpus-embeddings.json"
    cache_path.write_text(
        json.dumps(
            {
                "model": "fake-embedding-model",
                "entries": [
                    {"key": HybridLlmReranker.corpus_key(paper), "embedding": embedding}
                    for paper, embedding in zip(
                        corpus,
                        [[1.0, 0.0], [0.0, 1.0], [0.8, 0.2]],
                    )
                ],
            }
        ),
        encoding="utf-8",
    )
    embedding_client = FakeEmbeddingClient({"candidate abstract": [1.0, 0.0]})
    chat_client = _make_chat_client('{"scores": [0.88]}')
    monkeypatch.setattr(
        "zotero_arxiv_daily.reranker.hybrid_llm.OpenAI",
        lambda **kwargs: chat_client,
    )
    monkeypatch.setattr(
        HybridLlmReranker,
        "_make_embedding_client",
        lambda self: embedding_client,
    )

    ranked = HybridLlmReranker(_enable_hybrid(config, cache_path)).rerank(candidates, corpus)

    assert ranked[0].score == 8.8
    assert embedding_client.encoded_texts == ["candidate abstract"]
    prompt = str(chat_client.calls[0]["messages"])
    assert "Corpus Paper 2" in prompt
    assert "Corpus Paper 1" not in prompt


def test_hybrid_llm_reranker_records_zotero_evidence_for_email_reasons(config, tmp_path, monkeypatch):
    corpus = make_sample_corpus(3)
    candidates = [
        make_sample_paper(title="Candidate", abstract="candidate abstract"),
    ]
    cache_path = tmp_path / "zotero-corpus-embeddings.json"
    cache_path.write_text(
        json.dumps(
            {
                "model": "fake-embedding-model",
                "entries": [
                    {"key": HybridLlmReranker.corpus_key(paper), "embedding": embedding}
                    for paper, embedding in zip(
                        corpus,
                        [[0.0, 1.0], [0.8, 0.2], [1.0, 0.0]],
                    )
                ],
            }
        ),
        encoding="utf-8",
    )
    embedding_client = FakeEmbeddingClient({"candidate abstract": [1.0, 0.0]})
    chat_client = _make_chat_client('{"scores": [0.86]}')
    monkeypatch.setattr(
        "zotero_arxiv_daily.reranker.hybrid_llm.OpenAI",
        lambda **kwargs: chat_client,
    )
    monkeypatch.setattr(
        HybridLlmReranker,
        "_make_embedding_client",
        lambda self: embedding_client,
    )

    ranked = HybridLlmReranker(_enable_hybrid(config, cache_path)).rerank(candidates, corpus)

    assert ranked[0].matched_zotero_titles == ["Corpus Paper 2", "Corpus Paper 1"]
    assert "Corpus Paper 2" in ranked[0].recommendation_reason
    assert "Zotero" in ranked[0].recommendation_reason
    assert "摘要相似度" in ranked[0].recommendation_reason


def test_hybrid_llm_reranker_builds_corpus_embedding_cache_when_missing(config, tmp_path, monkeypatch):
    corpus = make_sample_corpus(2)
    candidates = [make_sample_paper(title="Candidate", abstract="candidate abstract")]
    cache_path = tmp_path / "zotero-corpus-embeddings.json"
    vectors = {
        corpus[0].abstract: [1.0, 0.0],
        corpus[1].abstract: [0.0, 1.0],
        "candidate abstract": [1.0, 0.0],
    }
    embedding_client = FakeEmbeddingClient(vectors)
    chat_client = _make_chat_client('{"scores": [0.7]}')
    monkeypatch.setattr(
        "zotero_arxiv_daily.reranker.hybrid_llm.OpenAI",
        lambda **kwargs: chat_client,
    )
    monkeypatch.setattr(
        HybridLlmReranker,
        "_make_embedding_client",
        lambda self: embedding_client,
    )

    HybridLlmReranker(_enable_hybrid(config, cache_path)).rerank(candidates, corpus)

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert cache["model"] == "fake-embedding-model"
    assert len(cache["entries"]) == 2
    assert corpus[0].abstract in embedding_client.encoded_texts
    assert corpus[1].abstract in embedding_client.encoded_texts


def test_hybrid_llm_reranker_extends_partial_corpus_embedding_cache(config, tmp_path, monkeypatch):
    corpus = sorted(make_sample_corpus(2), key=lambda paper: paper.added_date, reverse=True)
    cache_path = tmp_path / "zotero-corpus-embeddings.json"
    cached_key = HybridLlmReranker.corpus_key(corpus[0])
    cache_path.write_text(
        json.dumps(
            {
                "model": "fake-embedding-model",
                "entries": [{"key": cached_key, "embedding": [1.0, 0.0]}],
            }
        ),
        encoding="utf-8",
    )
    embedding_client = FakeEmbeddingClient({corpus[1].abstract: [0.0, 1.0]})
    monkeypatch.setattr(
        HybridLlmReranker,
        "_make_embedding_client",
        lambda self: embedding_client,
    )

    embeddings = HybridLlmReranker(_enable_hybrid(config, cache_path)).prepare_corpus_embeddings(corpus)

    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]
    assert embedding_client.encoded_texts == [corpus[1].abstract]
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert len(cache["entries"]) == 2


def test_hybrid_llm_reranker_does_not_create_deepseek_client_until_scoring(config, tmp_path, monkeypatch):
    cache_path = tmp_path / "zotero-corpus-embeddings.json"
    monkeypatch.setattr(
        HybridLlmReranker,
        "_make_embedding_client",
        lambda self: FakeEmbeddingClient({}),
    )
    monkeypatch.setattr(
        "zotero_arxiv_daily.reranker.hybrid_llm.OpenAI",
        lambda **kwargs: pytest.fail("DeepSeek client should be lazy"),
    )

    HybridLlmReranker(_enable_hybrid(config, cache_path))


def test_hybrid_llm_reranker_retries_retryable_deepseek_errors(config, tmp_path, monkeypatch):
    corpus = make_sample_corpus(1)
    candidates = [make_sample_paper(title="Candidate", abstract="candidate abstract")]
    cache_path = tmp_path / "zotero-corpus-embeddings.json"
    cache_path.write_text(
        json.dumps(
            {
                "model": "fake-embedding-model",
                "entries": [
                    {"key": HybridLlmReranker.corpus_key(corpus[0]), "embedding": [1.0, 0.0]}
                ],
            }
        ),
        encoding="utf-8",
    )
    embedding_client = FakeEmbeddingClient({"candidate abstract": [1.0, 0.0]})
    chat_client = _make_flaky_chat_client('{"scores": [0.9]}')
    monkeypatch.setattr(
        "zotero_arxiv_daily.reranker.hybrid_llm.OpenAI",
        lambda **kwargs: chat_client,
    )
    monkeypatch.setattr(
        HybridLlmReranker,
        "_make_embedding_client",
        lambda self: embedding_client,
    )
    monkeypatch.setattr("zotero_arxiv_daily.reranker.hybrid_llm.time.sleep", lambda _: None)

    ranked = HybridLlmReranker(_enable_hybrid(config, cache_path)).rerank(candidates, corpus)

    assert ranked[0].score == 9.0
    assert len(chat_client.calls) == 2


def test_hybrid_llm_reranker_falls_back_to_embedding_scores_after_retryable_deepseek_errors(config, tmp_path, monkeypatch):
    corpus = make_sample_corpus(1)
    candidates = [
        make_sample_paper(title="Candidate 1", abstract="candidate abstract"),
        make_sample_paper(title="Candidate 2", abstract="second candidate abstract"),
    ]
    cache_path = tmp_path / "zotero-corpus-embeddings.json"
    cache_path.write_text(
        json.dumps(
            {
                "model": "fake-embedding-model",
                "entries": [
                    {"key": HybridLlmReranker.corpus_key(corpus[0]), "embedding": [1.0, 0.0]}
                ],
            }
        ),
        encoding="utf-8",
    )
    embedding_client = FakeEmbeddingClient(
        {
            "candidate abstract": [1.0, 0.0],
            "second candidate abstract": [1.0, 0.0],
        }
    )
    chat_client = _make_failing_chat_client()
    monkeypatch.setattr(
        "zotero_arxiv_daily.reranker.hybrid_llm.OpenAI",
        lambda **kwargs: chat_client,
    )
    monkeypatch.setattr(
        HybridLlmReranker,
        "_make_embedding_client",
        lambda self: embedding_client,
    )
    monkeypatch.setattr("zotero_arxiv_daily.reranker.hybrid_llm.time.sleep", lambda _: None)

    hybrid_config = _enable_hybrid(config, cache_path)
    with open_dict(hybrid_config.reranker.hybrid_llm):
        hybrid_config.reranker.hybrid_llm.candidate_batch_size = 1
    reranker = HybridLlmReranker(hybrid_config)

    ranked = reranker.rerank(candidates, corpus)

    assert ranked[0].score == 10.0
    assert ranked[1].score == 10.0
    assert reranker.llm_scoring_disabled is True
    assert len(chat_client.calls) == 3


def test_hybrid_llm_reranker_falls_back_to_embedding_scores_after_malformed_deepseek_json(config, tmp_path, monkeypatch):
    corpus = make_sample_corpus(1)
    candidates = [
        make_sample_paper(title="Strong Candidate", abstract="strong candidate abstract"),
        make_sample_paper(title="Weak Candidate", abstract="weak candidate abstract"),
    ]
    cache_path = tmp_path / "zotero-corpus-embeddings.json"
    cache_path.write_text(
        json.dumps(
            {
                "model": "fake-embedding-model",
                "entries": [
                    {"key": HybridLlmReranker.corpus_key(corpus[0]), "embedding": [1.0, 0.0]}
                ],
            }
        ),
        encoding="utf-8",
    )
    embedding_client = FakeEmbeddingClient(
        {
            "strong candidate abstract": [1.0, 0.0],
            "weak candidate abstract": [0.0, 1.0],
        }
    )
    chat_client = _make_chat_client('{"scores": [0.2, 0.3]}')
    monkeypatch.setattr(
        "zotero_arxiv_daily.reranker.hybrid_llm.OpenAI",
        lambda **kwargs: chat_client,
    )
    monkeypatch.setattr(
        HybridLlmReranker,
        "_make_embedding_client",
        lambda self: embedding_client,
    )
    hybrid_config = _enable_hybrid(config, cache_path)
    with open_dict(hybrid_config.reranker.hybrid_llm):
        hybrid_config.reranker.hybrid_llm.candidate_batch_size = 1
    reranker = HybridLlmReranker(hybrid_config)

    ranked = reranker.rerank(candidates, corpus)

    assert [paper.title for paper in ranked] == ["Strong Candidate", "Weak Candidate"]
    assert candidates[0].score == 10.0
    assert candidates[1].score == 0.0
    assert reranker.llm_scoring_disabled is True
    assert len(chat_client.calls) == 1


def test_hybrid_llm_reranker_limits_deepseek_scoring_to_top_embedding_candidates(config, tmp_path, monkeypatch):
    corpus = make_sample_corpus(1)
    candidates = [
        make_sample_paper(title="Strong Candidate", abstract="strong candidate abstract"),
        make_sample_paper(title="Middle Candidate", abstract="middle candidate abstract"),
        make_sample_paper(title="Weak Candidate", abstract="weak candidate abstract"),
    ]
    cache_path = tmp_path / "zotero-corpus-embeddings.json"
    cache_path.write_text(
        json.dumps(
            {
                "model": "fake-embedding-model",
                "entries": [
                    {"key": HybridLlmReranker.corpus_key(corpus[0]), "embedding": [1.0, 0.0]}
                ],
            }
        ),
        encoding="utf-8",
    )
    embedding_client = FakeEmbeddingClient(
        {
            "strong candidate abstract": [1.0, 0.0],
            "middle candidate abstract": [0.8, 0.2],
            "weak candidate abstract": [0.0, 1.0],
        }
    )
    chat_client = _make_chat_client('{"scores": [0.9, 0.8]}')
    monkeypatch.setattr(
        "zotero_arxiv_daily.reranker.hybrid_llm.OpenAI",
        lambda **kwargs: chat_client,
    )
    monkeypatch.setattr(
        HybridLlmReranker,
        "_make_embedding_client",
        lambda self: embedding_client,
    )
    hybrid_config = _enable_hybrid(config, cache_path)
    with open_dict(hybrid_config.reranker.hybrid_llm):
        hybrid_config.reranker.hybrid_llm.llm_candidate_num = 2
    ranked = HybridLlmReranker(hybrid_config).rerank(candidates, corpus)

    prompt = str(chat_client.calls[0]["messages"])
    assert "Strong Candidate" in prompt
    assert "Middle Candidate" in prompt
    assert "Weak Candidate" not in prompt
    assert [paper.title for paper in ranked] == [
        "Strong Candidate",
        "Middle Candidate",
        "Weak Candidate",
    ]
    assert candidates[2].score == 0.0


def test_hybrid_llm_candidate_selection_reserves_space_for_high_impact_journals(config, tmp_path, monkeypatch):
    candidates = [
        make_sample_paper(title=f"Candidate {idx}")
        for idx in range(70)
    ]
    candidates[64].venue = "Nature Machine Intelligence"
    candidates[64].venue_issns = ["2522-5839"]
    embedding_scores = [0.90 - idx * 0.01 for idx in range(70)]
    monkeypatch.setattr(
        HybridLlmReranker,
        "_make_embedding_client",
        lambda self: FakeEmbeddingClient({}),
    )
    hybrid_config = _enable_hybrid(config, tmp_path / "cache.json")
    with open_dict(hybrid_config.reranker.hybrid_llm):
        hybrid_config.reranker.hybrid_llm.llm_candidate_num = 60
        hybrid_config.reranker.hybrid_llm.llm_global_candidate_num = 50
        hybrid_config.reranker.hybrid_llm.llm_high_impact_candidate_num = 10
        hybrid_config.reranker.hybrid_llm.llm_high_impact_min_score = 0.20

    reranker = HybridLlmReranker(hybrid_config)
    selected = reranker.select_llm_candidate_indices(candidates, embedding_scores)

    assert len(selected) == 60
    assert 64 in selected
    assert 59 not in selected
    assert candidates[64].llm_selection_reason == "venue_reserve"


def test_hybrid_llm_reranker_treats_openai_timeouts_as_retryable():
    timeout_error = type("APITimeoutError", (Exception,), {})("request timed out")

    assert HybridLlmReranker._is_retryable_llm_error(timeout_error) is True
