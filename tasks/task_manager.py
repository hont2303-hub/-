"""
タスクファイル管理
Python（記事生成）と Claude for Chrome（ブラウザ操作）の橋渡し役。
pending_posts.json に投稿待ち記事を書き出し、Claude が読み込んで投稿する。
"""
import json
from datetime import datetime
from pathlib import Path

from shared.models import Article
from shared.database import get_ready_articles, update_article_status

TASKS_FILE = Path(__file__).parent / "pending_posts.json"


def export_pending_tasks(limit: int = 5) -> list[dict]:
    """
    DBの ready 状態の記事を読み込み、pending_posts.json に書き出す。
    Claude for Chrome がこのファイルを読んで投稿を実行する。
    """
    articles = get_ready_articles(limit=limit)
    if not articles:
        print("投稿待ちの記事がありません。先に python main.py --generate を実行してください。")
        return []

    tasks = []
    for article in articles:
        tasks.append({
            "id": article.id,
            "title": article.title,
            "body_markdown": article.body_markdown,
            "summary": article.summary,
            "hashtags": article.hashtags,
            "status": "pending",
            "image_path": "",
            "note_url": "",
            "posted_at": "",
        })

    data = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(tasks),
        "articles": tasks,
    }
    TASKS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {len(tasks)} 件の記事を {TASKS_FILE} に書き出しました")
    return tasks


def show_pending() -> None:
    """投稿待ち記事の一覧を表示する"""
    articles = get_ready_articles(limit=20)
    if not articles:
        print("投稿待ちの記事はありません")
        return

    print(f"\n📋 投稿待ち記事 ({len(articles)} 件)\n")
    for a in articles:
        print(f"  [{a.id}] {a.title}")
        print(f"       文字数: {a.char_count}字 / スコア: {a.quality_score:.2f} / ステータス: {a.status}")
    print()

    if TASKS_FILE.exists():
        data = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        print(f"📄 タスクファイル最終更新: {data.get('exported_at', '不明')}")
        posted = sum(1 for a in data.get("articles", []) if a["status"] == "posted")
        pending = sum(1 for a in data.get("articles", []) if a["status"] == "pending")
        print(f"   投稿済み: {posted} 件 / 未投稿: {pending} 件\n")


def sync_results_to_db() -> None:
    """
    pending_posts.json の投稿結果を DB に反映する。
    Claude が投稿完了後に status を更新したファイルを読み込む。
    """
    if not TASKS_FILE.exists():
        print("タスクファイルが見つかりません")
        return

    data = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    synced = 0
    for article in data.get("articles", []):
        if article["status"] == "posted" and article.get("note_url"):
            update_article_status(
                article_id=article["id"],
                status="posted",
                note_url=article["note_url"],
            )
            synced += 1

    print(f"✅ {synced} 件の投稿結果をDBに反映しました")
