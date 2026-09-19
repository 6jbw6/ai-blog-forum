from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, comment="分类名称")
    slug = Column(String(64), unique=True, index=True, nullable=False, comment="URL唯一标识")
    description = Column(String(255), nullable=True, comment="分类描述")
    sort_order = Column(Integer, default=0, nullable=False, comment="排序权重")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    articles = relationship("Article", back_populates="category")
