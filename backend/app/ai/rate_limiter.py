"""内存滑动窗口限流器 — 单容器部署，无需 Redis"""
from __future__ import annotations
import time
from collections import defaultdict


class RateLimiter:
    """基于滑动窗口的限流器"""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.monotonic()

    def allow(self, key: str) -> bool:
        """检查是否允许请求。返回 True=放行，False=限流"""
        now = time.monotonic()

        # 定期清理（每 60 秒）
        if now - self._last_cleanup > 60:
            self._cleanup(now)

        # 移除窗口外的旧记录
        timestamps = self._requests[key]
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)

        if len(timestamps) >= self.max_requests:
            return False

        timestamps.append(now)
        return True

    def _cleanup(self, now: float) -> None:
        """清理过期的 key"""
        self._last_cleanup = now
        cutoff = now - self.window_seconds
        expired_keys = [
            k for k, v in self._requests.items()
            if not v or v[-1] < cutoff
        ]
        for k in expired_keys:
            del self._requests[k]


# 全局实例（按 spec 配置）
user_limiter = RateLimiter(max_requests=10, window_seconds=60)
global_limiter = RateLimiter(max_requests=60, window_seconds=60)
