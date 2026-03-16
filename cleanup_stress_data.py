#!/usr/bin/env python3
"""
ERP 压力测试数据清除器
按 FK 依赖逆序删除所有 id >= 100000 的测试数据，重置序列

用法: docker exec erp-4-erp-1 python /app/cleanup_stress_data.py
"""
import os
import sys
import time

import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgres://erp@localhost:5432/erp")
BASE_ID = 100_000

# 删除顺序：子表在前，父表在后（FK 依赖逆序）
TABLES = [
    # 末端叶子表
    "operation_logs",
    "voucher_entries",
    "shipment_items",
    "stock_logs",
    "invoice_items",
    "sales_delivery_items",
    "purchase_receipt_items",
    "purchase_return_items",
    "disbursement_refund_bills",
    "receipt_refund_bills",
    "receivable_write_offs",
    "disbursement_bills",
    "receipt_bills",
    # 中间表
    "receivable_bills",
    "payable_bills",
    "invoices",
    "sales_delivery_bills",
    "purchase_receipt_bills",
    "purchase_returns",
    "shipments",
    "vouchers",
    "payment_orders",
    "payments",
    "sn_codes",
    # 明细表
    "order_items",
    "purchase_order_items",
    # 主表
    "orders",
    "purchase_orders",
    "warehouse_stocks",
    "rebate_logs",
    # 基础数据
    "products",
    "customers",
    "suppliers",
]


def main():
    print("=" * 60)
    print("ERP 压力测试数据清除器")
    print(f"将删除所有 id >= {BASE_ID} 的数据")
    print("=" * 60)

    dsn = DB_URL.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    t0 = time.time()
    total_deleted = 0

    for table in TABLES:
        try:
            cur.execute(f"DELETE FROM {table} WHERE id >= %s", (BASE_ID,))
            deleted = cur.rowcount
            if deleted > 0:
                print(f"  {table:40s} 删除 {deleted:>10,} 条")
                total_deleted += deleted
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"  {table:40s} 错误: {e}")

    # 重置序列
    print("\n重置序列...")
    for table in TABLES:
        try:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
            )
            conn.commit()
        except Exception:
            conn.rollback()

    elapsed = time.time() - t0
    print(f"\n清除完成！共删除 {total_deleted:,} 条数据，耗时 {elapsed:.1f}s")

    # VACUUM ANALYZE 释放空间
    print("\n执行 VACUUM ANALYZE 释放空间...")
    conn.autocommit = True
    cur.execute("VACUUM ANALYZE")
    print("  ✓ VACUUM ANALYZE 完成")

    # 输出当前数据量
    cur.execute(
        "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20"
    )
    print("\n当前各表数据量:")
    for name, count in cur.fetchall():
        if count > 0:
            print(f"  {name:30s} {count:>10,}")

    cur.close()
    conn.close()
    print("\n全部完成！")


if __name__ == "__main__":
    main()
