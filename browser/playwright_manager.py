"""
Playwrightブラウザ管理
セッションの起動・認証状態の保存・再利用を担当する
"""
import json
from pathlib import Path
from contextlib import asynccontextmanager
from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config.settings import get_settings

AUTH_DIR = Path(__file__).parent / "auth_storage"


def _auth_path(service: str) -> Path:
    """サービス名に対応する認証状態ファイルのパス"""
    AUTH_DIR.mkdir(exist_ok=True)
    return AUTH_DIR / f"{service}_auth.json"


@asynccontextmanager
async def get_browser():
    """Chromiumブラウザを起動してコンテキストマネージャで返す"""
    settings = get_settings()
    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=settings.browser_headless,
            slow_mo=settings.browser_slow_mo,
        )
        try:
            yield browser
        finally:
            await browser.close()


@asynccontextmanager
async def get_context(service: str, browser: Browser):
    """
    認証状態を保存・再利用するブラウザコンテキストを返す。
    service: 'note' / 'x' / 'gemini' のいずれか
    """
    auth_file = _auth_path(service)
    storage_state = str(auth_file) if auth_file.exists() else None

    context: BrowserContext = await browser.new_context(
        storage_state=storage_state,
        locale="ja-JP",
        timezone_id="Asia/Tokyo",
        viewport={"width": 1280, "height": 900},
    )
    try:
        yield context
    finally:
        # 認証状態を保存して次回のログインをスキップ
        await context.storage_state(path=str(auth_file))
        await context.close()
        logger.debug(f"{service} の認証状態を保存しました: {auth_file}")


async def new_page(context: BrowserContext) -> Page:
    """新しいページを開いて返す"""
    page = await context.new_page()
    # タイムアウトを60秒に設定
    page.set_default_timeout(60_000)
    return page


async def is_logged_in(page: Page, check_url: str, logged_in_selector: str) -> bool:
    """
    指定URLにアクセスしてログイン済みかどうかを確認する。
    logged_in_selector が見つかればログイン済みと判定。
    """
    try:
        await page.goto(check_url, wait_until="domcontentloaded")
        await page.wait_for_selector(logged_in_selector, timeout=5_000)
        return True
    except Exception:
        return False
