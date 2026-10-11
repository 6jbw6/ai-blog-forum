"""内容审核策略回归：命中敏感词只「拦下 + 转人工审核」，绝不自动封号。

旧策略是一次子串命中即永久封禁且无申诉通道，而词库只有几十个硬编码词——
加空格、换同音字就绕过，对真垃圾信息几乎无效，却很容易误伤讲反诈 / 反洗钱 /
数据投毒的技术文章。惩罚与触发条件完全不成比例，因此改为机器只分流、封号由人决定。
"""
import logging

from app.core import content_moderation
from app.models.article import Article
from app.models.user import User
from tests.conftest import TEST_PASSWORD, auth_header, login_token, make_article, make_user

BANNED_SAMPLE = "这个赌博网站值得一看"


def _post_comment(client, article_id, content, username):
    return client.post(
        "/api/v1/comments",
        json={"article_id": article_id, "content": content},
        headers=auth_header(login_token(client, username)),
    ).json()


def _post_article(client, username, slug, content):
    return client.post(
        "/api/v1/articles",
        json={"title": "测试文章", "slug": slug, "content": content},
        headers=auth_header(login_token(client, username)),
    ).json()


def test_violating_comment_is_held_not_banned(client, db):
    author = make_user(db, "author_mp1")
    make_user(db, "spammer_mp1")
    art = make_article(db, author)

    body = _post_comment(client, art.id, BANNED_SAMPLE, "spammer_mp1")
    assert body["code"] == 200, "命中敏感词的评论仍然入库，只是转待审"
    assert body["data"]["is_approved"] is False, "待审评论不得直接公开"
    assert "审核" in body["message"]

    spammer = db.query(User).filter_by(username="spammer_mp1").one()
    assert spammer.is_active, "内容命中不得封号"
    assert spammer.ban_reason is None

    again = client.post("/api/v1/auth/login",
                        json={"username": "spammer_mp1", "password": TEST_PASSWORD}).json()
    assert again["code"] == 200, "命中敏感词后账号必须仍能登录"


def test_held_comment_hidden_from_public_but_in_admin_queue(client, db):
    admin = make_user(db, "admin_mp2", role="admin")
    make_user(db, "spammer_mp2")
    art = make_article(db, admin)
    _post_comment(client, art.id, BANNED_SAMPLE, "spammer_mp2")

    public = client.get(f"/api/v1/comments/article/{art.id}").json()["data"]
    assert public == [], "待审评论不得出现在公开评论区"

    token = auth_header(login_token(client, "admin_mp2"))
    queue = client.get("/api/v1/comments/admin/list", headers=token).json()["data"]
    assert queue["total"] == 1, "待审评论必须进管理员审核队列"

    approved = client.put(f"/api/v1/comments/admin/{queue['list'][0]['id']}/approve",
                          headers=token).json()
    assert approved["code"] == 200
    public_after = client.get(f"/api/v1/comments/article/{art.id}").json()["data"]
    assert len(public_after) == 1, "管理员放行后评论公开可见"


def test_held_comment_sends_no_notification(client, db):
    author = make_user(db, "author_mp3")
    make_user(db, "spammer_mp3")
    art = make_article(db, author)
    _post_comment(client, art.id, BANNED_SAMPLE, "spammer_mp3")

    from app.models.notification import Notification
    assert db.query(Notification).count() == 0, "待审评论不得给作者推站内提醒"


def test_violating_article_rejected_without_ban(client, db):
    make_user(db, "writer_mp4")
    body = _post_article(client, "writer_mp4", "mp4-slug", BANNED_SAMPLE)
    assert body["code"] == 400, "命中敏感词的博文不予发布"
    assert "未保存" in body["message"]
    assert db.query(Article).count() == 0, "被拒的博文不得落库"

    writer = db.query(User).filter_by(username="writer_mp4").one()
    assert writer.is_active, "内容命中不得封号"


def test_violating_article_edit_rejected_without_ban(client, db):
    author = make_user(db, "writer_mp5")
    art = make_article(db, author)
    token = auth_header(login_token(client, "writer_mp5"))
    body = client.put(f"/api/v1/articles/{art.id}", json={"content": BANNED_SAMPLE},
                      headers=token).json()
    assert body["code"] == 400
    db.refresh(art)
    assert art.content == "正文内容，用于检索与展示。", "被拒的修改不得落库"
    assert db.query(User).filter_by(username="writer_mp5").one().is_active


def test_admin_is_exempt_from_content_gate(client, db):
    """管理员是审核者本人，不该被自己的闸门挡住（否则他的发言会卡在自己的待审队列里）"""
    admin = make_user(db, "admin_mp6", role="admin")
    art = make_article(db, admin)

    comment = _post_comment(client, art.id, BANNED_SAMPLE, "admin_mp6")
    assert comment["code"] == 200
    assert comment["data"]["is_approved"] is True, "管理员评论直接公开"

    article = _post_article(client, "admin_mp6", "mp6-slug", BANNED_SAMPLE)
    assert article["code"] == 200, "管理员发布命中敏感词的博文不应被拦"
    assert db.query(Article).filter(Article.slug == "mp6-slug").count() == 1


def test_clean_content_still_publishes(client, db):
    author = make_user(db, "author_mp7")
    make_user(db, "reader_mp7")
    art = make_article(db, author)

    body = _post_comment(client, art.id, "这篇讲 LoRA 量化的文章很有帮助", "reader_mp7")
    assert body["code"] == 200
    assert body["data"]["is_approved"] is True
    assert body["message"] == "评论发表成功"


def test_violation_leaves_audit_trail(client, db, caplog):
    """封号权交回人工后，审计日志是管理员判断「这人是不是惯犯」的唯一依据"""
    author = make_user(db, "author_mp8")
    make_user(db, "spammer_mp8")
    art = make_article(db, author)

    with caplog.at_level(logging.WARNING, logger="app.moderation"):
        _post_comment(client, art.id, BANNED_SAMPLE, "spammer_mp8")

    entry = next((r for r in caplog.records if r.name == "app.moderation"), None)
    assert entry is not None, "命中敏感词必须留下审计日志"
    assert "spammer_mp8" in entry.getMessage()
    assert "赌博" in entry.getMessage()


def test_auto_ban_helper_is_gone():
    """锁死策略：不要再有人把「命中即封号」加回来"""
    assert not hasattr(content_moderation, "auto_ban_if_violation")
    assert not hasattr(content_moderation, "AUTO_BAN_SOURCE")
    # 封禁能力本身保留，但只服务于管理员手动操作
    assert callable(content_moderation.ban_user)
    assert callable(content_moderation.unban_user)
