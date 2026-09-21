import hashlib
from typing import Optional


def gravatar_url(email: str) -> str:
    """基于邮箱生成 Gravatar / 备用随机头像 URL"""
    email_hash = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    return f"https://weavatar.com/avatar/{email_hash}?d=identicon"


def effective_avatar(avatar: Optional[str], email: Optional[str]) -> Optional[str]:
    """用户未上传头像时按邮箱推导，保证评论、列表、个人中心展示同一头像"""
    if avatar:
        return avatar
    return gravatar_url(email) if email else None
