"""
Claude APIを使った記事生成
トピックを受け取って記事本文を生成し、品質評価する
"""
import json
from loguru import logger

from shared.claude_client import call_claude
from shared.models import Topic, Article
from config.settings import get_settings


def generate_article(topic: Topic) -> Article:
    """
    トピックから記事を生成する。
    品質スコアが閾値未満の場合は再生成する（最大 max_regenerate 回）。
    """
    settings = get_settings()
    best_article: Article | None = None

    for attempt in range(settings.max_regenerate + 1):
        if attempt > 0:
            logger.info(f"品質不足のため再生成します（{attempt}/{settings.max_regenerate}回目）")

        article = _call_writer(topic, settings)
        logger.info(
            f"記事生成完了: '{article.title}' "
            f"({article.char_count}字, 品質スコア: {article.quality_score:.2f})"
        )

        # 品質チェック
        if article.quality_score >= settings.quality_threshold:
            article.status = "ready"
            return article

        # まだ閾値未満だが現時点のベストを保持
        if best_article is None or article.quality_score > best_article.quality_score:
            best_article = article

    # 最大再生成回数に達した場合はベストを採用
    if best_article:
        logger.warning(
            f"品質閾値 {settings.quality_threshold} に達しませんでしたが、"
            f"ベストスコア {best_article.quality_score:.2f} の記事を採用します"
        )
        best_article.status = "ready"
        return best_article

    raise RuntimeError("記事生成に完全に失敗しました")


def _call_writer(topic: Topic, settings) -> Article:
    """Claudeに記事生成を依頼してArticleオブジェクトを返す"""
    keywords_str = "、".join(topic.keywords) if topic.keywords else ""
    prompt = f"""以下のトピックでnote.comに投稿する記事を執筆してください。

## トピック情報
- タイトル候補: {topic.title}
- キーワード: {keywords_str}
- noteタグ: {", ".join(topic.tags)}
- 狙い: {topic.reason}

## 要件
- 文字数: {settings.article_min_chars}〜{settings.article_max_chars}字
- Markdown形式
- Claude Code（Anthropicのコーディングアシスタント）の活用に関する内容
- 日本語で執筆

JSONで返してください。"""

    response_text = call_claude(
        user_message=prompt,
        prompt_file="writer.md",
        max_tokens=8192,
    )

    return _parse_article_response(response_text, topic)


def _parse_article_response(response_text: str, topic: Topic) -> Article:
    """レスポンスからArticleオブジェクトを生成する"""
    json_text = _extract_json(response_text)

    if not json_text:
        # JSONが取得できない場合はレスポンス全体を本文として扱う
        logger.warning("レスポンスからJSONを抽出できませんでした。テキストをそのまま使用します。")
        return Article(
            topic_id=topic.id,
            title=topic.title,
            body_markdown=response_text,
            summary=topic.title[:100],
            hashtags=[f"#{tag}" for tag in topic.tags[:3]],
            quality_score=0.5,
            status="draft",
        )

    try:
        data = json.loads(json_text)
        body = data.get("body_markdown", "")
        return Article(
            topic_id=topic.id,
            title=data.get("title", topic.title),
            body_markdown=body,
            summary=data.get("summary", "")[:140],
            hashtags=data.get("hashtags", [f"#{tag}" for tag in topic.tags[:3]]),
            quality_score=float(data.get("quality_score", 0.5)),
            status="draft",
        )
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"記事レスポンスのパースに失敗: {e}")
        return Article(
            topic_id=topic.id,
            title=topic.title,
            body_markdown=response_text,
            summary=topic.title[:100],
            hashtags=[f"#{tag}" for tag in topic.tags[:3]],
            quality_score=0.4,
            status="draft",
        )


def _extract_json(text: str) -> str:
    """テキストからJSONブロックを抽出する"""
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            return text[start:end].strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return ""
