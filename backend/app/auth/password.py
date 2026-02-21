"""密码哈希工具 — 使用 bcrypt，兼容旧的 pbkdf2_sha256 哈希"""
from passlib.context import CryptContext

# bcrypt 为首选，pbkdf2_sha256 标记为 deprecated（可验证但不再用于新哈希）
pwd_context = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], default="bcrypt", deprecated=["pbkdf2_sha256"])


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def needs_rehash(hashed: str) -> bool:
    """检查是否需要重新哈希（从旧算法迁移到 bcrypt）"""
    return pwd_context.needs_update(hashed)


def validate_password_strength(password: str) -> None:
    """校验密码强度，不通过则抛出 HTTPException"""
    from fastapi import HTTPException
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于6位")
    if not any(c.isdigit() for c in password) or not any(c.isalpha() for c in password):
        raise HTTPException(status_code=400, detail="密码必须包含字母和数字")
