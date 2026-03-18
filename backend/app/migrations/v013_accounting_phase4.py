"""v013 — 阶段4迁移

出入库单+发票 6表 + 索引 + 1407科目补充。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    from tortoise import Tortoise

    try:
        await Tortoise.generate_schemas(safe=True)
    except Exception:
        pass  # Column already exists from init_db()

    indexes = [
        ("idx_sdb_account_customer", "sales_delivery_bills", "account_set_id, customer_id"),
        ("idx_sdb_order", "sales_delivery_bills", "order_id"),
        ("idx_sdi_bill", "sales_delivery_items", "delivery_bill_id"),
        ("idx_prb_account_supplier", "purchase_receipt_bills", "account_set_id, supplier_id"),
        ("idx_prb_po", "purchase_receipt_bills", "purchase_order_id"),
        ("idx_pri_bill", "purchase_receipt_items", "receipt_bill_id"),
        ("idx_inv_account_direction", "invoices", "account_set_id, direction"),
        ("idx_inv_account_status", "invoices", "account_set_id, status"),
        ("idx_inv_receivable", "invoices", "receivable_bill_id"),
        ("idx_inv_payable", "invoices", "payable_bill_id"),
        ("idx_inv_items_invoice", "invoice_items", "invoice_id"),
    ]
    for idx_name, table, columns in indexes:
        try:
            await conn.execute_query(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})"
            )
        except Exception:
            pass

    try:
        from app.models.accounting import AccountSet, ChartOfAccount
        account_sets = await AccountSet.all()
        for a in account_sets:
            exists = await ChartOfAccount.filter(account_set_id=a.id, code="1407").exists()
            if not exists:
                await ChartOfAccount.create(
                    account_set_id=a.id, code="1407", name="发出商品",
                    level=1, category="asset", direction="debit", is_leaf=True
                )
    except Exception:
        pass

    logger.info("阶段4迁移完成：出入库单+发票表 + 索引 + 1407科目")
