import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, hash_password, create_access_token
from app.core.response import Result, BusinessException
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserLogin, UserRegister, UserOut, TokenOut, UserProfileUpdate

router = APIRouter(prefix="/auth", tags=["认证鉴权"])

AVATAR_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static" / "avatars"
AVATAR_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
AVATAR_MAX_SIZE = 2 * 1024 * 1024


@router.post("/login", response_model=Result[TokenOut], summary="用户与管理员登录")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    if login_data.username.lower() == "admin":
        user = db.query(User).filter((User.username == "admin") | (User.role == "admin")).first()
    else:
        user = db.query(User).filter(
            (User.username == login_data.username)
            | (User.email == login_data.username)
            | (User.nickname == login_data.username)
        ).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise BusinessException("用户名或密码错误", code=400)

    if not user.is_active:
        raise BusinessException("该账号已被禁用", code=403)

    token = create_access_token(data={"sub": user.username, "role": user.role, "id": user.id})
    return Result.success(data=TokenOut(access_token=token, user=UserOut.model_validate(user)))


@router.post("/register", response_model=Result[UserOut], summary="读者注册")
def register(reg_data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        (User.username == reg_data.username) | (User.email == reg_data.email)
    ).first()
    if existing:
        raise BusinessException("用户名或电子邮箱已存在", code=400)

    new_user = User(
        username=reg_data.username,
        email=reg_data.email,
        password_hash=hash_password(reg_data.password),
        nickname=reg_data.nickname or reg_data.username,
        bio=reg_data.bio or "",
        role="reader"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return Result.success(data=UserOut.model_validate(new_user), message="注册成功")


@router.get("/me", response_model=Result[UserOut], summary="获取当前登录用户信息")
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return Result.success(data=UserOut.model_validate(current_user))


@router.put("/me", response_model=Result[UserOut], summary="更新当前登录用户个人资料")
def update_current_user_profile(
    profile_data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if profile_data.username is not None and profile_data.username.strip():
        new_username = profile_data.username.strip()
        existing = db.query(User).filter(User.username == new_username, User.id != current_user.id).first()
        if existing:
            raise BusinessException("该用户名已被占用", code=400)
        current_user.username = new_username
        if not profile_data.nickname:
            current_user.nickname = new_username

    if profile_data.nickname is not None and profile_data.nickname.strip():
        current_user.nickname = profile_data.nickname.strip()
    if profile_data.bio is not None:
        current_user.bio = profile_data.bio.strip()
    if profile_data.avatar is not None:
        current_user.avatar = profile_data.avatar.strip()
    if profile_data.password and profile_data.password.strip():
        current_user.password_hash = hash_password(profile_data.password.strip())
    
    db.commit()
    db.refresh(current_user)
    return Result.success(data=UserOut.model_validate(current_user), message="个人资料已成功更新")


@router.post("/avatar", response_model=Result[UserOut], summary="上传个人头像图片")
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ext = AVATAR_ALLOWED_TYPES.get(file.content_type or "")
    if not ext:
        raise BusinessException("仅支持 JPG、PNG、WebP、GIF 格式的头像图片", code=400)

    content = await file.read()
    if len(content) > AVATAR_MAX_SIZE:
        raise BusinessException("头像图片不能超过 2MB", code=400)
    if not content:
        raise BusinessException("头像图片内容为空", code=400)

    filename = f"{current_user.id}_{uuid.uuid4().hex}{ext}"
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    (AVATAR_DIR / filename).write_bytes(content)

    current_user.avatar = f"/static/avatars/{filename}"
    db.commit()
    db.refresh(current_user)
    return Result.success(data=UserOut.model_validate(current_user), message="头像更新成功")
