"""限流组件与高危端点闸门：登录防爆破、AI 问答防匿名刷 LLM。"""

import json

from app.core.rate_limit import SlidingWindowRateLimiter, parse_rate


def test_parse_rate():
    assert parse_rate("10/60") == (10, 60.0)
    assert parse_rate("3") == (3, 60.0)
    # 非法配置回退默认值，而不是让进程起不来
    assert parse_rate("bogus") == (10, 60.0)
    assert parse_rate("0/60") == (10, 60.0)


def test_sliding_window_allows_then_blocks():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
    assert [limiter.allow("1.2.3.4") for _ in range(3)] == [True, True, True]
    assert limiter.allow("1.2.3.4") is False
    # 独立 key 互不影响
    assert limiter.allow("5.6.7.8") is True
    limiter.reset()
    assert limiter.allow("1.2.3.4") is True


def test_login_rate_limit_blocks_brute_force(client, monkeypatch):
    from app.api.v1.auth import login_limiter

    monkeypatch.setattr(login_limiter, "max_requests", 3)
    login_limiter.reset()

    for _ in range(3):
        resp = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "wrong-pass"})
        assert resp.status_code == 200 and resp.json()["code"] == 400

    blocked = client.post("/api/v1/auth/login", json={"username": "nobody", "password": "wrong-pass"})
    assert blocked.status_code == 429
    assert "频繁" in blocked.json()["message"]


def test_ai_ask_rate_limit_returns_429(client, monkeypatch, db):
    from app.api.v1 import ai_assistant

    monkeypatch.setattr(ai_assistant.ai_ask_limiter, "max_requests", 0)
    ai_assistant.ai_ask_limiter.reset()

    resp = client.post("/api/v1/ai/ask", json={"question": "什么是 RAG？"})
    assert resp.status_code == 429


def test_ai_ask_streams_sse_when_under_limit(client, monkeypatch, db):
    """限额内的请求应正常进入 SSE 流式响应（用假 RAG 服务隔离 LLM 依赖）"""
    from app.api.v1 import ai_assistant

    class _FakeRagService:
        async def stream_rag_chat(self, db=None, question=None, history=None, user_id=None):
            yield 'data: {"type": "token", "content": "RAG 是检索增强生成"}\n\n'
            yield 'data: {"type": "citations", "citations": []}\n\n'
            yield 'data: {"type": "done"}\n\n'

    monkeypatch.setattr(ai_assistant, "rag_service", _FakeRagService())
    ai_assistant.ai_ask_limiter.reset()

    resp = client.post("/api/v1/ai/ask", json={"question": "什么是 RAG？"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    frames = [json.loads(line.removeprefix("data: ")) for line in resp.text.splitlines() if line.startswith("data: ")]
    assert frames[0]["type"] == "token" and "RAG" in frames[0]["content"]
    assert frames[-1]["type"] == "done"
