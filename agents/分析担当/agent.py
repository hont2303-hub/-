"""
分析担当エージェント
noteトレンドを収集し、Claude APIでトピック候補を生成してDBに保存する
"""
import asyncio
from loguru import logger

from browser.playwright_manager import get_browser, get_context, new_page
from agents.分析担当.note_scraper import scrape_trending_articles, format_articles_for_analysis
from agents.分析担当.trend_analyzer import analyze_trends
from shared.database import insert_topic, get_pending_topics


async def run(target_count: int = 5) -> list:
    """
    分析担当エージェントを実行する。
    target_count: 生成するトピック候補の最低数
    返り値: 生成されたTopicのリスト
    """
    logger.info("=== 分析担当エージェント 開始 ===")

    # 1. noteからトレンド記事を収集
    articles = []
    try:
        async with get_browser() as browser:
            async with get_context("note_scraper", browser) as context:
                page = await new_page(context)
                articles = await scrape_trending_articles(page)
                logger.info(f"トレンド記事を {len(articles)} 件収集しました")
    except Exception as e:
        logger.warning(f"トレンド収集に失敗しました（フォールバックを使用）: {e}")

    # 2. 収集データをClaude APIで分析してトピック生成
    articles_text = format_articles_for_analysis(articles)
    topics = analyze_trends(articles_text)

    # 3. DBに保存
    saved_topics = []
    for topic in topics:
        try:
            topic_id = insert_topic(topic)
            topic.id = topic_id
            saved_topics.append(topic)
            logger.info(f"トピックを保存: [{topic_id}] {topic.title}")
        except Exception as e:
            logger.error(f"トピック保存エラー: {e}")

    logger.info(f"=== 分析担当エージェント 完了: {len(saved_topics)} 件のトピックを生成 ===")
    return saved_topics


if __name__ == "__main__":
    asyncio.run(run())
