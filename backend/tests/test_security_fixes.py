"""安全修复回归测试（2026-10-10 审查发现，勿删勿简化）：

1. [P0] 公开接口不再泄露用户 email：文章列表/详情的 author、用户 profile
2. [P1a] 修改密码必须验证旧密码
3. [P1b] 文章更新与评论编辑补内容审核（防「先发正常、再编辑塞违规词」绕过）
4. [P1c] GET /ai/config 的 LLM API Key 只回传掩码
"""
from app.core.config import settings
from tests.conftest import (
    TEST_PASSWORD,
    auth_header,
    login_token,
    make_article,
    make_user,
)


# ---------- P0：email 不再随公开接口泄露 ----------

def test_article_list_author_has_no_email(client, db):
    author = make_user(db, "author1")
    make_article(db, author)
    resp = client.get("/api/v1/articles")
    items = resp.json()["data"]["list"]
    assert items, "文章列表不应为空"
    for item in items:
        a = item["author"]
        assert a is not None
        assert "email" not in a, "文章 author 不得携带 email"
        assert "is_active" not in a, "文章 author 不得携带 is_active"


def test_article_detail_author_has_no_email(client, db):
    author = make_user(db, "author2", email="secret2@qq.com")
    art = make_article(db, author)
    resp = client.get(f"/api/v1/articles/{art.id}")
    a = resp.json()["data"]["author"]
    assert a is not None
    assert "email" not in a
    assert "secret2" not in resp.text, "响应全文不得出现作者邮箱明文"


def test_user_profile_has_no_email(client, db):
    target = make_user(db, "target3", email="leakme3@qq.com")
    resp = client.get(f"/api/v1/users/{target.id}/profile")
    assert resp.json()["code"] == 200
    assert "email" not in resp.json()["data"]
    assert "leakme3" not in resp.text, "profile 响应不得出现邮箱明文"


def test_login_still_returns_own_email(client, db):
    """本人登录响应仍应带 email（合法自见场景），验证拆分未误伤"""
    make_user(db, "selfview4", email="self4@qq.com")
    body = client.post(
        "/api/v1/auth/login", json={"username": "selfview4", "password": TEST_PASSWORD}
    ).json()
    assert body["data"]["user"]["email"] == "self4@qq.com"


# ---------- P1a：改密码必须验证旧密码 ----------

def test_change_password_requires_old_password(client, db):
    make_user(db, "pwuser5")
    token = login_token(client, "pwuser5")
    resp = client.put(
        "/api/v1/auth/me",
        json={"password": "newpass123"},  # 未带 old_password
        headers=auth_header(token),
    )
    assert resp.json()["code"] == 400


def test_change_password_rejects_wrong_old_password(client, db):
    make_user(db, "pwuser6")
    token = login_token(client, "pwuser6")
    resp = client.put(
        "/api/v1/auth/me",
        json={"password": "newpass123", "old_password": "wrong-old-pass"},
        headers=auth_header(token),
    )
    assert resp.json()["code"] == 400


def test_change_password_with_correct_old_password(client, db):
    make_user(db, "pwuser7")
    token = login_token(client, "pwuser7")
    resp = client.put(
        "/api/v1/auth/me",
        json={"password": "newpass123", "old_password": TEST_PASSWORD},
        headers=auth_header(token),
    )
    assert resp.json()["code"] == 200
    # 新密码可登录，旧密码失效
    ok = client.post(
        "/api/v1/auth/login", json={"username": "pwuser7", "password": "newpass123"}
    ).json()
    assert ok["code"] == 200
    bad = client.post(
        "/api/v1/auth/login", json={"username": "pwuser7", "password": TEST_PASSWORD}
    ).json()
    assert bad["code"] != 200


def test_update_profile_without_password_untouched(client, db):
    """不改密码时（未提交 password 字段）资料更新不受影响，无需 old_password"""
    make_user(db, "pwuser8")
    token = login_token(client, "pwuser8")
    resp = client.put(
        "/api/v1/auth/me",
        json={"bio": "新签名"},
        headers=auth_header(token),
    )
    assert resp.json()["code"] == 200
    assert resp.json()["data"]["bio"] == "新签名"


# ---------- P1b：编辑路径补内容审核 ----------

def test_update_article_with_banned_word_rejected(client, db):
    author = make_user(db, "writer9")
    art = make_article(db, author)
    token = login_token(client, "writer9")
    resp = client.put(
        f"/api/v1/articles/{art.id}",
        json={"content": "这是赌博违规内容"},
        headers=auth_header(token),
    )
    body = resp.json()
    assert body["code"] == 403, "编辑塞违规词必须被拒绝"
    # 发布者被自动封号
    again = client.post(
        "/api/v1/auth/login", json={"username": "writer9", "password": TEST_PASSWORD}
    ).json()
    assert again["code"] == 403


