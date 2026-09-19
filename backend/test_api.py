import sys
import os
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("--- 1. 测试根路径健康检查 ---")
r = client.get("/")
print("Root:", r.status_code, r.json())
assert r.status_code == 200

print("\n--- 2. 测试管理员登录 ---")
r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
print("Login:", r.status_code, r.json()["message"])
assert r.status_code == 200
token = r.json()["data"]["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("\n--- 3. 测试文章分页列表 ---")
r = client.get("/api/v1/articles?page=1&size=5")
articles_data = r.json()["data"]
print(f"Articles Total: {articles_data['total']}, Retrieved: {len(articles_data['list'])}")
assert articles_data["total"] >= 3

print("\n--- 4. 测试基于向量的自然语言语义检索 (Semantic Search) ---")
r = client.post("/api/v1/ai/semantic-search", json={"query": "显存不够怎么微调大模型？", "top_k": 3})
search_data = r.json()["data"]
print(f"Semantic Search Results Count: {len(search_data)}")
for item in search_data:
    print(f"  -> 《{item['title']}》 相似度: {item['similarity']} 匹配片段: {item['matched_snippet'][:60]}...")
assert len(search_data) > 0

print("\n--- 5. 测试 AI 一键提炼摘要与标签推荐 ---")
r = client.post(
    "/api/v1/ai/summary",
    json={
        "title": "测试文章",
        "content": "这是一篇关于深度学习注意力机制 Transformer 和 LoRA 微调的技术文章，探讨高并发系统设计与 FastAPI 实践。"
    }
)
print("AI Summary:", r.json()["data"])
assert "summary" in r.json()["data"]

print("\n🎉 后端核心 API 与 AI 算法检索流水线测试全部通过！")
