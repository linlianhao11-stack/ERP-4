"""加密工具测试"""
from __future__ import annotations
import os
import pytest

os.environ.setdefault("API_KEYS_ENCRYPTION_SECRET", "test-secret-key-for-unit-tests-only")

from app.ai.encryption import encrypt_value, decrypt_value, mask_key


class TestEncryption:
    def test_roundtrip(self):
        original = "sk-abc123xyz"
        encrypted = encrypt_value(original)
        assert encrypted != original
        assert decrypt_value(encrypted) == original

    def test_empty_string(self):
        assert encrypt_value("") == ""
        assert decrypt_value("") == ""

    def test_none_value(self):
        assert encrypt_value(None) == ""
        assert decrypt_value(None) == ""

    def test_different_encryptions_same_input(self):
        """Fernet 每次加密结果不同（包含时间戳和 IV）"""
        a = encrypt_value("same")
        b = encrypt_value("same")
        assert a != b
        assert decrypt_value(a) == decrypt_value(b) == "same"

    def test_invalid_ciphertext(self):
        assert decrypt_value("not-valid-base64!") is None

    def test_mask_key_short(self):
        assert mask_key("sk-ab") == "sk-a***"

    def test_mask_key_long(self):
        assert mask_key("sk-abcdefghijklmnop") == "sk-abc***"

    def test_mask_key_empty(self):
        assert mask_key("") == ""
        assert mask_key(None) == ""
