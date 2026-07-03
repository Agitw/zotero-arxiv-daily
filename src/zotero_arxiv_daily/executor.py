from loguru import logger
from pyzotero import zotero
from omegaconf import DictConfig, ListConfig
from .utils import glob_match
from .retriever import get_retriever_cls
from .protocol import CorpusPaper, chinese_tldr_unavailable_message, is_chinese_language
from .zotero_local import fetch_local_zotero_corpus
import random
from datetime import datetime
from pathlib import Path
from .reranker import get_reranker_cls
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
        corpus = self.fetch_zotero_corpus()
        corpus = self.filter_corpus(corpus)
        if len(corpus) == 0:
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
        reranked_papers = []
        if len(all_papers) > 0:
            rerank_candidate_num = self.config.executor.get("rerank_candidate_num")
            if rerank_candidate_num is not None:
                all_papers = all_papers[:rerank_candidate_num]
                logger.info(f"Limited rerank candidates to {len(all_papers)} papers")
            logger.info("Reranking papers...")
            reranked_papers = self.reranker.rerank(all_papers, corpus)
            reranked_papers = reranked_papers[:self.config.executor.max_paper_num]
            logger.info("Generating TLDR and affiliations...")
            if getattr(self.reranker, "llm_scoring_disabled", False):
                logger.warning("Skipping LLM TLDR generation because LLM scoring is unavailable")
                for p in reranked_papers:
                    if is_chinese_language(self.config.llm.get("language")):
                        p.tldr = chinese_tldr_unavailable_message()
                    else:
                        p.tldr = p.abstract
                    p.affiliations = None
            else:
                openai_client = self.get_openai_client()
                for p in tqdm(reranked_papers):
                    p.generate_tldr(openai_client, self.config.llm)
                    p.generate_affiliations(openai_client, self.config.llm)
        elif not self.config.executor.send_empty:
            logger.info("No new papers found. No email will be sent.")
            return
        logger.info("Sending email...")
        email_content = render_email(reranked_papers)
        if self.config.executor.get("email_preview_path"):
            preview_path = Path(str(self.config.executor.email_preview_path))
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(email_content, encoding="utf-8")
            logger.info(f"Wrote email preview to {preview_path}")
        if as_bool(self.config.executor.get("skip_email")):
            logger.info("Skipping email send because executor.skip_email is true")
            return
        send_email(self.config, email_content)
        logger.info("Email sent successfully")
