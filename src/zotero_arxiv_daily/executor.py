from loguru import logger
from pyzotero import zotero
from omegaconf import DictConfig, ListConfig
from .utils import glob_match
from .retriever import get_retriever_cls
from .protocol import CorpusPaper
from .recommendation_funnel import RecommendationFunnel
from .recommendation_history import RecommendationHistory
from .zotero_local import fetch_local_zotero_corpus
from .feedback import FeedbackProfile, apply_feedback, fetch_github_issue_feedback, load_feedback_profile
import random
from datetime import datetime
from pathlib import Path
from .reranker import get_reranker_cls
from .reranker.base import apply_venue_bonuses
from .construct_email import render_email
from .utils import send_email
from openai import OpenAI
from tqdm import tqdm


def normalize_path_patterns(patterns: list[str] | ListConfig | None, config_key: str) -> list[str] | None:
    if patterns is None:
        return None

    if not isinstance(patterns, (list, ListConfig)):
        raise TypeError(
            f"config.zotero.{config_key} must be a list of glob patterns or null, "
            'for example ["2026/survey/**"]. Single strings are not supported.'
        )

    if any(not isinstance(pattern, str) for pattern in patterns):
        raise TypeError(f"config.zotero.{config_key} must contain only glob pattern strings.")

    return list(patterns)


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def select_papers_for_email(
    ranked_papers,
    max_paper_num: int,
    include_all_deepseek_score_at_least: float | None,
):
    top_limit = max(0, int(max_paper_num))
    if include_all_deepseek_score_at_least is None:
        return ranked_papers[:top_limit]
    threshold = float(include_all_deepseek_score_at_least)
    return [
        paper
        for index, paper in enumerate(ranked_papers)
        if index < top_limit
        or (
            paper.score_source == "deepseek"
            and paper.deepseek_score is not None
            and paper.deepseek_score >= threshold
        )
    ]


