"""认证模块测试"""
import pytest
from app.auth.password import hash_password, verify_password, validate_password_strength
from fastapi import HTTPException


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("TestPass123")
        assert verify_password("TestPass123", hashed)
        assert not verify_password("WrongPass", hashed)

    def test_different_hashes(self):
        h1 = hash_password("TestPass123")
        h2 = hash_password("TestPass123")
        assert h1 != h2  # bcrypt 每次生成不同的 salt

    def test_password_strength_valid(self):
        # 不应该抛出异常
        validate_password_strength("Abc12345")

    def test_password_strength_too_short(self):
        with pytest.raises(HTTPException) as exc:
            validate_password_strength("Ab1")
        assert exc.value.status_code == 400

    def test_password_strength_no_digits(self):
        with pytest.raises(HTTPException) as exc:
            validate_password_strength("Abcdefgh")
        assert exc.value.status_code == 400

    def test_password_strength_no_letters(self):
        with pytest.raises(HTTPException) as exc:
            validate_password_strength("12345678")
        assert exc.value.status_code == 400
