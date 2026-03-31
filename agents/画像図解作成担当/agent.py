"""
画像図解作成担当エージェント
記事を解析してGeminiで画像を生成し、DBに登録する
"""
import asyncio
import json
from loguru import logger

from browser.playwright_manager import get_browser, get_context
from agents.画像図解作成担当.gemini_image import ensure_gemini_login, generate_image
from shared.claude_client import call_claude
from shared.database import get_ready_articles, insert_image
from shared.models import Article, Image


def _analyze_article_for_images(article: Article) -> list[dict]:
    """
    Claude APIを使って記事のどこに画像が必要かを分析する。
    返り値: [{"description": str, "insert_position": str, "image_type": str}]
    """
    prompt = f"""以下の記事を分析して、どこにどのような図解・画像を入れると
読者の理解が深まるか判断してください。

## 記事タイトル
{article.title}

## 記事本文（最初の2000字）
{article.body_markdown[:2000]}

JSONで返してください。"""

    response = call_claude(
        user_message=prompt,
        prompt_file="image_creator.md",
        max_tokens=2048,
    )

    # JSONを抽出
    json_text = ""
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        if end > start:
            json_text = response[start:end].strip()
    elif "{" in response:
        start = response.find("{")
        end = response.rfind("}") + 1
        json_text = response[start:end]

    try:
        data = json.loads(json_text)
        return data.get("images", [])
    except Exception:
        # パース失敗時は汎用的な図解を1枚生成
        return [{
            "description": f"'{article.title}' の内容を視覚的に説明するフローチャートまたは概念図",
            "insert_position": "まとめ",
            "image_type": "summary",
        }]


async def run(articles: list[Article] | None = None) -> list[Image]:
    """
    画像図解作成担当エージェントを実行する。
    articles: 対象記事リスト（Noneの場合はDBからready状態の記事を取得）
    返り値: 生成・保存したImageのリスト
    """
    logger.info("=== 画像図解作成担当エージェント 開始 ===")

    if articles is None:
        articles = get_ready_articles(limit=10)

    if not articles:
        logger.warning("画像生成対象の記事がありません")
        return []

    all_images: list[Image] = []

    async with get_browser() as browser:
        async with get_context("gemini", browser) as context:
            page = await ensure_gemini_login(context)

            for article in articles:
                logger.info(f"記事の画像分析: '{article.title}'")

                # 画像が必要な箇所を分析
                image_specs = _analyze_article_for_images(article)
                logger.info(f"{len(image_specs)} 枚の画像を生成します")

                for idx, spec in enumerate(image_specs):
                    file_path = await generate_image(
                        page=page,
                        description=spec.get("description", ""),
                        article_id=article.id,
                        image_index=idx,
                    )

                    if file_path:
                        image = Image(
                            article_id=article.id,
                            file_path=file_path,
                            description=spec.get("description", ""),
                            insert_position=spec.get("insert_position", ""),
                        )
                        image_id = insert_image(image)
                        image.id = image_id
                        all_images.append(image)
                        logger.info(f"画像を登録: [{image_id}] {file_path}")

                    # Geminiへの連続リクエストを緩和
                    await asyncio.sleep(3)

    logger.info(f"=== 画像図解作成担当エージェント 完了: {len(all_images)} 枚の画像を生成 ===")
    return all_images


if __name__ == "__main__":
    asyncio.run(run())
