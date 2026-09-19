from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True, nullable=False, comment="用户名/登录账号")
    password_hash = Column(String(255), nullable=False, comment="加盐哈希密码")
    email = Column(String(128), unique=True, index=True, nullable=False, comment="电子邮箱")
    nickname = Column(String(64), nullable=False, default="博主", comment="展示昵称")
    avatar = Column(String(255), nullable=True, comment="头像URL")
    bio = Column(String(255), nullable=True, default="", comment="个人签名")
    role = Column(String(32), nullable=False, default="reader", comment="角色: admin|reader")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否激活")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    articles = relationship("Article", back_populates="author")
