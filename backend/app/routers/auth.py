from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from app.auth.jwt import create_access_token
from app.auth.dependencies import get_current_user, get_current_user_allow_password_change
from app.models import User
from app.schemas.auth import LoginRequest, ChangePasswordRequest
from app.config import LOGIN_MAX_ATTEMPTS, LOGIN_WINDOW_SECONDS
from app.services.operation_log_service import log_operation
from app.auth.password import hash_password, verify_password, needs_rehash, validate_password_strength

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 登录尝试记录: {ip: [timestamp, ...]}
_login_attempts = {}
_last_cleanup = 0


def _cleanup_login_attempts():
    """定期清理过期的登录尝试记录，防止内存无限增长"""
    global _last_cleanup
    now_ts = datetime.now().timestamp()
    # 每 60 秒最多清理一次
    if now_ts - _last_cleanup < 60:
        return
    _last_cleanup = now_ts
    expired_ips = [
        ip for ip, atts in _login_attempts.items()
        if not atts or now_ts - max(atts) > LOGIN_WINDOW_SECONDS
    ]
    for ip in expired_ips:
        del _login_attempts[ip]


@router.post("/login")
async def login(data: LoginRequest, request: Request):
    forwarded = request.headers.get("x-forwarded-for")
    # Take the last IP in X-Forwarded-For (added by the last trusted proxy) to avoid client spoofing
    client_ip = forwarded.split(",")[-1].strip() if forwarded else (request.client.host if request.client else "unknown")
    now_ts = datetime.now().timestamp()
    _cleanup_login_attempts()
    attempts = _login_attempts.get(client_ip, [])
    attempts = [t for t in attempts if now_ts - t < LOGIN_WINDOW_SECONDS]
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail=f"登录尝试过于频繁，请{LOGIN_WINDOW_SECONDS // 60}分钟后再试")
    user = await User.filter(username=data.username, is_active=True).first()
    if not user or not verify_password(data.password, user.password_hash):
        attempts.append(now_ts)
        _login_attempts[client_ip] = attempts
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    _login_attempts.pop(client_ip, None)
    # 透明迁移：旧 pbkdf2_sha256 哈希自动升级为 bcrypt
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(data.password)
        await user.save()
    await log_operation(user, "LOGIN_SUCCESS", "USER", user.id, f"登录成功，IP: {client_ip}")
    token = create_access_token({"user_id": user.id, "username": user.username, "role": user.role, "token_version": user.token_version})
    return {
        "access_token": token,
        "must_change_password": user.must_change_password,
        "user": {
            "id": user.id, "username": user.username,
            "display_name": user.display_name, "role": user.role,
            "permissions": user.permissions or []
        }
    }


@router.get("/me")
async def get_me(user: User = Depends(get_current_user_allow_password_change)):
    return {
        "id": user.id, "username": user.username,
        "display_name": user.display_name, "role": user.role,
        "permissions": user.permissions or [],
        "must_change_password": user.must_change_password,
    }


@router.post("/change-password")
async def change_password(data: ChangePasswordRequest, user: User = Depends(get_current_user_allow_password_change)):
    validate_password_strength(data.new_password)
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    user.token_version += 1
    await user.save()
    await log_operation(user, "PASSWORD_CHANGE", "USER", user.id, f"用户 {user.username} 修改密码")
    return {"message": "密码修改成功"}
