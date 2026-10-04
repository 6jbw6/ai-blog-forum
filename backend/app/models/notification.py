from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # 提醒类型: article_comment(评论了你的博文) | reply(回复了你的评论)
    kind = Column(String(16), nullable=False, default="reply", server_default="reply", comment="提醒类型")
    # 触发本提醒的评论；评论被删除时置空（ON DELETE SET NULL），提醒本身保留并标记为「该评论已删除」
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="SET NULL"), nullable=True,
                        index=True, comment="触发提醒的评论 id")
    # 发送者账号：昵称与头像按账号实时解析，账号注销则回退到下面的快照字段
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
                       index=True, comment="发送者账号 id")
    sender_name = Column(String(64), nullable=False)
    sender_avatar = Column(String(255), nullable=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    article_title = Column(String(255), nullable=False)
    article_slug = Column(String(255), nullable=False)
    reply_content = Column(Text, nullable=False)
    # 回复型提醒的「被回复原文」；评论博文型无原文，落库为空串
    parent_content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", backref="notifications", foreign_keys=[user_id])
    # 发送者账号（昵称 / 头像实时解析）；与收件人 user_id 同指 users 表，需显式声明外键避免歧义
    sender = relationship("User", foreign_keys=[sender_id])
    article = relationship("Article")
