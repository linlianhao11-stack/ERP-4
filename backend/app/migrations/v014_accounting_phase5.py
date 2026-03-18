"""v014 — 阶段5迁移

确保 admin 拥有 period_end 权限。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    from app.models import User

    admin = await User.filter(username="admin").first()
    if admin:
        current = admin.permissions or []
        # period_end 权限应该在 phase1 已添加，这里只是确认
        if "period_end" not in current:
            admin.permissions = current + ["period_end"]
            await admin.save()
            logger.info("admin 用户补充 period_end 权限")
    logger.info("阶段5迁移完成")