class Executor:
    def __init__(self, config:DictConfig):
        self.config = config
        self.include_path_patterns = normalize_path_patterns(config.zotero.include_path, "include_path")
        self.ignore_path_patterns = normalize_path_patterns(config.zotero.ignore_path, "ignore_path")
        self.retrievers = {
            source: get_retriever_cls(source)(config) for source in config.executor.source
        }
        self.reranker = get_reranker_cls(config.executor.reranker)(config)
        self.openai_client = None

    def get_openai_client(self):
        if self.openai_client is None:
            self.openai_client = OpenAI(api_key=self.config.llm.api.key, base_url=self.config.llm.api.base_url)
        return self.openai_client

    def fetch_zotero_corpus(self) -> list[CorpusPaper]:
        zotero_source = self.config.zotero.get("source", "api")
        if zotero_source == "auto":
            zotero_source = "api" if self.config.zotero.get("user_id") and self.config.zotero.get("api_key") else "local"
        if zotero_source == "local":
            return fetch_local_zotero_corpus(self.config.zotero.get("local_sqlite_path") or None)

        logger.info("Fetching zotero corpus")
        zot = zotero.Zotero(self.config.zotero.user_id, 'user', self.config.zotero.api_key)
        collections = zot.everything(zot.collections())
        collections = {c['key']:c for c in collections}
        corpus = zot.everything(zot.items(itemType='conferencePaper || journalArticle || preprint'))
        corpus = [c for c in corpus if c['data']['abstractNote'] != '']
        def get_collection_path(col_key:str) -> str:
            if p := collections[col_key]['data']['parentCollection']:
                return get_collection_path(p) + '/' + collections[col_key]['data']['name']
            else:
                return collections[col_key]['data']['name']
        for c in corpus:
            paths = [get_collection_path(col) for col in c['data']['collections']]
            c['paths'] = paths
        logger.info(f"Fetched {len(corpus)} zotero papers")
        return [CorpusPaper(
            title=c['data']['title'],
            abstract=c['data']['abstractNote'],
            added_date=datetime.strptime(c['data']['dateAdded'], '%Y-%m-%dT%H:%M:%SZ'),
            paths=c['paths']
        ) for c in corpus]
    
    def filter_corpus(self, corpus:list[CorpusPaper]) -> list[CorpusPaper]:
        if self.include_path_patterns:
            logger.info(f"Selecting zotero papers matching include_path: {self.include_path_patterns}")
            corpus = [
                c for c in corpus
                if any(
                    glob_match(path, pattern)
                    for path in c.paths
                    for pattern in self.include_path_patterns
                )
            ]
        if self.ignore_path_patterns:
            logger.info(f"Excluding zotero papers matching ignore_path: {self.ignore_path_patterns}")
            corpus = [
                c for c in corpus
                if not any(
                    glob_match(path, pattern)
                    for path in c.paths
                    for pattern in self.ignore_path_patterns
                )
            ]
        if self.include_path_patterns or self.ignore_path_patterns:
            samples = random.sample(corpus, min(5, len(corpus)))
            samples = '\n'.join([c.title + ' - ' + '\n'.join(c.paths) for c in samples])
            logger.info(f"Selected {len(corpus)} zotero papers:\n{samples}\n...")
        return corpus

    
    def run(self):
        funnel = RecommendationFunnel(self.config.executor.get("recommendation_funnel_path"))
        try:
            return self._run_pipeline(funnel)
        except Exception as exc:
            funnel.record_failure(exc)
            raise

    def _run_pipeline(self, funnel: RecommendationFunnel):
        corpus = self.fetch_zotero_corpus()
        corpus = self.filter_corpus(corpus)
        if len(corpus) == 0:
            funnel.observe("final", [])
            logger.error(f"No zotero papers found. Please check your zotero settings:\n{self.config.zotero}")
            return
        all_papers = []
        for source, retriever in self.retrievers.items():
            logger.info(f"Retrieving {source} papers...")
            papers = retriever.retrieve_papers()
            if len(papers) == 0:
                logger.info(f"No {source} papers found")
                continue
            logger.info(f"Retrieved {len(papers)} {source} papers")
            all_papers.extend(papers)
        logger.info(f"Total {len(all_papers)} papers retrieved from all sources")
        funnel.observe("retrieved", all_papers)
        history_path = self.config.executor.get("recommendation_history_path")
        recommendation_history = None
        if history_path:
            recommendation_history = RecommendationHistory(
                history_path,
                retention_days=int(self.config.executor.get("recommendation_history_days") or 60),
            )
            retrieved_count = len(all_papers)
            all_papers = recommendation_history.filter_unseen(all_papers)
            logger.info(
                f"Recommendation history removed {retrieved_count - len(all_papers)} already-sent papers; "
                f"{len(all_papers)} unseen papers remain"
            )
        funnel.observe("unseen", all_papers)
        reranked_papers = []
        if len(all_papers) > 0:
            rerank_candidate_num = self.config.executor.get("rerank_candidate_num")
            if rerank_candidate_num is not None:
                all_papers = all_papers[:rerank_candidate_num]
                logger.info(f"Limited rerank candidates to {len(all_papers)} papers")
            funnel.observe("rerank_candidates", all_papers)
            logger.info("Reranking papers...")
            reranked_papers = self.reranker.rerank(all_papers, corpus)
            funnel.record_llm_batches(getattr(self.reranker, "llm_batch_metrics", []))
            funnel.observe("semantic_ranked", reranked_papers)
            funnel.observe(
                "llm_selected",
                [paper for paper in reranked_papers if paper.llm_selection_reason],
            )
            funnel.observe(
                "llm_attempted",
                [paper for paper in reranked_papers if paper.llm_scoring_attempted],
            )
            funnel.observe(
                "llm_scored",
                [paper for paper in reranked_papers if paper.llm_scoring_succeeded],
            )
            funnel.observe(
                "llm_fallback",
                [
                    paper
                    for paper in reranked_papers
                    if paper.llm_scoring_attempted and not paper.llm_scoring_succeeded
                ],
            )
            reranked_papers = apply_venue_bonuses(
                reranked_papers,
                self.config.reranker.get("venue_bonuses"),
                minimum_deepseek_score=float(
                    self.config.reranker.get("venue_bonus_min_deepseek_score") or 6.0
                ),
            )
            funnel.observe("venue_bonus_ranked", reranked_papers)
            feedback_path = self.config.executor.get("feedback_path")
            feedback_profile = FeedbackProfile()
            if feedback_path:
                feedback_profile = load_feedback_profile(feedback_path)
                logger.info(f"Loaded recommendation feedback profile from {feedback_path}")
            github_feedback = fetch_github_issue_feedback(
                self.config.executor.get("feedback_github_repository"),
                self.config.executor.get("feedback_github_token"),
            )
            feedback_profile = self._merge_feedback_profiles(feedback_profile, github_feedback)
            reranked_papers = apply_feedback(reranked_papers, feedback_profile)
            funnel.observe("feedback_ranked", reranked_papers)
            ranked_count = len(reranked_papers)
            reranked_papers = select_papers_for_email(
                reranked_papers,
                self.config.executor.max_paper_num,
                self.config.executor.get("include_all_deepseek_score_at_least"),
            )
            extra_count = max(0, len(reranked_papers) - int(self.config.executor.max_paper_num))
            if extra_count:
                logger.info(
                    f"Included {extra_count} additional papers scoring at least "
                    f"{self.config.executor.include_all_deepseek_score_at_least} by DeepSeek "
                    f"after the top-{self.config.executor.max_paper_num} limit "
                    f"({ranked_count} ranked papers total)"
                )
            funnel.observe("final", reranked_papers)
            logger.info("Generating TLDR and affiliations...")
            openai_client = self.get_openai_client()
            if getattr(self.reranker, "llm_scoring_disabled", False):
                logger.warning(
                    "LLM rerank scoring is unavailable; generating TLDR and preserving retriever affiliations"
                )
                for p in reranked_papers:
                    p.generate_tldr(openai_client, self.config.llm)
            else:
                for p in tqdm(reranked_papers):
                    p.generate_tldr(openai_client, self.config.llm)
                    p.generate_affiliations(openai_client, self.config.llm)
        elif not self.config.executor.send_empty:
            funnel.observe("final", [])
            logger.info("No new papers found. No email will be sent.")
            return
        else:
            funnel.observe("final", [])
        logger.info("Sending email...")
        email_content = render_email(
            reranked_papers,
            feedback_endpoint=self.config.executor.get("feedback_endpoint"),
            feedback_secret=self.config.executor.get("feedback_secret"),
        )
        if self.config.executor.get("email_preview_path"):
            preview_path = Path(str(self.config.executor.email_preview_path))
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(email_content, encoding="utf-8")
            logger.info(f"Wrote email preview to {preview_path}")
        if as_bool(self.config.executor.get("skip_email")):
            logger.info("Skipping email send because executor.skip_email is true")
            return
        send_email(self.config, email_content)
        if recommendation_history is not None:
            recommendation_history.record(reranked_papers)
        funnel.observe("emailed", reranked_papers)
        logger.info("Email sent successfully")

    def _merge_feedback_profiles(self, base: FeedbackProfile, extra: FeedbackProfile) -> FeedbackProfile:
        return FeedbackProfile(
            paper_feedback={**base.paper_feedback, **extra.paper_feedback},
            positive_keywords=[*base.positive_keywords, *extra.positive_keywords],
            negative_keywords=[*base.negative_keywords, *extra.negative_keywords],
            preferred_venues=[*base.preferred_venues, *extra.preferred_venues],
            blocked_venues=[*base.blocked_venues, *extra.blocked_venues],
        )
