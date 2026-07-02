"""Tests for LLM-based abstract matching reranker."""

from types import SimpleNamespace

from omegaconf import open_dict

from zotero_arxiv_daily.reranker.llm import LlmReranker
from tests.canned_responses import make_sample_corpus, make_sample_paper


def _make_chat_client(responses: list[str]):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        content = responses.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    client = SimpleNamespace(
        calls=calls,
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )
    return client


def _enable_llm_reranker(config):
    with open_dict(config.reranker):
        config.reranker.llm = {
            "model": "deepseek-v4-flash",
            "batch_size": 2,
            "candidate_batch_size": 2,
            "corpus_batch_size": 2,
            "max_corpus_papers": None,
        }
    return config


def test_llm_reranker_scores_candidate_abstract_against_corpus_batches(config, monkeypatch):
    client = _make_chat_client(['{"scores": [0.9, 0.1]}', '{"scores": [0.4]}'])
    monkeypatch.setattr("zotero_arxiv_daily.reranker.llm.OpenAI", lambda **kwargs: client)
    config = _enable_llm_reranker(config)

    reranker = LlmReranker(config)
    scores = reranker.get_similarity_score(
        ["candidate abstract about protein binding"],
        ["protein interaction corpus", "language model corpus", "molecular dynamics corpus"],
    )

    assert scores.shape == (1, 3)
    assert scores.tolist() == [[0.9, 0.1, 0.4]]
    assert len(client.calls) == 2
    assert client.calls[0]["model"] == "deepseek-v4-flash"
    assert "candidate abstract about protein binding" in str(client.calls[0]["messages"])


def test_llm_reranker_clamps_scores_and_uses_zero_for_malformed_responses(config, monkeypatch):
    client = _make_chat_client(['{"scores": [1.2, -0.2]}', "not json"])
    monkeypatch.setattr("zotero_arxiv_daily.reranker.llm.OpenAI", lambda **kwargs: client)
    config = _enable_llm_reranker(config)

    reranker = LlmReranker(config)
    scores = reranker.get_similarity_score(
        ["candidate one", "candidate two"],
        ["corpus abstract one", "corpus abstract two"],
    )

    assert scores.shape == (2, 2)
    assert scores.tolist() == [[1.0, 0.0], [0.0, 0.0]]


def test_llm_reranker_reranks_candidate_abstracts_in_batches(config, monkeypatch):
    client = _make_chat_client(['{"scores": [0.2, 0.9]}', '{"scores": [0.4]}'])
    monkeypatch.setattr("zotero_arxiv_daily.reranker.llm.OpenAI", lambda **kwargs: client)
    config = _enable_llm_reranker(config)
    config.reranker.llm.corpus_batch_size = 100

    corpus = make_sample_corpus(3)
    papers = [
        make_sample_paper(title="Low match", abstract="general machine learning abstract"),
        make_sample_paper(title="High match", abstract="protein binding and molecular dynamics abstract"),
        make_sample_paper(title="Middle match", abstract="protein structure abstract"),
    ]

    ranked = LlmReranker(config).rerank(papers, corpus)

    assert [paper.title for paper in ranked] == ["High match", "Middle match", "Low match"]
    assert [paper.score for paper in ranked] == [9.0, 4.0, 2.0]
    assert len(client.calls) == 2


def test_llm_reranker_uses_every_corpus_chunk_for_candidate_scores(config, monkeypatch):
    client = _make_chat_client([
        '{"scores": [0.1, 0.2]}',
        '{"scores": [0.8, 0.3]}',
        '{"scores": [0.4, 0.7]}',
    ])
    monkeypatch.setattr("zotero_arxiv_daily.reranker.llm.OpenAI", lambda **kwargs: client)
    config = _enable_llm_reranker(config)

    corpus = make_sample_corpus(5)
    papers = [
        make_sample_paper(title="Candidate A", abstract="candidate a abstract"),
        make_sample_paper(title="Candidate B", abstract="candidate b abstract"),
    ]

    ranked = LlmReranker(config).rerank(papers, corpus)

    assert [paper.title for paper in ranked] == ["Candidate A", "Candidate B"]
    assert [paper.score for paper in ranked] == [8.0, 7.0]
    assert len(client.calls) == 3
    assert "Corpus Paper 4" in str(client.calls[0]["messages"])
    assert "Corpus Paper 2" in str(client.calls[1]["messages"])
    assert "Corpus Paper 0" in str(client.calls[2]["messages"])
