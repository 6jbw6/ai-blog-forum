"""评论链路：树形结构（根评论 + 楼中楼回复）、编辑/删除权限、博主提醒派发。"""

from tests.conftest import auth_header, login_token, make_article, make_user


def _create_comment(client, token, article_id, content, parent_id=None):
    resp = client.post(
        "/api/v1/comments",
        json={"article_id": article_id, "content": content, "parent_id": parent_id},
        headers=auth_header(token),
    )
    return resp


def test_anonymous_cannot_comment(client, db):
    author = make_user(db, "author_c1")
    article = make_article(db, author)
    resp = client.post("/api/v1/comments", json={"article_id": article.id, "content": "匿名评论"})
    assert resp.json()["code"] == 401


def test_comment_thread_nested_tree(client, db):
    owner = make_user(db, "author_c2")
    reader = make_user(db, "reader_c2")
    admin = make_user(db, "root_admin_c2", role="admin")
    article = make_article(db, owner)

    root = _create_comment(client, login_token(client, reader.username), article.id, "写得不错！")
    assert root.json()["code"] == 200
    root_id = root.json()["data"]["id"]
    assert root.json()["data"]["is_admin"] is False  # 读者评论不带站长徽标

    reply = _create_comment(
        client, login_token(client, admin.username), article.id, "谢谢支持", parent_id=root_id
    )
    assert reply.json()["code"] == 200
    # 「站长回复」徽标跟随 role=admin（见 CommentItem.vue），与文章归属无关
    assert reply.json()["data"]["is_admin"] is True

    tree = client.get(f"/api/v1/comments/article/{article.id}").json()["data"]
    assert len(tree) == 1  # 楼中楼必须挂在根评论下，不产生新的根节点
    assert tree[0]["content"] == "写得不错！"
    assert tree[0]["replies"][0]["content"] == "谢谢支持"
    assert tree[0]["replies"][0]["parent_id"] == root_id


def test_comment_notifies_article_owner(client, db):
    from app.models.notification import Notification

    author = make_user(db, "author_c3")
    reader = make_user(db, "reader_c3")
    article = make_article(db, author)

    _create_comment(client, login_token(client, reader.username), article.id, "求更新 RAG 系列")

    notifications = (
        db.query(Notification).filter(Notification.user_id == author.id).all()
    )
    assert len(notifications) == 1
    assert notifications[0].kind == "article_comment"
    assert notifications[0].reply_content == "求更新 RAG 系列"
    # 评论者本人不给自己派发提醒
    assert db.query(Notification).filter(Notification.user_id == reader.id).count() == 0


def test_only_author_can_edit_own_comment(client, db):
    author = make_user(db, "author_c4")
    reader = make_user(db, "reader_c4")
    article = make_article(db, author)
    comment_id = _create_comment(
        client, login_token(client, reader.username), article.id, "原文有笔误"
    ).json()["data"]["id"]

    stranger = make_user(db, "stranger_c4")
    forbidden = client.put(
        f"/api/v1/comments/{comment_id}",
        json={"content": "篡改他人评论"},
        headers=auth_header(login_token(client, stranger.username)),
    )
    assert forbidden.json()["code"] == 403

    ok = client.put(
        f"/api/v1/comments/{comment_id}",
        json={"content": "修正：原文有一处笔误"},
        headers=auth_header(login_token(client, reader.username)),
    )
    assert ok.json()["code"] == 200
    assert ok.json()["data"]["content"] == "修正：原文有一处笔误"


def test_admin_delete_removes_whole_subtree(client, db):
    author = make_user(db, "author_c5")
    admin = make_user(db, "root_admin_c5", role="admin")
    reader = make_user(db, "reader_c5")
    article = make_article(db, author)

    root_id = _create_comment(
        client, login_token(client, reader.username), article.id, "根评论"
    ).json()["data"]["id"]
    _create_comment(
        client, login_token(client, author.username), article.id, "作者回复", parent_id=root_id
    )

    resp = client.delete(
        f"/api/v1/comments/{root_id}", headers=auth_header(login_token(client, admin.username))
    )
    assert resp.json()["code"] == 200

    tree = client.get(f"/api/v1/comments/article/{article.id}").json()["data"]
    assert tree == []  # 子树整体删除，不残留孤儿回复


def test_reader_cannot_delete_others_comment(client, db):
    author = make_user(db, "author_c6")
    reader = make_user(db, "reader_c6")
    stranger = make_user(db, "stranger_c6")
    article = make_article(db, author)
    comment_id = _create_comment(
        client, login_token(client, reader.username), article.id, "别人的评论"
    ).json()["data"]["id"]

    resp = client.delete(
        f"/api/v1/comments/{comment_id}",
        headers=auth_header(login_token(client, stranger.username)),
    )
    assert resp.json()["code"] == 403
    assert client.get(f"/api/v1/comments/article/{article.id}").json()["data"]
