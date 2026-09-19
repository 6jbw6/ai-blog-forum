from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="用户名或邮箱")
    password: str = Field(..., min_length=6, max_length=64, description="密码")


class UserRegister(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    email: EmailStr
    nickname: Optional[str] = None
    bio: Optional[str] = Field("", max_length=255, description="个人签名")


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


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserProfileUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=1, max_length=64, description="用户名")
    nickname: Optional[str] = Field(None, min_length=1, max_length=64, description="用户昵称")
    avatar: Optional[str] = Field(None, description="头像 URL")
    bio: Optional[str] = Field(None, max_length=255, description="个人签名")
    password: Optional[str] = Field(None, min_length=6, max_length=64, description="修改新密码")
