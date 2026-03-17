import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from tortoise.expressions import F
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
_login_lock = asyncio.Lock()


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
    # Rate limiting relies on socket IP only; X-Forwarded-For is client-controlled and trivially spoofed.
    # Deploy behind nginx (with set_real_ip_from) so request.client.host reflects the real client IP.
    client_ip = request.client.host if request.client else "unknown"
    now_ts = datetime.now().timestamp()
    # Hold the lock across the entire check-verify-increment sequence to close the
    # race window where concurrent requests could bypass the rate limit.
    # This serializes login attempts but is acceptable for a 5-attempt limit.
    async with _login_lock:
        _cleanup_login_attempts()
        attempts = _login_attempts.get(client_ip, [])
        attempts = [t for t in attempts if now_ts - t < LOGIN_WINDOW_SECONDS]
        if len(attempts) >= LOGIN_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail=f"登录尝试过于频繁，请{LOGIN_WINDOW_SECONDS // 60}分钟后再试")
        # Query user inside lock scope
        user = await User.filter(username=data.username, is_active=True).first()
        if not user or not verify_password(data.password, user.password_hash):
            attempts.append(now_ts)
            _login_attempts[client_ip] = attempts
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        # Success - clear attempts
        _login_attempts.pop(client_ip, None)
    # 透明迁移：旧 pbkdf2_sha256 哈希自动升级为 bcrypt
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(data.password)
        await user.save()
    await log_operation(user, "LOGIN_SUCCESS", "USER", user.id, f"登录成功，IP: {client_ip}")
    token = create_access_token({"user_id": user.id, "username": user.username, "role": user.role, "token_version": user.token_version})
    # 检查密码是否过期
    # password_changed_at 为 NULL 表示迁移前的老用户，不视为过期（从首次修改密码开始计算）
    from app.config import PASSWORD_EXPIRY_DAYS
    password_expired = False
    if PASSWORD_EXPIRY_DAYS > 0 and user.password_changed_at is not None:
        if datetime.now(timezone.utc) - user.password_changed_at > timedelta(days=PASSWORD_EXPIRY_DAYS):
            password_expired = True
    resp = {
        "access_token": token,
        "must_change_password": user.must_change_password,
        "user": {
            "id": user.id, "username": user.username,
            "display_name": user.display_name, "role": user.role,
            "permissions": user.permissions or []
        }
    }
    if password_expired:
        resp["password_expired"] = True
    return resp


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
    await user.save()
    # 更新密码修改时间 + 原子递增 token_version
    await User.filter(id=user.id).update(
        password_changed_at=datetime.now(timezone.utc),
        token_version=F('token_version') + 1,
    )
    # Re-fetch to get the updated token_version for creating the new JWT token
    user = await User.get(id=user.id)
    await log_operation(user, "PASSWORD_CHANGE", "USER", user.id, f"用户 {user.username} 修改密码")
    new_token = create_access_token({"user_id": user.id, "username": user.username, "role": user.role, "token_version": user.token_version})
    return {
        "message": "密码修改成功",
        "access_token": new_token,
        "user": {
            "id": user.id, "username": user.username,
            "display_name": user.display_name, "role": user.role,
            "permissions": user.permissions or []
        }
    }


@router.post("/logout")
async def logout(user: User = Depends(get_current_user_allow_password_change)):
    # Atomic increment of token_version to invalidate all existing tokens
    await User.filter(id=user.id).update(token_version=F('token_version') + 1)
    return {"message": "已登出"}
