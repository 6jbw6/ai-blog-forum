from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.response import Result, BusinessException
from app.api.deps import require_admin
from app.models.tag import Tag
from app.models.article_tag import article_tags
from app.schemas.tag import TagCreate, TagUpdate, TagOut
import secrets

router = APIRouter(prefix="/tags", tags=["标签管理 (Tags)"])

DEFAULT_TAG_COLOR = "#059669"
# 「一个名称只能有一种颜色」：同名标签（忽略大小写与首尾空格）一律拒绝新建/改名
NAME_TAKEN_MESSAGE = "标签名称已存在，同一名称只能保留一种颜色"


def _normalize_name(name: str) -> str:
    """名称归一化：去首尾空白并把内部连续空白压成一个空格（与唯一索引口径对齐）"""
    return " ".join((name or "").split())


def _name_taken(db: Session, name: str, exclude_id: Optional[int] = None) -> bool:
    """按「空白归一化 + 忽略大小写」判断重名，避免同一名称出现两种颜色"""
    query = db.query(Tag.id).filter(func.lower(Tag.name) == name.lower())
    if exclude_id is not None:
        query = query.filter(Tag.id != exclude_id)
    return db.query(query.exists()).scalar()


def _generate_unique_slug(db: Session) -> str:
    """标签别名已无业务消费方（检索/路由均用 name 与 id），由后端自动生成唯一占位值"""
    while True:
        candidate = f"tag-{secrets.token_hex(4)}"
        if not db.query(Tag).filter(Tag.slug == candidate).first():
            return candidate


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
    name = _normalize_name(payload.name)
    if not name:
        raise BusinessException("标签名称不能为空", code=400)
    if _name_taken(db, name):
        raise BusinessException(NAME_TAKEN_MESSAGE, code=400)

    tag = Tag(name=name, color=(payload.color or "").strip().upper() or DEFAULT_TAG_COLOR)
    tag.slug = _generate_unique_slug(db)
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

    updates = payload.model_dump(exclude_unset=True)
    if updates.get("name") is not None:
        name = _normalize_name(updates["name"])
        if not name:
            raise BusinessException("标签名称不能为空", code=400)
        # 改名同样要防重名：否则会撞 tags.name 唯一索引，抛 IntegrityError 变成 500
        if _name_taken(db, name, exclude_id=tag.id):
            raise BusinessException(NAME_TAKEN_MESSAGE, code=400)
        updates["name"] = name
    if updates.get("color") is not None:
        updates["color"] = updates["color"].strip().upper()

    for field, val in updates.items():
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
