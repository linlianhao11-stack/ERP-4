"""限流器测试"""
from __future__ import annotations
import time
import pytest
from app.ai.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_allows_under_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.allow("user1")

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.allow("user1")
        assert limiter.allow("user1")
        assert not limiter.allow("user1")

    def test_independent_keys(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.allow("user1")
        assert limiter.allow("user2")
        assert not limiter.allow("user1")

    def test_window_expiry(self):
        limiter = RateLimiter(max_requests=1, window_seconds=0.1)
        assert limiter.allow("user1")
        assert not limiter.allow("user1")
        time.sleep(0.15)
        assert limiter.allow("user1")

    def test_cleanup_old_entries(self):
        limiter = RateLimiter(max_requests=100, window_seconds=0.05)
        for i in range(50):
            limiter.allow(f"user{i}")
        time.sleep(0.1)
        limiter.allow("cleanup_trigger")
        assert limiter.allow("user0")
