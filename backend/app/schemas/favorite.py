from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class FavoriteToggleResponse(BaseModel):
    is_favorited: bool
    favorites_count: int


class ArticleInteractionStatus(BaseModel):
    is_liked: bool
    is_favorited: bool
    likes_count: int


class FavoriteArticleItem(BaseModel):
    id: int
    title: str
    slug: str
    summary: Optional[str] = None
    category_name: Optional[str] = None
    cover_image: Optional[str] = None
    views_count: int = 0
    likes_count: int = 0
    created_at: datetime
    favorited_at: datetime
