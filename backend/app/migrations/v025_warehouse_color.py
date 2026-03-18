"""v025 — 仓位颜色标记

为 locations 表添加 color 字段。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # locations 表加 color 字段
    loc_cols = [r["name"] for r in (await conn.execute_query(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name='locations'"
    ))[1]]
    if "color" not in loc_cols:
        await conn.execute_query(
            "ALTER TABLE locations ADD COLUMN color VARCHAR(20) DEFAULT 'blue'"
        )
        logger.info("迁移完成: locations.color")
    # warehouses 表的 color 字段保留（向后兼容），不再使用
