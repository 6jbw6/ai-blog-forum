from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CategoryBase(BaseModel):
    name: str = Field(..., max_length=64)
    slug: str = Field(..., max_length=64)
    description: Optional[str] = None
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class CategoryOut(CategoryBase):
    id: int
    created_at: datetime
    article_count: Optional[int] = 0

    class Config:
        from_attributes = True
