"""v002 — 仓位关联仓库

给 locations 表添加 warehouse_id 列，将现有仓位归入默认仓库。
"""
from __future__ import annotations

from app.logger import get_logger
from app.models import Warehouse

logger = get_logger("migrations")


async def up(conn):
    default_wh = await Warehouse.filter(is_default=True).first()
    if not default_wh:
        return

    # 检查 locations 表是否已有 warehouse_id 列（PostgreSQL 兼容）
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'locations'"
    )
    has_warehouse_id = any(col["name"] == "warehouse_id" for col in columns)

    if not has_warehouse_id:
        wh_id = int(default_wh.id)
        logger.info("迁移: 为 locations 表添加 warehouse_id 列")
        await conn.execute_query(
            f"ALTER TABLE locations ADD COLUMN IF NOT EXISTS warehouse_id INT REFERENCES warehouses(id) DEFAULT {wh_id}"
        )
        # 将所有现有仓位归入默认仓库（参数化查询）
        await conn.execute_query(
            "UPDATE locations SET warehouse_id = $1 WHERE warehouse_id IS NULL", [wh_id]
        )
        # 移除旧的 code 唯一索引/约束（如果存在）
        try:
            await conn.execute_query("DROP INDEX IF EXISTS uid_locations_code_91776a")
        except Exception as e:
            logger.warning(f"删除旧索引失败（可忽略）: {e}")
        try:
            await conn.execute_query("ALTER TABLE locations DROP CONSTRAINT IF EXISTS locations_code_key")
        except Exception as e:
            logger.warning(f"删除旧约束失败（可忽略）: {e}")
        # 创建 (warehouse_id, code) 联合唯一索引
        try:
            await conn.execute_query(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_location_warehouse_code ON locations(warehouse_id, code)"
            )
        except Exception as e:
            logger.warning(f"创建联合唯一索引失败: {e}")
        logger.info("迁移完成: 现有仓位已归入默认仓库")
    else:
        # 确保所有仓位都有 warehouse_id
        null_count = await conn.execute_query_dict(
            "SELECT COUNT(*) as cnt FROM locations WHERE warehouse_id IS NULL"
        )
        if null_count and null_count[0]["cnt"] > 0:
            await conn.execute_query(
                "UPDATE locations SET warehouse_id = $1 WHERE warehouse_id IS NULL", [int(default_wh.id)]
            )
            logger.info(f"迁移: {null_count[0]['cnt']} 个仓位已归入默认仓库")
