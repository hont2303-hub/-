"""
定期実行スケジューラ
APSchedulerを使って毎朝7時に自動でワークフローを起動する
"""
import asyncio
from loguru import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import get_settings


def _run_workflow_sync(dry_run: bool = False) -> None:
    """同期関数としてワークフローを実行（APScheduler対応）"""
    from orchestrator.workflow import run_full_cycle
    asyncio.run(run_full_cycle(dry_run=dry_run))


def start_scheduler(dry_run: bool = False) -> None:
    """
    スケジューラを起動する。
    POST_TIME（デフォルト: 07:00）に毎日1回ワークフローを実行する。
    """
    settings = get_settings()

    try:
        hour, minute = map(int, settings.post_time.split(":"))
    except ValueError:
        logger.warning(f"POST_TIME の形式が不正です: {settings.post_time}。07:00を使用します。")
        hour, minute = 7, 0

    scheduler = BlockingScheduler(timezone="Asia/Tokyo")
    scheduler.add_job(
        func=_run_workflow_sync,
        trigger=CronTrigger(hour=hour, minute=minute),
        kwargs={"dry_run": dry_run},
        id="note_automation",
        name="note.com 自動投稿",
        replace_existing=True,
    )

    logger.info(f"スケジューラを起動しました。毎日 {hour:02d}:{minute:02d} に実行します。")
    logger.info("Ctrl+C でスケジューラを停止できます。")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("スケジューラを停止しました。")
        scheduler.shutdown()
