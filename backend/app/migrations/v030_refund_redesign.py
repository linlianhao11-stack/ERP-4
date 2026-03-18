"""v030 — 退货退款模型重构

1. 扩展 ReceiptRefundBill / DisbursementRefundBill：新增 return_order_id、purchase_return_id、refund_info
2. 将 receipt_bills / disbursement_bills 中 bill_type='return_refund' 的记录迁移到对应 refund 表
3. 清理 receipt_bills / disbursement_bills 的 bill_type、return_order_id / purchase_return_id 列
4. 为 orders、purchase_returns 添加 refund_info 列
5. 将 receipt_refund_bills.original_receipt_id、disbursement_refund_bills.original_disbursement_id 改为 nullable
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # ── 1. receipt_refund_bills 新增列 ──────────────────────────────────
    await conn.execute_query(
        "ALTER TABLE receipt_refund_bills "
        "ADD COLUMN IF NOT EXISTS return_order_id INT NULL"
    )
    await conn.execute_query(
        "ALTER TABLE receipt_refund_bills "
        "ADD COLUMN IF NOT EXISTS refund_info TEXT NOT NULL DEFAULT ''"
    )
    # 外键约束（幂等：忽略已存在错误）
    try:
        await conn.execute_query(
            "ALTER TABLE receipt_refund_bills "
            "ADD CONSTRAINT fk_receipt_refund_return_order "
            "FOREIGN KEY (return_order_id) REFERENCES orders(id) ON DELETE SET NULL"
        )
    except Exception as e:
        if "already exists" not in str(e):
            logger.warning(f"添加 receipt_refund_bills.return_order_id 外键失败: {e}")

    # ── 2. disbursement_refund_bills 新增列 ─────────────────────────────
    await conn.execute_query(
        "ALTER TABLE disbursement_refund_bills "
        "ADD COLUMN IF NOT EXISTS purchase_return_id INT NULL"
    )
    await conn.execute_query(
        "ALTER TABLE disbursement_refund_bills "
        "ADD COLUMN IF NOT EXISTS refund_info TEXT NOT NULL DEFAULT ''"
    )
    try:
        await conn.execute_query(
            "ALTER TABLE disbursement_refund_bills "
            "ADD CONSTRAINT fk_disb_refund_purchase_return "
            "FOREIGN KEY (purchase_return_id) REFERENCES purchase_returns(id) ON DELETE SET NULL"
        )
    except Exception as e:
        if "already exists" not in str(e):
            logger.warning(f"添加 disbursement_refund_bills.purchase_return_id 外键失败: {e}")

    # ── 2b. 先将 original_receipt_id / original_disbursement_id 改为 nullable（数据迁移需要）
    col_info = await conn.execute_query_dict(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = 'receipt_refund_bills' AND column_name = 'original_receipt_id'"
    )
    if col_info and col_info[0]["is_nullable"] == "NO":
        await conn.execute_query(
            "ALTER TABLE receipt_refund_bills "
            "ALTER COLUMN original_receipt_id DROP NOT NULL"
        )
        logger.info("receipt_refund_bills.original_receipt_id 已改为 nullable")

    col_info2 = await conn.execute_query_dict(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name = 'disbursement_refund_bills' AND column_name = 'original_disbursement_id'"
    )
    if col_info2 and col_info2[0]["is_nullable"] == "NO":
        await conn.execute_query(
            "ALTER TABLE disbursement_refund_bills "
            "ALTER COLUMN original_disbursement_id DROP NOT NULL"
        )
        logger.info("disbursement_refund_bills.original_disbursement_id 已改为 nullable")

    # ── 3. 数据迁移：receipt_bills (bill_type='return_refund') → receipt_refund_bills ──
    # 仅在 bill_type 列存在时执行
    col_check = await conn.execute_query_dict(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'receipt_bills' AND column_name = 'bill_type'"
    )
    if col_check:
        # 生成新单号前缀 SKTK，避免与已有 refund bill_no 冲突用 NOT EXISTS 保护
        migrated = await conn.execute_query_dict(
            "SELECT id FROM receipt_bills WHERE bill_type = 'return_refund'"
        )
        if migrated:
            logger.info(f"发现 {len(migrated)} 条 receipt_bills (return_refund) 待迁移")
            # INSERT ... SELECT：amount 取绝对值，receipt_date → refund_date
            # bill_no 加 '-RF' 后缀避免与原 refund_bills 冲突
            await conn.execute_query("""
                INSERT INTO receipt_refund_bills
                    (bill_no, account_set_id, customer_id, return_order_id,
                     refund_date, amount, reason, refund_info, remark,
                     status, confirmed_by_id, confirmed_at,
                     voucher_id, voucher_no, creator_id, created_at)
                SELECT
                    SUBSTRING(rb.bill_no FROM 1 FOR 27) || '-RF',
                    rb.account_set_id,
                    rb.customer_id,
                    rb.return_order_id,
                    rb.receipt_date,
                    ABS(rb.amount),
                    rb.remark,
                    '',
                    rb.remark,
                    rb.status,
                    rb.confirmed_by_id,
                    rb.confirmed_at,
                    rb.voucher_id,
                    rb.voucher_no,
                    rb.creator_id,
                    rb.created_at
                FROM receipt_bills rb
                WHERE rb.bill_type = 'return_refund'
                  AND NOT EXISTS (
                      SELECT 1 FROM receipt_refund_bills rrf
                      WHERE rrf.bill_no = SUBSTRING(rb.bill_no FROM 1 FOR 27) || '-RF'
                  )
            """)
            logger.info("receipt_bills (return_refund) 数据迁移完成")

        # 删除迁移后的旧记录
        await conn.execute_query(
            "DELETE FROM receipt_bills WHERE bill_type = 'return_refund'"
        )

        # 删除 receipt_bills 的 bill_type、return_order_id 列
        try:
            await conn.execute_query(
                "ALTER TABLE receipt_bills DROP COLUMN IF EXISTS bill_type"
            )
        except Exception as e:
            logger.warning(f"删除 receipt_bills.bill_type 列失败: {e}")

        try:
            await conn.execute_query(
                "ALTER TABLE receipt_bills DROP COLUMN IF EXISTS return_order_id"
            )
        except Exception as e:
            logger.warning(f"删除 receipt_bills.return_order_id 列失败: {e}")

    # ── 4. 数据迁移：disbursement_bills (bill_type='return_refund') → disbursement_refund_bills ──
    col_check2 = await conn.execute_query_dict(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'disbursement_bills' AND column_name = 'bill_type'"
    )
    if col_check2:
        migrated2 = await conn.execute_query_dict(
            "SELECT id FROM disbursement_bills WHERE bill_type = 'return_refund'"
        )
        if migrated2:
            logger.info(f"发现 {len(migrated2)} 条 disbursement_bills (return_refund) 待迁移")
            await conn.execute_query("""
                INSERT INTO disbursement_refund_bills
                    (bill_no, account_set_id, supplier_id, purchase_return_id,
                     refund_date, amount, reason, refund_info, remark,
                     status, confirmed_by_id, confirmed_at,
                     voucher_id, voucher_no, creator_id, created_at)
                SELECT
                    SUBSTRING(db.bill_no FROM 1 FOR 27) || '-RF',
                    db.account_set_id,
                    db.supplier_id,
                    db.purchase_return_id,
                    db.disbursement_date,
                    ABS(db.amount),
                    db.remark,
                    '',
                    db.remark,
                    db.status,
                    db.confirmed_by_id,
                    db.confirmed_at,
                    db.voucher_id,
                    db.voucher_no,
                    db.creator_id,
                    db.created_at
                FROM disbursement_bills db
                WHERE db.bill_type = 'return_refund'
                  AND NOT EXISTS (
                      SELECT 1 FROM disbursement_refund_bills drf
                      WHERE drf.bill_no = SUBSTRING(db.bill_no FROM 1 FOR 27) || '-RF'
                  )
            """)
            logger.info("disbursement_bills (return_refund) 数据迁移完成")

        # 删除迁移后的旧记录
        await conn.execute_query(
            "DELETE FROM disbursement_bills WHERE bill_type = 'return_refund'"
        )

        # 删除 disbursement_bills 的 bill_type、purchase_return_id 列
        try:
            await conn.execute_query(
                "ALTER TABLE disbursement_bills DROP COLUMN IF EXISTS bill_type"
            )
        except Exception as e:
            logger.warning(f"删除 disbursement_bills.bill_type 列失败: {e}")

        try:
            await conn.execute_query(
                "ALTER TABLE disbursement_bills DROP COLUMN IF EXISTS purchase_return_id"
            )
        except Exception as e:
            logger.warning(f"删除 disbursement_bills.purchase_return_id 列失败: {e}")

    # ── 5. orders 表添加 refund_info 列 ────────────────────────────────
    await conn.execute_query(
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_info TEXT NOT NULL DEFAULT ''"
    )

    # ── 6. purchase_returns 表添加 refund_info 列 ──────────────────────
    await conn.execute_query(
        "ALTER TABLE purchase_returns ADD COLUMN IF NOT EXISTS refund_info TEXT NOT NULL DEFAULT ''"
    )

    logger.info("v030 退货退款模型重构迁移完成")
