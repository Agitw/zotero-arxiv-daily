from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3
import tempfile

from loguru import logger

from .protocol import CorpusPaper

SUPPORTED_ITEM_TYPES = {"conferencePaper", "journalArticle", "preprint"}
SUPPORTED_FIELDS = {"title", "abstractNote"}


def default_zotero_sqlite_path() -> Path:
    return Path.home() / "Zotero" / "zotero.sqlite"


@contextmanager
def _sqlite_snapshot(sqlite_path: Path):
    with tempfile.TemporaryDirectory(prefix="zotero-sqlite-") as tmp_dir:
        snapshot_path = Path(tmp_dir) / "zotero.sqlite"
        shutil.copy2(sqlite_path, snapshot_path)
        for suffix in ("-wal", "-shm"):
            sidecar = sqlite_path.with_name(sqlite_path.name + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, snapshot_path.with_name(snapshot_path.name + suffix))
        yield snapshot_path


def _parse_zotero_datetime(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return datetime.fromisoformat(value)


def _collection_paths(cur: sqlite3.Cursor) -> dict[int, str]:
    collections = {
        row[0]: {"name": row[1], "parent": row[2]}
        for row in cur.execute(
            "select collectionID, collectionName, parentCollectionID from collections"
        )
    }

    def path_for(collection_id: int, seen: set[int] | None = None) -> str:
        seen = seen or set()
        if collection_id in seen or collection_id not in collections:
            return ""
        seen.add(collection_id)
        collection = collections[collection_id]
        parent_id = collection["parent"]
        if parent_id is None:
            return collection["name"]
        parent_path = path_for(parent_id, seen)
        return f"{parent_path}/{collection['name']}" if parent_path else collection["name"]

    return {collection_id: path_for(collection_id) for collection_id in collections}


def fetch_local_zotero_corpus(sqlite_path: str | Path | None = None) -> list[CorpusPaper]:
    source_path = Path(sqlite_path).expanduser() if sqlite_path else default_zotero_sqlite_path()
    if not source_path.exists():
        raise FileNotFoundError(f"Zotero SQLite database not found: {source_path}")

    logger.info(f"Fetching local Zotero corpus from {source_path}")
    with _sqlite_snapshot(source_path) as snapshot_path:
        con = sqlite3.connect(f"file:{snapshot_path.as_posix()}?mode=ro", uri=True)
        try:
            cur = con.cursor()
            collection_paths = _collection_paths(cur)
            item_paths: dict[int, list[str]] = {}
            for collection_id, item_id in cur.execute("select collectionID, itemID from collectionItems"):
                path = collection_paths.get(collection_id)
                if path:
                    item_paths.setdefault(item_id, []).append(path)

            rows = cur.execute(
                """
                select i.itemID, i.dateAdded, it.typeName, f.fieldName, v.value
                from items i
                join itemTypes it on it.itemTypeID = i.itemTypeID
                join itemData d on d.itemID = i.itemID
                join fields f on f.fieldID = d.fieldID
                join itemDataValues v on v.valueID = d.valueID
                left join deletedItems di on di.itemID = i.itemID
                where di.itemID is null
                """
            ).fetchall()
        finally:
            con.close()

    grouped: dict[int, dict[str, object]] = {}
    for item_id, date_added, item_type, field_name, value in rows:
        if item_type not in SUPPORTED_ITEM_TYPES or field_name not in SUPPORTED_FIELDS:
            continue
        item = grouped.setdefault(
            item_id,
            {
                "date_added": date_added,
                "fields": {},
                "paths": sorted(item_paths.get(item_id, [])),
            },
        )
        item["fields"][field_name] = value

    corpus = []
    for item in grouped.values():
        fields = item["fields"]
        title = str(fields.get("title") or "").strip()
        abstract = str(fields.get("abstractNote") or "").strip()
        if not title or not abstract:
            continue
        corpus.append(
            CorpusPaper(
                title=title,
                abstract=abstract,
                added_date=_parse_zotero_datetime(str(item["date_added"])),
                paths=list(item["paths"]),
            )
        )

    corpus.sort(key=lambda paper: paper.added_date, reverse=True)
    logger.info(f"Fetched {len(corpus)} local Zotero papers")
    return corpus
