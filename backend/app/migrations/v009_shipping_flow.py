"""v009 — 发货流程重构

添加 warehouse_stocks.reserved_qty / orders.shipping_status / order_items.shipped_qty，
创建 shipment_items 表。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    ws_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'warehouse_stocks'"
    )
    ws_col_names = [col["name"] for col in ws_columns]
    if "reserved_qty" not in ws_col_names:
        await conn.execute_query("ALTER TABLE warehouse_stocks ADD COLUMN IF NOT EXISTS reserved_qty INT DEFAULT 0")
        logger.info("迁移: warehouse_stocks 表添加 reserved_qty 列")

    o_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'orders'"
    )
    o_col_names = [col["name"] for col in o_columns]
    if "shipping_status" not in o_col_names:
        await conn.execute_query(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_status VARCHAR(20) DEFAULT 'completed'"
        )
        logger.info("迁移: orders 表添加 shipping_status 列")

    oi_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'order_items'"
    )
    oi_col_names = [col["name"] for col in oi_columns]
    if "shipped_qty" not in oi_col_names:
        await conn.execute_query("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS shipped_qty INT DEFAULT 0")
        await conn.execute_query("UPDATE order_items SET shipped_qty = ABS(quantity) WHERE shipped_qty = 0")
        logger.info("迁移: order_items 表添加 shipped_qty 列（历史数据已回填）")

    tables = await conn.execute_query_dict(
        "SELECT table_name as name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'shipment_items'"
    )
    if not any(t["name"] == "shipment_items" for t in tables):
        await conn.execute_query("""
            CREATE TABLE shipment_items (
                id SERIAL PRIMARY KEY,
                shipment_id INT NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
                order_item_id INT NOT NULL REFERENCES order_items(id) ON DELETE RESTRICT,
                product_id INT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
                quantity INT NOT NULL,
                sn_codes TEXT
            )
        """)
        await conn.execute_query("CREATE INDEX IF NOT EXISTS idx_shipment_items_shipment ON shipment_items(shipment_id)")
        await conn.execute_query("CREATE INDEX IF NOT EXISTS idx_shipment_items_order_item ON shipment_items(order_item_id)")
        logger.info("迁移: 创建 shipment_items 表")
