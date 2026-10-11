"""安全审计第二轮修复回归测试（2026-10-11 审查发现，勿删勿简化）：

1. [P0] 公开评论接口不再泄露评论者 email，后台审核走独立的管理员视图
2. [P1a] 封禁在 get_optional_user 路径同样生效（此前只挡住 get_current_user）
3. [P1b] 草稿 / 「仅自己可见」文章的评论区对无关人员隐身，且不接受留言
4. [P1c] 回复的 parent_id 必须同属一篇文章
5. [P1d] 注册接口限流
6. [P2a] 写入 .env 的大模型参数剥掉换行，堵住配置注入
7. [P2b] 大模型端点 SSRF 校验
8. [P2c] search_hits / views_count 防刷 —— 见 tests/test_hit_dedup.py
9. [P2d] 后台违规评论列表改为 SQL 过滤 + 真分页
10. [P3] SQL echo 与接口文档默认不再跟着 DEBUG / APP_ENV 走
"""
import pytest
from sqlalchemy import func

from app.api.v1 import ai_assistant
from app.core.config import Settings, settings
from app.core.content_moderation import BANNED_KEYWORDS, moderate_text, violated_content_filter
from app.core.response import BusinessException
from app.core.security import assert_safe_llm_endpoint
from app.models.comment import Comment
from tests.conftest import auth_header, login_token, make_article, make_user


