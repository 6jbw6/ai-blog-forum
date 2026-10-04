from typing import AsyncIterator, List
import asyncio
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db, SessionLocal
from app.core.notification_hub import notification_hub, unread_count_of
from app.core.response import Result
from app.core.utils import effective_avatar
from app.api.deps import get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/notifications", tags=["消息提醒 (Notifications)"])

# SSE 心跳间隔：中间代理通常按空闲时长断链，20s 一次注释帧足以保活
_KEEPALIVE_SECONDS = 20


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _with_live_sender(db: Session, notifications: List[Notification]) -> List[NotificationOut]:
    """发送者昵称 / 头像按账号**实时**解析，账号已注销时回退到创建当时的快照"""
    sender_ids = {n.sender_id for n in notifications if n.sender_id}
    senders = (
        {u.id: u for u in db.query(User).filter(User.id.in_(sender_ids)).all()}
        if sender_ids else {}
    )
    items: List[NotificationOut] = []
    for n in notifications:
        item = NotificationOut.model_validate(n)
        sender = senders.get(n.sender_id)
        if sender:
            item.sender_name = sender.nickname or sender.username or item.sender_name
            item.sender_avatar = effective_avatar(sender.avatar, sender.email) or item.sender_avatar
        items.append(item)
    return items


async def _notification_event_stream(request: Request, user_id: int) -> AsyncIterator[str]:
    """SSE 事件流：首帧对齐未读数，之后由广播中心实时推送；空闲时发注释帧保活"""
    queue = await notification_hub.subscribe(user_id)

    def _initial_unread() -> int:
        # 长连接不占用请求级 DB 会话，这里用短生命周期会话取一次未读数
        with SessionLocal() as session:
            return unread_count_of(session, user_id)

    try:
        yield _sse("ready", {"count": await asyncio.to_thread(_initial_unread), "notification": None})
        while True:
            if await request.is_disconnected():
                break
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield _sse("notification", payload)
    finally:
        await notification_hub.unsubscribe(user_id, queue)


@router.get("/stream", summary="站内提醒实时推送 (SSE 长连接，需登录)")
async def stream_notifications(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """事件格式：

    - `event: ready` + `{"count": 未读数}`：连上即对齐状态
    - `event: notification` + `{"count": 未读数, "notification": {...}}`：新提醒（评论博文 / 回复评论）
    - `: keep-alive` 注释帧：20s 一次心跳，防空闲断链
    """
    return StreamingResponse(
        _notification_event_stream(request, current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
            "X-Accel-Buffering": "no"  # 禁用中间代理缓冲，保证秒级送达
        }
    )


@router.get("/my", response_model=Result[List[NotificationOut]], summary="获取当前登录用户的评论消息提醒 (需登录)")
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
    return Result.success(data=_with_live_sender(db, notifications))


@router.get("/unread-count", response_model=Result[int], summary="获取未读提醒数量 (需登录)")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return Result.success(data=unread_count_of(db, current_user.id))


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
    # 广播给该用户的其他连接 / 标签页，未读红点同步归零
    notification_hub.publish(current_user.id, {"count": 0, "notification": None})
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
        notification_hub.publish(
            current_user.id, {"count": unread_count_of(db, current_user.id), "notification": None}
        )
    return Result.success(message="消息已标记为已读")
