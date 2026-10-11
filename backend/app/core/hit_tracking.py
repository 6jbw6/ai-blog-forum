"""浏览量与搜索热度的持久化去重

`views_count` 与 `search_hits` 不只是展示数字——`update_realtime_top_articles` 按
search_hits、views_count 倒序取前三名决定首页「置顶精选」。这两个数此前是每请求无条件 +1：
作者反复刷新自己的详情页、或匿名脚本刷搜索，都能把任意文章顶上榜。进程内限流只能抬高
成本、换个 IP 就绕过去了，所以去重必须落库。

计数口径因此从「页面加载次数」变成「独立访客天数」——同一访客对同一篇文章一天只算一次。
这是有意的取舍：一个能被无限刷新的数字对排序毫无价值，而真实读者一天内反复刷同一篇
本来也不该被当成多次阅读。
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Iterable, Optional

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import client_ip_of, hit_limiter
from app.models.article import Article
from app.models.article_hit import ArticleHit
from app.models.user import User

logger = logging.getLogger("app.hits")

KIND_VIEW = "view"
KIND_SEARCH = "search"


def _today_bucket() -> int:
    return int(datetime.utcnow().strftime("%Y%m%d"))


def viewer_key_of(request: Request, user: Optional[User]) -> str:
    """访客标识：登录用户按账号（换设备仍算同一人），访客按 IP 哈希。

    IP 不明文落库——台账要留 30 天，存明文等于攒一份访客行踪记录。
    """
    if user is not None:
        return f"u:{user.id}"
    return "ip:" + hashlib.sha256(client_ip_of(request).encode("utf-8")).hexdigest()[:32]


def _counted(db: Session, article_id: int, kind: str, viewer_key: str) -> bool:
    """尝试登记一次计数，返回这次是否真的算数。

    撞唯一约束即说明该访客今天已经为这篇文章贡献过一次。用 SAVEPOINT 包住插入，
    冲突时只回滚这一条、不影响外层事务里已有的其它改动。
    """
    try:
        with db.begin_nested():
            db.add(ArticleHit(
                article_id=article_id,
                kind=kind,
                viewer_key=viewer_key,
                day_bucket=_today_bucket(),
            ))
        return True
    except IntegrityError:
        return False


def record_article_view(db: Session, article: Article, request: Request, user: Optional[User]) -> None:
    """登记一次浏览，并按去重结果累加 views_count。作者本人访问不计。"""
    if user is not None and user.id == article.author_id:
        return
    if not hit_limiter.allow(f"hit:ip:{client_ip_of(request)}"):
        return
    if _counted(db, article.id, KIND_VIEW, viewer_key_of(request, user)):
        article.views_count += 1
        db.commit()


def record_search_hits(db: Session, article_ids: Iterable[int], request: Request, user: Optional[User]) -> None:
    """登记一次搜索命中，并按去重结果累加 search_hits。搜索者自己的文章不计。

    站内搜索与 AI 语义检索共用这里，因此换接口刷不会重置去重。
    """
    ids = list(article_ids)
    if not ids:
        return
    if not hit_limiter.allow(f"hit:ip:{client_ip_of(request)}"):
        return

    if user is not None:
        own_ids = {
            r[0] for r in db.query(Article.id)
            .filter(Article.id.in_(ids), Article.author_id == user.id)
            .all()
        }
        ids = [i for i in ids if i not in own_ids]
    if not ids:
        return

    viewer_key = viewer_key_of(request, user)
    counted = [i for i in ids if _counted(db, i, KIND_SEARCH, viewer_key)]
    if not counted:
        return

    try:
        db.query(Article).filter(Article.id.in_(counted)).update(
            {Article.search_hits: Article.search_hits + 1},
            synchronize_session=False
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("搜索热度累加失败，本次跳过", exc_info=True)


def prune_old_hits(db: Session) -> int:
    """清掉超过保留期的台账行，返回删除行数（启动时调用一次）"""
    cutoff = datetime.utcnow() - timedelta(days=settings.HIT_LOG_RETENTION_DAYS)
    deleted = (
        db.query(ArticleHit)
        .filter(ArticleHit.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
