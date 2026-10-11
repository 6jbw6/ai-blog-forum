from typing import Generator
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

logger = logging.getLogger("app.database")

# SQL echo 只由显式的 SQL_ECHO 开关决定，不再跟着 DEBUG / APP_ENV 推断：
# echo=True 会把每条 SQL（含密码哈希、用户数据参数）全量写进日志，而 APP_ENV
# 默认值是 development —— 部署时漏配就等于把生产库的查询参数打进日志。
# 需要看 SQL 时在 .env 里显式加 SQL_ECHO=true。
_engine_echo = settings.SQL_ECHO

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
