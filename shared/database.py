"""
SQLite接続・テーブル初期化・CRUD操作
全エージェントがこのモジュールを通じてデータを共有する
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional
from loguru import logger

from shared.models import Topic, Article, Image, XPost

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "note_automation.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 並列書き込み対応
    return conn


def init_db() -> None:
    """テーブルを初期化（存在しない場合のみ作成）"""
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS topics (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                keywords    TEXT    NOT NULL DEFAULT '[]',
                tags        TEXT    NOT NULL DEFAULT '[]',
                reason      TEXT    DEFAULT '',
                priority    INTEGER DEFAULT 5,
                status      TEXT    DEFAULT 'pending',
                source_urls TEXT    DEFAULT '[]',
                created_at  TEXT    DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS articles (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id        INTEGER REFERENCES topics(id),
                title           TEXT    NOT NULL,
                body_markdown   TEXT    NOT NULL,
                summary         TEXT    DEFAULT '',
                hashtags        TEXT    DEFAULT '[]',
                quality_score   REAL    DEFAULT 0.0,
                status          TEXT    DEFAULT 'draft',
                note_url        TEXT    DEFAULT '',
                created_at      TEXT    DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS images (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id      INTEGER REFERENCES articles(id),
                file_path       TEXT    NOT NULL,
                description     TEXT    DEFAULT '',
                insert_position TEXT    DEFAULT '',
                created_at      TEXT    DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS x_posts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id  INTEGER REFERENCES articles(id),
                tweet_text  TEXT    NOT NULL,
                status      TEXT    DEFAULT 'pending',
                posted_at   TEXT    DEFAULT '',
                error_msg   TEXT    DEFAULT ''
            );
        """)
    conn.close()
    logger.info(f"データベースを初期化しました: {DB_PATH}")


# ── Topics ──────────────────────────────────────────────

def insert_topic(topic: Topic) -> int:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """INSERT INTO topics (title, keywords, tags, reason, priority, status, source_urls)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (topic.title, topic.keywords_json(), topic.tags_json(),
             topic.reason, topic.priority, topic.status, topic.source_urls_json())
        )
        topic.id = cur.lastrowid
    conn.close()
    return topic.id


def get_pending_topics(limit: int = 10) -> list[Topic]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM topics WHERE status='pending' ORDER BY priority ASC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [_row_to_topic(r) for r in rows]


def update_topic_status(topic_id: int, status: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE topics SET status=?, updated_at=datetime('now','localtime') WHERE id=?",
            (status, topic_id)
        )
    conn.close()


def _row_to_topic(row: sqlite3.Row) -> Topic:
    return Topic(
        id=row["id"],
        title=row["title"],
        keywords=json.loads(row["keywords"]),
        tags=json.loads(row["tags"]),
        reason=row["reason"],
        priority=row["priority"],
        status=row["status"],
        source_urls=json.loads(row["source_urls"]),
        created_at=row["created_at"],
    )


# ── Articles ─────────────────────────────────────────────

def insert_article(article: Article) -> int:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """INSERT INTO articles (topic_id, title, body_markdown, summary, hashtags, quality_score, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (article.topic_id, article.title, article.body_markdown,
             article.summary, article.hashtags_json(),
             article.quality_score, article.status)
        )
        article.id = cur.lastrowid
    conn.close()
    return article.id


def get_ready_articles(limit: int = 5) -> list[Article]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM articles WHERE status='ready' ORDER BY created_at ASC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [_row_to_article(r) for r in rows]


def update_article_status(article_id: int, status: str, note_url: str = "") -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE articles SET status=?, note_url=? WHERE id=?",
            (status, note_url, article_id)
        )
    conn.close()


def get_article_by_id(article_id: int) -> Optional[Article]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    conn.close()
    return _row_to_article(row) if row else None


def _row_to_article(row: sqlite3.Row) -> Article:
    return Article(
        id=row["id"],
        topic_id=row["topic_id"],
        title=row["title"],
        body_markdown=row["body_markdown"],
        summary=row["summary"],
        hashtags=json.loads(row["hashtags"]),
        quality_score=row["quality_score"],
        status=row["status"],
        note_url=row["note_url"],
        created_at=row["created_at"],
    )


# ── Images ───────────────────────────────────────────────

def insert_image(image: Image) -> int:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """INSERT INTO images (article_id, file_path, description, insert_position)
               VALUES (?, ?, ?, ?)""",
            (image.article_id, image.file_path, image.description, image.insert_position)
        )
        image.id = cur.lastrowid
    conn.close()
    return image.id


def get_images_for_article(article_id: int) -> list[Image]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM images WHERE article_id=?", (article_id,)
    ).fetchall()
    conn.close()
    return [_row_to_image(r) for r in rows]


def _row_to_image(row: sqlite3.Row) -> Image:
    return Image(
        id=row["id"],
        article_id=row["article_id"],
        file_path=row["file_path"],
        description=row["description"],
        insert_position=row["insert_position"],
        created_at=row["created_at"],
    )


# ── X Posts ──────────────────────────────────────────────

def insert_x_post(xpost: XPost) -> int:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "INSERT INTO x_posts (article_id, tweet_text, status) VALUES (?, ?, ?)",
            (xpost.article_id, xpost.tweet_text, xpost.status)
        )
        xpost.id = cur.lastrowid
    conn.close()
    return xpost.id


def update_x_post_status(xpost_id: int, status: str, posted_at: str = "", error_msg: str = "") -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE x_posts SET status=?, posted_at=?, error_msg=? WHERE id=?",
            (status, posted_at, error_msg, xpost_id)
        )
    conn.close()
