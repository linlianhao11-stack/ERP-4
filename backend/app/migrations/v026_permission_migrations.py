"""v026 — 权限迁移

一次性为活跃非 admin 用户追加 AI 权限 + 代采代发权限。
"""
from __future__ import annotations

from app.logger import get_logger
from app.models import SystemSetting, User

logger = get_logger("migrations")


async def up(conn):
    await _migrate_ai_permissions()
    await _migrate_dropship_permissions()


async def _migrate_ai_permissions():
    """一次性：为所有活跃非 admin 用户追加 AI 权限"""
    from app.ai.view_permissions import AI_PERMISSION_KEYS

    flag = await SystemSetting.filter(key="ai.permissions_migrated").first()
    if flag:
        return

    users = await User.filter(is_active=True).exclude(role="admin").all()
    migrated = 0
    for user in users:
        perms = user.permissions or []
        if "ai_chat" not in perms:
            perms.extend(AI_PERMISSION_KEYS)
            user.permissions = list(set(perms))
            await user.save()
            migrated += 1
    if migrated:
        logger.info(f"AI 权限迁移完成，已为 {migrated} 个用户添加 AI 权限")
    await SystemSetting.get_or_create(key="ai.permissions_migrated", defaults={"value": "1"})


async def _migrate_dropship_permissions():
    """一次性：为所有活跃非 admin 用户追加代采代发权限"""
    flag = await SystemSetting.filter(key="dropship.permissions_migrated").first()
    if flag:
        return

    dropship_perms = ["dropship", "dropship_pay"]
    users = await User.filter(is_active=True).exclude(role="admin").all()
    migrated = 0
    for user in users:
        perms = user.permissions or []
        if "dropship" not in perms:
            perms.extend(dropship_perms)
            user.permissions = list(set(perms))
            await user.save()
            migrated += 1
    if migrated:
        logger.info(f"代采代发权限迁移完成，已为 {migrated} 个用户添加权限")
    await SystemSetting.get_or_create(key="dropship.permissions_migrated", defaults={"value": "1"})
