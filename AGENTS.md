# AGENTS.md

This file provides guidance to Codex and other coding agents when working with this repository.

## Project Overview

Zotero-arXiv-Daily recommends new arXiv, bioRxiv, and medRxiv papers based on a user's Zotero library. It retrieves the user's Zotero corpus, fetches new papers from configured sources, reranks candidates, generates summaries via an OpenAI-compatible LLM API, and sends an HTML email through SMTP. It is designed to run from GitHub Actions.

## Commands

```powershell
# Run the application
uv run src/zotero_arxiv_daily/main.py

# Run tests, excluding slow tests by default
uv run pytest

# Run all tests, including slow tests
uv run pytest -m ""

# Run a single test
uv run pytest tests/test_utils.py::TestGlobMatch -v

# Install or sync dependencies
uv sync
```

No linter or formatter is currently configured.

## Architecture

The app follows a linear pipeline orchestrated by `Executor` in `src/zotero_arxiv_daily/executor.py`:

1. Fetch Zotero corpus through the pyzotero API.
2. Filter the corpus with optional `include_path` and `ignore_path` glob patterns.
3. Retrieve new papers from configured sources.
4. Rerank candidates with the configured reranker.
5. Generate TLDRs and affiliations through an OpenAI-compatible LLM API.
6. Render and send the email through SMTP.

Retrievers live in `src/zotero_arxiv_daily/retriever/` and register with `@register_retriever`.
Rerankers live in `src/zotero_arxiv_daily/reranker/` and register with `@register_reranker`.

Configuration uses Hydra and OmegaConf. `config/default.yaml` composes `config/base.yaml` plus `config/custom.yaml`. Environment variables are interpolated with `${oc.env:VAR_NAME,default}` syntax.

## Testing

Tests marked `slow` are skipped by default via `pyproject.toml`. Most tests use Python stubs and do not require networked services.

## Git Workflow

- Prefer small, working commits.
- Verify with `uv run pytest` before claiming completion.
- Do not overwrite user changes in the worktree.

## Agent skills

### Issue tracker

Issues and PRDs are tracked as local markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Triage uses the default five-label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repo: read root `CONTEXT.md` and `docs/adr/` when present. See `docs/agents/domain.md`.
