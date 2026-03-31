"""
定期実行スケジューラ
毎日 POST_TIME に記事生成 & タスクファイル出力を自動実行する。
（ブラウザ投稿は Claude for Chrome で手動実行）
"""
import asyncio
from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import get_settings


def _run_generate_and_export() -> None:
    """記事生成 & タスクエクスポートを同期実行（APScheduler対応）"""
    from shared.database import init_db
    from agents.分析担当.trend_analyzer import analyze_trends
    from agents.分析担当.note_scraper import format_articles_for_analysis
    from shared.database import insert_topic
    from tasks.task_manager import export_pending_tasks

    settings = get_settings()
    init_db()

    # トピック生成
    articles_text = format_articles_for_analysis([])
    topics = analyze_trends(articles_text)
    for topic in topics:
        insert_topic(topic)
    logger.info(f"スケジューラ: {len(topics)} 件のトピックを生成しました")

    # 記事生成
    from agents.文章作成.article_generator import generate_article
    from shared.database import get_pending_topics, insert_article, update_topic_status

    pending = get_pending_topics(limit=settings.articles_per_day)
    for topic in pending:
        try:
            update_topic_status(topic.id, "selected")
            article = generate_article(topic)
            insert_article(article)
            logger.info(f"スケジューラ: 記事生成完了 '{article.title}'")
        except Exception as e:
            logger.error(f"記事生成エラー: {e}")
            update_topic_status(topic.id, "pending")

    # タスクファイル出力
    export_pending_tasks(limit=settings.articles_per_day)
    logger.info("スケジューラ: tasks/pending_posts.json を更新しました")
    logger.info("👉 次に claude --chrome を起動して記事を投稿してください")


def start_scheduler() -> None:
    """スケジューラを起動する"""
    settings = get_settings()

    try:
        hour, minute = map(int, settings.post_time.split(":"))
    except ValueError:
        hour, minute = 7, 0

    scheduler = BlockingScheduler(timezone="Asia/Tokyo")
    scheduler.add_job(
        func=_run_generate_and_export,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="note_generate",
        name="note.com 記事生成",
        replace_existing=True,
    )

    logger.info(f"スケジューラ起動: 毎日 {hour:02d}:{minute:02d} に記事生成を実行します")
    logger.info("記事生成後に claude --chrome で投稿してください")
    logger.info("Ctrl+C で停止")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("スケジューラを停止しました")
