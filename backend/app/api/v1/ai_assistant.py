import json
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.core.database import get_db
from app.core.response import Result, BusinessException
from app.api.deps import require_admin, get_current_user, get_optional_user
from app.models.user import User
from app.models.search_log import SearchLog
from app.models.ai_chat_message import AiChatMessage
from app.models.article import Article
from app.models.article_chunk import ArticleChunk
from app.schemas.ai import (
    AiAskRequest,
    AiSummaryRequest,
    AiSummaryResponse,
    SemanticSearchRequest,
    SemanticSearchResultItem,
    LlmConfigSchema,
    AiChatMessageItem,
    FetchModelsRequest
)
from app.ai_engine.rag_service import rag_service
from app.ai_engine.recommendation_service import record_search_query, get_dynamic_recommended_questions, get_dynamic_hot_keywords
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["AI 算法与大模型知识库 (AI Core)"])


@router.post("/ask", summary="AI 智能体 / RAG 知识库问答 (全链路 SSE 流式交互)")
async def ask_knowledge_base(
    payload: AiAskRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """
    全链路 SSE (Server-Sent Events) 打字机流式交互接口
    
    请求参数:
    - question: 读者提问
    - history: 多轮历史对话
    
    响应格式:
    - text/event-stream 协议包
    - data: {"type": "token", "content": "..."}
    - data: {"type": "citations", "citations": [...]}  (知识库来源溯源直达卡片)
    - data: {"type": "done"}
    """
    history_dicts = [{"role": h.role, "content": h.content} for h in payload.history]

    # 累加搜索热度，驱动动态问题推荐
    record_search_query(db, payload.question, search_type="ai_ask")

    user_id = user.id if user else None

    # 生成异步 SSE 生成器
    stream_generator = rag_service.stream_rag_chat(
        db=db,
        question=payload.question,
        history=history_dicts,
        user_id=user_id
    )

    return StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 等中间代理缓冲，确保低延迟秒级推送
        }
    )


