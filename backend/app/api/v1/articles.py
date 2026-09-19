from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from app.core.database import get_db
from app.core.response import Result, PageResult, BusinessException
from app.api.deps import require_admin, get_optional_user, get_current_user
from app.models.article import Article
from app.models.tag import Tag
from app.models.article_tag import article_tags
from app.models.user import User
from app.models.article_like import ArticleLike
from app.models.favorite import Favorite
from app.schemas.article import ArticleCreate, ArticleUpdate, ArticleListItem, ArticleDetail
from app.ai_engine.rag_service import rag_service
from app.ai_engine.recommendation_service import record_search_query

router = APIRouter(prefix="/articles", tags=["文章管理 (Articles)"])


def update_realtime_top_articles(db: Session, limit: int = 3):
    """
    根据搜索热度 (search_hits) 与浏览量实时计算置顶精选博文，
    默认排名前 3 的文章自动标记为置顶 (is_top = True)，其余文章为 False。
    """
    try:
        top_articles = (
            db.query(Article.id)
            .filter(Article.is_published == True)
            .order_by(
                Article.search_hits.desc(),
                Article.views_count.desc(),
                Article.created_at.desc()
            )
            .limit(limit)
            .all()
        )
        top_ids = [r[0] for r in top_articles]
        if top_ids:
            db.query(Article).filter(Article.id.in_(top_ids)).update({"is_top": True}, synchronize_session=False)
            db.query(Article).filter(~Article.id.in_(top_ids)).update({"is_top": False}, synchronize_session=False)
            db.commit()
    except Exception:
        db.rollback()


