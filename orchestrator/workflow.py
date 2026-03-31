"""
全体ワークフロー制御
分析→執筆→画像作成→note投稿→X投稿 の1サイクルを実行する
"""
import asyncio
from loguru import logger

from config.settings import get_settings
from shared.database import init_db, get_ready_articles, update_article_status, get_images_for_article
from browser.playwright_manager import get_browser, get_context
from note投稿.note_login import ensure_note_login
from note投稿.note_publisher import publish_article


async def run_full_cycle(dry_run: bool = False) -> dict:
    """
    1サイクル分のワークフローを実行する。
    dry_run=True の場合は実際の投稿を行わない。

    返り値: {
        "topics": 生成トピック数,
        "articles": 生成記事数,
        "images": 生成画像数,
        "posted": note投稿成功数,
        "tweeted": X投稿成功数,
    }
    """
    settings = get_settings()
    stats = {"topics": 0, "articles": 0, "images": 0, "posted": 0, "tweeted": 0}

    logger.info("=" * 60)
    logger.info(f"note自動投稿システム 1サイクル開始 (dry_run={dry_run})")
    logger.info(f"目標記事数: {settings.articles_per_day}記事/日")
    logger.info("=" * 60)

    # DBを初期化
    init_db()

    # ─── STEP 1: 分析担当 ─────────────────────────
    logger.info("【STEP 1/5】分析担当: noteトレンドを収集してトピックを生成します")
    try:
        from agents.分析担当.agent import run as run_analyst
        topics = await run_analyst(target_count=settings.articles_per_day)
        stats["topics"] = len(topics)
        logger.info(f"STEP 1 完了: {stats['topics']} 件のトピックを生成")
    except Exception as e:
        logger.error(f"STEP 1 エラー: {e}")

    # ─── STEP 2: 文章作成担当 ─────────────────────
    logger.info("【STEP 2/5】文章作成担当: 記事を生成します")
    try:
        from agents.文章作成.agent import run as run_writer
        articles = await run_writer(count=settings.articles_per_day)
        stats["articles"] = len(articles)
        logger.info(f"STEP 2 完了: {stats['articles']} 件の記事を生成")
    except Exception as e:
        logger.error(f"STEP 2 エラー: {e}")
        articles = []

    # ─── STEP 3: 画像図解作成担当 ─────────────────
    logger.info("【STEP 3/5】画像図解作成担当: Geminiで画像を生成します")
    try:
        from agents.画像図解作成担当.agent import run as run_image_creator
        images = await run_image_creator(articles=articles if articles else None)
        stats["images"] = len(images)
        logger.info(f"STEP 3 完了: {stats['images']} 枚の画像を生成")
    except Exception as e:
        logger.error(f"STEP 3 エラー: {e}")

    # ─── STEP 4: note投稿 ─────────────────────────
    logger.info("【STEP 4/5】note投稿: note.comに記事を公開します")
    ready_articles = get_ready_articles(limit=settings.articles_per_day)

    if not ready_articles:
        logger.warning("STEP 4: 投稿可能な記事がありません")
    else:
        async with get_browser() as browser:
            async with get_context("note", browser) as context:
                page = await ensure_note_login(context)

                for article in ready_articles:
                    try:
                        article_images = get_images_for_article(article.id)
                        note_url = await publish_article(
                            page=page,
                            article=article,
                            images=article_images,
                            dry_run=dry_run,
                        )
                        status = "posted" if note_url else "failed"
                        update_article_status(article.id, status, note_url)

                        if note_url:
                            article.note_url = note_url
                            stats["posted"] += 1
                            logger.info(f"note投稿成功: {note_url}")
                        else:
                            logger.warning(f"note投稿失敗: {article.title}")

                        await asyncio.sleep(5)  # 連続投稿の間隔

                    except Exception as e:
                        logger.error(f"note投稿エラー ({article.title}): {e}")
                        update_article_status(article.id, "failed")

    logger.info(f"STEP 4 完了: {stats['posted']} 件をnoteに投稿")

    # ─── STEP 5: X投稿担当 ─────────────────────────
    logger.info("【STEP 5/5】X投稿担当: 投稿記事をXで拡散します")
    try:
        from agents.X投稿.agent import run as run_x_poster
        # STEP4で投稿した記事をXで拡散
        posted_articles = [a for a in ready_articles if a.note_url]
        if posted_articles:
            xposts = await run_x_poster(articles=posted_articles, dry_run=dry_run)
            stats["tweeted"] = sum(1 for xp in xposts if xp.status == "posted")
        logger.info(f"STEP 5 完了: {stats['tweeted']} 件をXに投稿")
    except Exception as e:
        logger.error(f"STEP 5 エラー: {e}")

    # ─── サマリー ────────────────────────────────
    logger.info("=" * 60)
    logger.info("1サイクル 完了サマリー:")
    logger.info(f"  トピック生成  : {stats['topics']} 件")
    logger.info(f"  記事生成      : {stats['articles']} 件")
    logger.info(f"  画像生成      : {stats['images']} 枚")
    logger.info(f"  note投稿      : {stats['posted']} 件")
    logger.info(f"  X（Twitter）  : {stats['tweeted']} 件")
    logger.info("=" * 60)

    return stats
