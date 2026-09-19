from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class AiChatMessage(Base):
    """
    AI 智能体用户专属对话历史表 (持久化记录每个账号的历史问答交互)
    """
    __tablename__ = "ai_chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属用户ID")
    role = Column(String(16), nullable=False, comment="角色: user | assistant")
    content = Column(Text, nullable=False, comment="消息Markdown内容")
    citations = Column(Text, nullable=True, comment="引用溯源卡片JSON列表")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="发送时间")

    user = relationship("User", backref="ai_chat_messages")
