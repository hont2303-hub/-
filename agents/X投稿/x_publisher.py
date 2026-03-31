"""
X（Twitter）投稿処理
Playwrightでログインしてツイートを投稿する
"""
import asyncio
from datetime import datetime
from loguru import logger
from playwright.async_api import BrowserContext, Page

from browser.playwright_manager import new_page, is_logged_in
from shared.claude_client import call_claude
from shared.models import Article, XPost
from config.settings import get_settings

X_URL = "https://x.com"
X_HOME_URL = "https://x.com/home"
LOGGED_IN_SELECTOR = "[data-testid='SideNav_AccountSwitcher_Button'], [aria-label='アカウントメニュー']"


async def ensure_x_login(context: BrowserContext) -> Page:
    """X（Twitter）にログイン済みのページを返す"""
    settings = get_settings()
    page = await new_page(context)

    logged_in = await is_logged_in(page, X_HOME_URL, LOGGED_IN_SELECTOR)
    if logged_in:
        logger.info("X: セッション再利用でログイン済みです")
        return page

    logger.info("X: ログイン処理を開始します")

    if not settings.x_email or not settings.x_password:
        raise ValueError("X_EMAIL と X_PASSWORD を .env に設定してください")

    await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)

    # メールアドレス/ユーザー名入力
    await page.wait_for_selector("input[name='text'], input[autocomplete='username']")
    await page.fill("input[name='text'], input[autocomplete='username']", settings.x_email)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(1500)

    # ユーザー名確認画面が出る場合（Xの2段階確認）
    username_check = await page.query_selector("input[data-testid='ocfEnterTextTextInput']")
    if username_check and settings.x_username:
        await username_check.fill(settings.x_username)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1500)

    # パスワード入力
    await page.wait_for_selector("input[name='password'], input[type='password']", timeout=10_000)
    await page.fill("input[name='password'], input[type='password']", settings.x_password)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(3000)

    logged_in = await is_logged_in(page, X_HOME_URL, LOGGED_IN_SELECTOR)
    if not logged_in:
        raise RuntimeError("Xのログインに失敗しました。認証情報を確認してください。")

    logger.info("X: ログイン成功")
    return page


def create_tweet_text(article: Article) -> str:
    """
    Claude APIを使って記事からツイート文を生成する。
    note_url を含めて140字以内に収める。
    """
    prompt = f"""以下の記事のツイート文を作成してください。

## 記事タイトル
{article.title}

## 記事の要約
{article.summary}

## ハッシュタグ
{" ".join(article.hashtags[:3])}

## note記事URL
{article.note_url}

URLとハッシュタグを含めて140字以内のツイートを作成してください。
JSONで返してください。"""

    response = call_claude(
        user_message=prompt,
        prompt_file="x_poster.md",
        max_tokens=512,
    )

    # JSONからツイートテキストを抽出
    import json
    json_text = ""
    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        json_text = response[start:end].strip() if end > start else ""
    elif "{" in response:
        start = response.find("{")
        end = response.rfind("}") + 1
        json_text = response[start:end]

    try:
        data = json.loads(json_text)
        tweet_body = data.get("tweet_text", "")
    except Exception:
        tweet_body = article.summary or article.title

    # URLとハッシュタグを追加
    hashtags_str = " ".join(article.hashtags[:2])
    url = article.note_url
    tweet = f"{tweet_body}\n\n{url}\n{hashtags_str}"

    # 140字に収める
    if len(tweet) > 140:
        max_body = 140 - len(url) - len(hashtags_str) - 4
        tweet = f"{tweet_body[:max_body]}...\n\n{url}\n{hashtags_str}"

    return tweet


async def post_tweet(page: Page, tweet_text: str, dry_run: bool = False) -> bool:
    """ツイートを投稿する"""
    if dry_run:
        logger.info(f"ドライランモード: ツイートをスキップ\n{tweet_text}")
        return True

    logger.info(f"ツイートを投稿します: {tweet_text[:50]}...")

    try:
        await page.goto(X_HOME_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # ツイート入力欄を探す
        tweet_input_selectors = [
            "[data-testid='tweetTextarea_0']",
            "div[aria-label='ツイートを入力']",
            "div[aria-label='Tweet text']",
            ".public-DraftEditor-content",
        ]
        for sel in tweet_input_selectors:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await page.wait_for_timeout(500)
                await el.fill(tweet_text)
                await page.wait_for_timeout(500)
                break

        # 投稿ボタンをクリック
        post_btn_selectors = [
            "[data-testid='tweetButtonInline']",
            "[data-testid='tweetButton']",
            "button[aria-label='ポストする']",
            "button[aria-label='Tweet']",
        ]
        for sel in post_btn_selectors:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                await page.wait_for_timeout(2000)
                logger.info("ツイートを投稿しました")
                return True

        logger.warning("投稿ボタンが見つかりませんでした")
        return False

    except Exception as e:
        logger.error(f"ツイート投稿エラー: {e}")
        return False


async def run_for_article(
    context: BrowserContext,
    article: Article,
    dry_run: bool = False,
) -> XPost:
    """
    単一記事のX投稿を実行する。
    返り値: XPost オブジェクト（status付き）
    """
    xpost = XPost(article_id=article.id)

    try:
        # ツイート文生成
        tweet_text = create_tweet_text(article)
        xpost.tweet_text = tweet_text

        # ログインしてツイート
        page = await ensure_x_login(context)
        success = await post_tweet(page, tweet_text, dry_run=dry_run)

        if success:
            xpost.status = "posted"
            xpost.posted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            xpost.status = "failed"
            xpost.error_msg = "投稿ボタンが見つかりませんでした"

    except Exception as e:
        xpost.status = "failed"
        xpost.error_msg = str(e)
        logger.error(f"X投稿エラー: {e}")

    return xpost
