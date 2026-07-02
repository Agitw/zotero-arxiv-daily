import logging
import os
import sys

import dotenv
import hydra
from loguru import logger
from omegaconf import DictConfig

from zotero_arxiv_daily.executor import Executor

os.environ["TOKENIZERS_PARALLELISM"] = "false"
dotenv.load_dotenv()


@hydra.main(version_base=None, config_path="../../config", config_name="default")
def main(config: DictConfig):
    log_level = "DEBUG" if config.executor.debug else "INFO"
    logger.remove()
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    for logger_name in logging.root.manager.loggerDict:
        if "zotero_arxiv_daily" in logger_name:
            continue
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    executor = Executor(config)
    if not hasattr(executor.reranker, "prepare_corpus_embeddings"):
        raise ValueError("Configured reranker does not support corpus embedding cache preparation.")
    corpus = executor.filter_corpus(executor.fetch_zotero_corpus())
    executor.reranker.prepare_corpus_embeddings(corpus)
    logger.info(f"Prepared Zotero embedding cache for {len(corpus)} papers")


if __name__ == "__main__":
    main()
