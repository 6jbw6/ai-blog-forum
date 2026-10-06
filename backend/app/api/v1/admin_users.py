"""管理员用户管理：搜索、封号、解封 (require_admin)"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import Result, BusinessException
from app.api.deps import require_admin
from app.models.user import User

router = APIRouter(prefix="/admin/users", tags=["用户管理 (Admin)"])


def _escape_like(keyword: str) -> str:
    return keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class AdminUserItem(BaseModel):
    id: int
    username: str
    nickname: str
    email: str
    role: str
    is_active: bool
    ban_reason: Optional[str] = None
    banned_at: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class BanActionPayload(BaseModel):
    reason: str = Field(..., min_length=2, max_length=200, description="封禁/解封原因 (必填)")


def _fmt(dt) -> Optional[str]:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


@router.get("", response_model=Result[List[AdminUserItem]], summary="搜索用户 (管理员)")
def search_users_admin(
    keyword: Optional[str] = Query(None, max_length=64, description="用户名 / 昵称 / 用户ID，留空返回全部"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """按用户名、昵称或专属数字 ID 快速检索；关键词为纯数字时优先精确匹配 ID"""
    query = db.query(User)
    kw = (keyword or "").strip()
    if kw:
        if kw.isdigit():
            # 纯数字：先精确匹配 ID，再回退模糊匹配用户名/昵称
            uid = int(kw)
            query = query.filter(
                or_(
                    User.id == uid,
                    User.username.like(f"%{_escape_like(kw)}%", escape="\\"),
                    User.nickname.like(f"%{_escape_like(kw)}%", escape="\\"),
                )
            )
        else:
            query = query.filter(
                or_(
                    User.username.like(f"%{_escape_like(kw)}%", escape="\\"),
                    User.nickname.like(f"%{_escape_like(kw)}%", escape="\\"),
                )
            )
    users = query.order_by(User.id).limit(50).all()
    return Result.success(data=[
        AdminUserItem(
            id=u.id,
            username=u.username,
            nickname=u.nickname,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            ban_reason=u.ban_reason,
            banned_at=_fmt(u.banned_at),
            created_at=_fmt(u.created_at) or "",
        )
        for u in users
    ])


@router.post("/{user_id}/ban", response_model=Result[AdminUserItem], summary="封禁账号 (管理员)")
def ban_user(
    user_id: int,
    payload: BanActionPayload,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise BusinessException("用户不存在", code=404)
    if not user.is_active:
        raise BusinessException("该账号已处于封禁状态", code=400)
    if user.id == admin.id:
        raise BusinessException("不能封禁自己", code=400)
    if user.role == "admin":
        raise BusinessException("不能封禁其他管理员账号", code=400)

    from app.core.content_moderation import ban_user
    ban_user(db, user, f"管理员手动封禁：{payload.reason}")
    db.refresh(user)
    return Result.success(
        data=AdminUserItem(
            id=user.id, username=user.username, nickname=user.nickname, email=user.email,
            role=user.role, is_active=user.is_active, ban_reason=user.ban_reason,
            banned_at=_fmt(user.banned_at), created_at=_fmt(user.created_at) or "",
        ),
        message=f"已封禁用户「{user.username}」",
    )


@router.post("/{user_id}/unban", response_model=Result[AdminUserItem], summary="解封账号 (管理员)")
def unban_user_endpoint(
    user_id: int,
    payload: BanActionPayload,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise BusinessException("用户不存在", code=404)
    if user.is_active:
        raise BusinessException("该账号未被封禁", code=400)

    from app.core.content_moderation import unban_user
    unban_user(db, user)
    db.refresh(user)
    return Result.success(
        data=AdminUserItem(
            id=user.id, username=user.username, nickname=user.nickname, email=user.email,
            role=user.role, is_active=user.is_active, ban_reason=None,
            banned_at=None, created_at=_fmt(user.created_at) or "",
        ),
        message=f"已解封用户「{user.username}」，原因：{payload.reason}",
    )
