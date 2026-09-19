from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.article_tag import article_tags


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, comment="标签名称")
    slug = Column(String(64), unique=True, nullable=False, comment="标签别名")
    color = Column(String(32), default="#059669", nullable=False, comment="标签UI展示色")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    articles = relationship("Article", secondary=article_tags, back_populates="tags")
