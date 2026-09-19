from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.core.database import Base


class SystemSetting(Base):
    """系统动态配置表 (用于在线动态调整 LLM Key、Prompt 模板、RAG 阈值等)"""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    setting_key = Column(String(64), unique=True, index=True, nullable=False, comment="配置键名")
    setting_value = Column(Text, nullable=True, comment="配置值")
    description = Column(String(255), nullable=True, comment="配置说明")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
