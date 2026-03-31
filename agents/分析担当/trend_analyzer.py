"""
Claude APIを使ったトレンド分析
収集した記事データからトピック候補を生成する
"""
import json
from loguru import logger

from shared.claude_client import call_claude
from shared.models import Topic


def analyze_trends(articles_text: str) -> list[Topic]:
    """
    収集した記事テキストをClaude APIに渡してトピック候補を生成する。
    返り値: Topic のリスト
    """
    response_text = call_claude(
        user_message=articles_text,
        prompt_file="analyst.md",
        max_tokens=4096,
    )

    topics = _parse_topics_response(response_text)
    logger.info(f"Claude APIから {len(topics)} 件のトピック候補を生成しました")
    return topics


def _parse_topics_response(response_text: str) -> list[Topic]:
    """Claude APIのレスポンスからTopicリストを抽出する"""
    # JSONブロックを抽出
    json_text = _extract_json(response_text)
    if not json_text:
        logger.warning("レスポンスからJSONを抽出できませんでした。フォールバックトピックを使用します。")
        return _fallback_topics()

    try:
        data = json.loads(json_text)
        topics_data = data.get("topics", [])
        topics = []
        for t in topics_data:
            topic = Topic(
                title=t.get("title", ""),
                keywords=t.get("keywords", []),
                tags=t.get("tags", []),
                reason=t.get("reason", ""),
                priority=int(t.get("priority", 5)),
            )
            if topic.title:
                topics.append(topic)
        return topics
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"トピックのパースに失敗: {e}")
        return _fallback_topics()


def _extract_json(text: str) -> str:
    """テキストからJSONブロックを抽出する"""
    # ```json ... ``` ブロックを探す
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            return text[start:end].strip()
    # { で始まるJSONを探す
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return ""


def _fallback_topics() -> list[Topic]:
    """スクレイピング失敗時のフォールバックトピック"""
    return [
        Topic(
            title="Claude Codeで始めるAI駆動開発入門",
            keywords=["Claude Code", "AI開発", "入門"],
            tags=["ClaudeCode", "AI活用", "プログラミング"],
            reason="入門記事は常に需要が高い",
            priority=1,
        ),
        Topic(
            title="Claude Codeを使って業務を10倍効率化する5つの方法",
            keywords=["Claude Code", "業務効率化", "自動化"],
            tags=["ClaudeCode", "業務効率化", "生成AI"],
            reason="具体的な数字と実践的な内容で読まれやすい",
            priority=2,
        ),
        Topic(
            title="Claude CodeのMCPサーバーで何ができるか完全解説",
            keywords=["Claude Code", "MCP", "ツール連携"],
            tags=["ClaudeCode", "MCP", "AI活用"],
            reason="MCPは最新機能で注目度が高い",
            priority=3,
        ),
        Topic(
            title="非エンジニアでもできるClaude Codeを使ったタスク自動化",
            keywords=["Claude Code", "非エンジニア", "自動化"],
            tags=["ClaudeCode", "自動化", "ノーコード"],
            reason="非エンジニア向けコンテンツは差別化できる",
            priority=4,
        ),
        Topic(
            title="Claude CodeとCursorを比較してみた【2024年版】",
            keywords=["Claude Code", "Cursor", "比較"],
            tags=["ClaudeCode", "Cursor", "AIエディタ"],
            reason="比較記事は検索流入が多い",
            priority=5,
        ),
    ]
