from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class CommentCreate(BaseModel):
    article_id: int
    parent_id: Optional[int] = None
    user_name: Optional[str] = Field(None, max_length=64)
    user_email: Optional[EmailStr] = None
    content: str = Field(..., min_length=1, max_length=1000)


class CommentOut(BaseModel):
    id: int
    article_id: int
    parent_id: Optional[int] = None
    user_name: str
    user_email: str
    user_avatar: Optional[str] = None
    content: str
    is_approved: bool
    is_admin: bool
    created_at: datetime
    replies: List["CommentOut"] = []

    class Config:
        from_attributes = True


CommentOut.model_rebuild()
