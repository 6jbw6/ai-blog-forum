import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional
from openai import AsyncOpenAI
from app.core.config import settings


class UnifiedLLMClient:
    """
    基于官方 OpenAI Python SDK 的企业级统一大模型接入客户端
    
    设计准则:
    1. 纯净云端/端点接入：已彻底移除本地 Mock 降级引擎，严格依赖配置的 API Key 与大模型服务；
    2. 官方原生流式传输：依托 AsyncOpenAI SDK 原生 stream 迭代器解析 Token 流；
    3. 完善的鉴权校验与错误提示：若未配置 API Key 或端点响应异常，直接向用户反馈明确指引，绝不伪造本地假数据；
    4. 隐私合规：脱敏所有内部个人信息，统一规范定义为“AI 智能体”。
    """

    def __init__(self, provider: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider or settings.LLM_PROVIDER
        self.api_key = api_key or settings.LLM_API_KEY
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """初始化官方 AsyncOpenAI 客户端"""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key or "missing-key",
                base_url=self.base_url,
                timeout=45.0
            )
        return self._client

    async def stream_chat(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """流式调用大模型生成回答 (输出单个 token 增量)"""
        # 严格校验 API Key，绝不启用本地假数据降级
        if not self.api_key or self.api_key.strip() == "":
            yield (
                "**【系统配置提示】未检测到有效的大模型 API Key！**\n\n"
                "已按要求彻底停用本地假数据降级引擎。\n\n"
                "请前往 `backend/.env` 配置 `LLM_API_KEY`（或在博客管理后台【AI 引擎中枢配置】页面填入），保存后即可体验实时 AI 大模型问答。"
            )
            return

        client = self._get_client()

        try:
            stream_resp = await client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                stream=True,
                temperature=0.7
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
                f"当前配置端点：`{self.base_url}`，模型：`{self.model}`。\n"
                f"请检查网络连接、API Key 是否有效或 Base URL 与模型名称是否匹配。"
            )

