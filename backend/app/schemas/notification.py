from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    user_id: int
    sender_name: str
    sender_avatar: Optional[str] = None
    article_id: int
    article_title: str
    article_slug: str
    reply_content: str
    parent_content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
