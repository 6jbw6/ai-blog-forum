from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.response import Result, BusinessException
from app.api.deps import get_current_user
from app.models.user import User
from app.models.article import Article
from app.models.favorite import Favorite
from app.schemas.favorite import FavoriteToggleResponse, FavoriteArticleItem

router = APIRouter(prefix="/favorites", tags=["用户收藏 (Favorites)"])


@router.post("/toggle/{article_id}", response_model=Result[FavoriteToggleResponse], summary="切换博文收藏状态 (需登录)")
def toggle_favorite(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise BusinessException("文章不存在", code=404)

    existing = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.article_id == article_id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        count = db.query(Favorite).filter(Favorite.article_id == article_id).count()
        return Result.success(data=FavoriteToggleResponse(is_favorited=False, favorites_count=count), message="已取消收藏")
    else:
        fav = Favorite(user_id=current_user.id, article_id=article_id)
        db.add(fav)
        db.commit()
        count = db.query(Favorite).filter(Favorite.article_id == article_id).count()
        return Result.success(data=FavoriteToggleResponse(is_favorited=True, favorites_count=count), message="已收藏")


@router.get("/my", response_model=Result[List[FavoriteArticleItem]], summary="获取当前登录用户的收藏博文列表 (需登录)")
def get_my_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    records = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )

    items = []
    for r in records:
        if r.article and r.article.is_published:
            items.append(FavoriteArticleItem(
                id=r.article.id,
                title=r.article.title,
                slug=r.article.slug,
                summary=r.article.summary,
                category_name=r.article.category.name if r.article.category else None,
                cover_image=r.article.cover_image,
                views_count=r.article.views_count,
                likes_count=r.article.likes_count,
                created_at=r.article.created_at,
                favorited_at=r.created_at
            ))

    return Result.success(data=items)
