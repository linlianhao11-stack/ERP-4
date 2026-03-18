"""v017 — 采购退货单表

CREATE TABLE purchase_returns + purchase_return_items。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    await conn.execute_script("""
        CREATE TABLE IF NOT EXISTS purchase_returns (
            id SERIAL PRIMARY KEY,
            return_no VARCHAR(30) UNIQUE NOT NULL,
            purchase_order_id INT NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
            supplier_id INT NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
            account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL,
            total_amount DECIMAL(12,2) DEFAULT 0,
            is_refunded BOOLEAN DEFAULT FALSE,
            refund_status VARCHAR(20) DEFAULT 'pending',
            tracking_no VARCHAR(100),
            reason TEXT,
            created_by_id INT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_pr_po ON purchase_returns(purchase_order_id);
        CREATE INDEX IF NOT EXISTS idx_pr_supplier ON purchase_returns(supplier_id);

        CREATE TABLE IF NOT EXISTS purchase_return_items (
            id SERIAL PRIMARY KEY,
            purchase_return_id INT NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
            purchase_item_id INT REFERENCES purchase_order_items(id) ON DELETE SET NULL,
            product_id INT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
            quantity INT NOT NULL,
            unit_price DECIMAL(12,2) NOT NULL,
            amount DECIMAL(12,2) NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pri_return ON purchase_return_items(purchase_return_id);
    """)
    logger.info("采购退货单表迁移完成")
