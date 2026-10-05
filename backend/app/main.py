import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.response import setup_exception_handlers, Result
from app.core.notification_hub import notification_hub
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
    additive = {
        "is_manual_top": "ALTER TABLE articles ADD COLUMN is_manual_top TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否人工置顶'",
        "is_private": "ALTER TABLE articles ADD COLUMN is_private TINYINT(1) NOT NULL DEFAULT 0 COMMENT '已发布但仅作者本人可见'",
    }
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("articles")}
        for name, ddl in additive.items():
            if name in cols:
                continue
            with engine.begin() as conn:
                conn.execute(text(ddl))
            logging.getLogger("app.database").info(f"articles 表已补充 {name} 列")
    except Exception as e:
        logging.getLogger("app.database").warning(f"articles 列迁移跳过: {e}")


_ensure_article_columns()


def _ensure_comment_columns():
    """轻量列迁移：为已存在的 comments 表补充后加字段（create_all 不会 alter 旧表）"""
    from sqlalchemy import inspect, text
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("comments")}
        if "likes_count" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE comments ADD COLUMN likes_count INT NOT NULL DEFAULT 0 COMMENT '评论点赞数'"
                ))
            logging.getLogger("app.database").info("comments 表已补充 likes_count 列")
    except Exception as e:
        logging.getLogger("app.database").warning(f"comments 列迁移跳过: {e}")


_ensure_comment_columns()


def _ensure_notification_columns():
    """notifications 表轻量迁移 + 外键删除动作校正（create_all 不会 alter 旧表）

    - `kind`：提醒类型（历史行归位 reply）
    - `comment_id`：触发提醒的评论。**删除评论不再删除整条提醒**，只把内容标记为「该评论已删除」，
      因此外键删除动作必须是 SET NULL —— 早期建的 ON DELETE CASCADE 需就地改掉
    - `sender_id`：发送者账号，昵称 / 头像按账号实时解析（历史行按 sender_name 回填）
    """
    from sqlalchemy import inspect, text
    logger = logging.getLogger("app.database")

    def fk_delete_rule(constraint: str) -> str:
        with engine.begin() as conn:
            return conn.execute(text(
                "SELECT DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS "
                "WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'notifications' "
                "AND CONSTRAINT_NAME = :n"
            ), {"n": constraint}).scalar() or ""

    try:
        cols = {c["name"] for c in inspect(engine).get_columns("notifications")}

        if "kind" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE notifications ADD COLUMN kind VARCHAR(16) NOT NULL DEFAULT 'reply' "
                    "COMMENT '提醒类型: article_comment|reply' AFTER user_id"
                ))
            logger.info("notifications 表已补充 kind 列")

        if "comment_id" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE notifications ADD COLUMN comment_id INT NULL COMMENT '触发提醒的评论 id' AFTER kind, "
                    "ADD INDEX ix_notifications_comment_id (comment_id), "
                    "ADD CONSTRAINT fk_notifications_comment_id FOREIGN KEY (comment_id) "
                    "REFERENCES comments (id) ON DELETE SET NULL"
                ))
            logger.info("notifications 表已补充 comment_id 列")

        if "sender_id" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE notifications ADD COLUMN sender_id INT NULL COMMENT '发送者账号 id' AFTER comment_id, "
                    "ADD INDEX ix_notifications_sender_id (sender_id), "
                    "ADD CONSTRAINT fk_notifications_sender_id FOREIGN KEY (sender_id) "
                    "REFERENCES users (id) ON DELETE SET NULL"
                ))
                # 历史行按发送者用户名 / 昵称回填账号，回填后即可参与实时解析
                conn.execute(text(
                    "UPDATE notifications n JOIN users u "
                    "ON u.username = n.sender_name OR u.nickname = n.sender_name "
                    "SET n.sender_id = u.id WHERE n.sender_id IS NULL"
                ))
            logger.info("notifications 表已补充 sender_id 列并回填历史发送者")

        # 校正删除动作：早期版本 comment_id 为 CASCADE，会把整条提醒删掉
        for constraint, column, ref_table in (
            ("fk_notifications_comment_id", "comment_id", "comments"),
            ("fk_notifications_sender_id", "sender_id", "users"),
        ):
            rule = fk_delete_rule(constraint)
            if rule and rule.upper() != "SET NULL":
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE notifications DROP FOREIGN KEY {constraint}"))
                    conn.execute(text(
                        f"ALTER TABLE notifications ADD CONSTRAINT {constraint} FOREIGN KEY ({column}) "
                        f"REFERENCES {ref_table} (id) ON DELETE SET NULL"
                    ))
                logger.info(f"notifications.{constraint} 删除动作已由 {rule} 校正为 SET NULL")
    except Exception as e:
        logger.warning(f"notifications 列迁移跳过: {e}")


_ensure_notification_columns()

# 用户头像等静态资产目录
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
(STATIC_DIR / "avatars").mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 站内提醒 SSE：把主事件循环交给广播中心，业务线程才能安全投递推送
    notification_hub.bind_loop(asyncio.get_running_loop())
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

# 配置 CORS 跨域资源共享中间件：来源白名单来自 CORS_ORIGINS 配置，
# 默认只放行本地前端开发端口；「*」+ credentials 的旧配置会向任意来源放行携带凭证的请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGIN_LIST,
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
