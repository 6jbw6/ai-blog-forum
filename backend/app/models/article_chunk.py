from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship
from app.core.database import Base


class ArticleChunk(Base):
    """
    文章向量切片表 (RAG 知识库检索核心数据实体)
    用于存储博文分块文本、标题层级元数据以及高维特征向量
    """
    __tablename__ = "article_chunks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False, comment="分块序号")
    chunk_title = Column(String(255), nullable=True, comment="所属章节标题或文章标题")
    content = Column(Text, nullable=False, comment="分块正文切片")
    
    # 存储 Embedding 向量 (JSON 序列化后的浮点数数组，兼具高灵活性与零额外外部存储依赖)
    embedding_json = Column(LONGTEXT, nullable=False, comment="特征向量 JSON 序列化数据")
    
    token_count = Column(Integer, default=0, nullable=False, comment="切片估算 Token 数量")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    article = relationship("Article", back_populates="chunks")
