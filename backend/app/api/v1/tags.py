from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.response import Result, BusinessException
from app.api.deps import require_admin
from app.models.tag import Tag
from app.models.article_tag import article_tags
from app.schemas.tag import TagCreate, TagUpdate, TagOut

router = APIRouter(prefix="/tags", tags=["标签管理 (Tags)"])


@router.get("", response_model=Result[List[TagOut]], summary="获取所有标签列表")
def list_tags(db: Session = Depends(get_db)):
    tags = db.query(Tag).order_by(Tag.id.asc()).all()
    # 统计关联文章数
    counts = dict(
        db.query(article_tags.c.tag_id, func.count(article_tags.c.article_id))
        .group_by(article_tags.c.tag_id)
        .all()
    )
    result = []
    for t in tags:
        item = TagOut.model_validate(t)
        item.article_count = counts.get(t.id, 0)
        result.append(item)
    return Result.success(data=result)


@router.post("", response_model=Result[TagOut], summary="创建标签 (管理员)")
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    exists = db.query(Tag).filter((Tag.name == payload.name) | (Tag.slug == payload.slug)).first()
    if exists:
        raise BusinessException("标签名称或别名 slug 已存在", code=400)

    tag = Tag(**payload.model_dump())
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return Result.success(data=TagOut.model_validate(tag), message="标签创建成功")


@router.put("/{id}", response_model=Result[TagOut], summary="更新标签 (管理员)")
def update_tag(
    id: int,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    tag = db.query(Tag).filter(Tag.id == id).first()
    if not tag:
        raise BusinessException("标签不存在", code=404)

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(tag, field, val)

    db.commit()
    db.refresh(tag)
    return Result.success(data=TagOut.model_validate(tag), message="更新成功")


@router.delete("/{id}", response_model=Result[None], summary="删除标签 (管理员)")
def delete_tag(
    id: int,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin)
):
    tag = db.query(Tag).filter(Tag.id == id).first()
    if not tag:
        raise BusinessException("标签不存在", code=404)

    db.delete(tag)
    db.commit()
    return Result.success(message="删除成功")
