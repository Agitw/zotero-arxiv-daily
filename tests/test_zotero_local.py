from datetime import datetime
import sqlite3

from zotero_arxiv_daily.zotero_local import fetch_local_zotero_corpus


def _make_local_zotero_db(path):
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.executescript(
        """
        create table itemTypes (itemTypeID integer primary key, typeName text not null);
        create table fields (fieldID integer primary key, fieldName text not null);
        create table items (
            itemID integer primary key,
            itemTypeID int not null,
            dateAdded timestamp not null,
            dateModified timestamp,
            clientDateModified timestamp,
            libraryID int,
            key text,
            version int,
            synced int
        );
        create table itemData (itemID int, fieldID int, valueID int, primary key (itemID, fieldID));
        create table itemDataValues (valueID integer primary key, value text);
        create table collections (
            collectionID integer primary key,
            collectionName text not null,
            parentCollectionID int,
            clientDateModified timestamp,
            libraryID int,
            key text,
            version int,
            synced int
        );
        create table collectionItems (collectionID int, itemID int, orderIndex int, primary key (collectionID, itemID));
        create table deletedItems (itemID integer primary key, dateDeleted timestamp);
        """
    )
    cur.executemany(
        "insert into itemTypes(itemTypeID, typeName) values (?, ?)",
        [(11, "conferencePaper"), (21, "journalArticle"), (30, "preprint"), (3, "book")],
    )
    cur.executemany(
        "insert into fields(fieldID, fieldName) values (?, ?)",
        [(1, "title"), (2, "abstractNote")],
    )
    cur.executemany(
        "insert into collections(collectionID, collectionName, parentCollectionID) values (?, ?, ?)",
        [(1, "Parent", None), (2, "Child", 1)],
    )
    cur.executemany(
        "insert into items(itemID, itemTypeID, dateAdded) values (?, ?, ?)",
        [
            (100, 21, "2026-07-03 08:00:00"),
            (101, 21, "2026-07-03 08:01:00"),
            (102, 21, "2026-07-03 08:02:00"),
            (103, 3, "2026-07-03 08:03:00"),
        ],
    )
    cur.executemany(
        "insert into itemDataValues(valueID, value) values (?, ?)",
        [
            (1, "Kept article"),
            (2, "A useful abstract."),
            (3, "Missing abstract"),
            (4, ""),
            (5, "Deleted article"),
            (6, "Deleted abstract."),
            (7, "Book title"),
            (8, "Book abstract."),
        ],
    )
    cur.executemany(
        "insert into itemData(itemID, fieldID, valueID) values (?, ?, ?)",
        [
            (100, 1, 1),
            (100, 2, 2),
            (101, 1, 3),
            (101, 2, 4),
            (102, 1, 5),
            (102, 2, 6),
            (103, 1, 7),
            (103, 2, 8),
        ],
    )
    cur.execute("insert into collectionItems(collectionID, itemID, orderIndex) values (2, 100, 0)")
    cur.execute("insert into deletedItems(itemID, dateDeleted) values (102, '2026-07-03 09:00:00')")
    con.commit()
    con.close()


def test_fetch_local_zotero_corpus_reads_articles_with_abstracts_and_paths(tmp_path):
    db_path = tmp_path / "zotero.sqlite"
    _make_local_zotero_db(db_path)

    corpus = fetch_local_zotero_corpus(db_path)

    assert len(corpus) == 1
    assert corpus[0].title == "Kept article"
    assert corpus[0].abstract == "A useful abstract."
    assert corpus[0].added_date == datetime(2026, 7, 3, 8, 0, 0)
    assert corpus[0].paths == ["Parent/Child"]
