from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    """发表评论提交体。

    评论人身份一律以登录账号为准（昵称 / 邮箱 / 头像都由服务端按 user_id 解析），
    因此这里不接受任何身份字段——留着只会让前端误以为可以自己填。
    """
    article_id: int
    parent_id: Optional[int] = None
    content: str = Field(..., min_length=1, max_length=1000)


class CommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class CommentOut(BaseModel):
    """对外评论视图：绝不输出 user_email。

    评论列表是游客可访问的公开接口，带上邮箱等于让人按文章 id 遍历
    批量收集全站评论者的真实邮箱（撞库与钓鱼素材）。后台审核需要看邮箱，
    走下面的 AdminCommentOut。
    """
    id: int
    article_id: int
    parent_id: Optional[int] = None
    user_id: Optional[int] = None
    user_name: str
    user_avatar: Optional[str] = None
    content: str
    is_approved: bool
    is_admin: bool
    likes_count: int = 0
    is_liked: bool = False
    created_at: datetime
    replies: List["CommentOut"] = []
    # 后台审核列表填充：所属文章定位（门户返回 None）
    article_title: Optional[str] = None
    article_slug: Optional[str] = None

    class Config:
        from_attributes = True


class AdminCommentOut(CommentOut):
    """后台审核专用视图：在公开字段之外附带评论人邮箱，仅 require_admin 接口可用"""
    user_email: Optional[str] = None

    class Config:
        from_attributes = True


class MyCommentOut(BaseModel):
    """个人主页「评论」维度条目：本人评论 + 所属文章定位"""
    id: int
    article_id: int
    article_title: str
    article_slug: str
    content: str
    is_approved: bool
    created_at: datetime


CommentOut.model_rebuild()
