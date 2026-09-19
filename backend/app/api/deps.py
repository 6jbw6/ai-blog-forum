from typing import Optional
from fastapi import Depends, Header
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.response import BusinessException
from app.models.user import User


def get_token_from_header(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """从 Authorization 请求头提取 Bearer Token"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_current_user(
    token: Optional[str] = Depends(get_token_from_header),
    db: Session = Depends(get_db)
) -> User:
    """RBAC 鉴权依赖项：校验 JWT 令牌并提取当前登录用户"""
    if not token:
        raise BusinessException("请先登录系统", code=401)

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise BusinessException("登录凭证已过期或无效，请重新登录", code=401)

    username = payload["sub"]
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise BusinessException("用户不存在或账号已被禁用", code=401)

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """RBAC 权限守卫：仅允许具备管理员权限的用户访问"""
    if current_user.role != "admin":
        raise BusinessException("权限不足：该操作仅系统管理员可执行", code=403)
    return current_user


def get_optional_user(
    token: Optional[str] = Depends(get_token_from_header),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """可选用户识别：未登录不阻断"""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    return db.query(User).filter(User.username == payload["sub"]).first()
