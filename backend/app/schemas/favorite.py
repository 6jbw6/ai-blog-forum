from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from app.schemas.article import ArticleListItem


class FavoriteToggleResponse(BaseModel):
    is_favorited: bool
    favorites_count: int


class ArticleInteractionStatus(BaseModel):
    is_liked: bool
    is_favorited: bool
    likes_count: int


class FavoriteArticleItem(ArticleListItem):
    """收藏列表条目：完整文章字段 + 收藏时间"""
    favorited_at: Optional[datetime] = None
