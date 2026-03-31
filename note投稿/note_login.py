"""
note.com ログイン処理
Playwrightで認証状態を保存・再利用する
"""
from loguru import logger
from playwright.async_api import BrowserContext, Page

from browser.playwright_manager import new_page, is_logged_in
from config.settings import get_settings

NOTE_URL = "https://note.com"
NOTE_LOGIN_URL = "https://note.com/login"
NOTE_DASHBOARD_URL = "https://note.com/notes"
# ログイン済み確認セレクタ（ヘッダーのアカウントアイコン）
LOGGED_IN_SELECTOR = "[data-testid='header-user-icon'], .o-header__userIcon, header img[alt]"


async def ensure_note_login(context: BrowserContext) -> Page:
    """
    note.comにログイン済みのページを返す。
    セッションが有効なら再ログインしない。
    """
    settings = get_settings()
    page = await new_page(context)

    # ログイン確認
    logged_in = await is_logged_in(page, NOTE_DASHBOARD_URL, LOGGED_IN_SELECTOR)
    if logged_in:
        logger.info("note.com: セッション再利用でログイン済みです")
        return page

    logger.info("note.com: ログイン処理を開始します")

    if not settings.note_email or not settings.note_password:
        raise ValueError("NOTE_EMAIL と NOTE_PASSWORD を .env に設定してください")

    # ログインページへ移動
    await page.goto(NOTE_LOGIN_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)

    # メールアドレス入力
    email_selectors = [
        "input[name='login_id']",
        "input[type='email']",
        "input[placeholder*='メール']",
        "input[placeholder*='mail']",
    ]
    for sel in email_selectors:
        el = await page.query_selector(sel)
        if el:
            await el.fill(settings.note_email)
            break

    # パスワード入力
    pwd_selectors = [
        "input[name='password']",
        "input[type='password']",
    ]
    for sel in pwd_selectors:
        el = await page.query_selector(sel)
        if el:
            await el.fill(settings.note_password)
            break

    # ログインボタンクリック
    login_btn_selectors = [
        "button[type='submit']",
        "button:has-text('ログイン')",
        ".o-login__btn",
    ]
    for sel in login_btn_selectors:
        btn = await page.query_selector(sel)
        if btn:
            await btn.click()
            break

    # ログイン完了を待つ
    await page.wait_for_timeout(3000)

    # 確認
    logged_in = await is_logged_in(page, NOTE_DASHBOARD_URL, LOGGED_IN_SELECTOR)
    if not logged_in:
        raise RuntimeError("note.comのログインに失敗しました。認証情報を確認してください。")

    logger.info("note.com: ログイン成功")
    return page
