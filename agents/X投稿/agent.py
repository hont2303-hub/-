"""
X投稿エージェント
投稿済みのnote記事をX（Twitter）で拡散する
"""
import asyncio
from loguru import logger

from browser.playwright_manager import get_browser, get_context
from agents.X投稿.x_publisher import run_for_article
from shared.database import get_ready_articles, insert_x_post, update_x_post_status
from shared.models import Article, XPost
from config.settings import get_settings


async def run(
    articles: list[Article] | None = None,
    dry_run: bool = False,
) -> list[XPost]:
    """
    X投稿エージェントを実行する。
    articles: 対象記事リスト（Noneの場合はDBからposted状態の記事を取得）
    dry_run: Trueの場合は実際には投稿しない
    返り値: XPostのリスト
    """
    logger.info("=== X投稿エージェント 開始 ===")

    if articles is None:
        # note_urlが設定されているready→posted記事を取得
        from shared.database import get_connection
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM articles WHERE status='posted' AND note_url != '' ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        conn.close()
        from shared.database import _row_to_article
        articles = [_row_to_article(r) for r in rows]

    if not articles:
        logger.warning("X投稿対象の記事がありません（note_urlが設定されている記事が必要）")
        return []

    all_xposts: list[XPost] = []

    async with get_browser() as browser:
        async with get_context("x", browser) as context:
            for article in articles:
                if not article.note_url:
                    logger.warning(f"note_urlが未設定のためスキップ: '{article.title}'")
                    continue

                xpost = await run_for_article(context, article, dry_run=dry_run)

                # DBに保存
                xpost_id = insert_x_post(xpost)
                xpost.id = xpost_id
                update_x_post_status(xpost_id, xpost.status, xpost.posted_at, xpost.error_msg)
                all_xposts.append(xpost)

                logger.info(f"X投稿結果 [{xpost_id}]: {xpost.status} - {article.title}")

                # 連続投稿の間隔を空ける
                if len(articles) > 1:
                    await asyncio.sleep(10)

    logger.info(f"=== X投稿エージェント 完了: {len(all_xposts)} 件を処理 ===")
    return all_xposts


if __name__ == "__main__":
    asyncio.run(run())
