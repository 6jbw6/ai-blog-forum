from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.schemas.category import CategoryOut
from app.schemas.tag import TagOut
from app.schemas.user import UserOut


class ArticleBase(BaseModel):
    title: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)
    summary: Optional[str] = None
    cover_image: Optional[str] = None
    is_published: bool = True
    is_top: bool = False
    category_id: Optional[int] = None


class ArticleCreate(ArticleBase):
    content: str = Field(..., min_length=1, description="Markdown正文")
    tag_ids: List[int] = Field(default_factory=list)


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    cover_image: Optional[str] = None
    is_published: Optional[bool] = None
    is_top: Optional[bool] = None
    category_id: Optional[int] = None
    tag_ids: Optional[List[int]] = None


class ArticleListItem(BaseModel):
    id: int
    title: str
    slug: str
    summary: Optional[str] = None
    cover_image: Optional[str] = None
    is_published: bool
    is_top: bool
    views_count: int
    likes_count: int
    search_hits: int = 0
    vector_status: str
    category: Optional[CategoryOut] = None
    tags: List[TagOut] = []
    author: Optional[UserOut] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArticleDetail(ArticleListItem):
    content: str

    class Config:
        from_attributes = True
