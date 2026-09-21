"""门户公开的用户检索与个人主页接口（游客可访问）"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import Result, BusinessException
from app.core.utils import effective_avatar
from app.models.article import Article
from app.models.user import User
from app.schemas.user import UserSearchItem, UserProfileItem

router = APIRouter(prefix="/users", tags=["用户"])


def _escape_like(keyword: str) -> str:
    """转义 LIKE 通配符，防止用户输入 %/_ 扰动匹配范围"""
    return (
        keyword.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


@router.get("/search", response_model=Result[list[UserSearchItem]], summary="按用户名/昵称模糊搜索用户（门户公开）")
def search_users(
    q: str = Query(..., min_length=1, max_length=64, description="搜索关键词"),
    limit: int = Query(8, ge=1, le=20, description="返回条数上限"),
    db: Session = Depends(get_db),
):
    """
    门户搜索页的用户维度检索：
    匹配用户名或展示昵称（MySQL collation 不区分大小写），附带各用户
    已发布博文数，博文数多的活跃作者排在前面。
    """
    keyword = f"%{_escape_like(q.strip())}%"
    users = (
        db.query(User)
        .filter(
            User.is_active == True,  # noqa: E712
            (User.username.like(keyword, escape="\\")) | (User.nickname.like(keyword, escape="\\")),
        )
        .order_by(User.id)
        .limit(limit)
        .all()
    )
    if not users:
        return Result.success(data=[])

    # 批量统计已发布博文数（一次分组查询，避免逐用户 N+1）
    counts = dict(
        db.query(Article.author_id, func.count(Article.id))
        .filter(
            Article.author_id.in_([u.id for u in users]),
            Article.is_published == True,  # noqa: E712
        )
        .group_by(Article.author_id)
        .all()
    )

    items = [
        UserSearchItem(
            id=u.id,
            username=u.username,
            nickname=u.nickname,
            avatar=effective_avatar(u.avatar, u.email),
            bio=u.bio or "",
            article_count=counts.get(u.id, 0),
            created_at=u.created_at,
        )
        for u in users
    ]
    items.sort(key=lambda x: (-x.article_count, x.id))
    return Result.success(data=items)


@router.get("/{user_id}/profile", response_model=Result[UserProfileItem], summary="获取用户公开资料（个人主页头部）")
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    """个人主页公开资料：注册即可访问，包含昵称/签名/头像/邮箱、已发布博文数与累计获赞数"""
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
    if not user:
        raise BusinessException("用户不存在或已注销", code=404)

    stats = (
        db.query(func.count(Article.id), func.coalesce(func.sum(Article.likes_count), 0))
        .filter(Article.author_id == user_id, Article.is_published == True)  # noqa: E712
        .first()
    )

    return Result.success(
        data=UserProfileItem(
            id=user.id,
            username=user.username,
            nickname=user.nickname,
            email=user.email,
            avatar=user.avatar,
            bio=user.bio or "",
            role=user.role,
            article_count=int(stats[0] or 0),
            total_likes=int(stats[1] or 0),
            created_at=user.created_at,
        )
    )