def test_update_comment_with_banned_word_rejected(client, db):
    author = make_user(db, "cmtowner10")
    art = make_article(db, author)
    commenter = make_user(db, "commenter10")
    token = login_token(client, "commenter10")
    created = client.post(
        "/api/v1/comments",
        json={"article_id": art.id, "content": "正常评论"},
        headers=auth_header(token),
    ).json()
    assert created["code"] == 200, f"创建评论失败: {created}"
    comment_id = created["data"]["id"]

    resp = client.put(
        f"/api/v1/comments/{comment_id}",
        json={"content": "加入裸聊违规词"},
        headers=auth_header(token),
    )
    assert resp.json()["code"] == 403, "评论编辑塞违规词必须被拒绝"
    # 编辑后内容仍是原文，未被落库
    detail = client.get(f"/api/v1/comments/article/{art.id}").json()["data"]
    assert detail and detail[0]["content"] == "正常评论"


# ---------- P1c：LLM API Key 掩码回传 ----------

def test_ai_config_masks_api_key(client, db, monkeypatch):
    fake_key = "sk-1234567890abcdefWXYZ"
    monkeypatch.setattr(settings, "LLM_API_KEY", fake_key)
    make_user(db, "root11", role="admin")
    token = login_token(client, "root11")
    resp = client.get("/api/v1/ai/config", headers=auth_header(token))
    body = resp.json()
    assert body["code"] == 200
    masked = body["data"]["api_key"]
    assert fake_key not in masked, "不得回传完整明文密钥"
    assert "****" in masked, "必须以掩码形式展示"
    assert masked.startswith("sk-1"), "掩码应保留可辨识的前缀"


# ---------- 低危A：/ai/history limit 边界校验 ----------

def test_ai_history_limit_bounds(client, db):
    make_user(db, "histuser12")
    token = login_token(client, "histuser12")
    assert client.get("/api/v1/ai/history?limit=0", headers=auth_header(token)).status_code == 422
    assert client.get("/api/v1/ai/history?limit=-5", headers=auth_header(token)).status_code == 422
    assert client.get("/api/v1/ai/history?limit=99999", headers=auth_header(token)).status_code == 422
    ok = client.get("/api/v1/ai/history?limit=50", headers=auth_header(token))
    assert ok.status_code == 200 and ok.json()["code"] == 200


# ---------- 低危A：文章搜索 LIKE 通配符转义 ----------

def test_article_search_escapes_like_wildcards(client, db):
    author = make_user(db, "liker13")
    make_article(db, author, title="Hello World")
    make_article(db, author, title="Another Post")
    # 未转义时 "%" 是通配符会命中全部；转义后按字面 % 匹配，无文章含 %，应为空
    resp = client.get("/api/v1/articles", params={"keyword": "%"})
    items = resp.json()["data"]["list"]
    assert items == [], "搜索 % 不得退化为全表匹配"


# ---------- 低危B：密码强度准入 ----------

def test_register_rejects_weak_passwords(client):
    for weak in ["short1", "onlyletters", "12345678", "password"]:
        resp = client.post("/api/v1/auth/register", json={
            "username": f"weak_{weak[:6]}",
            "password": weak,
            "email": f"weak_{weak[:6]}@qq.com",
        })
        assert resp.status_code == 422, f"弱密码 {weak!r} 应被拒绝"


def test_register_accepts_strong_password(client):
    resp = client.post("/api/v1/auth/register", json={
        "username": "strong14",
        "password": "pass1234",
        "email": "strong14@qq.com",
    })
    assert resp.json()["code"] == 200


def test_change_password_rejects_weak_new_password(client, db):
    make_user(db, "weakpw15")
    token = login_token(client, "weakpw15")
    resp = client.put(
        "/api/v1/auth/me",
        json={"password": "12345678", "old_password": TEST_PASSWORD},  # 纯数字，弱
        headers=auth_header(token),
    )
    assert resp.status_code == 422


# ---------- 低危C：头像上传魔数校验 ----------

def test_avatar_rejects_fake_image_content(client, db):
    make_user(db, "avatar16")
    token = login_token(client, "avatar16")
    resp = client.post(
        "/api/v1/auth/avatar",
        files={"file": ("fake.png", b"<html><script>alert(1)</script></html>", "image/png")},
        headers=auth_header(token),
    )
    assert resp.json()["code"] == 400, "伪造 PNG 头的内容必须被拒绝"


def test_avatar_accepts_real_png_magic(client, db):
    make_user(db, "avatar17")
    token = login_token(client, "avatar17")
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    resp = client.post(
        "/api/v1/auth/avatar",
        files={"file": ("ok.png", png_bytes, "image/png")},
        headers=auth_header(token),
    )
    assert resp.json()["code"] == 200, f"合法 PNG 应通过: {resp.json()}"


# ---------- 低危C：评论身份以登录账号为准 ----------

def test_comment_identity_not_forgeable(client, db):
    author = make_user(db, "postowner18")
    art = make_article(db, author)
    commenter = make_user(db, "realuser18")
    token = login_token(client, "realuser18")
    resp = client.post(
        "/api/v1/comments",
        json={
            "article_id": art.id,
            "content": "试图伪造身份",
            "user_name": "站长",
            "user_email": "admin@qq.com",
        },
        headers=auth_header(token),
    )
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["user_name"] != "站长", "评论显示名不得采用 payload 伪造值"
    assert body["data"]["user_email"] != "admin@qq.com", "评论邮箱不得采用 payload 伪造值"
