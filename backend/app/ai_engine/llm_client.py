import json
from typing import AsyncGenerator, List, Dict, Any, Optional
from openai import AsyncOpenAI
import httpx
from app.core.config import settings

# 各协议在「完整 URL」模式下调用方自带的后缀；非完整 URL 模式由 SDK / 拼接补齐
API_FORMAT_SUFFIX = {
    "openai-chat": "/chat/completions",
    "openai-responses": "/responses",
    "anthropic": "/v1/messages",
}


def normalize_sdk_base(base_url: str, full_url: bool, suffix: str) -> str:
    """OpenAI 系 SDK 会在 base_url 末尾自动补协议路径；「完整 URL」模式下
    调用方地址已自带该后缀，需剥掉后才能交给 SDK"""
    b = base_url.strip().rstrip("/")
    if full_url and b.endswith(suffix):
        b = b[: -len(suffix)]
    return b


class UnifiedLLMClient:
    """
    企业级统一大模型接入客户端，支持三种 API 格式：
    - openai-chat:      OpenAI Chat Completions 格式（官方 SDK 流式）
    - openai-responses: OpenAI Responses API 格式（官方 SDK 流式）
    - anthropic:        Anthropic Messages 格式（httpx 直连 + SSE 解析）

    设计准则:
    1. 纯净云端/端点接入：严格依赖配置的 API Key 与大模型服务，绝不伪造本地假数据；
    2. 原生流式传输：逐 Token 输出增量；
    3. 完善的鉴权校验与错误提示：未配置 API Key 或端点响应异常时直接向用户反馈明确指引；
    4. 隐私合规：脱敏所有内部个人信息，统一规范定义为"AI 智能体"。
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_format: str = "openai-chat",
        temperature: float = 0.7,
        full_url: bool = False,
    ):
        self.provider = provider or settings.LLM_PROVIDER
        self.api_key = api_key or settings.LLM_API_KEY
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.api_format = api_format if api_format in API_FORMAT_SUFFIX else "openai-chat"
        self.temperature = temperature
        self.full_url = full_url
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """初始化官方 AsyncOpenAI 客户端（「完整 URL」先剥掉自带后缀）"""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key or "missing-key",
                base_url=normalize_sdk_base(self.base_url, self.full_url, API_FORMAT_SUFFIX[self.api_format]),
                timeout=45.0
            )
        return self._client

    def _anthropic_url(self) -> str:
        """Anthropic Messages 端点：完整 URL 模式原样使用，否则补 /v1/messages"""
        return self.base_url if self.full_url else self.base_url + "/v1/messages"

    async def _stream_anthropic(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Anthropic Messages 协议：httpx 直连 + SSE 行解析"""
        # system 角色不进 messages，放顶层 system 字段
        system_text = "\n".join(m.get("content", "") for m in messages if m.get("role") == "system")
        chat_messages = [m for m in messages if m.get("role") != "system"]
        body: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": self.temperature,
            "messages": chat_messages,
            "stream": True,
        }
        if system_text:
            body["system"] = system_text

        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=45.0) as http:
            async with http.stream("POST", self._anthropic_url(), headers=headers, json=body) as resp:
                if resp.status_code != 200:
                    raw = (await resp.aread()).decode("utf-8", "replace")
                    raise RuntimeError(f"HTTP {resp.status_code}: {raw[:300]}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    obj = json.loads(payload)
                    if obj.get("type") == "content_block_delta":
                        delta = obj.get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            yield delta["text"]

    async def stream_chat(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """流式调用大模型生成回答 (输出单个 token 增量)，按 API 格式分派"""
        # 严格校验 API Key，绝不启用本地假数据降级
        if not self.api_key or self.api_key.strip() == "":
            yield (
                "**【系统配置提示】未检测到有效的大模型 API Key！**\n\n"
                "已按要求彻底停用本地假数据降级引擎。\n\n"
                "请前往 `backend/.env` 配置 `LLM_API_KEY`（或在博客管理后台【AI 引擎中枢配置】页面填入），保存后即可体验实时 AI 大模型问答。"
            )
            return

        try:
            if self.api_format == "anthropic":
                async for token in self._stream_anthropic(messages):
                    yield token
                return

            client = self._get_client()
            if self.api_format == "openai-responses":
                stream_resp = await client.responses.create(
                    model=self.model,
                    input=messages,  # type: ignore
                    stream=True,
                    temperature=self.temperature,
                )
                async for event in stream_resp:
                    if getattr(event, "type", "") == "response.output_text.delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            yield delta
            else:
                stream_resp = await client.chat.completions.create(
                    model=self.model,
                    messages=messages,  # type: ignore
                    stream=True,
                    temperature=self.temperature,
                )
                async for chunk in stream_resp:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            yield delta.content

        except Exception as e:
            yield (
                f"\n\n**【大模型 API 调用发生异常】**\n\n"
                f"错误详情：`{str(e)}`\n\n"
                f"当前配置端点：`{self.base_url}`，模型：`{self.model}`，API 格式：`{self.api_format}`。\n"
                f"请检查网络连接、API Key 是否有效或 Base URL 与模型名称是否匹配。"
            )
