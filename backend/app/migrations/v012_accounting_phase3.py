"""v012 — 阶段3应收应付迁移

7张新表 + AR/AP索引 + admin AR/AP权限。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    from tortoise import Tortoise
    from app.models import User

    try:
        await Tortoise.generate_schemas(safe=True)
    except Exception:
        pass  # Column already exists from init_db()

    # AR/AP 索引
    ar_ap_indexes = [
        ("idx_receivable_bills_set_customer", "receivable_bills", "account_set_id, customer_id"),
        ("idx_receivable_bills_set_status", "receivable_bills", "account_set_id, status"),
        ("idx_receipt_bills_customer", "receipt_bills", "customer_id"),
        ("idx_receipt_bills_receivable", "receipt_bills", "receivable_bill_id"),
        ("idx_receipt_refund_bills_original", "receipt_refund_bills", "original_receipt_id"),
        ("idx_receivable_write_offs_receivable", "receivable_write_offs", "receivable_bill_id"),
        ("idx_payable_bills_set_supplier", "payable_bills", "account_set_id, supplier_id"),
        ("idx_payable_bills_set_status", "payable_bills", "account_set_id, status"),
        ("idx_disbursement_bills_payable", "disbursement_bills", "payable_bill_id"),
        ("idx_disbursement_refund_bills_original", "disbursement_refund_bills", "original_disbursement_id"),
    ]
    for name, table, columns in ar_ap_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception as e:
            logger.warning(f"创建索引 {name} 失败（可忽略）: {e}")

    # 为 admin 用户添加 AR/AP 权限
    new_perms = [
        "accounting_ar_view", "accounting_ar_edit", "accounting_ar_confirm",
        "accounting_ap_view", "accounting_ap_edit", "accounting_ap_confirm",
    ]
    admin = await User.filter(username="admin").first()
    if admin:
        current = admin.permissions or []
        added = [p for p in new_perms if p not in current]
        if added:
            admin.permissions = current + added
            await admin.save()
            logger.info(f"admin 用户新增 AR/AP 权限: {added}")

    logger.info("阶段3应收应付迁移完成")
