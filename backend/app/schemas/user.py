from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.email_policy import EMAIL_DOMAIN_REJECT_MESSAGE, is_mainstream_email
from app.core.utils import effective_avatar


def _ensure_mainstream_email(value: Optional[str]) -> Optional[str]:
    """邮箱服务商准入：只允许主流邮箱，自有域名 / 自建邮局一律拒绝"""
    if value is None:
        return value
    if not is_mainstream_email(str(value)):
        raise ValueError(EMAIL_DOMAIN_REJECT_MESSAGE)
    return value


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="用户名或邮箱")
    password: str = Field(..., min_length=6, max_length=64, description="密码")


class UserRegister(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    email: EmailStr
    nickname: Optional[str] = None
    bio: Optional[str] = Field("", max_length=255, description="个人签名")

    _check_email_provider = field_validator("email")(_ensure_mainstream_email)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    nickname: str
    avatar: Optional[str] = None
    bio: Optional[str] = ""
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def fill_avatar_from_email(self) -> "UserOut":
        self.avatar = effective_avatar(self.avatar, self.email)
        return self


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=1, max_length=64, description="用户名")
    nickname: Optional[str] = Field(None, min_length=1, max_length=64, description="用户昵称")
    # EmailStr 校验格式；服务商准入由下面的校验器统一把关（只允许主流邮箱，不接受自有域名）
    email: Optional[EmailStr] = Field(None, description="电子邮箱（可修改，仅支持主流邮箱服务商）")
    avatar: Optional[str] = Field(None, description="头像 URL")
    bio: Optional[str] = Field(None, max_length=255, description="个人签名")
    password: Optional[str] = Field(None, min_length=6, max_length=64, description="修改新密码")

    _check_email_provider = field_validator("email")(_ensure_mainstream_email)


class UserSearchItem(BaseModel):
    """门户搜索页的用户检索结果条目"""
    id: int
    username: str
    nickname: str
    avatar: Optional[str] = None
    bio: Optional[str] = ""
    article_count: int = 0
    created_at: datetime


class UserProfileItem(BaseModel):
    """个人主页头部公开信息"""
    id: int
    username: str
    nickname: str
    email: str
    avatar: Optional[str] = None
    bio: Optional[str] = ""
    role: str
    article_count: int = 0
    total_likes: int = 0
    created_at: datetime

    @model_validator(mode="after")
    def fill_avatar_from_email(self) -> "UserProfileItem":
        self.avatar = effective_avatar(self.avatar, self.email)
        return self
