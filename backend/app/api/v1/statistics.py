from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.response import Result
from app.api.deps import require_admin
from app.models.article import Article
from app.models.category import Category
from app.models.comment import Comment
from app.models.article_chunk import ArticleChunk

router = APIRouter(prefix="/statistics", tags=["数据看板与大屏 (Statistics)"])


@router.get("/dashboard", summary="后台运营数据看板大屏统计 (管理员)")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    # 核心指标统计
    total_articles = db.query(func.count(Article.id)).scalar() or 0
    published_articles = db.query(func.count(Article.id)).filter(Article.is_published == True).scalar() or 0
    draft_articles = total_articles - published_articles
    
    total_views = db.query(func.sum(Article.views_count)).scalar() or 0
    total_likes = db.query(func.sum(Article.likes_count)).scalar() or 0
    total_comments = db.query(func.count(Comment.id)).scalar() or 0
    
    # 核心 RAG 知识库切片容量
    total_chunks = db.query(func.count(ArticleChunk.id)).scalar() or 0

    # 分类分布统计 (供前端 ECharts / 环形图渲染)
    category_counts = (
        db.query(Category.name, func.count(Article.id))
        .join(Article, Article.category_id == Category.id)
        .group_by(Category.name)
        .all()
    )
    category_distribution = [{"name": name, "value": count} for name, count in category_counts]

    # 最热门博文 Top 5
    top_articles = (
        db.query(Article.id, Article.title, Article.slug, Article.views_count, Article.likes_count)
        .filter(Article.is_published == True)
        .order_by(Article.views_count.desc())
        .limit(5)
        .all()
    )
    top_articles_list = [
        {"id": a.id, "title": a.title, "slug": a.slug, "views": a.views_count, "likes": a.likes_count}
        for a in top_articles
    ]

    return Result.success(data={
        "metrics": {
            "total_articles": total_articles,
            "published_articles": published_articles,
            "draft_articles": draft_articles,
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "rag_chunks_indexed": total_chunks,
        },
        "category_distribution": category_distribution,
        "top_articles": top_articles_list
    })
