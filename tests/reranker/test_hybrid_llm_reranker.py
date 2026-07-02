"""Tests for cached hybrid LLM reranking."""

import json
from types import SimpleNamespace

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


def _enable_hybrid(config, cache_path):
    with open_dict(config.executor):
        config.executor.reranker = "hybrid_llm"
    with open_dict(config.reranker):
        config.reranker.hybrid_llm = {
            "model": "deepseek-v4-flash",
            "embedding_provider": "fake",
            "embedding_model": "fake-embedding-model",
            "cache_path": str(cache_path),
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
