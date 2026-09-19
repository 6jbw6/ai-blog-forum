from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, comment="父级评论ID(实现嵌套评论树)")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="评论用户ID")
    
    user_name = Column(String(64), nullable=False, comment="评论人昵称")
    user_email = Column(String(128), nullable=False, comment="评论人邮箱")
    user_avatar = Column(String(255), nullable=True, comment="评论人头像")
    content = Column(Text, nullable=False, comment="评论内容")
    
    is_approved = Column(Boolean, default=True, nullable=False, comment="审核状态(1通过 0待审)")
    is_admin = Column(Boolean, default=False, nullable=False, comment="是否博主回复")
    ip_address = Column(String(64), nullable=True, comment="IP地址")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    article = relationship("Article", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], backref="replies")
    user = relationship("User", backref="comments")
