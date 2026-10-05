"""pytest 全局夹具：内存 SQLite + 完整业务路由，不依赖真实 MySQL / LLM / 反向代理。

说明：
- 不导入 app.main（其 import 副作用包含 MySQL 建表与轻量迁移），测试应用在
  本文件按同样的组件组装：api_v1_router + 全局异常处理器 + get_db 覆盖；
- 项目的 LONGTEXT 列（正文 / 向量 JSON）注册 SQLite 方言映射为 TEXT，
  生产 MySQL 行为不受影响；
- 通知中心的 SSE 广播在无事件循环时是安全的 no-op（publish 内部短路），
  评论链路测试可照常触发派发逻辑并直接断言 Notification 落库。
"""
import os
import sys
import uuid
from pathlib import Path

# 必须先于任何 app.* 导入：pydantic Settings 在 import 时即实例化
os.environ.setdefault("APP_ENV", "testing")
os.environ["DEBUG"] = "true"  # 强制开发分支：JWT 密钥走临时随机值，而非要求显式注入

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.response import setup_exception_handlers
from app.api.v1 import api_v1_router
from app.core.security import hash_password
from app.models.user import User
from app.models.article import Article
from app.models.comment import Comment
from app.models.notification import Notification


@compiles(LONGTEXT, "sqlite")
def _compile_longtext_sqlite(type_, compiler, **kw):
    return "TEXT"


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False
)
import app.models  # noqa: F401,E402  确保全部表注册进 metadata
Base.metadata.create_all(bind=test_engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    """每个用例结束后清空全部业务表，保证用例间完全隔离"""
    yield
    with TestingSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
    from app.api.v1.auth import login_limiter
    from app.api.v1.ai_assistant import ai_ask_limiter

    login_limiter.reset()
    ai_ask_limiter.reset()


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(db):
    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(api_v1_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------- 测试数据工厂 ----------

TEST_PASSWORD = "password123"


def make_user(db, username: str, role: str = "reader", email: str | None = None) -> User:
    user = User(
        username=username,
        email=email or f"{username}@qq.com",
        password_hash=hash_password(TEST_PASSWORD),
        nickname=username,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_article(
    db,
    author: User,
    title: str = "默认测试文章",
    is_published: bool = True,
    is_private: bool = False,
    content: str = "正文内容，用于检索与展示。",
) -> Article:
    article = Article(
        title=title,
        slug=f"slug-{uuid.uuid4().hex[:10]}",
        summary=f"{title} 的摘要",
        content=content,
        author_id=author.id,
        is_published=is_published,
        is_private=is_private,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def login_token(client: TestClient, username: str, password: str = TEST_PASSWORD) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    body = resp.json()
    assert body["code"] == 200, f"登录失败: {body}"
    return body["data"]["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
