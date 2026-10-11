import json
import logging
import random
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import desc
import httpx
from app.core.database import get_db, SessionLocal
from app.core.rate_limit import SlidingWindowRateLimiter, client_ip_of, parse_rate
from app.core.response import Result, BusinessException
from app.api.deps import require_admin, get_current_user, get_optional_user
from app.models.user import User
from app.models.search_log import SearchLog
from app.models.ai_chat_message import AiChatMessage
from app.models.article import Article
from app.models.article_chunk import ArticleChunk
from app.models.system_setting import SystemSetting
from app.schemas.article import ArticleListItem
from app.schemas.ai import (
    AiAskRequest,
    SemanticSearchRequest,
    SemanticSearchResultItem,
    LlmConfigSchema,
    AiChatMessageItem,
    FetchModelsRequest,
    CustomModelCreate,
    CustomModelItem,
    API_FORMATS
)
from app.ai_engine.rag_service import rag_service
from app.ai_engine.recommendation_service import record_search_query, get_dynamic_recommended_questions, get_dynamic_hot_keywords
from app.ai_engine.llm_client import UnifiedLLMClient, API_FORMAT_SUFFIX, normalize_sdk_base
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["AI 算法与大模型知识库 (AI Core)"])

# LLM 调用是真金白银：接口对访客开放，必须挡住匿名高频消耗 API 余额的行为。
# 登录用户按账号限（换设备也有效），访客按 IP 限
ai_ask_limiter = SlidingWindowRateLimiter(*parse_rate(settings.AI_ASK_RATE_LIMIT, fallback=(6, 60.0)))

# 进程启动时的默认模型（.env 值）：删除正在使用的自定义模型时回退到它
_boot_default_model = settings.LLM_MODEL


