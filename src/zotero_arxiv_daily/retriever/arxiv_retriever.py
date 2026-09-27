from .base import BaseRetriever, SourceRetrievalError, register_retriever
import arxiv
from arxiv import Result as ArxivResult
from ..protocol import Paper
from ..utils import extract_markdown_from_pdf, extract_tex_code_from_tar
from tempfile import TemporaryDirectory
import feedparser
from tqdm import tqdm
import multiprocessing
import os
from queue import Empty
from time import sleep
from typing import Any, Callable, TypeVar
from loguru import logger
import requests
from datetime import datetime

T = TypeVar("T")

DOWNLOAD_TIMEOUT = (10, 60)
PDF_EXTRACT_TIMEOUT = 180
TAR_EXTRACT_TIMEOUT = 180
SUBPROCESS_START_TIMEOUT = 30


def _download_file(url: str, path: str) -> None:
    with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as response:
        response.raise_for_status()
        with open(path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)


def _run_in_subprocess(
    result_queue: Any,
    func: Callable[..., T | None],
    args: tuple[Any, ...],
) -> None:
    try:
        result_queue.put(("started", None))
        result_queue.put(("ok", func(*args)))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _run_with_hard_timeout(
    func: Callable[..., T | None],
    args: tuple[Any, ...],
    *,
    timeout: float,
    operation: str,
    paper_title: str,
) -> T | None:
    start_methods = multiprocessing.get_all_start_methods()
    context = multiprocessing.get_context("fork" if "fork" in start_methods else start_methods[0])
    result_queue = context.Queue()
    process = context.Process(target=_run_in_subprocess, args=(result_queue, func, args))
    process.start()

    try:
        status, payload = result_queue.get(timeout=SUBPROCESS_START_TIMEOUT)
        if status != "started":
            raise ValueError(f"Unexpected subprocess status before start: {status}")
        status, payload = result_queue.get(timeout=timeout)
    except Empty:
        if process.is_alive():
            process.kill()
        process.join(5)
        result_queue.close()
        result_queue.join_thread()
        logger.warning(f"{operation} timed out for {paper_title} after {timeout} seconds")
        return None

    process.join(5)
    result_queue.close()
    result_queue.join_thread()

    if status == "ok":
        return payload

    logger.warning(f"{operation} failed for {paper_title}: {payload}")
    return None


def _extract_text_from_pdf_worker(pdf_url: str) -> str:
    with TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, "paper.pdf")
        _download_file(pdf_url, path)
        return extract_markdown_from_pdf(path)


def _extract_text_from_html_worker(html_url: str) -> str | None:
    import trafilatura

    downloaded = trafilatura.fetch_url(html_url)
    if downloaded is None:
        raise ValueError(f"Failed to download HTML from {html_url}")
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    if not text:
        raise ValueError(f"No text extracted from {html_url}")
    return text


def _extract_text_from_tar_worker(source_url: str, paper_id: str, paper_title: str | None = None) -> str | None:
    with TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, "paper.tar.gz")
        _download_file(source_url, path)
        file_contents = extract_tex_code_from_tar(path, paper_id, paper_title=paper_title)
        if not file_contents or "all" not in file_contents:
            raise ValueError("Main tex file not found.")
        return file_contents["all"]


