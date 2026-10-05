"""可见性链路：草稿 / 仅自己可见（is_private）文章在列表与 slug 直取两条路径上的隐身规则。

规则基线（README 与实现一致）：未发布草稿与 is_private 文章对作者本人与管理员可见，
对其他读者与游客一律按「不存在」处理，避免泄露存在性。
"""

from tests.conftest import auth_header, login_token, make_article, make_user


def test_public_article_listed_for_anonymous(client, db):
    author = make_user(db, "author1")
    article = make_article(db, author, title="公开博文")

    resp = client.get("/api/v1/articles")
    body = resp.json()
    assert body["code"] == 200
    assert article.id in [a["id"] for a in body["data"]["list"]]


def test_draft_and_private_hidden_from_public_list(client, db):
    author = make_user(db, "author2")
    public = make_article(db, author, title="公开")
    draft = make_article(db, author, title="草稿", is_published=False)
    private = make_article(db, author, title="私密", is_private=True)

    body = client.get("/api/v1/articles").json()
    listed_ids = [a["id"] for a in body["data"]["list"]]
    assert public.id in listed_ids
    assert draft.id not in listed_ids
    assert private.id not in listed_ids


def test_non_owner_cannot_reach_private_or_draft_by_slug(client, db):
    author = make_user(db, "author3")
    private = make_article(db, author, title="私密文", is_private=True)
    draft = make_article(db, author, title="草稿文", is_published=False)

    for article in (private, draft):
        # 游客
        anon = client.get(f"/api/v1/articles/{article.slug}")
        assert anon.json()["code"] == 404
        # 其他登录读者
        stranger = make_user(db, f"stranger_{article.id}")
        resp = client.get(
            f"/api/v1/articles/{article.slug}",
            headers=auth_header(login_token(client, stranger.username)),
        )
        assert resp.json()["code"] == 404


def test_author_and_admin_can_reach_private_article_by_slug(client, db):
    author = make_user(db, "author4")
    admin = make_user(db, "root_admin4", role="admin")
    private = make_article(db, author, title="作者私密文", is_private=True)

    author_resp = client.get(
        f"/api/v1/articles/{private.slug}",
        headers=auth_header(login_token(client, author.username)),
    )
    assert author_resp.json()["code"] == 200
    assert author_resp.json()["data"]["title"] == "作者私密文"

    admin_resp = client.get(
        f"/api/v1/articles/{private.slug}",
        headers=auth_header(login_token(client, admin.username)),
    )
    assert admin_resp.json()["code"] == 200


def test_published_only_false_leak_is_gated_by_ownership(client, db):
    """published_only=false 本是后台入口：仅作者本人 / 管理员可用它看到自己的非公开文章"""
    author = make_user(db, "author5")
    stranger = make_user(db, "stranger5")
    private = make_article(db, author, title="私密", is_private=True)

    author_body = client.get(
        "/api/v1/articles",
        params={"published_only": "false", "author_id": author.id},
        headers=auth_header(login_token(client, author.username)),
    ).json()
    assert private.id in [a["id"] for a in author_body["data"]["list"]]

    stranger_body = client.get(
        "/api/v1/articles",
        params={"published_only": "false", "author_id": author.id},
        headers=auth_header(login_token(client, stranger.username)),
    ).json()
    assert private.id not in [a["id"] for a in stranger_body["data"]["list"]]

    admin_body = client.get(
        "/api/v1/articles",
        params={"published_only": "false"},
        headers=auth_header(login_token(client, make_user(db, "root_admin5", role="admin").username)),
    ).json()
    assert private.id in [a["id"] for a in admin_body["data"]["list"]]
