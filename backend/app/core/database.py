from typing import Generator
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

logger = logging.getLogger("app.database")

# SQL echo 只在开发环境启用：echo=True 会把每条 SQL（含密码哈希、用户数据参数）
# 全量写进日志。生产环境即使 DEBUG 误配为 True 也强制关闭，杜绝日志泄密。
_engine_echo = settings.DEBUG and settings.APP_ENV not in ("production", "prod")

engine = create_engine(
    settings.DATABASE_URL,
    echo=_engine_echo,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    """FastAPI 依赖注入：获取数据库会话并在请求结束后自动释放"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