def _seed_comment(db, article, user, content, parent_id=None, is_approved=True):
    """直接落库造评论：走 API 造违规评论会连带把作者封号，不适合批量铺数据"""
    c = Comment(
        article_id=article.id,
        parent_id=parent_id,
        user_id=user.id,
        user_name=user.nickname,
        user_email=user.email,
        content=content,
        is_approved=is_approved,
        is_admin=user.role == "admin",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _flatten(comments):
    """把树形评论摊平，便于对整个响应做字段断言"""
    for c in comments:
        yield c
        yield from _flatten(c.get("replies") or [])


# ---------- P0：评论接口不再泄露邮箱 ----------

def test_public_comment_list_has_no_email(client, db):
    author = make_user(db, "art_owner_r2")
    reader = make_user(db, "commenter_r2")
    art = make_article(db, author)
    token = login_token(client, "commenter_r2")
    posted = client.post("/api/v1/comments",
                         json={"article_id": art.id, "content": "写得很好"},
                         headers=auth_header(token))
    assert posted.json()["code"] == 200
    _seed_comment(db, art, reader, "再来一条", parent_id=posted.json()["data"]["id"])

    # 完全匿名的请求，不带任何令牌
    resp = client.get(f"/api/v1/comments/article/{art.id}")
    tree = resp.json()["data"]
    assert tree, "评论列表不应为空"
    for c in _flatten(tree):
        assert "user_email" not in c, "公开评论响应（含各层回复）不得携带 user_email"


def test_post_comment_response_has_no_email(client, db):
    author = make_user(db, "art_owner_r2b")
    make_user(db, "commenter_r2b")
    art = make_article(db, author)
    token = login_token(client, "commenter_r2b")
    body = client.post("/api/v1/comments",
                       json={"article_id": art.id, "content": "沙发"},
                       headers=auth_header(token)).json()
    assert body["code"] == 200
    assert "user_email" not in body["data"]


def test_admin_comment_list_still_returns_email(client, db):
    admin = make_user(db, "admin_r2", role="admin")
    reader = make_user(db, "spammer_r2")
    art = make_article(db, admin)
    _seed_comment(db, art, reader, "赌博网站推广", is_approved=False)

    token = login_token(client, "admin_r2")
    body = client.get("/api/v1/comments/admin/list", headers=auth_header(token)).json()
    assert body["code"] == 200
    assert body["data"]["total"] == 1
    assert body["data"]["list"][0]["user_email"] == "spammer_r2@qq.com", \
        "后台审核页需要看到评论人邮箱"


def test_admin_comment_list_requires_admin(client, db):
    make_user(db, "reader_r2c")
    token = login_token(client, "reader_r2c")
    body = client.get("/api/v1/comments/admin/list", headers=auth_header(token)).json()
    assert body["code"] == 403


def test_admin_comment_list_filters_and_paginates_in_sql(client, db):
    admin = make_user(db, "admin_r2d", role="admin")
    reader = make_user(db, "bulk_r2d")
    art = make_article(db, admin)
    for i in range(7):
        _seed_comment(db, art, reader, f"正常内容 {i}")
    for i in range(5):
        _seed_comment(db, art, reader, f"赌博推广第 {i} 条", is_approved=False)

    token = login_token(client, "admin_r2d")
    page1 = client.get("/api/v1/comments/admin/list?page=1&size=2",
                       headers=auth_header(token)).json()["data"]
    page3 = client.get("/api/v1/comments/admin/list?page=3&size=2",
                       headers=auth_header(token)).json()["data"]

    assert page1["total"] == 5, "只统计命中敏感词的评论"
    assert len(page1["list"]) == 2 and len(page3["list"]) == 1
    for row in page1["list"]:
        assert moderate_text(row["content"])[0], "列表里不得混入合规评论"


def test_violated_filter_matches_python_moderation(db):
    """SQL 过滤条件与 moderate_text 必须同口径，否则后台会漏审或误审"""
    admin = make_user(db, "admin_r2e", role="admin")
    art = make_article(db, admin)
    samples = ["赌博", "这是一篇讲 LoRA 微调的文章", "办假证联系方式", "冰毒 制作", "完全正常的内容"]
    for s in samples:
        _seed_comment(db, art, admin, s)

    ids_sql = {
        r[0] for r in
        db.query(Comment.id).filter(violated_content_filter(Comment.content)).all()
    }
    ids_py = {cid for cid, text in db.query(Comment.id, Comment.content).all()
              if moderate_text(text)[0]}
    assert ids_sql == ids_py
    assert len(ids_sql) == 3


# ---------- P1a：封禁在可选鉴权路径同样生效 ----------

def test_banned_user_loses_optional_auth_privileges(client, db):
    from app.core.content_moderation import ban_user

    victim = make_user(db, "banned_r2")
    make_article(db, victim, title="封号者的私密草稿", is_published=False, is_private=True)
    token = login_token(client, "banned_r2")
    ban_user(db, victim, "测试封禁")

    assert client.get("/api/v1/auth/me", headers=auth_header(token)).json()["code"] == 401

    drafts = client.get(f"/api/v1/articles?published_only=false&author_id={victim.id}",
                        headers=auth_header(token)).json()
    assert drafts["data"]["list"] == [], "封号后不得再经 get_optional_user 取回自己的草稿"


def test_active_author_can_still_see_own_drafts(client, db):
    """对照用例：没被封的作者本人权限不受影响"""
    author = make_user(db, "author_r2f")
    make_article(db, author, title="在写的草稿", is_published=False)
    token = login_token(client, "author_r2f")
    body = client.get(f"/api/v1/articles?published_only=false&author_id={author.id}",
                      headers=auth_header(token)).json()
    assert [a["title"] for a in body["data"]["list"]] == ["在写的草稿"]


# ---------- P1b：私密 / 草稿文章的评论区 ----------

def test_private_article_comments_hidden_from_strangers(client, db):
    author = make_user(db, "author_r2g")
    stranger = make_user(db, "stranger_r2g")
    art = make_article(db, author, title="仅自己可见", is_published=True, is_private=True)
    _seed_comment(db, art, author, "私密文章下的讨论")

    anon = client.get(f"/api/v1/comments/article/{art.id}").json()
    assert anon["code"] == 404, "匿名不得读到私密文章的评论"

    other = client.get(f"/api/v1/comments/article/{art.id}",
                       headers=auth_header(login_token(client, "stranger_r2g"))).json()
    assert other["code"] == 404, "无关登录用户不得读到私密文章的评论"


def test_private_article_comments_visible_to_author_and_admin(client, db):
    author = make_user(db, "author_r2h")
    admin = make_user(db, "admin_r2h", role="admin")
    art = make_article(db, author, is_published=False)
    _seed_comment(db, art, author, "草稿下自己的备注")

    for who in ("author_r2h", "admin_r2h"):
        body = client.get(f"/api/v1/comments/article/{art.id}",
                          headers=auth_header(login_token(client, who))).json()
        assert body["code"] == 200, f"{who} 应当能看到"
        assert len(body["data"]) == 1


def test_cannot_comment_on_private_or_draft_article(client, db):
    author = make_user(db, "author_r2i")
    stranger = make_user(db, "stranger_r2i")
    priv = make_article(db, author, is_published=True, is_private=True)
    draft = make_article(db, author, title="草稿", is_published=False)
    token = login_token(client, "stranger_r2i")

    for art in (priv, draft):
        body = client.post("/api/v1/comments",
                           json={"article_id": art.id, "content": "路过留言"},
                           headers=auth_header(token)).json()
        assert body["code"] == 404, "无关人员不得在私密 / 草稿文章下留言"
        assert db.query(func.count(Comment.id)).filter(Comment.article_id == art.id).scalar() == 0


def test_author_can_comment_on_own_draft(client, db):
    author = make_user(db, "author_r2j")
    draft = make_article(db, author, is_published=False)
    token = login_token(client, "author_r2j")
    body = client.post("/api/v1/comments",
                       json={"article_id": draft.id, "content": "自己给自己记一笔"},
                       headers=auth_header(token)).json()
    assert body["code"] == 200


# ---------- P1c：parent_id 必须同属一篇文章 ----------

def test_reply_cannot_be_attached_to_another_article(client, db):
    author = make_user(db, "author_r2k")
    art1 = make_article(db, author, title="文章一")
    art2 = make_article(db, author, title="文章二")
    token = login_token(client, "author_r2k")

    root = client.post("/api/v1/comments", json={"article_id": art1.id, "content": "一楼"},
                       headers=auth_header(token)).json()["data"]
    body = client.post("/api/v1/comments",
                       json={"article_id": art2.id, "parent_id": root["id"], "content": "跨文章挂载"},
                       headers=auth_header(token)).json()
    assert body["code"] == 400

    listing = client.get(f"/api/v1/comments/article/{art2.id}").json()["data"]
    assert listing == [], "跨文章回复不得落库、更不得浮到目标文章的根评论层"


def test_reply_to_missing_comment_rejected(client, db):
    author = make_user(db, "author_r2l")
    art = make_article(db, author)
    token = login_token(client, "author_r2l")
    body = client.post("/api/v1/comments",
                       json={"article_id": art.id, "parent_id": 999999, "content": "回复不存在的评论"},
                       headers=auth_header(token)).json()
    assert body["code"] == 404


def test_reply_within_same_article_still_nested(client, db):
    author = make_user(db, "author_r2m")
    art = make_article(db, author)
    token = login_token(client, "author_r2m")
    root = client.post("/api/v1/comments", json={"article_id": art.id, "content": "楼主"},
                       headers=auth_header(token)).json()["data"]
    body = client.post("/api/v1/comments",
                       json={"article_id": art.id, "parent_id": root["id"], "content": "正常回复"},
                       headers=auth_header(token)).json()
    assert body["code"] == 200

    tree = client.get(f"/api/v1/comments/article/{art.id}").json()["data"]
    assert len(tree) == 1 and len(tree[0]["replies"]) == 1, "同文章回复仍应正常嵌套"


# ---------- P1d：注册限流 ----------

def test_register_is_rate_limited(client, db):
    from app.api.v1.auth import register_limiter
    limit = register_limiter.max_requests

    codes = []
    for i in range(limit + 3):
        resp = client.post("/api/v1/auth/register", json={
            "username": f"bulk_r2_{i}",
            "password": "password123",
            "email": f"bulk_r2_{i}@qq.com",
        })
        codes.append(resp.status_code if resp.status_code == 429 else resp.json()["code"])

    assert codes[:limit] == [200] * limit, "限流额度内应全部注册成功"
    assert codes[limit:] == [429] * 3, "超出额度必须返回 429"


def test_login_rate_limit_still_in_place(client, db):
    """对照用例：登录闸门没被这轮改动带坏"""
    from app.api.v1.auth import login_limiter
    for _ in range(login_limiter.max_requests + 1):
        resp = client.post("/api/v1/auth/login",
                           json={"username": "ghost_r2", "password": "password123"})
    assert resp.status_code == 429


# ---------- P2a：.env 值净化 ----------

def test_env_value_strips_newlines():
    assert ai_assistant._sanitize_env_value("https://a.com\nJWT_SECRET_KEY=pwned") == \
        "https://a.com JWT_SECRET_KEY=pwned"
    assert ai_assistant._sanitize_env_value("a\r\nb\tc  d") == "a b c d"
    assert "\n" not in ai_assistant._sanitize_env_value("x\n" * 50)


def test_llm_config_rejects_overlong_fields(client, db):
    admin = make_user(db, "admin_r2n", role="admin")
    token = login_token(client, "admin_r2n")
    resp = client.put("/api/v1/ai/config", json={
        "provider": "p" * 200,
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "top_k": 4,
        "similarity_threshold": 0.18,
    }, headers=auth_header(token))
    assert resp.status_code == 422, "超长 provider 必须被 schema 长度上限挡下"


def test_llm_config_bounds_rag_params(client, db):
    admin = make_user(db, "admin_r2o", role="admin")
    token = login_token(client, "admin_r2o")
    for top_k, threshold in ((0, 0.18), (999, 0.18), (4, 1.5), (4, -0.1)):
        resp = client.put("/api/v1/ai/config", json={
            "provider": "deepseek", "base_url": None, "model": None,
            "top_k": top_k, "similarity_threshold": threshold,
        }, headers=auth_header(token))
        assert resp.status_code == 422, f"top_k={top_k} threshold={threshold} 应被边界校验挡下"


# ---------- P2b：大模型端点 SSRF ----------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:11434/v1",
    "http://localhost:8080/v1",
    "http://169.254.169.254/latest/meta-data/",
    "http://192.168.1.10:8000/v1",
    "http://10.0.0.5/v1",
    "http://[::1]:8000/v1",
])
def test_llm_endpoint_rejects_private_targets(url):
    with pytest.raises(BusinessException):
        assert_safe_llm_endpoint(url)


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_INFO",
    "ftp://example.com/x",
    "not a url",
    "",
])
def test_llm_endpoint_rejects_bad_scheme(url):
    with pytest.raises(BusinessException):
        assert_safe_llm_endpoint(url)


