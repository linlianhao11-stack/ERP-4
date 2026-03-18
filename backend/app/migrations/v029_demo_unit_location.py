"""v029 — 样机增加仓位字段

为 demo_units 表添加 location_id 外键，支持样机关联到具体仓位。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # 添加 location_id 列（可为空）
    try:
        await conn.execute_query(
            "ALTER TABLE demo_units ADD COLUMN IF NOT EXISTS location_id INT NULL"
        )
    except Exception as e:
        if "already exists" not in str(e):
            logger.warning(f"添加 location_id 列失败: {e}")

    # 添加外键约束
    try:
        await conn.execute_query(
            "ALTER TABLE demo_units ADD CONSTRAINT fk_demo_unit_location "
            "FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL"
        )
    except Exception as e:
        if "already exists" not in str(e):
            logger.warning(f"添加外键约束失败: {e}")

    # 添加索引
    try:
        await conn.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_demo_units_location ON demo_units(location_id)"
        )
    except Exception as e:
        logger.warning(f"创建索引失败: {e}")

    logger.info("迁移: demo_units 添加 location_id 字段")
