"""
note.com 自動投稿システム エントリーポイント

## 使い方

### ① 記事を生成する（ブラウザ不要・Claude API使用）
    python main.py --generate

### ② 投稿待ち記事をタスクファイルに書き出す
    python main.py --export

### ③ 投稿待ち記事の一覧を確認する
    python main.py --show-pending

### ④ Claudeが投稿した結果をDBに反映する
    python main.py --sync

### ⑤ 生成＋エクスポートを一括実行
    python main.py --generate --export

### ⑥ 記事数を指定して生成
    python main.py --generate --count 3

---

## Claude for Chrome での投稿手順

1. python main.py --generate --export  # 記事生成 & タスクファイル出力
2. claude --chrome                      # Claude Code + Chrome を起動
3. 「pending_posts.jsonの記事をnoteに投稿してください」と指示
4. python main.py --sync                # 投稿結果をDBに反映
"""
import argparse
import asyncio
import sys
from loguru import logger

from shared.database import init_db


def setup_logging() -> None:
    from pathlib import Path
    Path("logs").mkdir(exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")
    logger.add(
        "logs/note_automation_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="1 day",
        retention="30 days",
        encoding="utf-8",
    )


async def run_generate(count: int) -> None:
    """記事を生成してDBに保存する（ブラウザ不要）"""
    init_db()

    # STEP 1: トピック分析
    logger.info("【STEP 1/2】分析担当: トピックを生成します")
    from agents.分析担当.trend_analyzer import analyze_trends
    from agents.分析担当.note_scraper import format_articles_for_analysis
    from shared.database import insert_topic, get_pending_topics

    # noteのスクレイピングは省略してClaude APIでトピック直接生成
    articles_text = format_articles_for_analysis([])  # フォールバックトピックを使用
    topics = analyze_trends(articles_text)
    for topic in topics:
        insert_topic(topic)
    logger.info(f"  → {len(topics)} 件のトピックを生成しました")

    # STEP 2: 記事生成
    logger.info(f"【STEP 2/2】文章作成: {count} 件の記事を生成します")
    from agents.文章作成.agent import run as run_writer
    articles = await run_writer(count=count)
    logger.info(f"  → {len(articles)} 件の記事を生成しました")

    print(f"\n✅ 完了: {len(articles)} 件の記事を生成しました")
    print("次のステップ: python main.py --export  でタスクファイルを出力してください\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="note.com 自動投稿システム",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--generate", action="store_true", help="記事を生成する（Claude API使用）")
    parser.add_argument("--kit",      action="store_true", help="投稿キット（タイトル/本文/タグ/X文）を1ファイルに出力")
    parser.add_argument("--export",   action="store_true", help="投稿待ち記事をtasks/pending_posts.jsonに書き出す")
    parser.add_argument("--show-pending", action="store_true", help="投稿待ち記事の一覧を表示")
    parser.add_argument("--sync",     action="store_true", help="投稿済みURLをDBに反映する")
    parser.add_argument("--count",    type=int, default=5, help="生成する記事数（デフォルト: 5）")
    parser.add_argument("--schedule", action="store_true", help="スケジューラを起動（毎日POST_TIMEに自動生成）")
    args = parser.parse_args()

    setup_logging()
    init_db()

    if not any([args.generate, args.kit, args.export, args.show_pending, args.sync, args.schedule]):
        parser.print_help()
        print("\n💡 まずは: python main.py --generate --kit")
        return

    if args.generate:
        asyncio.run(run_generate(count=args.count))

    if args.kit:
        from tasks.task_manager import export_posting_kit
        export_posting_kit(limit=args.count)

    if args.export:
        from tasks.task_manager import export_pending_tasks
        export_pending_tasks(limit=args.count)

    if args.show_pending:
        from tasks.task_manager import show_pending
        show_pending()

    if args.sync:
        from tasks.task_manager import sync_results_to_db
        sync_results_to_db()

    if args.schedule:
        from orchestrator.scheduler import start_scheduler
        start_scheduler()


if __name__ == "__main__":
    main()
