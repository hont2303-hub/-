"""
Google Geminiを使った画像生成
PlaywrightでGemini（gemini.google.com）を操作して画像を生成・保存する
"""
import asyncio
import re
import urllib.request
from pathlib import Path
from loguru import logger
from playwright.async_api import Page, BrowserContext

from browser.playwright_manager import new_page, is_logged_in
from config.settings import get_settings

GEMINI_URL = "https://gemini.google.com"
IMAGE_DIR = Path(__file__).parent.parent.parent / "data" / "images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# Googleログインページ
GOOGLE_LOGIN_URL = "https://accounts.google.com/signin"


async def ensure_gemini_login(context: BrowserContext) -> Page:
    """Geminiにログイン済みのページを返す"""
    settings = get_settings()
    page = await new_page(context)

    # ログイン確認
    logged_in = await is_logged_in(page, GEMINI_URL, "[data-test-id='input-area'], textarea")
    if logged_in:
        logger.info("Gemini: セッション再利用でログイン済みです")
        return page

    logger.info("Gemini: Googleアカウントでログインします")

    if not settings.google_email or not settings.google_password:
        raise ValueError("GOOGLE_EMAIL と GOOGLE_PASSWORD を .env に設定してください")

    # Googleログイン
    await page.goto(GOOGLE_LOGIN_URL, wait_until="domcontentloaded")
    await page.wait_for_selector("input[type='email']")
    await page.fill("input[type='email']", settings.google_email)
    await page.click("#identifierNext button, [data-primary-action-label] button")
    await page.wait_for_timeout(1500)

    await page.wait_for_selector("input[type='password']", timeout=10_000)
    await page.fill("input[type='password']", settings.google_password)
    await page.click("#passwordNext button, [data-primary-action-label] button")
    await page.wait_for_timeout(2000)

    # Geminiへ移動
    await page.goto(GEMINI_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    logger.info("Gemini: ログイン完了")
    return page


async def generate_image(
    page: Page,
    description: str,
    article_id: int,
    image_index: int,
) -> str | None:
    """
    Geminiに画像生成を依頼して、生成された画像をローカルに保存する。
    返り値: 保存した画像ファイルのパス（失敗時はNone）
    """
    try:
        # Geminiのチャット入力欄を探す
        await page.goto(GEMINI_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # テキスト入力欄を探す（複数セレクタに対応）
        input_selectors = [
            "div[contenteditable='true']",
            "textarea",
            "[data-test-id='input-area']",
            "p[data-placeholder]",
        ]

        input_el = None
        for selector in input_selectors:
            input_el = await page.query_selector(selector)
            if input_el:
                break

        if not input_el:
            logger.error("Geminiの入力欄が見つかりません")
            return None

        # プロンプト入力
        prompt = f"以下の説明に基づいた図解・イラストを生成してください：\n\n{description}\n\nシンプルで見やすいデザインにしてください。"
        await input_el.click()
        await input_el.fill(prompt)
        await page.wait_for_timeout(500)

        # 送信ボタンをクリック
        send_selectors = [
            "button[aria-label*='送信']",
            "button[aria-label*='Send']",
            "[data-test-id='send-button']",
            "button[type='submit']",
        ]
        for selector in send_selectors:
            send_btn = await page.query_selector(selector)
            if send_btn:
                await send_btn.click()
                break
        else:
            await page.keyboard.press("Enter")

        # 画像生成を待つ（最大60秒）
        logger.info(f"Geminiで画像生成中: {description[:50]}...")
        await page.wait_for_timeout(5000)

        # 生成された画像を探す
        img_saved = await _save_generated_image(page, article_id, image_index)
        if img_saved:
            logger.info(f"画像を保存しました: {img_saved}")
            return img_saved

        # 画像がなければスクリーンショットで代用
        screenshot_path = IMAGE_DIR / f"article_{article_id}_img_{image_index}.png"
        await page.screenshot(path=str(screenshot_path), full_page=False)
        logger.info(f"スクリーンショットで代用しました: {screenshot_path}")
        return str(screenshot_path)

    except Exception as e:
        logger.error(f"Gemini画像生成エラー: {e}")
        return None


async def _save_generated_image(page: Page, article_id: int, image_index: int) -> str | None:
    """ページ内の生成画像を見つけてダウンロードする"""
    # 生成された画像要素を探す（Geminiのレスポンス内）
    img_selectors = [
        "img[src*='generativelanguage']",
        "img[src*='blob:']",
        ".response-container img",
        "[data-test-id='response'] img",
    ]

    for selector in img_selectors:
        img_el = await page.query_selector(selector)
        if img_el:
            src = await img_el.get_attribute("src")
            if src and src.startswith("http"):
                save_path = IMAGE_DIR / f"article_{article_id}_img_{image_index}.png"
                try:
                    urllib.request.urlretrieve(src, str(save_path))
                    return str(save_path)
                except Exception:
                    pass
            elif src and src.startswith("blob:"):
                # blob URLはスクリーンショット方式で対応
                save_path = IMAGE_DIR / f"article_{article_id}_img_{image_index}.png"
                await img_el.screenshot(path=str(save_path))
                return str(save_path)

    return None
