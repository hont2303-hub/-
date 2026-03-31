"""
noteトレンド収集
Playwrightを使ってnote.comの人気記事・タグ・トレンドを収集する
"""
import asyncio
from loguru import logger
from playwright.async_api import Page

# 収集対象のnoteタグページ（Claude Code関連）
TARGET_TAG_URLS = [
    "https://note.com/hashtag/ClaudeCode",
    "https://note.com/hashtag/AI活用",
    "https://note.com/hashtag/生成AI",
    "https://note.com/hashtag/プログラミング",
    "https://note.com/hashtag/自動化",
]

NOTE_TREND_URL = "https://note.com/all"


async def scrape_trending_articles(page: Page) -> list[dict]:
    """
    noteのトレンド記事一覧からタイトル・スキ数・タグを収集する。
    返り値: [{"title": str, "url": str, "likes": int, "tags": list[str]}]
    """
    results = []

    # トップページのトレンド記事を収集
    try:
        await page.goto(NOTE_TREND_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        articles = await page.query_selector_all("article")
        for article in articles[:20]:
            try:
                title_el = await article.query_selector("h3, h2, .note-title")
                link_el = await article.query_selector("a")
                title = await title_el.inner_text() if title_el else ""
                url = await link_el.get_attribute("href") if link_el else ""
                if title and url:
                    if not url.startswith("http"):
                        url = "https://note.com" + url
                    results.append({"title": title.strip(), "url": url, "likes": 0, "tags": []})
            except Exception:
                continue
        logger.info(f"トレンドページから {len(results)} 件の記事を収集しました")
    except Exception as e:
        logger.warning(f"トレンドページの収集に失敗: {e}")

    # タグページからも収集
    for tag_url in TARGET_TAG_URLS[:3]:
        try:
            await page.goto(tag_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            tag_articles = await page.query_selector_all("article, .note-preview")
            for article in tag_articles[:10]:
                try:
                    title_el = await article.query_selector("h3, h2, .note-title, [class*='title']")
                    link_el = await article.query_selector("a")
                    title = await title_el.inner_text() if title_el else ""
                    url = await link_el.get_attribute("href") if link_el else ""
                    if title and url:
                        if not url.startswith("http"):
                            url = "https://note.com" + url
                        tag = tag_url.split("/")[-1]
                        results.append({"title": title.strip(), "url": url, "likes": 0, "tags": [tag]})
                except Exception:
                    continue
            logger.info(f"{tag_url} から記事を収集しました")
        except Exception as e:
            logger.warning(f"タグページ {tag_url} の収集に失敗: {e}")

    # 重複除去（URLで）
    seen_urls = set()
    unique_results = []
    for r in results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_results.append(r)

    return unique_results


def format_articles_for_analysis(articles: list[dict]) -> str:
    """収集した記事情報をClaude分析用のテキストに変換する"""
    if not articles:
        return "収集した記事データがありません。一般的なClaude Codeの活用トピックを提案してください。"

    lines = ["以下はnote.comで収集した記事タイトル一覧です：\n"]
    for i, a in enumerate(articles[:30], 1):
        tags_str = ", ".join(a.get("tags", []))
        lines.append(f"{i}. {a['title']}" + (f"（タグ: {tags_str}）" if tags_str else ""))

    lines.append("\n上記のトレンドを踏まえて、Claude Codeの活用に関する記事トピックを5件以上提案してください。")
    return "\n".join(lines)
