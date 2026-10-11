"""进程内滑动窗口限流：为高危端点（登录爆破、匿名刷 LLM 余额）提供最基础的防滥用闸门。

设计取舍：不引入 Redis 等外部依赖，计数随进程生命周期存续——单实例部署下即够用；
多 worker / 多实例部署时各进程独立计数，整体上限近似按进程数放大，上量后应替换为
共享存储的分布式限流。限流命中统一抛 HTTP 429，经由全局异常处理器输出统一 JSON 结构。
"""
import threading
import time
from collections import deque

from fastapi import Request

from app.core.config import settings

# key 空间安全上限：超过后回收已滑出窗口的 key，防止公网扫描把 dict 撑到无界
_MAX_TRACKED_KEYS = 10_000


def parse_rate(spec: str, fallback: tuple[int, float] = (10, 60.0)) -> tuple[int, float]:
    """解析「次数/窗口秒」格式的限流配置，如 "10/60" → (10, 60.0)；非法配置回退默认值"""
    try:
        count_str, _, window_str = spec.partition("/")
        count = int(count_str.strip())
        window = float(window_str.strip() or 60)
        if count <= 0 or window <= 0:
            raise ValueError
        return count, window
    except ValueError:
        return fallback


class SlidingWindowRateLimiter:
    """按 key（IP / 账号）计数的滑动窗口限流器，线程安全"""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        window_start = now - self.window_seconds
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= window_start:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            if len(self._hits) > _MAX_TRACKED_KEYS:
                for stale_key, stale_hits in list(self._hits.items()):
                    if not stale_hits or stale_hits[-1] <= window_start:
                        del self._hits[stale_key]
            return True

    def reset(self) -> None:
        """清空全部计数（测试辅助）"""
        with self._lock:
            self._hits.clear()


# 计数写入闸门：views_count / search_hits 的持久化去重台账（article_hits）每收到一次
# 浏览或搜索命中就要尝试插一行，撞唯一约束才算重复。这道闸拦在插库之前，
# 免得有人拿高频请求把数据库当压测靶子——真正的去重正确性由台账的唯一约束保证。
# 文章详情、站内搜索、AI 语义检索三条路径共用这一个实例，同一来源 IP 合并计数。
hit_limiter = SlidingWindowRateLimiter(
    *parse_rate(settings.HIT_RATE_LIMIT, fallback=(60, 60.0))
)


def client_ip_of(request: Request, trust_proxy_headers: bool | None = None) -> str:
    """取调用方 IP。

    只有在显式开启 TRUST_PROXY_HEADERS（即前面确有可信反向代理）时才采信
    X-Forwarded-For——否则该请求头可被客户端任意伪造，反而成为绕过限流的通道；
    直连场景下 socket 对端地址即是真实来源。
    """
    if trust_proxy_headers is None:
        trust_proxy_headers = settings.TRUST_PROXY_HEADERS
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"
