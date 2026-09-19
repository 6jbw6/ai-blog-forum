from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.article_tag import article_tags


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False, index=True, comment="文章标题")
    slug = Column(String(255), unique=True, index=True, nullable=False, comment="URL唯一标识")
    summary = Column(Text, nullable=True, comment="文章摘要(支持AI一键生成)")
    content = Column(LONGTEXT, nullable=False, comment="Markdown文章正文")
    cover_image = Column(String(255), nullable=True, comment="封面图地址")
    
    is_published = Column(Boolean, default=True, nullable=False, comment="是否发布(0草稿 1发布)")
    is_top = Column(Boolean, default=False, nullable=False, comment="是否置顶")
    views_count = Column(Integer, default=0, nullable=False, comment="浏览阅读量")
    likes_count = Column(Integer, default=0, nullable=False, comment="点赞数")
    search_hits = Column(Integer, default=0, nullable=False, comment="搜索与检索命中热度")
    
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # 核心 AI 知识库标识
    vector_status = Column(String(32), default="unprocessed", nullable=False, comment="向量化状态: unprocessed|indexed|failed")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    category = relationship("Category", back_populates="articles")
    author = relationship("User", back_populates="articles")
    tags = relationship("Tag", secondary=article_tags, back_populates="articles")
    chunks = relationship("ArticleChunk", back_populates="article", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="article", cascade="all, delete-orphan")
