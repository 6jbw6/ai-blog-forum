import hashlib
from typing import List
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.response import Result, PageResult, BusinessException
from app.api.deps import require_admin, get_optional_user, get_current_user
from app.models.comment import Comment
from app.models.article import Article
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentOut

router = APIRouter(prefix="/comments", tags=["评论管理 (Comments)"])


def get_gravatar(email: str) -> str:
    """基于邮箱生成 Gravatar / 备用随机头像 URL"""
    email_hash = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    return f"https://weavatar.com/avatar/{email_hash}?d=identicon"


@router.get("/article/{article_id}", response_model=Result[List[CommentOut]], summary="获取文章的树形评论列表")
def get_article_comments(article_id: int, db: Session = Depends(get_db)):
    # 仅获取已审核通过的评论
    all_comments = (
        db.query(Comment)
        .filter(Comment.article_id == article_id, Comment.is_approved == True)
        .order_by(Comment.created_at.asc())
        .all()
    )

    # 内存中构建父子树形嵌套结构
    comment_dict = {}
    root_comments = []

    for c in all_comments:
        c_out = CommentOut.model_validate(c)
        c_out.replies = []
        comment_dict[c.id] = c_out

    for c in all_comments:
        c_out = comment_dict[c.id]
        if c.parent_id and c.parent_id in comment_dict:
            comment_dict[c.parent_id].replies.append(c_out)
        else:
            root_comments.append(c_out)

    return Result.success(data=root_comments)


@router.post("", response_model=Result[CommentOut], summary="发表文章评论 (需登录)")
def create_comment(
    payload: CommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    article = db.query(Article).filter(Article.id == payload.article_id).first()
    if not article:
        raise BusinessException("目标文章不存在", code=404)

    is_admin = bool(user.role == "admin")
    user_name = payload.user_name or user.username or user.nickname or "技术读者"
    user_email = payload.user_email or user.email
    avatar = user.avatar if user.avatar else get_gravatar(user_email)

    client_ip = request.client.host if request.client else "127.0.0.1"

    comment = Comment(
        article_id=payload.article_id,
        parent_id=payload.parent_id,
        user_id=user.id,
        user_name=user_name,
        user_email=user_email,
        user_avatar=avatar,
        content=payload.content.strip(),
        is_approved=True,  # 默认通过，管理员后台可管理
        is_admin=is_admin,
        ip_address=client_ip
    )

    db.add(comment)
    db.commit()
    db.refresh(comment)

    # 如果是回复别人的评论，触发站内回复消息提醒
    if payload.parent_id:
        parent_comment = db.query(Comment).filter(Comment.id == payload.parent_id).first()
        if parent_comment:
            recipient_id = parent_comment.user_id
            if not recipient_id:
                target_user = db.query(User).filter(
                    (User.email == parent_comment.user_email) | (User.username == parent_comment.user_name)
                ).first()
                if target_user:
                    recipient_id = target_user.id

            if recipient_id and recipient_id != user.id:
                from app.models.notification import Notification
                notif = Notification(
                    user_id=recipient_id,
                    sender_name=user_name,
                    sender_avatar=avatar,
                    article_id=article.id,
                    article_title=article.title,
                    article_slug=article.slug,
                    reply_content=payload.content.strip(),
                    parent_content=parent_comment.content,
                    is_read=False
                )
                db.add(notif)
                db.commit()

    return Result.success(data=CommentOut.model_validate(comment), message="评论发表成功")


@router.get("/admin/list", response_model=Result[PageResult[CommentOut]], summary="后台分页查询评论列表 (管理员)")
def list_admin_comments(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    query = db.query(Comment).order_by(Comment.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()

    data = [CommentOut.model_validate(c) for c in items]
    return Result.success(data=PageResult.create(items=data, total=total, page=page, size=size))


@router.put("/admin/{id}/approve", response_model=Result[None], summary="审核通过/隐藏评论 (管理员)")
def toggle_comment_approval(
    id: int,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    comment = db.query(Comment).filter(Comment.id == id).first()
    if not comment:
        raise BusinessException("评论不存在", code=404)

    comment.is_approved = not comment.is_approved
    db.commit()
    return Result.success(message="评论状态已更新")


@router.delete("/admin/{id}", response_model=Result[None], summary="删除评论 (管理员)")
def delete_comment(
    id: int,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    comment = db.query(Comment).filter(Comment.id == id).first()
    if not comment:
        raise BusinessException("评论不存在", code=404)

    db.delete(comment)
    db.commit()
    return Result.success(message="评论已删除")