def test_llm_endpoint_allows_private_when_explicitly_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_LLM_ENDPOINTS", True)
    assert assert_safe_llm_endpoint("http://127.0.0.1:11434/v1") == "http://127.0.0.1:11434/v1"


def test_fetch_models_endpoint_blocks_ssrf(client, db):
    admin = make_user(db, "admin_r2p", role="admin")
    token = login_token(client, "admin_r2p")
    body = client.post("/api/v1/ai/models",
                       json={"base_url": "http://169.254.169.254/latest/meta-data/", "api_key": "sk-x"},
                       headers=auth_header(token)).json()
    assert body["code"] == 400
    assert "内网" in body["message"]


def test_fetch_models_requires_admin(client, db):
    make_user(db, "reader_r2q")
    token = login_token(client, "reader_r2q")
    body = client.post("/api/v1/ai/models",
                       json={"base_url": "https://api.deepseek.com", "api_key": "sk-x"},
                       headers=auth_header(token)).json()
    assert body["code"] == 403


def test_update_ai_config_blocks_private_base_url(client, db):
    admin = make_user(db, "admin_r2r", role="admin")
    token = login_token(client, "admin_r2r")
    original = settings.LLM_BASE_URL
    body = client.put("/api/v1/ai/config", json={
        "provider": "deepseek", "base_url": "http://10.1.2.3:8000/v1",
        "model": "deepseek-chat", "top_k": 4, "similarity_threshold": 0.18,
    }, headers=auth_header(token)).json()
    assert body["code"] == 400
    assert settings.LLM_BASE_URL == original, "被拒绝的端点不得写进运行时配置"


