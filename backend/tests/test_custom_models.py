"""自定义模型（AI 设置页「自定义模型」弹窗）回归：
权限守卫、增删查与脱敏回传、连通性失败拦截、运行时热切换。"""
from app.api.v1 import ai_assistant
from app.ai_engine.llm_client import UnifiedLLMClient
from tests.conftest import auth_header, login_token, make_user


def _admin_token(client, db):
    make_user(db, "admin_cm", role="admin")
    return login_token(client, "admin_cm")


def test_custom_model_requires_admin(client, db):
    make_user(db, "reader_cm")
    token = login_token(client, "reader_cm")
    resp = client.get("/api/v1/ai/custom-models", headers=auth_header(token))
    assert resp.json()["code"] == 403, "普通用户不得访问自定义模型接口"


def test_connectivity_failure_rejects_add(client, db):
    token = _admin_token(client, db)
    resp = client.post(
        "/api/v1/ai/custom-models",
        json={
            "api_format": "openai-chat",
            "base_url": "http://127.0.0.1:9/v1",  # discard 端口，必然拒绝连接
            "model_id": "nope",
            "api_key": "sk-x",
        },
        headers=auth_header(token),
    )
    body = resp.json()
    assert body["code"] == 400, "连通性测试失败的模型不得入库"
    assert "连通性测试失败" in body["message"]


def test_add_list_delete_custom_model(client, db, monkeypatch):
    token = _admin_token(client, db)
    headers = auth_header(token)

    async def fake_probe(payload):
        return {"latency_ms": 88}

    monkeypatch.setattr(ai_assistant, "_probe_custom_model", fake_probe)

    payload = {
        "api_format": "openai-chat",
        "base_url": "https://api.example.com/v1",
        "full_url": False,
        "model_id": "test-model-1",
        "display_name": "测试模型",
        "api_key": "sk-test123456",
        "temperature": 0.5,
    }
    resp = client.post("/api/v1/ai/custom-models", json=payload, headers=headers)
    body = resp.json()
    assert body["code"] == 200, body
    assert len(body["data"]) == 1
    item = body["data"][0]
    assert item["display_name"] == "测试模型"
    assert item["latency_ms"] == 88
    assert "****" in item["api_key"], "回传的 API Key 必须脱敏"

    # 同端点 + 同模型 + 同格式视为同一条目，覆盖更新而非堆叠
    resp = client.post("/api/v1/ai/custom-models", json=payload, headers=headers)
    assert len(resp.json()["data"]) == 1

    listed = client.get("/api/v1/ai/custom-models", headers=headers).json()["data"]
    assert len(listed) == 1 and listed[0]["model_id"] == "test-model-1"

    # 运行时热切换：主配置「模型选择」命中自定义模型（按展示名称匹配），
    # 引擎客户端必须切换到该模型的专属端点 / 密钥 / 模型 ID
    resp = client.put(
        "/api/v1/ai/config",
        json={
            "provider": "测试接入商",
            "api_key": None,
            "base_url": None,
            "model": "测试模型",
            "top_k": 4,
            "similarity_threshold": 0.18,
        },
        headers=headers,
    )
    assert resp.json()["code"] == 200
    assert ai_assistant.rag_service.llm.api_key == "sk-test123456"
    assert ai_assistant.rag_service.llm.base_url == "https://api.example.com/v1"
    assert ai_assistant.rag_service.llm.model == "test-model-1"

    # 删除后列表为空
    resp = client.delete(f"/api/v1/ai/custom-models/{item['id']}", headers=headers)
    assert resp.json()["code"] == 200
    assert client.get("/api/v1/ai/custom-models", headers=headers).json()["data"] == []

    # 还原运行时客户端，避免污染同进程的后续用例
    ai_assistant.rag_service.llm = UnifiedLLMClient()