@register_retriever("arxiv")
class ArxivRetriever(BaseRetriever):
    def __init__(self, config):
        super().__init__(config)
        if self.config.source.arxiv.category is None:
            raise ValueError("category must be specified for arxiv.")

    def _retrieve_raw_papers(self) -> list[ArxivResult | Paper]:
        client = arxiv.Client(num_retries=2, delay_seconds=3)
        query = '+'.join(self.config.source.arxiv.category)
        include_cross_list = self.config.source.arxiv.get("include_cross_list", False)
        # Get the latest paper from arxiv rss feed
        feed = feedparser.parse(f"https://rss.arxiv.org/atom/{query}")
        if 'Feed error for query' in feed.feed.get("title", ""):
            raise ValueError(f"Invalid ARXIV_QUERY: {query}.")
        if feed.get("status", 200) >= 400 or feed.get("bozo") or not feed.feed.get("title"):
            raise SourceRetrievalError(f"arXiv RSS feed is unavailable or invalid for {query}")
        raw_papers = []
        allowed_announce_types = {"new", "cross"} if include_cross_list else {"new"}
        entries_by_id = {
            entry.id.removeprefix("oai:arXiv.org:"): entry
            for entry in feed.entries
            if entry.get("arxiv_announce_type", "new") in allowed_announce_types
        }
        all_paper_ids = list(entries_by_id)
        if self.config.executor.debug:
            all_paper_ids = all_paper_ids[:10]

        # Get full information of each paper from arxiv api
        api_unavailable = False
        with tqdm(total=len(all_paper_ids)) as bar:
            for i in range(0, len(all_paper_ids), 20):
                ids = all_paper_ids[i:i + 20]
                search = arxiv.Search(id_list=ids, max_results=len(ids))
                if not api_unavailable:
                    try:
                        # The client already retries; avoid nested retry storms.
                        batch = list(client.results(search))
                        if not batch:
                            raise SourceRetrievalError("arXiv API returned no metadata for RSS paper IDs")
                    except (
                        arxiv.HTTPError,
                        arxiv.UnexpectedEmptyPageError,
                        requests.RequestException,
                        SourceRetrievalError,
                    ) as exc:
                        if isinstance(exc, arxiv.HTTPError) and exc.status not in {406, 429, 500, 502, 503, 504}:
                            raise
                        warning = (
                            f"arXiv API unavailable ({type(exc).__name__}: {exc}); "
                            "using RSS metadata for remaining papers"
                        )
                        self.retrieval_warnings.append(warning)
                        logger.warning(warning)
                        api_unavailable = True
                if api_unavailable:
                    batch = [self._paper_from_rss(entries_by_id[paper_id]) for paper_id in ids]
                bar.update(len(batch))
                raw_papers.extend(batch)
                if not api_unavailable and i + 20 < len(all_paper_ids):
                    sleep(3)

        return raw_papers

    def _paper_from_rss(self, entry: feedparser.FeedParserDict) -> Paper:
        paper_id = entry.id.removeprefix("oai:arXiv.org:")
        abstract = entry.get("summary", "").partition("Abstract:")[2].strip()
        published = entry.get("published", "")
        try:
            datetime.fromisoformat(published.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise SourceRetrievalError(f"arXiv RSS entry {paper_id} has no valid announcement date") from exc
        if not entry.get("title") or not abstract:
            raise SourceRetrievalError(f"arXiv RSS entry {paper_id} has no title or abstract")
        return Paper(
            source=self.name,
            title=entry.title,
            authors=[name.strip() for name in entry.get("author", "").split(",") if name.strip()],
            abstract=abstract,
            url=f"https://arxiv.org/abs/{paper_id}",
            pdf_url=f"https://arxiv.org/pdf/{paper_id}",
            full_text=None,
            venue="arXiv",
            published_date=published,
        )

    def convert_to_paper(self, raw_paper: ArxivResult | Paper) -> Paper:
        if isinstance(raw_paper, Paper):
            return raw_paper
        title = raw_paper.title
        authors = [a.name for a in raw_paper.authors]
        abstract = raw_paper.summary
        pdf_url = raw_paper.pdf_url
        full_text = extract_text_from_tar(raw_paper)
        if full_text is None:
            full_text = extract_text_from_html(raw_paper)
        if full_text is None:
            full_text = extract_text_from_pdf(raw_paper)
        return Paper(
            source=self.name,
            title=title,
            authors=authors,
            abstract=abstract,
            url=raw_paper.entry_id,
            pdf_url=pdf_url,
            full_text=full_text,
            venue="arXiv",
            published_date=raw_paper.published.date().isoformat() if hasattr(raw_paper.published, "date") else str(raw_paper.published),
        )


def extract_text_from_html(paper: ArxivResult) -> str | None:
    html_url = paper.entry_id.replace("/abs/", "/html/")
    try:
        return _extract_text_from_html_worker(html_url)
    except Exception as exc:
        logger.warning(f"HTML extraction failed for {paper.title}: {exc}")
        return None


def extract_text_from_pdf(paper: ArxivResult) -> str | None:
    if paper.pdf_url is None:
        logger.warning(f"No PDF URL available for {paper.title}")
        return None
    return _run_with_hard_timeout(
        _extract_text_from_pdf_worker,
        (paper.pdf_url,),
        timeout=PDF_EXTRACT_TIMEOUT,
        operation="PDF extraction",
        paper_title=paper.title,
    )


def extract_text_from_tar(paper: ArxivResult) -> str | None:
    source_url = paper.source_url()
    if source_url is None:
        logger.warning(f"No source URL available for {paper.title}")
        return None
    return _run_with_hard_timeout(
        _extract_text_from_tar_worker,
        (source_url, paper.entry_id, paper.title),
        timeout=TAR_EXTRACT_TIMEOUT,
        operation="Tar extraction",
        paper_title=paper.title,
    )
