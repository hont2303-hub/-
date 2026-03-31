"""
note.com 自動投稿システム エントリーポイント

使用方法:
    # 1サイクルを今すぐ実行
    python main.py

    # ドライランモード（投稿しない）
    python main.py --dry-run

    # スケジューラを起動（毎日POST_TIMEに自動実行）
    python main.py --schedule

    # 特定のエージェントのみ実行
    python main.py --step analyze   # 分析担当のみ
    python main.py --step write     # 文章作成のみ
    python main.py --step image     # 画像生成のみ
    python main.py --step post      # note投稿のみ
    python main.py --step tweet     # X投稿のみ
"""
import argparse
import asyncio
import sys
from loguru import logger

from shared.database import init_db


def setup_logging() -> None:
    """ログ設定を初期化する"""
    from pathlib import Path
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")
    logger.add(
        "logs/note_automation_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="1 day",
        retention="30 days",
        encoding="utf-8",
    )


async def run_step(step: str, dry_run: bool = False) -> None:
    """特定のステップのみを実行する"""
    init_db()

    if step == "analyze":
        from agents.分析担当.agent import run
        await run()

    elif step == "write":
        from agents.文章作成.agent import run
        await run()

    elif step == "image":
        from agents.画像図解作成担当.agent import run
        await run()

    elif step == "post":
        from shared.database import get_ready_articles, update_article_status, get_images_for_article
        from browser.playwright_manager import get_browser, get_context
        from note投稿.note_login import ensure_note_login
        from note投稿.note_publisher import publish_article

        articles = get_ready_articles()
        if not articles:
            logger.warning("投稿可能な記事がありません")
            return

        async with get_browser() as browser:
            async with get_context("note", browser) as context:
                page = await ensure_note_login(context)
                for article in articles:
                    images = get_images_for_article(article.id)
                    note_url = await publish_article(page, article, images, dry_run=dry_run)
                    status = "posted" if note_url else "failed"
                    update_article_status(article.id, status, note_url)
                    logger.info(f"{'投稿完了' if note_url else '投稿失敗'}: {article.title}")

    elif step == "tweet":
        from agents.X投稿.agent import run
        await run(dry_run=dry_run)

    else:
        logger.error(f"不明なステップ: {step}")
        logger.info("使用可能なステップ: analyze / write / image / post / tweet")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="note.com 自動投稿システム")
    parser.add_argument("--dry-run", action="store_true", help="投稿をスキップする（テスト用）")
    parser.add_argument("--schedule", action="store_true", help="スケジューラを起動する")
    parser.add_argument(
        "--step",
        choices=["analyze", "write", "image", "post", "tweet"],
        help="特定のステップのみ実行する",
    )
    args = parser.parse_args()

    setup_logging()

    if args.dry_run:
        logger.info("ドライランモードで実行します（実際の投稿は行いません）")

    if args.schedule:
        from orchestrator.scheduler import start_scheduler
        start_scheduler(dry_run=args.dry_run)

    elif args.step:
        asyncio.run(run_step(args.step, dry_run=args.dry_run))

    else:
        from orchestrator.workflow import run_full_cycle
        stats = asyncio.run(run_full_cycle(dry_run=args.dry_run))
        logger.info(f"完了: {stats}")


if __name__ == "__main__":
    main()
