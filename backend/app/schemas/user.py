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


def _ensure_strong_password(value: Optional[str]) -> Optional[str]:
    """密码强度准入：字母 + 数字混合（注册与改密时校验）。

    登录侧不做强度校验——存量弱密码账号仍可登录，但改密时会被强制升级。
    """
    if value is None:
        return value
    if not (any(c.isalpha() for c in value) and any(c.isdigit() for c in value)):
        raise ValueError("密码需同时包含字母和数字")
    return value


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="用户名或邮箱")
    password: str = Field(..., min_length=6, max_length=64, description="密码")


class UserRegister(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=8, max_length=64, description="密码（至少 8 位，字母数字混合）")
    email: EmailStr
    nickname: Optional[str] = None
    bio: Optional[str] = Field("", max_length=255, description="个人签名")

    _check_email_provider = field_validator("email")(_ensure_mainstream_email)
    _check_password_strength = field_validator("password")(_ensure_strong_password)


class UserOut(BaseModel):
    """本人视角：登录响应与 /auth/me 场景，允许携带 email"""
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


class UserPublicOut(BaseModel):
    """公开视角：文章作者等对外展示场景，绝不输出 email / is_active，
    防止游客通过文章列表批量收集全站用户邮箱（撞库与钓鱼素材）"""
    id: int
    username: str
    nickname: str
    avatar: Optional[str] = None
    bio: Optional[str] = ""
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def fill_avatar_no_email(self) -> "UserPublicOut":
        # avatar 若为空则回退到按用户名生成的默认头像（不依赖 email）
        if not self.avatar:
            self.avatar = f"https://api.dicebear.com/7.x/bottts-neutral/svg?seed={self.username}"
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
    # 修改密码必须携带旧密码：防止会话被劫持后攻击者直接换密永久接管账号
    old_password: Optional[str] = Field(None, max_length=64, description="当前密码（修改密码时必填）")
    password: Optional[str] = Field(None, min_length=8, max_length=64, description="修改新密码（至少 8 位，字母数字混合）")

    _check_email_provider = field_validator("email")(_ensure_mainstream_email)
    _check_password_strength = field_validator("password")(_ensure_strong_password)


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
    """个人主页头部公开信息（不输出 email：注册即可访问的公开接口，
    返回邮箱会被批量枚举收集，用于撞库与钓鱼）"""
    id: int
    username: str
    nickname: str
    avatar: Optional[str] = None
    bio: Optional[str] = ""
    role: str
    article_count: int = 0
    total_likes: int = 0
    created_at: datetime

    @model_validator(mode="after")
    def fill_avatar_no_email(self) -> "UserProfileItem":
        if not self.avatar:
            self.avatar = f"https://api.dicebear.com/7.x/bottts-neutral/svg?seed={self.username}"
        return self
