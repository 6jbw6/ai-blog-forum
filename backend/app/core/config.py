import logging
import secrets
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("app.config")

# 曾随仓库公开、必须作废的 JWT 密钥与占位符：任何环境命中即拒绝（生产）或临时随机顶替（开发）
COMPROMISED_JWT_SECRETS = frozenset({
    "super_secret_ai_blog_jwt_token_key_2026_engineering",
    "your_jwt_secret_key",
})


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI博客论坛"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # Database
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "your_mysql_password"
    DB_NAME: str = "ai_blog"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    # CORS 允许来源（逗号分隔）。默认仅放行本地前端开发端口；生产部署必须
    # 显式配置为站点自身域名，禁止回退到「*」——与 allow_credentials=True
    # 组合等于对任意来源开放跨域携带凭证
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def CORS_ORIGIN_LIST(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # JWT Security：密钥不再内置默认值（历史兜底密钥已随仓库公开泄露）。
    # 生产环境必须显式注入，开发环境允许每次重启生成临时随机密钥
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    @model_validator(mode="after")
    def _resolve_jwt_secret(self) -> "Settings":
        if self.JWT_SECRET_KEY and self.JWT_SECRET_KEY not in COMPROMISED_JWT_SECRETS:
            return self
        if self.APP_ENV in ("production", "prod") or not self.DEBUG:
            if self.JWT_SECRET_KEY in COMPROMISED_JWT_SECRETS:
                raise RuntimeError(
                    "JWT_SECRET_KEY 使用了随仓库泄露/占位的密钥值，必须更换为新的随机密钥后才能启动"
                )
            raise RuntimeError(
                "生产环境必须通过环境变量显式注入 JWT_SECRET_KEY（随机密钥会让每次重启作废全部登录态）"
            )
        self.JWT_SECRET_KEY = secrets.token_hex(32)
        logger.warning(
            "JWT_SECRET_KEY 未配置（或命中已泄露/占位密钥），已生成临时随机密钥："
            "重启后所有已签发令牌失效，仅限本地开发使用"
        )
        return self

    # Initial Admin
    INITIAL_ADMIN_USERNAME: str = "admin"
    # 初始管理员密码的开发默认值；生产环境务必通过 INITIAL_ADMIN_PASSWORD 覆盖，上线后立即修改
    INITIAL_ADMIN_PASSWORD: str = "123456"
    INITIAL_ADMIN_EMAIL: str = "admin@aiblog.com"

    # 高危端点限流（格式「次数/窗口秒」）：登录防撞库爆破、AI 问答防匿名刷 LLM 余额
    LOGIN_RATE_LIMIT: str = "10/60"
    AI_ASK_RATE_LIMIT: str = "6/60"
    # 仅在前面确有可信反向代理（Nginx 等）时开启：采信 X-Forwarded-For 解析真实客户端 IP
    TRUST_PROXY_HEADERS: bool = False

    # AI / LLM Configuration
    LLM_PROVIDER: str = "deepseek"  # "deepseek" | "zhipu" | "openai"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"

    # RAG Settings
    RAG_TOP_K: int = 4
    # 词法融合相关度阈值：similarity = 0.75 × TF-IDF余弦 + 0.25 × 饱和BM25
    # 实测真实语料下：相关查询 22%~41%，无关查询 0%~15%，取 0.18 兼顾精度与召回
    RAG_SIMILARITY_THRESHOLD: float = 0.18

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
