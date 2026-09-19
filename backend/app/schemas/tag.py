from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class TagBase(BaseModel):
    name: str = Field(..., max_length=64)
    slug: str = Field(..., max_length=64)
    color: str = Field(default="#059669", max_length=32)


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    color: Optional[str] = None


class TagOut(TagBase):
    id: int
    created_at: datetime
    article_count: Optional[int] = 0

    class Config:
        from_attributes = True
