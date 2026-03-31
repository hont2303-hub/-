"""
文章作成エージェント
DBからトピックを取得し、Claude APIで記事を生成してDBに保存する
"""
import asyncio
from loguru import logger

from agents.文章作成.article_generator import generate_article
from shared.database import get_pending_topics, insert_article, update_topic_status
from shared.models import Article
from config.settings import get_settings


async def run(count: int | None = None) -> list[Article]:
    """
    文章作成エージェントを実行する。
    count: 生成する記事数（Noneの場合は設定ファイルの articles_per_day を使用）
    返り値: 生成・保存したArticleのリスト
    """
    settings = get_settings()
    target = count if count is not None else settings.articles_per_day

    logger.info(f"=== 文章作成エージェント 開始: {target}記事を生成します ===")

    # DBからトピックを取得
    topics = get_pending_topics(limit=target)
    if not topics:
        logger.warning("pendingのトピックがありません。先に分析担当を実行してください。")
        return []

    saved_articles: list[Article] = []

    for topic in topics[:target]:
        try:
            logger.info(f"記事生成開始: '{topic.title}'")
            # トピックのステータスを更新
            update_topic_status(topic.id, "selected")

            # 記事生成
            article = generate_article(topic)

            # DBに保存
            article_id = insert_article(article)
            article.id = article_id
            saved_articles.append(article)

            logger.info(
                f"記事を保存しました: [{article_id}] '{article.title}' "
                f"({article.char_count}字)"
            )

        except Exception as e:
            logger.error(f"記事生成エラー (トピック: {topic.title}): {e}")
            update_topic_status(topic.id, "pending")  # 失敗したら元に戻す
            continue

    logger.info(f"=== 文章作成エージェント 完了: {len(saved_articles)} 件の記事を生成 ===")
    return saved_articles


if __name__ == "__main__":
    asyncio.run(run())
