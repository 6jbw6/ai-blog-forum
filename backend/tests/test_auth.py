"""鉴权链路：注册准入（邮箱白名单 / 重复账号）、登录校验、JWT 会话。"""


def test_register_and_login_roundtrip(client):
    resp = client.post("/api/v1/auth/register", json={
        "username": "reader1",
        "password": "password123",
        "email": "reader1@qq.com",
        "nickname": "读者一号",
    })
    body = resp.json()
    assert resp.status_code == 200 and body["code"] == 200, body
    assert body["data"]["role"] == "reader"

    login_resp = client.post("/api/v1/auth/login", json={
        "username": "reader1",
        "password": "password123",
    })
    login_body = login_resp.json()
    assert login_body["code"] == 200
    token = login_body["data"]["access_token"]
    assert login_body["data"]["user"]["username"] == "reader1"

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["code"] == 200
    assert me.json()["data"]["nickname"] == "读者一号"


def test_register_rejects_non_mainstream_email_domain(client):
    resp = client.post("/api/v1/auth/register", json={
        "username": "selfhost",
        "password": "password123",
        "email": "someone@self-hosted-mail.dev",
    })
    assert resp.status_code == 422
    assert "主流邮箱" in resp.json()["message"]


def test_register_rejects_duplicate_username_or_email(client):
    payload = {"username": "dup", "password": "password123", "email": "dup@qq.com"}
    assert client.post("/api/v1/auth/register", json=payload).json()["code"] == 200

    dup_name = client.post("/api/v1/auth/register", json={**payload, "email": "other@qq.com"})
    assert dup_name.json()["code"] == 400

    dup_email = client.post("/api/v1/auth/register", json={**payload, "username": "other"})
    assert dup_email.json()["code"] == 400


def test_login_with_wrong_password_fails(client, db):
    from tests.conftest import make_user

    make_user(db, "alice")
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "wrong-password"})
    body = resp.json()
    assert resp.status_code == 200  # 业务异常统一 200 + code 标识
    assert body["code"] == 400
    assert "用户名或密码错误" in body["message"]


def test_me_requires_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.json()["code"] == 401


def test_me_rejects_tampered_token(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.json()["code"] == 401
