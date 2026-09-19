from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # JWT Security
    JWT_SECRET_KEY: str = "super_secret_ai_blog_jwt_token_key_2026_engineering"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Initial Admin
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = "admin123"
    INITIAL_ADMIN_EMAIL: str = "admin@aiblog.com"

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