@router.get("", response_model=Result[PageResult[ArticleListItem]], summary="分页获取文章列表")
def list_articles(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    published_only: bool = True,
    db: Session = Depends(get_db)
):
    # 首页默认状态下实时刷新置顶精选（排名前 3 的高搜索热度博文）
    if page == 1 and not keyword and not category_id and not tag_id:
        update_realtime_top_articles(db, limit=3)

    query = db.query(Article).options(
        joinedload(Article.category),
        joinedload(Article.tags),
        joinedload(Article.author)
    )

    if published_only:
        query = query.filter(Article.is_published == True)

    if category_id:
        query = query.filter(Article.category_id == category_id)

    if tag_id:
        query = query.join(Article.tags).filter(Tag.id == tag_id)

    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(or_(Article.title.like(kw), Article.summary.like(kw), Article.content.like(kw)))
        record_search_query(db, keyword, search_type="portal_search")
        # 实时累加命中文章的搜索热度
        matched_articles = query.all()
        if matched_articles:
            matched_ids = [a.id for a in matched_articles]
            db.query(Article).filter(Article.id.in_(matched_ids)).update(
                {Article.search_hits: Article.search_hits + 1},
                synchronize_session=False
            )
            db.commit()

    total = query.distinct().count()
    
    # 置顶文章优先，其次按创建时间倒序
    articles = (
        query.order_by(Article.is_top.desc(), Article.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    items = [ArticleListItem.model_validate(a) for a in articles]
    page_data = PageResult.create(items=items, total=total, page=page, size=size)
    return Result.success(data=page_data)


@router.get("/user/my-likes", summary="获取当前登录用户点赞的博文列表 (需登录)")
def get_my_liked_articles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    likes = (
        db.query(ArticleLike)
        .filter(ArticleLike.user_id == current_user.id)
        .order_by(ArticleLike.created_at.desc())
        .all()
    )
    items = []
    for l in likes:
        if l.article and l.article.is_published:
            items.append({
                "id": l.article.id,
                "title": l.article.title,
                "slug": l.article.slug,
                "summary": l.article.summary,
                "category_name": l.article.category.name if l.article.category else None,
                "views_count": l.article.views_count,
                "likes_count": l.article.likes_count,
                "created_at": l.article.created_at,
                "liked_at": l.created_at
            })
    return Result.success(data=items)


@router.get("/user/my-created", summary="获取当前登录用户创作的博文列表 (需登录)")
def get_my_created_articles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    articles = (
        db.query(Article)
        .filter(Article.author_id == current_user.id)
        .order_by(Article.created_at.desc())
        .all()
    )
    items = []
    for a in articles:
        items.append({
            "id": a.id,
            "title": a.title,
            "slug": a.slug,
            "summary": a.summary,
            "category_name": a.category.name if a.category else None,
            "is_published": a.is_published,
            "views_count": a.views_count,
            "likes_count": a.likes_count,
            "created_at": a.created_at,
            "vector_status": a.vector_status
        })
    return Result.success(data=items)


@router.get("/{id_or_slug}", response_model=Result[ArticleDetail], summary="根据ID或别名获取文章详情")
def get_article_detail(
    id_or_slug: str,
    db: Session = Depends(get_db)
):
    query = db.query(Article).options(
        joinedload(Article.category),
        joinedload(Article.tags),
        joinedload(Article.author)
    )
    if id_or_slug.isdigit():
        article = query.filter(Article.id == int(id_or_slug)).first()
    else:
        article = query.filter(Article.slug == id_or_slug).first()

    if not article:
        raise BusinessException("博文不存在或已删除", code=404)

    # 浏览量自增
    article.views_count += 1
    db.commit()
    db.refresh(article)

    return Result.success(data=ArticleDetail.model_validate(article))


@router.post("", response_model=Result[ArticleDetail], summary="创建文章并自动同步构建 RAG 向量切片 (博主用户)")
def create_article(
    payload: ArticleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    exist = db.query(Article).filter(Article.slug == payload.slug).first()
    if exist:
        raise BusinessException("文章别名 slug 已存在，请换一个唯一英文或拼音标识", code=400)

    article_data = payload.model_dump(exclude={"tag_ids"})
    # 新建博文点赞数初始严格为 0
    article_data["likes_count"] = 0
    article = Article(**article_data, author_id=current_user.id)

    # 关联标签
    if payload.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(payload.tag_ids)).all()
        article.tags = tags

    db.add(article)
    db.commit()
    db.refresh(article)

    # 核心步骤：触发自动化文本分块与特征向量化写入 RAG 知识库
    try:
        rag_service.index_article(db, article.id)
    except Exception as e:
        article.vector_status = "failed"
        db.commit()

    db.refresh(article)
    return Result.success(data=ArticleDetail.model_validate(article), message="文章发布并成功录入 AI 知识库")


@router.put("/{id}", response_model=Result[ArticleDetail], summary="更新文章与重新同步向量索引 (作者或管理员)")
def update_article(
    id: int,
    payload: ArticleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    article = db.query(Article).filter(Article.id == id).first()
    if not article:
        raise BusinessException("文章不存在", code=404)

    # 仅作者本人或系统管理员有权修改文章
    if article.author_id != current_user.id and current_user.role != "admin":
        raise BusinessException("您只能修改自己创作的文章", code=403)

    update_dict = payload.model_dump(exclude_unset=True)
    tag_ids = update_dict.pop("tag_ids", None)

    for field, val in update_dict.items():
        setattr(article, field, val)

    if tag_ids is not None:
        tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
        article.tags = tags

    db.commit()
    db.refresh(article)

    # 重构向量切片
    try:
        rag_service.index_article(db, article.id)
    except Exception:
        article.vector_status = "failed"
        db.commit()

    db.refresh(article)
    return Result.success(data=ArticleDetail.model_validate(article), message="文章更新并重新建立向量索引")


@router.delete("/{id}", response_model=Result[None], summary="删除文章 (作者或管理员)")
def delete_article(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    article = db.query(Article).filter(Article.id == id).first()
    if not article:
        raise BusinessException("文章不存在", code=404)

    # 仅作者本人或系统管理员有权删除文章
    if article.author_id != current_user.id and current_user.role != "admin":
        raise BusinessException("您只能删除自己创作的文章", code=403)

    db.delete(article)
    db.commit()
    return Result.success(message="文章及关联向量切片已彻底删除")


@router.post("/{id}/like", summary="文章点赞/取消点赞 (需登录)")
def like_article(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    article = db.query(Article).filter(Article.id == id).first()
    if not article:
        raise BusinessException("文章不存在", code=404)

    existing = db.query(ArticleLike).filter(
        ArticleLike.user_id == current_user.id,
        ArticleLike.article_id == article.id
    ).first()

    if existing:
        db.delete(existing)
        article.likes_count = max(0, article.likes_count - 1)
        db.commit()
        return Result.success(data={"liked": False, "likes_count": article.likes_count}, message="已取消点赞")
    else:
        new_like = ArticleLike(user_id=current_user.id, article_id=article.id)
        db.add(new_like)
        article.likes_count += 1
        db.commit()
        return Result.success(data={"liked": True, "likes_count": article.likes_count}, message="点赞成功")


@router.get("/{id}/interaction", summary="获取当前登录用户对文章的点赞与收藏状态")
def get_article_interaction(
    id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    article = db.query(Article).filter(Article.id == id).first()
    if not article:
        raise BusinessException("文章不存在", code=404)

    is_liked = False
    is_favorited = False
    if current_user:
        is_liked = bool(db.query(ArticleLike).filter(
            ArticleLike.user_id == current_user.id,
            ArticleLike.article_id == article.id
        ).first())
        is_favorited = bool(db.query(Favorite).filter(
            Favorite.user_id == current_user.id,
            Favorite.article_id == article.id
        ).first())

    return Result.success(data={
        "is_liked": is_liked,
        "is_favorited": is_favorited,
        "likes_count": article.likes_count
    })


@router.post("/{id}/reindex", response_model=Result[int], summary="手动触发该文章向量索引重构 (管理员)")
def reindex_article(
    id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin)
):
    chunks_count = rag_service.index_article(db, id)
    return Result.success(data=chunks_count, message=f"已成功切分并建立 {chunks_count} 个向量知识切片")
