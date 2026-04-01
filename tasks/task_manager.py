"""
タスクファイル管理
記事生成結果を「投稿キット」として出力する。
ユーザーがコピペしてnote.com / X に投稿するための形式。
"""
import json
from datetime import datetime
from pathlib import Path

from shared.database import get_ready_articles, update_article_status

TASKS_FILE  = Path(__file__).parent / "pending_posts.json"
REPORT_DIR  = Path(__file__).parent.parent / "data" / "reports"


def export_pending_tasks(limit: int = 5) -> list[dict]:
    """
    DBの ready 状態の記事を pending_posts.json に書き出す。
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
            "tweet": article.summary,          # X投稿文
            "tags": article.hashtags,          # タグ5つ（#なし）
            "quality_score": article.quality_score,
            "status": "pending",
            "note_url": "",
            "posted_at": "",
        })

    data = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(tasks),
        "articles": tasks,
    }
    TASKS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {len(tasks)} 件を {TASKS_FILE} に書き出しました")
    return tasks


def export_posting_kit(limit: int = 5) -> None:
    """
    「投稿キット」をMarkdownファイルとして出力する。
    ユーザーがこれを見ながらnote / Xに投稿する。
    """
    articles = get_ready_articles(limit=limit)
    if not articles:
        print("投稿待ちの記事がありません。")
        return

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    report_path = REPORT_DIR / f"投稿キット_{date_str}.md"

    # 曜日ラベルのマッピング
    day_labels = [
        "月曜（Tips系）",
        "火曜（体験談系）",
        "水曜（note新記事公開）",
        "木曜（Tips系）",
        "金曜（体験談・気づき系）",
    ]

    lines = [
        f"# 投稿キット（{datetime.now().strftime('%Y年%m月%d日')}）",
        f"> 生成記事数: {len(articles)} 件\n",
        "## 今週の投稿スケジュール",
        "",
        "| 曜日 | 内容 |",
        "|---|---|",
        "| 月・木 | Tips系：すぐ使えるノウハウ投稿 |",
        "| 火・金 | 体験談・気づき系：実録・失敗談 |",
        "| 水 | note新記事公開＋告知投稿 |",
        "| 土 | リプ返信・エンゲージメント強化 |",
        "| 日 | 翌週のネタ仕込み・企画 |",
        "",
        "---\n",
    ]

    for i, article in enumerate(articles, 1):
        tags_str = "　".join([f"#{t.lstrip('#')}" for t in article.hashtags])
        day_label = day_labels[i - 1] if i <= len(day_labels) else f"記事 {i}"
        lines += [
            f"## 記事 {i}｜{day_label}",
            "",
            f"### タイトル",
            f"```",
            article.title,
            f"```",
            "",
            f"### タグ（5つ）",
            f"```",
            tags_str,
            f"```",
            "",
            f"### X投稿文（コピペ用）",
            f"```",
            article.summary,
            f"```",
            "",
            f"### 本文（note.comに貼り付け）",
            f"```markdown",
            article.body_markdown,
            f"```",
            "",
            f"---",
            "",
        ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ 投稿キットを出力しました:")
    print(f"   {report_path}")
    print(f"\n📋 このファイルを開いて、記事を1つずつnote / Xに投稿してください。\n")


def show_pending() -> None:
    """投稿待ち記事の一覧を表示する"""
    articles = get_ready_articles(limit=20)
    if not articles:
        print("\n投稿待ちの記事はありません\n")
        return

    print(f"\n📋 投稿待ち記事 ({len(articles)} 件)\n")
    for a in articles:
        tags = " ".join([f"#{t}" for t in a.hashtags])
        print(f"  [{a.id}] {a.title}")
        print(f"       {a.char_count}字 / スコア:{a.quality_score:.2f} / タグ: {tags}")
    print()


def sync_results_to_db() -> None:
    """pending_posts.json の投稿結果を DB に反映する"""
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
