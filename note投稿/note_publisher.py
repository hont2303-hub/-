"""
note.com 記事投稿処理
Playwrightでエディタを操作して記事を公開する
"""
import asyncio
from pathlib import Path
from loguru import logger
from playwright.async_api import Page

from shared.models import Article, Image

NOTE_NEW_ARTICLE_URL = "https://note.com/notes/new"


async def publish_article(
    page: Page,
    article: Article,
    images: list[Image] | None = None,
    dry_run: bool = False,
) -> str:
    """
    note.comに記事を投稿する。
    返り値: 投稿した記事のURL（失敗時は空文字）
    """
    logger.info(f"note.comに投稿開始: '{article.title}'")

    # 新規記事作成ページへ移動
    await page.goto(NOTE_NEW_ARTICLE_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)

    # タイトル入力
    await _fill_title(page, article.title)

    # 本文入力
    await _fill_body(page, article.body_markdown)

    # 画像アップロード（あれば）
    if images:
        await _upload_images(page, images)

    if dry_run:
        logger.info("ドライランモード: 投稿をスキップします")
        return ""

    # タグ設定
    await _set_tags(page, article.hashtags)

    # 公開ボタンをクリック
    note_url = await _publish(page, article.title)
    logger.info(f"記事を公開しました: {note_url}")
    return note_url


async def _fill_title(page: Page, title: str) -> None:
    """タイトル入力欄を探して入力する"""
    title_selectors = [
        "input[placeholder*='タイトル']",
        "textarea[placeholder*='タイトル']",
        ".o-editorNoteTitle__input",
        "[data-testid='note-title-input']",
        "h1[contenteditable='true']",
    ]
    for sel in title_selectors:
        el = await page.query_selector(sel)
        if el:
            await el.click()
            await el.fill(title)
            logger.debug(f"タイトルを入力しました: {title[:30]}...")
            return
    logger.warning("タイトル入力欄が見つかりませんでした")


async def _fill_body(page: Page, body_markdown: str) -> None:
    """
    本文入力欄にMarkdownをペーストする。
    noteエディタはリッチテキストなのでclipboard経由でペーストする。
    """
    body_selectors = [
        ".ProseMirror",
        ".o-editorNote__body",
        "[data-testid='note-body-editor']",
        "div[contenteditable='true'][role='textbox']",
        "div[contenteditable='true']",
    ]

    # MarkdownをHTMLに変換せず、そのままプレーンテキストとして入力
    # noteエディタはMarkdownを一部解釈するため
    body_text = body_markdown

    for sel in body_selectors:
        el = await page.query_selector(sel)
        if el:
            await el.click()
            await page.wait_for_timeout(500)
            # JavaScriptでクリップボードに設定してペースト
            await page.evaluate(
                """(text) => {
                    navigator.clipboard.writeText(text).catch(() => {
                        const ta = document.createElement('textarea');
                        ta.value = text;
                        document.body.appendChild(ta);
                        ta.select();
                        document.execCommand('copy');
                        document.body.removeChild(ta);
                    });
                }""",
                body_text
            )
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Control+v")
            await page.wait_for_timeout(1000)
            logger.debug(f"本文を入力しました（{len(body_text)}字）")
            return
    logger.warning("本文入力欄が見つかりませんでした")


async def _upload_images(page: Page, images: list[Image]) -> None:
    """生成画像をnoteにアップロードする"""
    for image in images:
        file_path = Path(image.file_path)
        if not file_path.exists():
            logger.warning(f"画像ファイルが見つかりません: {file_path}")
            continue
        try:
            # 画像アップロードボタンを探す
            upload_btn_selectors = [
                "button[aria-label*='画像']",
                "button[title*='画像']",
                ".o-editorToolbar__imageBtn",
                "[data-testid='image-upload-button']",
            ]
            for sel in upload_btn_selectors:
                btn = await page.query_selector(sel)
                if btn:
                    # ファイル入力要素を探してセット
                    async with page.expect_file_chooser() as fc_info:
                        await btn.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(str(file_path))
                    await page.wait_for_timeout(2000)
                    logger.info(f"画像をアップロードしました: {file_path.name}")
                    break
        except Exception as e:
            logger.warning(f"画像アップロードに失敗: {e}")


async def _set_tags(page: Page, hashtags: list[str]) -> None:
    """タグを設定する"""
    # 公開設定ダイアログを開く
    publish_btn_selectors = [
        "button:has-text('公開設定')",
        "button:has-text('投稿設定')",
        "[data-testid='publish-settings-button']",
    ]
    for sel in publish_btn_selectors:
        btn = await page.query_selector(sel)
        if btn:
            await btn.click()
            await page.wait_for_timeout(1000)
            break

    # タグ入力欄を探す
    tag_input_selectors = [
        "input[placeholder*='タグ']",
        "[data-testid='tag-input']",
        ".o-tagInput input",
    ]
    for sel in tag_input_selectors:
        tag_input = await page.query_selector(sel)
        if tag_input:
            for tag in hashtags[:5]:  # noteは最大5タグ
                clean_tag = tag.lstrip("#")
                await tag_input.fill(clean_tag)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(300)
            logger.debug(f"タグを設定しました: {hashtags[:5]}")
            break


async def _publish(page: Page, title: str) -> str:
    """記事を公開して記事URLを返す"""
    # 公開ボタンをクリック
    publish_selectors = [
        "button:has-text('公開する')",
        "button:has-text('投稿する')",
        "[data-testid='publish-button']",
        ".o-publishButton",
    ]

    for sel in publish_selectors:
        btn = await page.query_selector(sel)
        if btn:
            await btn.click()
            await page.wait_for_timeout(3000)
            break

    # 公開完了後のURLを取得
    current_url = page.url
    if "note.com" in current_url and "/n/" in current_url:
        return current_url

    # URLが変わっていない場合は確認ダイアログを探す
    confirm_selectors = [
        "button:has-text('公開する')",
        "button:has-text('確認')",
        "[data-testid='confirm-publish']",
    ]
    for sel in confirm_selectors:
        btn = await page.query_selector(sel)
        if btn:
            await btn.click()
            await page.wait_for_timeout(3000)
            current_url = page.url
            if "/n/" in current_url:
                return current_url
            break

    logger.warning(f"投稿後のURL確認ができませんでした。現在のURL: {current_url}")
    return current_url