@router.post("/ask", summary="AI 智能体 / RAG 知识库问答 (全链路 SSE 流式交互)")
async def ask_knowledge_base(
    payload: AiAskRequest,
    request: Request,
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
    - data: {"type": "citations", "citations": [...]}  (知识来源溯源直达卡片)
    - data: {"type": "done"}
    """
    rate_key = f"user:{user.id}" if user else f"ip:{client_ip_of(request)}"
    if not ai_ask_limiter.allow(rate_key):
        raise HTTPException(status_code=429, detail="提问太频繁啦，休息一下再来")

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
    # 边界校验：无约束的 limit 可被传入超大值拉取全表（慢查询 DoS 面），负数则语义异常
    limit: int = Query(10, ge=1, le=50, description="最近对话轮数上限"),
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

    items: List[SemanticSearchResultItem] = []
    if results:
        articles = {
            a.id: a
            for a in (
                db.query(Article)
                .filter(Article.id.in_([r["article_id"] for r in results]))
                .options(
                    joinedload(Article.author),
                    selectinload(Article.tags),
                )
                .all()
            )
        }
        for r in results:
            article = articles.get(r["article_id"])
            if not article:
                continue
            item = SemanticSearchResultItem(
                **ArticleListItem.model_validate(article).model_dump(),
                article_id=article.id,
                similarity=r["similarity"],
                matched_snippet=r["matched_snippet"],
            )
            items.append(item)

    return Result.success(data=items)


@router.post("/reindex-all", response_model=Result[Dict[str, int]], summary="全量重建博文 RAG 向量知识库 (管理员)")
def reindex_all_articles(
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    result = rag_service.reindex_all_articles(db)
    return Result.success(data=result, message="全量向量切片与索引重构完成")


def _mask_api_key(key: Optional[str]) -> str:
    """API Key 掩码化：密钥明文不离开服务端。

    前端把掩码值原样回传保存时，update_ai_config 对含 **** 的 key 不生效
    （既有逻辑），形成「展示掩码 / 提交掩码 = 不改密钥」的闭环。
    """
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


@router.get("/config", response_model=Result[LlmConfigSchema], summary="获取当前大模型与 RAG 运行参数 (管理员)")
def get_ai_config(_admin = Depends(require_admin)):
    config_data = LlmConfigSchema(
        provider=settings.LLM_PROVIDER,
        api_key=_mask_api_key(settings.LLM_API_KEY),
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        top_k=settings.RAG_TOP_K,
        similarity_threshold=settings.RAG_SIMILARITY_THRESHOLD
    )
    return Result.success(data=config_data)


def _persist_llm_env(updates: dict[str, str]):
    """将热更新的大模型参数安全持久化至本地 .env 文件，防止服务重启丢失"""
    # 测试环境绝不触碰真实 .env（pytest 的热更用例会污染开发配置）
    if settings.APP_ENV == "testing":
        return
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
    _admin = Depends(require_admin),
    db: Session = Depends(get_db)
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

    # 同步更新运行时 LLM 客户端：所选模型命中自定义模型时，使用其专属端点/密钥/协议/温度
    rag_service.llm = _build_llm_client(payload.model, db)
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


# ---------- 自定义模型（AI 设置页「自定义模型」弹窗） ----------

_CUSTOM_MODELS_KEY = "custom_llm_models"


@router.get("/current-model", response_model=Result[dict], summary="获取当前接入的大模型标识 (游客可访问)")
def get_current_model(db: Session = Depends(get_db)):
    """AI 问答抽屉左下角展示当前接入的模型 ID；若启用的是自定义模型则返回其真实模型 ID"""
    custom = _resolve_custom_model(settings.LLM_MODEL, db)
    model_id = custom["model_id"] if custom else settings.LLM_MODEL
    return Result.success(data={"model": model_id})


def _load_custom_models(db: Session) -> List[dict]:
    """自定义模型清单持久化于 system_settings 表（JSON 数组）"""
    row = db.query(SystemSetting).filter(SystemSetting.setting_key == _CUSTOM_MODELS_KEY).first()
    if not row or not row.setting_value:
        return []
    try:
        data = json.loads(row.setting_value)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_custom_models(db: Session, items: List[dict]) -> None:
    value = json.dumps(items, ensure_ascii=False)
    row = db.query(SystemSetting).filter(SystemSetting.setting_key == _CUSTOM_MODELS_KEY).first()
    if row:
        row.setting_value = value
    else:
        db.add(SystemSetting(
            setting_key=_CUSTOM_MODELS_KEY,
            setting_value=value,
            description="自定义大模型接入配置（AI 设置页「自定义模型」弹窗维护）"
        ))
    db.commit()


def _mask_custom_item(item: dict) -> dict:
    masked = dict(item)
    masked["api_key"] = _mask_api_key(item.get("api_key"))
    return masked


async def _probe_custom_model(payload: CustomModelCreate) -> dict:
    """连通性测试：向目标端点发起一次真实的最小请求（会消耗少量 Token），失败抛业务异常"""
    fmt = payload.api_format if payload.api_format in API_FORMATS else "openai-chat"
    key = payload.api_key.strip()
    started = time.perf_counter()
    try:
        if fmt == "anthropic":
            base = payload.base_url.strip().rstrip("/")
            url = base if payload.full_url else base + "/v1/messages"
            headers = {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            body = {"model": payload.model_id.strip(), "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}
            async with httpx.AsyncClient(timeout=20.0) as http:
                resp = await http.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=key,
                base_url=normalize_sdk_base(payload.base_url, payload.full_url, API_FORMAT_SUFFIX[fmt]),
                timeout=20.0,
            )
            if fmt == "openai-responses":
                # Responses API 要求 max_output_tokens >= 16
                await client.responses.create(model=payload.model_id.strip(), input="hi", max_output_tokens=16)
            else:
                await client.chat.completions.create(
                    model=payload.model_id.strip(),
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                )
        return {"latency_ms": int((time.perf_counter() - started) * 1000)}
    except BusinessException:
        raise
    except Exception as e:
        # 详细异常只进服务端日志，前端提示保持简洁
        logging.getLogger("app.ai").warning(f"自定义模型连通性测试失败: {e}")
        raise BusinessException("连通性测试失败", code=400)


@router.get("/custom-models", response_model=Result[List[CustomModelItem]], summary="获取自定义模型列表 (管理员)")
def list_custom_models(_admin=Depends(require_admin), db: Session = Depends(get_db)):
    return Result.success(data=[_mask_custom_item(m) for m in _load_custom_models(db)])


@router.post("/custom-models", response_model=Result[List[CustomModelItem]], summary="新增自定义模型（先做真实连通性测试）(管理员)")
async def add_custom_model(
    payload: CustomModelCreate,
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    if payload.api_format not in API_FORMATS:
        raise BusinessException("不支持的 API 格式", code=400)

    # 同端点 + 同模型 + 同格式视为同一条目：覆盖更新且保持 ID 稳定
    models = _load_custom_models(db)
    idx = next(
        (
            i for i, m in enumerate(models)
            if m.get("model_id") == payload.model_id.strip()
            and m.get("base_url", "").rstrip("/") == payload.base_url.strip().rstrip("/")
            and m.get("api_format") == payload.api_format
        ),
        None,
    )
    probe = await _probe_custom_model(payload)
    item = {
        "id": models[idx]["id"] if idx is not None else uuid.uuid4().hex,
        "api_format": payload.api_format,
        "base_url": payload.base_url.strip().rstrip("/"),
        "full_url": payload.full_url,
        "model_id": payload.model_id.strip(),
        "display_name": (payload.display_name or "").strip() or payload.model_id.strip(),
        "api_key": payload.api_key.strip(),
        "temperature": payload.temperature,
        "latency_ms": probe["latency_ms"],
    }
    if idx is not None:
        models[idx] = item
    else:
        models.append(item)
    _save_custom_models(db, models)

    # 页面已无独立模型选择器：添加即启用该模型（热切换 + 持久化）
    settings.LLM_MODEL = item["display_name"]
    _persist_llm_env({"LLM_MODEL": item["display_name"]})
    rag_service.llm = UnifiedLLMClient(
        provider=settings.LLM_PROVIDER,
        api_key=item["api_key"],
        base_url=item["base_url"],
        model=item["model_id"],
        api_format=item["api_format"],
        temperature=item.get("temperature", 0.7),
        full_url=item.get("full_url", False),
    )
    return Result.success(
        data=[_mask_custom_item(m) for m in models],
        message=f"连通性测试通过（{probe['latency_ms']}ms），已添加并启用该模型"
    )


@router.delete("/custom-models/{model_row_id}", response_model=Result[List[CustomModelItem]], summary="删除自定义模型 (管理员)")
def remove_custom_model(model_row_id: str, _admin=Depends(require_admin), db: Session = Depends(get_db)):
    models = _load_custom_models(db)
    removed = next((m for m in models if m.get("id") == model_row_id), None)
    models = [m for m in models if m.get("id") != model_row_id]
    _save_custom_models(db, models)

    # 删除的是正在使用的模型 → 回退到默认端点与启动模型
    if removed and removed.get("display_name") == settings.LLM_MODEL:
        settings.LLM_MODEL = _boot_default_model
        _persist_llm_env({"LLM_MODEL": _boot_default_model})
        rag_service.llm = UnifiedLLMClient(
            provider=settings.LLM_PROVIDER,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
        )
    return Result.success(data=[_mask_custom_item(m) for m in models])


def _resolve_custom_model(model_name: Optional[str], db: Session) -> Optional[dict]:
    """主页面「模型选择」的名称若命中自定义模型（Model ID 或展示名称），返回其完整接入配置"""
    if not model_name:
        return None
    for m in _load_custom_models(db):
        if model_name in (m.get("model_id"), m.get("display_name")):
            return m
    return None


def _build_llm_client(model_name: Optional[str], db: Session) -> UnifiedLLMClient:
    """按所选模型构建运行时客户端：命中自定义模型则用其专属端点 / 密钥 / 协议 / 温度"""
    custom = _resolve_custom_model(model_name, db)
    if custom:
        return UnifiedLLMClient(
            provider=settings.LLM_PROVIDER,
            api_key=custom.get("api_key"),
            base_url=custom.get("base_url"),
            model=custom.get("model_id"),
            api_format=custom.get("api_format", "openai-chat"),
            temperature=custom.get("temperature", 0.7),
            full_url=custom.get("full_url", False),
        )
    return UnifiedLLMClient(
        provider=settings.LLM_PROVIDER,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
    )


def apply_custom_model_to_runtime():
    """进程启动时调用：当前所选模型若为自定义模型，则切到其专属接入配置"""
    try:
        with SessionLocal() as db:
            rag_service.llm = _build_llm_client(settings.LLM_MODEL, db)
    except Exception:
        pass
