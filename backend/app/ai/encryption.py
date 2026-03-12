"""API Key 加密/解密工具 — Fernet 对称加密"""
from __future__ import annotations
import base64
import hashlib
import os
from cryptography.fernet import Fernet, InvalidToken
from app.logger import get_logger

logger = get_logger("ai.encryption")


def _get_fernet() -> Fernet:
    """从环境变量派生 Fernet 密钥（32 字节 base64），惰性读取"""
    secret = os.environ.get("API_KEYS_ENCRYPTION_SECRET", "")
    if not secret:
        raise RuntimeError("API_KEYS_ENCRYPTION_SECRET 环境变量未设置")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_value(plaintext: str | None) -> str:
    """加密明文，返回 base64 密文字符串"""
    if not plaintext:
        return ""
    try:
        return _get_fernet().encrypt(plaintext.encode()).decode()
    except Exception:
        logger.error("加密失败")
        return ""


def decrypt_value(ciphertext: str | None) -> str | None:
    """解密密文，返回明文。解密失败返回 None"""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        logger.warning("解密失败，可能密钥已变更")
        return None


def mask_key(key: str | None) -> str:
    """脱敏显示 API Key: sk-abc***"""
    if not key:
        return ""
    visible = min(len(key) - 1, 6)
    return key[:visible] + "***"
