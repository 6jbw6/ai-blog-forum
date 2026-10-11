from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from app.core.database import Base


class ArticleHit(Base):
    """浏览量 / 搜索热度的去重台账。

    一行代表「某个访客在某个自然日对某篇文章贡献过一次有效计数」。
    去重靠 (article_id, kind, viewer_key, day_bucket) 的唯一约束由数据库保证——
    并发请求同时插入时只有一个能成功，不存在「先查后插」的竞态窗口。

    刻意不建到 Article 的 relationship：文章删除由外键 ON DELETE CASCADE 在库侧连带清理，
    挂了关系反而会让 ORM 在删文章时试图把 article_id 置空（该列 NOT NULL）。
    """
    __tablename__ = "article_hits"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(8), nullable=False, comment="view=浏览 | search=搜索命中")
    viewer_key = Column(String(64), nullable=False, comment="访客标识 u:{用户id} 或 ip:{哈希}")
    day_bucket = Column(Integer, nullable=False, comment="自然日 YYYYMMDD，去重粒度")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("article_id", "kind", "viewer_key", "day_bucket", name="uq_article_hit_dedup"),
    )
