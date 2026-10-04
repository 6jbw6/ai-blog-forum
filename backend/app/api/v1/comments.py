from typing import List, Optional
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.notification_hub import notification_hub, unread_count_of
from app.core.response import Result, PageResult, BusinessException
from app.core.utils import effective_avatar
from app.api.deps import require_admin, get_optional_user, get_current_user
from app.models.comment import Comment
from app.models.comment_like import CommentLike
from app.models.article import Article
from app.models.notification import Notification
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentUpdate, CommentOut, MyCommentOut
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/comments", tags=["评论管理 (Comments)"])

# 评论被删除后，提醒卡片里展示的占位文案（提醒本身保留，不整条删除）
DELETED_COMMENT_PLACEHOLDER = "该评论已删除"


def _live_avatar(comment: Comment) -> Optional[str]:
    """登录用户的评论实时取其当前头像；访客评论（无 user_id）保留发帖时的快照"""
    u = comment.user
    if u is None:
        return comment.user_avatar
    return effective_avatar(u.avatar, u.email)


@router.get("/article/{article_id}", response_model=Result[List[CommentOut]], summary="获取文章的树形评论列表")
def get_article_comments(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    # 仅获取已审核通过的评论
    all_comments = (
        db.query(Comment)
        .options(joinedload(Comment.user))
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
        c_out.user_avatar = _live_avatar(c)
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


def _resolve_account_id(db: Session, user_id: Optional[int], user_email: Optional[str], user_name: Optional[str]) -> Optional[int]:
    """访客评论（无 user_id 的历史数据）按邮箱 / 昵称反查账号，查不到则不派发"""
    if user_id:
        return user_id
    target = db.query(User).filter(
        (User.email == user_email) | (User.username == user_name)
    ).first()
    return target.id if target else None


def _dispatch_comment_notifications(db: Session, article: Article, comment: Comment, sender: User) -> None:
    """评论落库后的站内消息派发（同一评论可能派发给多个收件人，按人去重）

    - **回复某条评论**（parent_id 有值）→ 被回复者收到「回复了你的评论」，附被回复原文；
    - **博文作者** 始终收到「评论了你的博文」——顶级评论、以及发生在别人评论线程里的回复都算，
      博主因此不会漏掉自己博文下的任何一条讨论；
    - 同一人只发一条（被回复者恰好就是博主时保留信息量更大的 reply 类型）；
    - 收件人是评论者自己（自评 / 自回）时跳过，不给自己发消息。
    """
    targets: dict[int, dict] = {}

    if comment.parent_id:
        parent_comment = db.query(Comment).filter(Comment.id == comment.parent_id).first()
        if parent_comment:
            parent_author_id = _resolve_account_id(
                db, parent_comment.user_id, parent_comment.user_email, parent_comment.user_name
            )
            if parent_author_id:
                targets[parent_author_id] = {"kind": "reply", "parent_content": parent_comment.content or ""}

    if article.author_id:
        # setdefault：博主若就是被回复者，保留已排定的 reply 类型，不重复发第二条
        targets.setdefault(article.author_id, {"kind": "article_comment", "parent_content": ""})

    added = 0
    created: list[Notification] = []
    for recipient_id, meta in targets.items():
        if recipient_id == sender.id:
            continue
        notif = Notification(
            user_id=recipient_id,
            kind=meta["kind"],
            comment_id=comment.id,
            sender_id=sender.id,
            sender_name=comment.user_name,
            sender_avatar=comment.user_avatar,
            article_id=article.id,
            article_title=article.title,
            article_slug=article.slug,
            reply_content=comment.content,
            parent_content=meta["parent_content"],
            is_read=False
        )
        db.add(notif)
        created.append(notif)
        added += 1

    if added:
        db.commit()
        # 落库后立即 SSE 推送：收件人在线时红点与提醒列表秒级更新，无需等待轮询
        for notif in created:
            db.refresh(notif)
            notification_hub.publish(notif.user_id, {
                "count": unread_count_of(db, notif.user_id),
                "notification": _notification_payload(notif, sender),
            })


def _notification_payload(notif: Notification, sender: User) -> dict:
    """推送负载与 /notifications/my 的条目同构，前端可原地插入列表"""
    payload = NotificationOut.model_validate(notif).model_dump(mode="json")
    # 推送瞬间就按账号实时解析发送者昵称 / 头像（发送者即当前评论人）
    payload["sender_name"] = sender.nickname or sender.username or payload["sender_name"]
    payload["sender_avatar"] = effective_avatar(sender.avatar, sender.email) or payload["sender_avatar"]
    return payload


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

    # 站内消息提醒：回复评论 → 通知被回复者；博文作者 → 收到博文下所有评论提醒
    _dispatch_comment_notifications(db, article, comment, user)

    return Result.success(data=CommentOut.model_validate(comment), message="评论发表成功")


def _sync_edited_comment_snapshots(db: Session, comment: Comment) -> int:
    """评论被编辑后，同步提醒卡片里的正文快照（返回受影响行数）

    - 本评论作为提醒正文（`reply_content`）→ 直接覆盖为新内容；
    - 本评论被别人回复时还作为「被回复原文」（`parent_content`）→ 按其子评论反查更新；
    - 只改内容、不重置 `is_read`：编辑是订正原文，不该再打扰收件人一次。
    """
    updated = (
        db.query(Notification)
        .filter(Notification.comment_id == comment.id)
        .update({"reply_content": comment.content}, synchronize_session=False)
    )

    child_ids = [
        cid for (cid,) in db.query(Comment.id).filter(Comment.parent_id == comment.id).all()
    ]
    if child_ids:
        updated += (
            db.query(Notification)
            .filter(Notification.comment_id.in_(child_ids))
            .update({"parent_content": comment.content}, synchronize_session=False)
        )
    return updated


@router.get("/admin/list", response_model=Result[PageResult[CommentOut]], summary="后台分页查询评论列表 (管理员)")
def list_admin_comments(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    query = (
        db.query(Comment)
        .options(joinedload(Comment.user))
        .order_by(Comment.created_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()

    data = []
    for c in items:
        c_out = CommentOut.model_validate(c)
        c_out.user_avatar = _live_avatar(c)
        data.append(c_out)
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
    """收集整条评论线程并按叶子优先删除（comment_likes 由外键 ON DELETE CASCADE 连带清理）

    评论删除后**站内提醒保留**：只把它在提醒里的快照正文标记为「该评论已删除」，
    收件人仍能看到这条互动记录与来源博文（外键 ON DELETE SET NULL 负责把 comment_id 置空）。
    """
    ids = [root_id]
    frontier = [root_id]
    while frontier:
        frontier = [
            cid for (cid,) in db.query(Comment.id).filter(Comment.parent_id.in_(frontier)).all()
        ]
        ids.extend(frontier)

    if ids:
        # 本子树评论作为提醒正文 → 标记为已删除
        db.query(Notification).filter(Notification.comment_id.in_(ids)).update(
            {"reply_content": DELETED_COMMENT_PLACEHOLDER}, synchronize_session=False
        )
        # 触发提醒的回复本身也在被删子树里 → 它引用的「回复原文」同样标记
        inner_trigger_ids = [
            cid for (cid,) in db.query(Comment.id).filter(Comment.parent_id.in_(ids)).all()
        ]
        if inner_trigger_ids:
            db.query(Notification).filter(Notification.comment_id.in_(inner_trigger_ids)).update(
                {"parent_content": DELETED_COMMENT_PLACEHOLDER}, synchronize_session=False
            )

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
    # 提醒卡片里的正文是发表当时的快照：编辑后同步，避免收件人看到与原文不一致的内容
    _sync_edited_comment_snapshots(db, comment)
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