@router.get("/history", response_model=Result[List[AiChatMessageItem]], summary="拉取当前登录账号最近的 AI 对话历史")
def get_chat_history(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    拉取当前账号最近的 10 次对话 (最多 20 条按时间正序排列的问答记录)
    """
    max_messages = limit * 2
    records = (
        db.query(AiChatMessage)
        .filter(AiChatMessage.user_id == current_user.id)
        .order_by(desc(AiChatMessage.id))
        .limit(max_messages)
        .all()
    )
    records.reverse()
    items = []
    for r in records:
        cits = []
        if r.citations:
            try:
                cits = json.loads(r.citations)
            except Exception:
                cits = []
        items.append(AiChatMessageItem(
            id=r.id,
            role=r.role,
            content=r.content,
            citations=cits,
            created_at=r.created_at
        ))
    return Result.success(data=items)


@router.delete("/history", response_model=Result[None], summary="清空当前登录账号的全部 AI 对话历史")
def clear_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清空当前账号在数据库中的全部 AI 问答交互记录"""
    db.query(AiChatMessage).filter(AiChatMessage.user_id == current_user.id).delete()
    db.commit()
    return Result.success(message="历史会话已清空")


@router.get("/recommended-questions", response_model=Result[List[str]], summary="根据搜索热度与热门博文动态推荐 AI 提问")
def get_recommended_questions(
    limit: int = 6,
    refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    根据搜索热度 (search_logs)、高浏览量博文、核心知识库底池动态输出推荐问题，
    支持换一换 (refresh) 实时探索不同技术主题
    """
    questions = get_dynamic_recommended_questions(db=db, limit=limit, shuffle=True)
    return Result.success(data=questions)


@router.get("/hot-keywords", response_model=Result[List[str]], summary="根据搜索日志热度与博文概念动态推荐热搜关键词")
def get_hot_keywords(
    limit: int = 6,
    db: Session = Depends(get_db)
):
    """
    根据用户实际搜索日志 (SearchLog) 频次、热门博文分类与核心概念，动态输出热搜概念标签
    """
    keywords = get_dynamic_hot_keywords(db=db, limit=limit)
    return Result.success(data=keywords)


@router.post("/summary", response_model=Result[AiSummaryResponse], summary="AI 自动生成文章 TL;DR 摘要与推荐标签")
async def generate_ai_summary(payload: AiSummaryRequest):
    """供后台博文创作工作台调用：一键智能压缩长文为核心要点并预测分类标签"""
    data = await rag_service.llm.generate_summary_and_tags(payload.content, payload.title or "")
    return Result.success(data=AiSummaryResponse(**data))


@router.post("/semantic-search", response_model=Result[List[SemanticSearchResultItem]], summary="基于向量余弦相似度的自然语言语义检索")
def semantic_search(
    payload: SemanticSearchRequest,
    db: Session = Depends(get_db)
):
    """
    突破传统数据库 LIKE 关键字字面匹配局限
    即便没有输入相同词眼，也能基于特征向量余弦相似度召回语义最贴近的技术博文
    """
    record_search_query(db, payload.query, search_type="semantic_search")
    results = rag_service.semantic_search(db=db, query=payload.query, top_k=payload.top_k)
    # 实时累加命中检索博文的搜索热度
    matched_ids = list(set([r["article_id"] for r in results if "article_id" in r]))
    if matched_ids:
        try:
            db.query(Article).filter(Article.id.in_(matched_ids)).update(
                {Article.search_hits: Article.search_hits + 1},
                synchronize_session=False
            )
            db.commit()
        except Exception:
            db.rollback()

    items = [SemanticSearchResultItem(**r) for r in results]
    return Result.success(data=items)


@router.post("/reindex-all", response_model=Result[Dict[str, int]], summary="全量重建博文 RAG 向量知识库 (管理员)")
def reindex_all_articles(
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    result = rag_service.reindex_all_articles(db)
    return Result.success(data=result, message="全量向量切片与索引重构完成")


@router.get("/config", response_model=Result[LlmConfigSchema], summary="获取当前大模型与 RAG 运行参数 (管理员)")
def get_ai_config(_admin = Depends(require_admin)):
    config_data = LlmConfigSchema(
        provider=settings.LLM_PROVIDER,
        api_key=settings.LLM_API_KEY or "",
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        top_k=settings.RAG_TOP_K,
        similarity_threshold=settings.RAG_SIMILARITY_THRESHOLD
    )
    return Result.success(data=config_data)


def _persist_llm_env(updates: dict[str, str]):
    """将热更新的大模型参数安全持久化至本地 .env 文件，防止服务重启丢失"""
    try:
        env_path = Path(__file__).resolve().parents[3] / ".env"
        if not env_path.exists():
            return
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        new_lines = []
        found_keys = set()
        for line in lines:
            stripped = line.strip()
            matched = False
            for k, v in updates.items():
                if stripped.startswith(f"{k}=") or stripped.startswith(f"# {k}="):
                    new_lines.append(f"{k}={v}")
                    found_keys.add(k)
                    matched = True
                    break
            if not matched:
                new_lines.append(line)
        for k, v in updates.items():
            if k not in found_keys:
                new_lines.append(f"{k}={v}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception:
        pass


@router.put("/config", response_model=Result[None], summary="动态配置大模型 API 与 RAG 策略 (管理员)")
def update_ai_config(
    payload: LlmConfigSchema,
    _admin = Depends(require_admin)
):
    """支持在线热切换大模型接入商 (DeepSeek/智谱/OpenAI) 并自动持久化至本地 .env"""
    settings.LLM_PROVIDER = payload.provider
    env_updates: dict[str, str] = {
        "LLM_PROVIDER": payload.provider
    }

    if payload.api_key:
        clean_key = payload.api_key.strip()
        if clean_key and not clean_key.startswith("****") and "****" not in clean_key:
            settings.LLM_API_KEY = clean_key
            env_updates["LLM_API_KEY"] = clean_key
    if payload.base_url:
        settings.LLM_BASE_URL = payload.base_url
        env_updates["LLM_BASE_URL"] = payload.base_url
    if payload.model:
        settings.LLM_MODEL = payload.model
        env_updates["LLM_MODEL"] = payload.model
    settings.RAG_TOP_K = payload.top_k
    settings.RAG_SIMILARITY_THRESHOLD = payload.similarity_threshold

    # 持久化至 .env
    _persist_llm_env(env_updates)

    # 同步更新运行时 LLM 客户端
    rag_service.llm = rag_service.llm.__class__(
        provider=settings.LLM_PROVIDER,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL
    )
    return Result.success(message="大模型与 RAG 运行时配置已更新生效")


@router.post("/models", response_model=Result[List[str]], summary="在线拉取指定端点支持的模型列表 (管理员)")
async def fetch_available_models(
    payload: FetchModelsRequest,
    _admin = Depends(require_admin)
):
    """
    通过 OpenAI 兼容协议向供应商端点动态拉取支持的模型 ID 清单
    """
    base_url = payload.base_url.strip().rstrip("/")
    api_key = payload.api_key.strip() if payload.api_key else ""

    # 若未传 key 或传入掩码，使用系统当前已存储的有效 API Key
    if not api_key or api_key.startswith("****") or "****" in api_key:
        api_key = settings.LLM_API_KEY or ""

    if not api_key:
        raise BusinessException("请先填写大模型 API Key 后再拉取模型列表", code=400)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=15.0)
        models_resp = await client.models.list()

        # 提取模型标识
        model_ids = [m.id for m in models_resp.data if getattr(m, "id", None)]
        if not model_ids:
            raise BusinessException("供应商端点返回的模型列表为空", code=400)

        # 针对常见大模型做优先级排序 (如 deepseek, qwen 等靠前)
        def sort_priority(name: str):
            lower = name.lower()
            if "deepseek" in lower:
                return (0, lower)
            if "qwen" in lower:
                return (1, lower)
            if "gpt" in lower or "claude" in lower:
                return (2, lower)
            if "glm" in lower or "gemini" in lower:
                return (3, lower)
            return (4, lower)

        model_ids.sort(key=sort_priority)
        return Result.success(data=model_ids)
    except Exception as e:
        raise BusinessException(f"拉取模型列表失败: {str(e)}", code=400)
