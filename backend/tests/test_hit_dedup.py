"""浏览量 / 搜索热度持久化去重回归。

`views_count` 与 `search_hits` 决定首页「置顶精选」排名，此前每请求无条件 +1。
现在计数落在 article_hits 台账上，按「每访客每篇文章每天一次」去重，
作者本人的访问与搜索一律不计。
"""
from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy import func

from app.core.hit_tracking import KIND_SEARCH, KIND_VIEW, prune_old_hits, viewer_key_of
from app.models.article import Article
from app.models.article_hit import ArticleHit
from tests.conftest import auth_header, login_token, make_article, make_user


def _total_hits(db, kind=None):
    q = db.query(func.count(ArticleHit.id))
    if kind:
        q = q.filter(ArticleHit.kind == kind)
    return q.scalar() or 0


# ---------- 浏览量 ----------

def test_repeat_views_from_same_visitor_count_once(client, db):
    author = make_user(db, "author_hd1")
    art = make_article(db, author)
    for _ in range(5):
        client.get(f"/api/v1/articles/{art.slug}")
    db.refresh(art)
    assert art.views_count == 1, "同一访客反复刷新详情页只算一次浏览"
    assert _total_hits(db, KIND_VIEW) == 1


def test_author_view_never_counts(client, db):
    author = make_user(db, "author_hd2")
    art = make_article(db, author)
    token = login_token(client, "author_hd2")
    for _ in range(5):
        client.get(f"/api/v1/articles/{art.slug}", headers=auth_header(token))
    db.refresh(art)
    assert art.views_count == 0, "作者刷自己的文章不得累加浏览量"
    assert _total_hits(db, KIND_VIEW) == 0


def test_distinct_visitors_each_count(client, db):
    author = make_user(db, "author_hd3")
    art = make_article(db, author)
    for i in range(3):
        name = f"reader_hd3_{i}"
        make_user(db, name)
        client.get(f"/api/v1/articles/{art.slug}",
                   headers=auth_header(login_token(client, name)))
    db.refresh(art)
    assert art.views_count == 3, "不同访客各自计一次"


def test_dedup_is_persisted_not_in_process_memory(client, db):
    """去重依据在库里：进程内限流计数被清空后，重复浏览依然不会被重复计入"""
    from app.core.rate_limit import hit_limiter

    author = make_user(db, "author_hd4")
    art = make_article(db, author)
    client.get(f"/api/v1/articles/{art.slug}")
    hit_limiter.reset()
    client.get(f"/api/v1/articles/{art.slug}")
    db.refresh(art)
    assert art.views_count == 1, "清空进程内计数不得让同一访客重复计数"


# ---------- 搜索热度 ----------

def test_repeat_search_from_same_visitor_counts_once(client, db):
    author = make_user(db, "author_hd5")
    make_article(db, author, title="LoRA 微调实战", content="LoRA 微调显存占用与量化策略")
    for _ in range(8):
        client.get("/api/v1/articles?keyword=LoRA")
    assert (db.query(func.sum(Article.search_hits)).scalar() or 0) == 1
    assert _total_hits(db, KIND_SEARCH) == 1


def test_own_search_does_not_boost_own_article(client, db):
    author = make_user(db, "author_hd6")
    make_article(db, author, title="LoRA 微调实战", content="LoRA 微调显存占用与量化策略")
    token = login_token(client, "author_hd6")
    for _ in range(5):
        client.get("/api/v1/articles?keyword=LoRA", headers=auth_header(token))
    assert (db.query(func.sum(Article.search_hits)).scalar() or 0) == 0, \
        "作者搜自己的文章不得给自己涨热度"

    # 对照组：换个人搜同一关键词必须照常累加，否则上面那个 0 只能说明功能根本没跑
    make_user(db, "reader_hd6")
    client.get("/api/v1/articles?keyword=LoRA",
               headers=auth_header(login_token(client, "reader_hd6")))
    assert (db.query(func.sum(Article.search_hits)).scalar() or 0) == 1


def test_distinct_searchers_each_count(client, db):
    author = make_user(db, "author_hd7")
    make_article(db, author, title="向量检索原理", content="多路召回与重排策略")
    for i in range(3):
        name = f"reader_hd7_{i}"
        make_user(db, name)
        client.get("/api/v1/articles?keyword=向量检索",
                   headers=auth_header(login_token(client, name)))
    assert (db.query(func.sum(Article.search_hits)).scalar() or 0) == 3


# ---------- 台账本身 ----------

def test_viewer_key_hides_raw_ip(client, db):
    """访客 IP 不明文落库：台账要留 30 天，存明文等于攒一份访客行踪记录"""
    author = make_user(db, "author_hd8")
    art = make_article(db, author)
    client.get(f"/api/v1/articles/{art.slug}")

    row = db.query(ArticleHit).filter(ArticleHit.kind == KIND_VIEW).one()
    assert row.viewer_key.startswith("ip:")
    assert "testclient" not in row.viewer_key, "原始 IP 不得出现在台账里"
    assert len(row.viewer_key) > len("ip:") + 16, "应当是哈希而非截断的原文"


def test_logged_in_viewer_key_is_account_scoped(client, db):
    author = make_user(db, "author_hd9")
    art = make_article(db, author)
    reader = make_user(db, "reader_hd9")
    token = login_token(client, "reader_hd9")
    client.get(f"/api/v1/articles/{art.slug}", headers=auth_header(token))

    row = db.query(ArticleHit).filter(ArticleHit.kind == KIND_VIEW).one()
    assert row.viewer_key == f"u:{reader.id}", "登录访客按账号标识，换设备仍算同一人"


def test_prune_removes_only_expired_rows(db):
    author = make_user(db, "author_hd10")
    art = make_article(db, author)
    stale = ArticleHit(article_id=art.id, kind=KIND_VIEW, viewer_key="u:999",
                       day_bucket=20200101, created_at=datetime.utcnow() - timedelta(days=90))
    fresh = ArticleHit(article_id=art.id, kind=KIND_VIEW, viewer_key="u:998",
                       day_bucket=20200101, created_at=datetime.utcnow())
    db.add_all([stale, fresh])
    db.commit()

    deleted = prune_old_hits(db)
    assert deleted == 1
    left = {r.viewer_key for r in db.query(ArticleHit).all()}
    assert left == {"u:998"}, "只清过期行，近期台账必须保留（否则去重失效）"


def test_viewer_key_of_is_stable_for_same_visitor(db):
    """同一个请求上下文里多次取值必须得到同一标识，否则去重形同虚设"""
    reader = make_user(db, "reader_hd11")

    scope = {"type": "http", "headers": [], "client": ("203.0.113.7", 1234)}
    req = Request(scope)
    anon_a = viewer_key_of(req, None)
    assert anon_a == viewer_key_of(req, None)
    assert anon_a != viewer_key_of(req, reader)
    assert viewer_key_of(req, reader) == f"u:{reader.id}"
