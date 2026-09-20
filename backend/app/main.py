import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.response import setup_exception_handlers, Result
from app.api.v1 import api_v1_router
from app.core.database import Base, engine
from app.ai_engine.retrieval_index import retrieval_index
from pathlib import Path

# 业务日志出口：此前全项目没有任何 handler，root 默认 WARNING 会把 app.* 的 logger.info
# 整段丢弃（检索索引就绪/重建耗时、向量重建规模等后台过程完全不可观测）。
# 只挂在 "app" 这一命名空间上而不动 root —— SQLAlchemy 的 echo=True 已自行给
# sqlalchemy.engine 挂了 handler，配置 root 会让每条 SQL 重复输出两遍。
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _stream = logging.StreamHandler()
    _stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    _app_logger.addHandler(_stream)
    _app_logger.setLevel(logging.INFO)
    _app_logger.propagate = False

# 自动创建尚未存在的数据库表结构
Base.metadata.create_all(bind=engine)


def _ensure_article_columns():
    """轻量列迁移：为已存在的 articles 表补充后加字段（create_all 不会 alter 旧表）"""
    from sqlalchemy import inspect, text
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("articles")}
        if "is_manual_top" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE articles ADD COLUMN is_manual_top TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否人工置顶'"
                ))
            logging.getLogger("app.database").info("articles 表已补充 is_manual_top 列")
    except Exception as e:
        logging.getLogger("app.database").warning(f"articles 列迁移跳过: {e}")


_ensure_article_columns()

# 用户头像等静态资产目录
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
(STATIC_DIR / "avatars").mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 检索索引预热：后台线程加载切片并装配矩阵，进程就绪与索引就绪解耦，
    # 避免首个检索请求承担万级切片的全量构建耗时
    retrieval_index.warmup()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="面向 AI 算法与大模型应用开发 (RAG/Agent) 的企业级博客论坛知识库系统 API 契约文档",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置 CORS 跨域资源共享中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册企业级全局异常拦截器
setup_exception_handlers(app)

# 挂载业务路由
app.include_router(api_v1_router, prefix="/api")

# 挂载静态资产服务
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", summary="服务健康检查与元数据探针")
def root():
    return Result.success(data={
        "app_name": settings.APP_NAME,
        "status": "online",
        "docs_url": "/docs",
        "ai_engine_status": "ready",
        "llm_provider": settings.LLM_PROVIDER
    }, message="AI-Blog Knowledge Base Backend is Running")


@app.get("/health", summary="Liveness / Readiness 探针")
def health_check():
    return {"status": "ok"}
