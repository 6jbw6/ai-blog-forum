"""站内提醒的进程内 SSE 广播中心

单 uvicorn worker 部署下，发布方（评论 / 已读接口所在线程）与订阅方（SSE 长连接协程）在同一进程，
用「每个用户一组 asyncio.Queue」即可做到秒级推送；多 worker 或分布式部署时把 publish 换成 Redis pub/sub 即可。

线程安全：业务接口跑在 FastAPI 的线程池里，写队列必须切回事件循环（call_soon_threadsafe），
因此应用启动时通过 bind_loop() 绑定主循环。
"""
import asyncio
import logging
from typing import Dict, Optional, Set

logger = logging.getLogger("app.notification_hub")


class NotificationHub:
    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._subscribers: Dict[int, Set[asyncio.Queue]] = {}

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """应用启动时绑定主事件循环，供同步线程安全投递"""
        self._loop = loop

    async def subscribe(self, user_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=32)
        self._subscribers.setdefault(user_id, set()).add(queue)
        return queue

    async def unsubscribe(self, user_id: int, queue: asyncio.Queue) -> None:
        queues = self._subscribers.get(user_id)
        if not queues:
            return
        queues.discard(queue)
        if not queues:
            self._subscribers.pop(user_id, None)

    def publish(self, user_id: int, payload: dict) -> None:
        """向该用户的所有在线连接投递消息（无线程阻塞；投递失败只记日志，不影响业务）"""
        queues = list(self._subscribers.get(user_id) or ())
        loop = self._loop
        if not queues or loop is None or loop.is_closed():
            return
        for queue in queues:
            try:
                loop.call_soon_threadsafe(self._offer, queue, payload)
            except RuntimeError:  # 事件循环正在关闭
                return

    @staticmethod
    def _offer(queue: asyncio.Queue, payload: dict) -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            # 订阅端消费不过来时丢最旧的一条，保证推送永不阻塞业务线程
            try:
                queue.get_nowait()
                queue.put_nowait(payload)
            except Exception:
                logger.warning("通知推送队列已满且清理失败，本条消息丢弃")

    def online_user_count(self) -> int:
        return len(self._subscribers)


def unread_count_of(db, user_id: int) -> int:
    """未读提醒数：列表接口、SSE 推送负载、已读回执共用同一口径"""
    from app.models.notification import Notification  # 延迟导入，避免核心层与模型层互相依赖

    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .count()
    )


notification_hub = NotificationHub()
