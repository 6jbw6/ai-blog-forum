from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.response import Result
from app.api.deps import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["消息提醒 (Notifications)"])


@router.get("/my", response_model=Result[List[NotificationOut]], summary="获取当前登录用户的评论回复消息提醒 (需登录)")
def get_my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return Result.success(data=[NotificationOut.model_validate(n) for n in notifications])


@router.get("/unread-count", response_model=Result[int], summary="获取未读提醒数量 (需登录)")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)
        .count()
    )
    return Result.success(data=count)


@router.put("/read-all", response_model=Result[None], summary="将全部提醒标记为已读 (需登录)")
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return Result.success(message="全部消息已标记为已读")


@router.put("/read/{id}", response_model=Result[None], summary="将单条提醒标记为已读 (需登录)")
def mark_as_read(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notif = db.query(Notification).filter(
        Notification.id == id,
        Notification.user_id == current_user.id
    ).first()
    if notif:
        notif.is_read = True
        db.commit()
    return Result.success(message="消息已标记为已读")
