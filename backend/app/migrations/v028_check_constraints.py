"""v028 — CHECK 约束

添加数据库级 CHECK 约束。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    constraints = [
        ("order_items", "chk_oi_qty_positive", "quantity > 0"),
        ("orders", "chk_order_total_nonneg", "total_amount >= 0"),
        ("warehouse_stocks", "chk_ws_reserved_nonneg", "reserved_qty >= 0"),
        ("invoice_items", "chk_ii_tax_rate_range", "tax_rate >= 0 AND tax_rate <= 100"),
        ("purchase_order_items", "chk_poi_tax_rate_range", "tax_rate >= 0 AND tax_rate <= 100"),
    ]
    for table, name, check_expr in constraints:
        try:
            await conn.execute_query(
                f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({check_expr})"
            )
        except Exception as e:
            if "already exists" not in str(e):
                logger.warning(f"CHECK 约束 {name} 创建失败: {e}")
    logger.info("迁移: 检查/创建 CHECK 约束")