# ---------- P3：SQL echo 与接口文档开关 ----------

def test_sql_echo_defaults_off():
    from app.core.database import engine
    assert engine.echo is False, "SQL 回显默认必须关闭"
    assert Settings(SQL_ECHO=False, APP_ENV="development", DEBUG=True).SQL_ECHO is False


def test_docs_exposure_follows_env_not_debug():
    prod = Settings(APP_ENV="production", JWT_SECRET_KEY="a" * 64, DEBUG=True)
    assert prod.is_production and prod.expose_api_docs is False, \
        "生产环境即使 DEBUG 误配为 True 也不得开放接口文档"

    opt_in = Settings(APP_ENV="production", JWT_SECRET_KEY="a" * 64, EXPOSE_API_DOCS=True)
    assert opt_in.expose_api_docs is True, "显式开启后生产也可放开"

    dev = Settings(APP_ENV="development", JWT_SECRET_KEY="a" * 64)
    assert dev.expose_api_docs is True, "开发环境默认保持可用"


def test_banned_keyword_list_has_no_like_wildcards():
    """词库会同时用于 SQL LIKE 与 Python 子串匹配，含通配符会让两边语义分叉"""
    assert BANNED_KEYWORDS, "敏感词表不应为空（空表会让 SQL 过滤条件退化成 or_() 报错）"
    for kw in BANNED_KEYWORDS:
        assert not ({"%", "_", "\\"} & set(kw)), f"敏感词 {kw!r} 含 LIKE 通配符"
