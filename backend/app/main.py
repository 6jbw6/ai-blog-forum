from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.response import setup_exception_handlers, Result
from app.api.v1 import api_v1_router
from app.core.database import Base, engine
from pathlib import Path

# 自动创建尚未存在的数据库表结构
Base.metadata.create_all(bind=engine)

# 用户头像等静态资产目录
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
(STATIC_DIR / "avatars").mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=settings.APP_NAME,
    description="面向 AI 算法与大模型应用开发 (RAG/Agent) 的企业级博客论坛知识库系统 API 契约文档",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
