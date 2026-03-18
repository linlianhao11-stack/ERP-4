"""v027 — 审查缺失索引

添加审查发现的缺失复合索引。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_voucher_as_period ON vouchers(account_set_id, period_name)",
        "CREATE INDEX IF NOT EXISTS idx_receivable_bill_as_status ON receivable_bills(account_set_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_receivable_bill_date ON receivable_bills(bill_date)",
        "CREATE INDEX IF NOT EXISTS idx_payable_bill_as_status ON payable_bills(account_set_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_order_item_wh_loc ON order_items(warehouse_id, location_id)",
        "CREATE INDEX IF NOT EXISTS idx_shipment_tracking ON shipments(tracking_no)",
        "CREATE INDEX IF NOT EXISTS idx_stock_log_wh_date ON stock_logs(warehouse_id, created_at DESC)",
    ]
    for sql in indexes:
        try:
            await conn.execute_query(sql)
        except Exception:
            pass  # 索引已存在或表不存在（SQLite 开发环境）
    logger.info("迁移: 检查/创建缺失复合索引")
