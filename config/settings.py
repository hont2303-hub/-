"""
環境変数の読み込みと設定管理
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # note.com
    note_email: str = Field(default="", alias="NOTE_EMAIL")
    note_password: str = Field(default="", alias="NOTE_PASSWORD")

    # X（Twitter）
    x_email: str = Field(default="", alias="X_EMAIL")
    x_password: str = Field(default="", alias="X_PASSWORD")
    x_username: str = Field(default="", alias="X_USERNAME")

    # Google（Gemini）
    google_email: str = Field(default="", alias="GOOGLE_EMAIL")
    google_password: str = Field(default="", alias="GOOGLE_PASSWORD")

    # 投稿設定
    articles_per_day: int = Field(default=5, alias="ARTICLES_PER_DAY")
    post_time: str = Field(default="07:00", alias="POST_TIME")
    article_min_chars: int = Field(default=3000, alias="ARTICLE_MIN_CHARS")
    article_max_chars: int = Field(default=5000, alias="ARTICLE_MAX_CHARS")
    quality_threshold: float = Field(default=0.7, alias="QUALITY_THRESHOLD")
    max_regenerate: int = Field(default=2, alias="MAX_REGENERATE")

    # ブラウザ
    browser_headless: bool = Field(default=False, alias="BROWSER_HEADLESS")
    browser_slow_mo: int = Field(default=100, alias="BROWSER_SLOW_MO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
