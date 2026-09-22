from typing import List, Optional
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.response import Result, PageResult, BusinessException
from app.core.utils import effective_avatar
from app.api.deps import require_admin, get_optional_user, get_current_user
from app.models.comment import Comment
from app.models.comment_like import CommentLike
from app.models.article import Article
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentUpdate, CommentOut, MyCommentOut

router = APIRouter(prefix="/comments", tags=["评论管理 (Comments)"])


@router.get("/article/{article_id}", response_model=Result[List[CommentOut]], summary="获取文章的树形评论列表")
def get_article_comments(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    # 仅获取已审核通过的评论
    all_comments = (
        db.query(Comment)
        .filter(Comment.article_id == article_id, Comment.is_approved == True)
        .order_by(Comment.created_at.asc())
        .all()
    )

    # 登录态下一次批量查询，标出当前用户点过赞的评论
    liked_ids = set()
    if current_user and all_comments:
        liked_ids = {
            cid for (cid,) in db.query(CommentLike.comment_id)
            .filter(
                CommentLike.user_id == current_user.id,
                CommentLike.comment_id.in_([c.id for c in all_comments])
            )
            .all()
        }

    # 内存中构建父子树形嵌套结构
    comment_dict = {}
    root_comments = []

    for c in all_comments:
        c_out = CommentOut.model_validate(c)
        c_out.replies = []
        c_out.is_liked = c.id in liked_ids
        comment_dict[c.id] = c_out

    for c in all_comments:
        c_out = comment_dict[c.id]
        if c.parent_id and c.parent_id in comment_dict:
            comment_dict[c.parent_id].replies.append(c_out)
        else:
            root_comments.append(c_out)

    return Result.success(data=root_comments)


@router.get("/my", response_model=Result[List[MyCommentOut]], summary="获取当前登录用户的评论列表 (需登录，个人主页用)")
def get_my_comments(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """本人评论时间线：附带所属文章标题与 slug，供个人主页跳转原文"""
    rows = (
        db.query(Comment, Article.title, Article.slug)
        .join(Article, Comment.article_id == Article.id)
        .filter(Comment.user_id == user.id)
        .order_by(Comment.created_at.desc())
        .all()
    )
    items = [
        MyCommentOut(
            id=c.id,
            article_id=c.article_id,
            article_title=title,
            article_slug=slug,
            content=c.content,
            is_approved=c.is_approved,
            created_at=c.created_at,
        )
        for c, title, slug in rows
    ]
    return Result.success(data=items)


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
    avatar = effective_avatar(user.avatar, user_email)

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


def _delete_comment_subtree(db: Session, root_id: int) -> int:
    """收集整条评论线程并按叶子优先删除（comment_likes 由外键 ON DELETE CASCADE 连带清理）"""
    ids = [root_id]
    frontier = [root_id]
    while frontier:
        frontier = [
            cid for (cid,) in db.query(Comment.id).filter(Comment.parent_id.in_(frontier)).all()
        ]
        ids.extend(frontier)

    for cid in reversed(ids):
        db.query(Comment).filter(Comment.id == cid).delete(synchronize_session=False)
    return len(ids)


@router.delete("/admin/{id}", response_model=Result[None], summary="删除评论 (管理员)")
def delete_comment(
    id: int,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    comment = db.query(Comment).filter(Comment.id == id).first()
    if not comment:
        raise BusinessException("评论不存在", code=404)

    _delete_comment_subtree(db, id)
    db.commit()
    return Result.success(message="评论已删除")


@router.post("/{id}/like", summary="点赞或取消点赞评论 (需登录)")
def like_comment(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comment = db.query(Comment).filter(Comment.id == id).first()
    if not comment:
        raise BusinessException("评论不存在", code=404)

    existing = db.query(CommentLike).filter(
        CommentLike.user_id == current_user.id,
        CommentLike.comment_id == comment.id
    ).first()

    if existing:
        db.delete(existing)
        comment.likes_count = max(0, comment.likes_count - 1)
        db.commit()
        return Result.success(data={"liked": False, "likes_count": comment.likes_count}, message="已取消点赞")

    db.add(CommentLike(user_id=current_user.id, comment_id=comment.id))
    comment.likes_count += 1
    db.commit()
    return Result.success(data={"liked": True, "likes_count": comment.likes_count}, message="点赞成功")


@router.put("/{id}", response_model=Result[CommentOut], summary="编辑评论内容 (仅作者本人)")
def update_comment(
    id: int,
    payload: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comment = db.query(Comment).filter(Comment.id == id).first()
    if not comment:
        raise BusinessException("评论不存在", code=404)

    # 管理员可删他人评论，但不代改他人发言，避免篡改原文
    if comment.user_id != current_user.id:
        raise BusinessException("只能修改自己发表的评论", code=403)

    content = payload.content.strip()
    if not content:
        raise BusinessException("评论内容不能为空", code=400)

    comment.content = content
    db.commit()
    db.refresh(comment)
    return Result.success(data=CommentOut.model_validate(comment), message="评论已更新")


@router.delete("/{id}", response_model=Result[None], summary="删除评论 (作者本人或管理员)")
def delete_own_comment(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comment = db.query(Comment).filter(Comment.id == id).first()
    if not comment:
        raise BusinessException("评论不存在", code=404)

    if comment.user_id != current_user.id and current_user.role != "admin":
        raise BusinessException("只能删除自己发表的评论", code=403)

    _delete_comment_subtree(db, id)
    db.commit()
    return Result.success(message="评论已删除")
