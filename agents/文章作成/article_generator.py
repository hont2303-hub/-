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
    """
    区切り文字形式のレスポンスをパースしてArticleオブジェクトを生成する。
    形式:
      ===TITLE===
      ===BODY===
      ===SUMMARY===
      ===HASHTAGS===
      ===SCORE===
      ===END===
    """
    def extract_section(text: str, start_tag: str, end_tag: str) -> str:
        start = text.find(start_tag)
        if start == -1:
            return ""
        start += len(start_tag)
        end = text.find(end_tag, start)
        return text[start:end].strip() if end != -1 else text[start:].strip()

    title = extract_section(response_text, "===TITLE===", "===BODY===") or topic.title
    body = extract_section(response_text, "===BODY===", "===SUMMARY===")
    summary = extract_section(response_text, "===SUMMARY===", "===HASHTAGS===")
    hashtags_raw = extract_section(response_text, "===HASHTAGS===", "===SCORE===")
    score_raw = extract_section(response_text, "===SCORE===", "===END===")

    # フォールバック: セクションが見つからない場合はレスポンス全体を本文として使用
    if not body:
        logger.warning("区切り文字形式のパースに失敗。レスポンスをそのまま本文として使用します。")
        body = response_text

    # ハッシュタグをリスト化
    if hashtags_raw:
        hashtags = [h.strip() for h in hashtags_raw.split(",") if h.strip()]
    else:
        hashtags = [f"#{tag}" for tag in topic.tags[:3]]

    # 品質スコアをパース
    try:
        quality_score = float(score_raw.strip()) if score_raw.strip() else 0.5
        quality_score = max(0.0, min(1.0, quality_score))
    except ValueError:
        quality_score = 0.5

    return Article(
        topic_id=topic.id,
        title=title,
        body_markdown=body,
        summary=(summary or topic.title)[:140],
        hashtags=hashtags,
        quality_score=quality_score,
        status="draft",
    )
