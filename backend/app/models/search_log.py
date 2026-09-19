from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.core.database import Base


class SearchLog(Base):
    """
    搜索与 AI 提问热度追踪表 (用于动态推荐热门问题)
    """
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    query = Column(String(255), nullable=False, unique=True, index=True, comment="检索或提问问题文本")
    search_type = Column(String(32), default="ai_ask", comment="类型: ai_ask | semantic_search | portal_search")
    hit_count = Column(Integer, default=1, nullable=False, index=True, comment="搜索频次与热度权重")
    last_searched_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True, comment="最近被提问/检索时间")
