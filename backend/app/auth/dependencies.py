"""认证依赖"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.jwt import verify_token, TokenExpiredError, TokenInvalidError
from app.models.user import User

security = HTTPBearer(auto_error=False)


async def _authenticate_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证Token并返回用户，不检查must_change_password"""
    if not credentials:
        raise HTTPException(status_code=401, detail="未授权")
    try:
        payload = verify_token(credentials.credentials)
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token已过期，请重新登录")
    except TokenInvalidError:
        raise HTTPException(status_code=401, detail="Token无效")
    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Token无效")
    user = await User.filter(id=user_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    token_ver = payload.get("token_version", 0)
    if token_ver != user.token_version:
        raise HTTPException(status_code=401, detail="Token已失效，请重新登录")
    return user


async def get_current_user(user: User = Depends(_authenticate_user)):
    """获取当前用户，强制检查must_change_password"""
    if user.must_change_password:
        raise HTTPException(
            status_code=403,
            detail="请先修改初始密码"
        )
    return user


async def get_current_user_allow_password_change(user: User = Depends(_authenticate_user)):
    """获取当前用户，跳过must_change_password检查（仅用于修改密码和获取用户信息）"""
    return user


def require_permission(*permissions):
    """要求用户拥有指定权限之一（多个参数为 OR 关系）"""
    async def checker(user: User = Depends(get_current_user)):
        if any(user.has_permission(p) for p in permissions):
            return user
        raise HTTPException(status_code=403, detail=f"缺少权限: {' 或 '.join(permissions)}")
    return checker
