from fastapi import APIRouter, Depends, HTTPException
from app.auth.password import hash_password, validate_password_strength
from app.auth.dependencies import require_permission
from app.models import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.operation_log_service import log_operation

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("")
async def list_users(user: User = Depends(require_permission("admin"))):
    users = await User.all().order_by("id")
    return [{"id": u.id, "username": u.username, "display_name": u.display_name,
             "role": u.role, "permissions": u.permissions, "is_active": u.is_active} for u in users]


@router.post("")
async def create_user(data: UserCreate, user: User = Depends(require_permission("admin"))):
    validate_password_strength(data.password)
    if await User.filter(username=data.username).exists():
        raise HTTPException(status_code=400, detail="用户名已存在")
    new_user = await User.create(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name or data.username,
        role=data.role,
        permissions=data.permissions
    )
    await log_operation(user, "USER_CREATE", "USER", new_user.id,
        f"创建用户 {data.username}，角色 {data.role}")
    return {"id": new_user.id, "message": "创建成功"}


@router.put("/{user_id}")
async def update_user(user_id: int, data: UserUpdate, admin: User = Depends(require_permission("admin"))):
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if data.role is not None and user.id == admin.id and admin.role == "admin" and data.role != "admin":
        raise HTTPException(status_code=400, detail="不能降级自己的管理员角色")
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.role is not None:
        user.role = data.role
    if data.permissions is not None:
        user.permissions = data.permissions
    if data.password:
        validate_password_strength(data.password)
        user.password_hash = hash_password(data.password)
        user.must_change_password = True
        user.token_version += 1
    await user.save()
    await log_operation(admin, "UPDATE_USER", "USER", user.id, f"更新用户 {user.username}")
    return {"message": "更新成功"}


@router.post("/{user_id}/toggle")
async def toggle_user(user_id: int, admin: User = Depends(require_permission("admin"))):
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    user.is_active = not user.is_active
    if not user.is_active:
        user.token_version += 1
    await user.save()
    action_text = "启用" if user.is_active else "禁用"
    await log_operation(admin, "USER_TOGGLE", "USER", user.id,
        f"{action_text}用户 {user.username}")
    return {"message": "状态更新成功", "is_active": user.is_active}
