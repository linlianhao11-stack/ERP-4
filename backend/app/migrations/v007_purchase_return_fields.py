"""v007 — 采购退货字段

给采购相关表添加退货字段（purchase_orders / purchase_order_items / suppliers / rebate_logs）。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # purchase_orders 表
    po_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    )
    po_col_names = [col["name"] for col in po_columns]

    po_new_cols = [
        ("return_tracking_no", "VARCHAR(100)"),
        ("is_refunded", "BOOLEAN DEFAULT FALSE"),
        ("return_amount", "DECIMAL(12,2) DEFAULT 0"),
        ("credit_used", "DECIMAL(12,2) DEFAULT 0"),
        ("returned_by_id", "INT REFERENCES users(id)"),
        ("returned_at", "TIMESTAMPTZ"),
    ]
    for col_name, col_type in po_new_cols:
        if col_name not in po_col_names:
            await conn.execute_query(f"ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            logger.info(f"迁移: purchase_orders 表添加 {col_name} 列")

    # purchase_order_items 表
    poi_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_order_items'"
    )
    poi_col_names = [col["name"] for col in poi_columns]

    if "returned_quantity" not in poi_col_names:
        await conn.execute_query("ALTER TABLE purchase_order_items ADD COLUMN IF NOT EXISTS returned_quantity INT DEFAULT 0")
        logger.info("迁移: purchase_order_items 表添加 returned_quantity 列")

    # suppliers 表
    sup_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'suppliers'"
    )
    sup_col_names = [col["name"] for col in sup_columns]

    if "credit_balance" not in sup_col_names:
        await conn.execute_query("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS credit_balance DECIMAL(12,2) DEFAULT 0")
        logger.info("迁移: suppliers 表添加 credit_balance 列")

    # rebate_logs.type 列扩展到 20 字符（支持 credit_charge 等新类型）
    try:
        await conn.execute_query("ALTER TABLE rebate_logs ALTER COLUMN type TYPE VARCHAR(20)")
    except Exception as e:
        logger.warning(f"修改 rebate_logs.type 列类型失败（可忽略）: {e}")
