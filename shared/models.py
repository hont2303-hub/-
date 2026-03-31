"""
全エージェント共通のデータモデル定義
"""
from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class Topic:
    """分析担当が生成するトピック候補"""
    id: Optional[int] = None
    title: str = ""
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    reason: str = ""
    priority: int = 5
    status: str = "pending"  # pending / selected / skipped
    source_urls: list[str] = field(default_factory=list)
    created_at: str = ""

    def keywords_json(self) -> str:
        return json.dumps(self.keywords, ensure_ascii=False)

    def tags_json(self) -> str:
        return json.dumps(self.tags, ensure_ascii=False)

    def source_urls_json(self) -> str:
        return json.dumps(self.source_urls, ensure_ascii=False)


@dataclass
class Article:
    """文章作成担当が生成する記事"""
    id: Optional[int] = None
    topic_id: Optional[int] = None
    title: str = ""
    body_markdown: str = ""
    summary: str = ""           # X投稿用140字要約
    hashtags: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    status: str = "draft"       # draft / ready / posted / failed
    note_url: str = ""
    created_at: str = ""

    def hashtags_json(self) -> str:
        return json.dumps(self.hashtags, ensure_ascii=False)

    @property
    def char_count(self) -> int:
        return len(self.body_markdown)


@dataclass
class Image:
    """画像図解作成担当が生成する画像"""
    id: Optional[int] = None
    article_id: Optional[int] = None
    file_path: str = ""
    description: str = ""       # Geminiへの指示
    insert_position: str = ""   # 記事内の挿入セクション名
    created_at: str = ""


@dataclass
class XPost:
    """X投稿担当が管理するツイート"""
    id: Optional[int] = None
    article_id: Optional[int] = None
    tweet_text: str = ""
    status: str = "pending"     # pending / posted / failed
    posted_at: str = ""
    error_msg: str = ""
