from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.response import Result, BusinessException
from app.api.deps import require_admin
from app.models.category import Category
from app.models.article import Article
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryOut

router = APIRouter(prefix="/categories", tags=["分类管理 (Categories)"])


@router.get("", response_model=Result[List[CategoryOut]], summary="获取所有分类列表")
def list_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).order_by(Category.sort_order.asc(), Category.id.asc()).all()
    # 统计每个分类下的文章数
    counts = dict(
        db.query(Article.category_id, func.count(Article.id))
        .filter(Article.is_published == True)
        .group_by(Article.category_id)
        .all()
    )
    result = []
    for c in categories:
        item = CategoryOut.model_validate(c)
        item.article_count = counts.get(c.id, 0)
        result.append(item)
    return Result.success(data=result)


@router.post("", response_model=Result[CategoryOut], summary="创建分类 (管理员)")
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    exists = db.query(Category).filter((Category.name == payload.name) | (Category.slug == payload.slug)).first()
    if exists:
        raise BusinessException("分类名称或别名 slug 已存在", code=400)

    cat = Category(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return Result.success(data=CategoryOut.model_validate(cat), message="分类创建成功")


@router.put("/{id}", response_model=Result[CategoryOut], summary="更新分类 (管理员)")
def update_category(
    id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    cat = db.query(Category).filter(Category.id == id).first()
    if not cat:
        raise BusinessException("分类不存在", code=404)

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(cat, field, val)

    db.commit()
    db.refresh(cat)
    return Result.success(data=CategoryOut.model_validate(cat), message="更新成功")


@router.delete("/{id}", response_model=Result[None], summary="删除分类 (管理员)")
def delete_category(
    id: int,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    cat = db.query(Category).filter(Category.id == id).first()
    if not cat:
        raise BusinessException("分类不存在", code=404)

    db.delete(cat)
    db.commit()
    return Result.success(message="删除成功")
