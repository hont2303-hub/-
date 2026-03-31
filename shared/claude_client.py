"""
Anthropic Claude API 共通クライアント
全エージェントがこのモジュールを通じてClaudeを呼び出す
"""
import time
from pathlib import Path
from loguru import logger
import anthropic

from config.settings import get_settings


def _load_prompt(prompt_file: str) -> str:
    """config/prompts/ 以下のプロンプトファイルを読み込む"""
    path = Path(__file__).parent.parent / "config" / "prompts" / prompt_file
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def call_claude(
    user_message: str,
    system_prompt: str = "",
    prompt_file: str = "",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 8192,
    retries: int = 3,
) -> str:
    """
    Claude APIを呼び出してテキストを返す。
    prompt_file が指定された場合は config/prompts/ から読み込む。
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    if prompt_file and not system_prompt:
        system_prompt = _load_prompt(prompt_file)

    for attempt in range(retries):
        try:
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": user_message}],
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = client.messages.create(**kwargs)
            return response.content[0].text

        except anthropic.RateLimitError:
            wait = 2 ** attempt
            logger.warning(f"レート制限に到達。{wait}秒後に再試行します（{attempt+1}/{retries}）")
            time.sleep(wait)
        except anthropic.APIError as e:
            logger.error(f"Claude API エラー: {e}")
            if attempt == retries - 1:
                raise

    raise RuntimeError("Claude API の呼び出しに失敗しました")
