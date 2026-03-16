# 压力测试数据生成实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 生成 ~120 万条压测数据 + 一键清除脚本，验证百万级数据性能

**Architecture:** Python 脚本直连 PostgreSQL，用 `io.StringIO` + `cursor.copy_from()` 批量导入（COPY 协议），按 FK 依赖顺序生成。所有测试数据 ID 从 100000 起始，通过前缀标记可追溯。

**Tech Stack:** Python 3 + psycopg2 + PostgreSQL COPY

---

### Task 1: 创建数据生成脚本

**Files:**
- Create: `backend/scripts/generate_stress_data.py`

**Step 1: 创建目录和脚本**

```bash
mkdir -p /Users/lin/Desktop/erp-4/backend/scripts
```

创建 `backend/scripts/generate_stress_data.py`，完整代码如下：

```python
#!/usr/bin/env python3
"""
ERP 压力测试数据生成器
通过 PostgreSQL COPY 协议批量导入 ~120 万条测试数据
所有测试数据 ID >= 100000，便于清除

用法: docker exec erp-4-erp-1 python /app/scripts/generate_stress_data.py
"""
import io
import os
import sys
import time
import random
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg2

# ---------- 配置 ----------
DB_URL = os.environ.get("DATABASE_URL", "postgres://erp@localhost:5432/erp")
BASE_ID = 100_000
BATCH_SIZE = 10_000

# 数据量配置
PRODUCTS = 5_000
CUSTOMERS = 2_000
SUPPLIERS = 500
ORDERS = 100_000
ORDER_ITEMS_PER_ORDER = 3  # 平均
PURCHASE_ORDERS = 20_000
PO_ITEMS_PER_PO = 3
WAREHOUSE_STOCKS = 20_000
STOCK_LOGS = 200_000
SHIPMENTS = 80_000
SHIPMENT_ITEMS_PER_SHIP = 1.5  # 平均
VOUCHERS = 50_000
VOUCHER_ENTRIES_PER_V = 2
RECEIVABLE_BILLS = 30_000
PAYABLE_BILLS = 15_000
OPERATION_LOGS = 100_000

# 时间范围
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2026, 3, 15)
DATE_RANGE_DAYS = (END_DATE - START_DATE).days

# ---------- 工具 ----------
def random_date():
    return START_DATE + timedelta(
        days=random.randint(0, DATE_RANGE_DAYS),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )

def random_price(low=10, high=5000):
    return round(random.uniform(low, high), 2)

def escape_copy(val):
    """转义 COPY 协议中的特殊字符"""
    if val is None:
        return "\\N"
    s = str(val)
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")

def copy_batch(cur, table, columns, rows):
    """用 COPY 协议批量导入"""
    buf = io.StringIO()
    for row in rows:
        buf.write("\t".join(escape_copy(v) for v in row) + "\n")
    buf.seek(0)
    cur.copy_from(buf, table, columns=columns)

def set_sequence(cur, table):
    """重置序列到最大 ID"""
    cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))")

# ---------- 品牌/类别池 ----------
BRANDS = ["华为", "小米", "苹果", "联想", "戴尔", "惠普", "三星", "索尼", "佳能", "大疆",
           "罗技", "雷蛇", "飞利浦", "松下", "海尔", "格力", "美的", "TCL", "创维", "TP-Link"]
CATEGORIES = ["手机", "笔记本", "平板", "显示器", "键盘", "鼠标", "耳机", "音箱", "摄像头", "路由器",
              "硬盘", "内存", "CPU", "显卡", "主板", "电源", "机箱", "线缆", "充电器", "保护壳"]
UNITS = ["个", "台", "件", "套", "箱", "盒", "卷", "米", "条", "把"]
ORDER_TYPES = ["CASH", "CREDIT", "CONSIGN_OUT"]
ORDER_STATUSES = ["completed", "completed", "completed", "completed", "pending"]  # 80% 完成
SHIPPING_STATUSES = ["shipped", "shipped", "shipped", "pending", "partial"]
PO_STATUSES = ["completed", "completed", "completed", "pending_review", "paid"]
VOUCHER_TYPES = ["记", "收", "付", "转"]
CARRIERS = ["shunfeng", "yuantong", "zhongtong", "yunda", "shentong", "ems", "jd", "jtexpress"]
CARRIER_NAMES = {"shunfeng": "顺丰速运", "yuantong": "圆通速递", "zhongtong": "中通快递",
                 "yunda": "韵达快递", "shentong": "申通快递", "ems": "EMS",
                 "jd": "京东物流", "jtexpress": "极兔速递"}

# ---------- 主逻辑 ----------
def main():
    print("=" * 60)
    print("ERP 压力测试数据生成器")
    print("=" * 60)

    dsn = DB_URL.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    cur = conn.cursor()

    # 获取现有引用数据
    cur.execute("SELECT id FROM warehouses WHERE NOT is_virtual AND is_active LIMIT 4")
    warehouse_ids = [r[0] for r in cur.fetchall()]
    if not warehouse_ids:
        print("ERROR: 没有找到可用仓库，请先创建仓库")
        sys.exit(1)

    cur.execute("SELECT id FROM users WHERE is_active LIMIT 3")
    user_ids = [r[0] for r in cur.fetchall()]
    if not user_ids:
        user_ids = [1]

    cur.execute("SELECT id FROM account_sets WHERE is_active LIMIT 1")
    row = cur.fetchone()
    account_set_id = row[0] if row else 1

    cur.execute("SELECT id FROM chart_of_accounts WHERE account_set_id = %s AND is_leaf AND is_active LIMIT 20", (account_set_id,))
    account_ids = [r[0] for r in cur.fetchall()]
    if not account_ids:
        account_ids = [1]

    t0 = time.time()

    # ===== 1. Products =====
    print(f"\n[1/14] 生成商品 {PRODUCTS} 条...")
    product_ids = list(range(BASE_ID, BASE_ID + PRODUCTS))
    rows = []
    for i, pid in enumerate(product_ids):
        brand = random.choice(BRANDS)
        cat = random.choice(CATEGORIES)
        cost = random_price(50, 2000)
        retail = round(cost * random.uniform(1.2, 2.5), 2)
        dt = random_date()
        rows.append((
            pid, f"ST-{brand[0]}{cat[0]}-{i+1:05d}", f"{brand} {cat} 型号{i+1}",
            brand, cat, retail, cost, random.choice(UNITS),
            f"[STRESS_TEST] 压测商品{i+1}", 13.00, True, dt, dt
        ))
    copy_batch(cur, "products", (
        "id", "sku", "name", "brand", "category", "retail_price", "cost_price",
        "unit", "description", "tax_rate", "is_active", "created_at", "updated_at"
    ), rows)
    set_sequence(cur, "products")
    conn.commit()
    print(f"  ✓ 商品完成 ({time.time()-t0:.1f}s)")

    # ===== 2. Customers =====
    print(f"\n[2/14] 生成客户 {CUSTOMERS} 条...")
    customer_ids = list(range(BASE_ID, BASE_ID + CUSTOMERS))
    rows = []
    for i, cid in enumerate(customer_ids):
        dt = random_date()
        rows.append((
            cid, f"压测客户-{i+1:04d}", f"联系人{i+1}", f"138{random.randint(10000000,99999999)}",
            f"测试地址{i+1}号", 0, 0, True, dt, dt
        ))
    copy_batch(cur, "customers", (
        "id", "name", "contact_person", "phone", "address", "balance", "rebate_balance",
        "is_active", "created_at", "updated_at"
    ), rows)
    set_sequence(cur, "customers")
    conn.commit()
    print(f"  ✓ 客户完成 ({time.time()-t0:.1f}s)")

    # ===== 3. Suppliers =====
    print(f"\n[3/14] 生成供应商 {SUPPLIERS} 条...")
    supplier_ids = list(range(BASE_ID, BASE_ID + SUPPLIERS))
    rows = []
    for i, sid in enumerate(supplier_ids):
        dt = random_date()
        rows.append((
            sid, f"压测供应商-{i+1:03d}", f"供联系人{i+1}", f"139{random.randint(10000000,99999999)}",
            f"供应商地址{i+1}号", 0, 0, True, dt, dt
        ))
    copy_batch(cur, "suppliers", (
        "id", "name", "contact_person", "phone", "address", "rebate_balance", "credit_balance",
        "is_active", "created_at", "updated_at"
    ), rows)
    set_sequence(cur, "suppliers")
    conn.commit()
    print(f"  ✓ 供应商完成 ({time.time()-t0:.1f}s)")

    # ===== 4. Warehouse Stocks =====
    print(f"\n[4/14] 生成库存记录 {WAREHOUSE_STOCKS} 条...")
    ws_rows = []
    ws_id = BASE_ID
    used_combos = set()
    for _ in range(WAREHOUSE_STOCKS):
        while True:
            wid = random.choice(warehouse_ids)
            pid = random.choice(product_ids)
            combo = (wid, pid)
            if combo not in used_combos:
                used_combos.add(combo)
                break
        qty = random.randint(0, 500)
        cost = random_price(50, 2000)
        dt = random_date()
        ws_rows.append((
            ws_id, wid, pid, None, qty, 0, cost, dt, dt, dt
        ))
        ws_id += 1
    copy_batch(cur, "warehouse_stocks", (
        "id", "warehouse_id", "product_id", "location_id", "quantity", "reserved_qty",
        "weighted_cost", "weighted_entry_date", "last_activity_at", "created_at"
    ), ws_rows)
    set_sequence(cur, "warehouse_stocks")
    conn.commit()
    print(f"  ✓ 库存完成 ({time.time()-t0:.1f}s)")

    # ===== 5. Orders =====
    print(f"\n[5/14] 生成订单 {ORDERS} 条...")
    order_ids = list(range(BASE_ID, BASE_ID + ORDERS))
    for batch_start in range(0, ORDERS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, ORDERS)
        rows = []
        for i in range(batch_start, batch_end):
            oid = order_ids[i]
            dt = random_date()
            otype = random.choice(ORDER_TYPES)
            total = random_price(100, 50000)
            cost = round(total * random.uniform(0.4, 0.8), 2)
            profit = round(total - cost, 2)
            status = random.choice(ORDER_STATUSES)
            ship_status = random.choice(SHIPPING_STATUSES) if status == "completed" else "pending"
            paid = total if status == "completed" else 0
            rows.append((
                oid, f"ST-SO-{dt.strftime('%Y%m%d')}-{i+1:06d}",
                otype, random.choice(customer_ids), random.choice(warehouse_ids),
                total, cost, profit, paid, 0, 0,
                status == "completed",  # is_cleared
                False, None, 0,  # refunded, refund_method, refund_amount
                ship_status, None, None, random.choice(user_ids),
                None, account_set_id, None, None,
                f"[STRESS_TEST]", dt, dt
            ))
        copy_batch(cur, "orders", (
            "id", "order_no", "order_type", "customer_id", "warehouse_id",
            "total_amount", "total_cost", "total_profit", "paid_amount", "rebate_used", "credit_used",
            "is_cleared", "refunded", "refund_method", "refund_amount",
            "shipping_status", "related_order_id", "employee_id", "creator_id",
            "voucher_id", "account_set_id", "voucher_no", "remark_images",
            "remark", "created_at", "updated_at"
        ))
        conn.commit()
        if (batch_start // BATCH_SIZE) % 5 == 0:
            print(f"  ... {batch_end}/{ORDERS}")
    set_sequence(cur, "orders")
    conn.commit()
    print(f"  ✓ 订单完成 ({time.time()-t0:.1f}s)")

    # ===== 6. Order Items =====
    total_items = ORDERS * ORDER_ITEMS_PER_ORDER
    print(f"\n[6/14] 生成订单明细 ~{total_items} 条...")
    oi_id = BASE_ID
    for batch_start in range(0, ORDERS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, ORDERS)
        rows = []
        for i in range(batch_start, batch_end):
            oid = order_ids[i]
            n_items = random.randint(1, 5)
            for _ in range(n_items):
                pid = random.choice(product_ids)
                qty = random.randint(1, 20)
                price = random_price(50, 3000)
                cost = round(price * random.uniform(0.4, 0.8), 2)
                amount = round(price * qty, 2)
                profit = round((price - cost) * qty, 2)
                rows.append((
                    oi_id, oid, pid, qty, price, cost, amount, profit,
                    0, qty, random.choice(warehouse_ids), None
                ))
                oi_id += 1
        copy_batch(cur, "order_items", (
            "id", "order_id", "product_id", "quantity", "unit_price", "cost_price",
            "amount", "profit", "rebate_amount", "shipped_qty", "warehouse_id", "location_id"
        ), rows)
        conn.commit()
        if (batch_start // BATCH_SIZE) % 5 == 0:
            print(f"  ... {batch_end}/{ORDERS} 订单已处理")
    set_sequence(cur, "order_items")
    conn.commit()
    actual_oi = oi_id - BASE_ID
    print(f"  ✓ 订单明细完成: {actual_oi} 条 ({time.time()-t0:.1f}s)")

    # ===== 7. Purchase Orders =====
    print(f"\n[7/14] 生成采购单 {PURCHASE_ORDERS} 条...")
    po_ids = list(range(BASE_ID, BASE_ID + PURCHASE_ORDERS))
    for batch_start in range(0, PURCHASE_ORDERS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, PURCHASE_ORDERS)
        rows = []
        for i in range(batch_start, batch_end):
            poid = po_ids[i]
            dt = random_date()
            total = random_price(500, 100000)
            status = random.choice(PO_STATUSES)
            rows.append((
                poid, f"ST-PO-{dt.strftime('%Y%m%d')}-{i+1:05d}",
                random.choice(supplier_ids), status, total, 0, None,
                random.choice(warehouse_ids), None,
                random.choice(user_ids), None, None, None, None,
                None, None, False, 0, 0,
                account_set_id, None, None, 0,
                f"[STRESS_TEST]", dt, dt
            ))
        copy_batch(cur, "purchase_orders", (
            "id", "po_no", "supplier_id", "status", "total_amount", "rebate_used", "remark",
            "target_warehouse_id", "target_location_id",
            "creator_id", "reviewed_by_id", "reviewed_at", "paid_by_id", "paid_at",
            "payment_method", "return_tracking_no", "is_refunded", "return_amount", "credit_used",
            "account_set_id", "returned_by_id", "returned_at", "rebate_amount",
            "po_remark", "created_at", "updated_at"
        ))
        conn.commit()
    set_sequence(cur, "purchase_orders")
    conn.commit()
    print(f"  ✓ 采购单完成 ({time.time()-t0:.1f}s)")

    # ===== 8. Purchase Order Items =====
    total_poi = PURCHASE_ORDERS * PO_ITEMS_PER_PO
    print(f"\n[8/14] 生成采购明细 ~{total_poi} 条...")
    poi_id = BASE_ID
    for batch_start in range(0, PURCHASE_ORDERS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, PURCHASE_ORDERS)
        rows = []
        for i in range(batch_start, batch_end):
            poid = po_ids[i]
            n_items = random.randint(1, 5)
            for _ in range(n_items):
                pid = random.choice(product_ids)
                qty = random.randint(5, 100)
                tax_incl = random_price(50, 3000)
                tax_rate = 0.13
                tax_excl = round(tax_incl / (1 + tax_rate), 2)
                amount = round(tax_incl * qty, 2)
                rows.append((
                    poi_id, poid, pid, qty, tax_incl, tax_rate, tax_excl, amount,
                    qty, 0, 0, random.choice(warehouse_ids), None
                ))
                poi_id += 1
        copy_batch(cur, "purchase_order_items", (
            "id", "purchase_order_id", "product_id", "quantity",
            "tax_inclusive_price", "tax_rate", "tax_exclusive_price", "amount",
            "received_quantity", "returned_quantity", "rebate_amount",
            "target_warehouse_id", "target_location_id"
        ), rows)
        conn.commit()
    set_sequence(cur, "purchase_order_items")
    conn.commit()
    actual_poi = poi_id - BASE_ID
    print(f"  ✓ 采购明细完成: {actual_poi} 条 ({time.time()-t0:.1f}s)")

    # ===== 9. Shipments =====
    print(f"\n[9/14] 生成物流记录 {SHIPMENTS} 条...")
    shipment_ids = list(range(BASE_ID, BASE_ID + SHIPMENTS))
    for batch_start in range(0, SHIPMENTS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, SHIPMENTS)
        rows = []
        for i in range(batch_start, batch_end):
            sid = shipment_ids[i]
            oid = random.choice(order_ids)
            carrier = random.choice(CARRIERS)
            dt = random_date()
            tracking = f"ST{random.randint(100000000000, 999999999999)}"
            rows.append((
                sid, f"ST-SH-{i+1:06d}", oid, carrier, CARRIER_NAMES[carrier],
                tracking, "signed", "已签收", None, None, False, None, dt, dt
            ))
        copy_batch(cur, "shipments", (
            "id", "shipment_no", "order_id", "carrier_code", "carrier_name",
            "tracking_no", "status", "status_text", "last_tracking_info", "phone",
            "kd100_subscribed", "sn_code", "created_at", "updated_at"
        ), rows)
        conn.commit()
    set_sequence(cur, "shipments")
    conn.commit()
    print(f"  ✓ 物流完成 ({time.time()-t0:.1f}s)")

    # ===== 10. Shipment Items =====
    total_si = int(SHIPMENTS * SHIPMENT_ITEMS_PER_SHIP)
    print(f"\n[10/14] 生成物流明细 ~{total_si} 条...")
    # 需要有效的 order_item_id — 使用生成的范围
    oi_max_id = oi_id - 1  # order_items 最大 ID
    si_id = BASE_ID
    for batch_start in range(0, SHIPMENTS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, SHIPMENTS)
        rows = []
        for i in range(batch_start, batch_end):
            sid = shipment_ids[i]
            n_items = random.choice([1, 1, 1, 2, 2, 3])
            for _ in range(n_items):
                rows.append((
                    si_id, sid,
                    random.randint(BASE_ID, oi_max_id),  # order_item_id
                    random.choice(product_ids),
                    random.randint(1, 10), None
                ))
                si_id += 1
        copy_batch(cur, "shipment_items", (
            "id", "shipment_id", "order_item_id", "product_id", "quantity", "sn_codes"
        ), rows)
        conn.commit()
    set_sequence(cur, "shipment_items")
    conn.commit()
    actual_si = si_id - BASE_ID
    print(f"  ✓ 物流明细完成: {actual_si} 条 ({time.time()-t0:.1f}s)")

    # ===== 11. Stock Logs =====
    print(f"\n[11/14] 生成库存日志 {STOCK_LOGS} 条...")
    change_types = ["sale", "purchase", "adjustment", "return", "transfer"]
    sl_id = BASE_ID
    for batch_start in range(0, STOCK_LOGS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, STOCK_LOGS)
        rows = []
        for i in range(batch_start, batch_end):
            pid = random.choice(product_ids)
            wid = random.choice(warehouse_ids)
            qty = random.randint(-50, 100)
            before = random.randint(0, 500)
            after = max(0, before + qty)
            dt = random_date()
            rows.append((
                sl_id, pid, wid,
                random.choice(change_types), qty, before, after,
                "order", random.randint(1, ORDERS),
                f"[STRESS_TEST]", random.choice(user_ids), dt
            ))
            sl_id += 1
        copy_batch(cur, "stock_logs", (
            "id", "product_id", "warehouse_id",
            "change_type", "quantity", "before_qty", "after_qty",
            "reference_type", "reference_id",
            "remark", "creator_id", "created_at"
        ), rows)
        conn.commit()
        if (batch_start // BATCH_SIZE) % 5 == 0:
            print(f"  ... {batch_end}/{STOCK_LOGS}")
    set_sequence(cur, "stock_logs")
    conn.commit()
    print(f"  ✓ 库存日志完成 ({time.time()-t0:.1f}s)")

    # ===== 12. Vouchers =====
    print(f"\n[12/14] 生成凭证 {VOUCHERS} 条...")
    voucher_ids = list(range(BASE_ID, BASE_ID + VOUCHERS))
    for batch_start in range(0, VOUCHERS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, VOUCHERS)
        rows = []
        for i in range(batch_start, batch_end):
            vid = voucher_ids[i]
            dt = random_date()
            period = dt.strftime("%Y-%m")
            vtype = random.choice(VOUCHER_TYPES)
            amount = random_price(100, 50000)
            rows.append((
                vid, account_set_id, vtype, f"ST-V-{period}-{i+1:06d}",
                period, dt.date().isoformat(), f"[STRESS_TEST] 压测凭证{i+1}",
                amount, amount, "posted", 0,
                random.choice(user_ids), None, None, None, None,
                None, None, dt, dt
            ))
        copy_batch(cur, "vouchers", (
            "id", "account_set_id", "voucher_type", "voucher_no",
            "period_name", "voucher_date", "summary",
            "total_debit", "total_credit", "status", "attachment_count",
            "creator_id", "approved_by_id", "approved_at", "posted_by_id", "posted_at",
            "source_type", "source_bill_id", "created_at", "updated_at"
        ), rows)
        conn.commit()
    set_sequence(cur, "vouchers")
    conn.commit()
    print(f"  ✓ 凭证完成 ({time.time()-t0:.1f}s)")

    # ===== 13. Voucher Entries =====
    total_ve = VOUCHERS * VOUCHER_ENTRIES_PER_V
    print(f"\n[13/14] 生成凭证分录 {total_ve} 条...")
    ve_id = BASE_ID
    for batch_start in range(0, VOUCHERS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, VOUCHERS)
        rows = []
        for i in range(batch_start, batch_end):
            vid = voucher_ids[i]
            amount = random_price(100, 50000)
            # 借方分录
            rows.append((
                ve_id, vid, 1, f"[STRESS_TEST]",
                random.choice(account_ids), amount, 0,
                None, None, None, None, None, None
            ))
            ve_id += 1
            # 贷方分录
            rows.append((
                ve_id, vid, 2, f"[STRESS_TEST]",
                random.choice(account_ids), 0, amount,
                None, None, None, None, None, None
            ))
            ve_id += 1
        copy_batch(cur, "voucher_entries", (
            "id", "voucher_id", "line_no", "summary",
            "account_id", "debit_amount", "credit_amount",
            "aux_customer_id", "aux_supplier_id", "aux_employee_id",
            "aux_department_id", "aux_product_id", "aux_bank_account_id"
        ), rows)
        conn.commit()
    set_sequence(cur, "voucher_entries")
    conn.commit()
    print(f"  ✓ 凭证分录完成 ({time.time()-t0:.1f}s)")

    # ===== 14. Receivable Bills =====
    print(f"\n[14a/14] 生成应收单 {RECEIVABLE_BILLS} 条...")
    for batch_start in range(0, RECEIVABLE_BILLS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, RECEIVABLE_BILLS)
        rows = []
        rb_id = BASE_ID + batch_start
        for i in range(batch_start, batch_end):
            dt = random_date()
            amount = random_price(100, 50000)
            received = round(amount * random.choice([0, 0.3, 0.5, 0.8, 1.0]), 2)
            unreceived = round(amount - received, 2)
            status = "completed" if unreceived == 0 else ("partial" if received > 0 else "pending")
            rows.append((
                rb_id, account_set_id, random.choice(customer_ids),
                random.choice(order_ids),
                f"ST-AR-{i+1:06d}", dt.date().isoformat(),
                amount, received, unreceived, status,
                None, None, f"[STRESS_TEST]", random.choice(user_ids), dt, dt
            ))
            rb_id += 1
        copy_batch(cur, "receivable_bills", (
            "id", "account_set_id", "customer_id", "order_id",
            "bill_no", "bill_date", "total_amount", "received_amount",
            "unreceived_amount", "status",
            "voucher_id", "voucher_no", "remark", "creator_id", "created_at", "updated_at"
        ), rows)
        conn.commit()
    set_sequence(cur, "receivable_bills")
    conn.commit()
    print(f"  ✓ 应收单完成 ({time.time()-t0:.1f}s)")

    # ===== 14b. Payable Bills =====
    print(f"\n[14b/14] 生成应付单 {PAYABLE_BILLS} 条...")
    for batch_start in range(0, PAYABLE_BILLS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, PAYABLE_BILLS)
        rows = []
        pb_id = BASE_ID + batch_start
        for i in range(batch_start, batch_end):
            dt = random_date()
            amount = random_price(500, 100000)
            paid = round(amount * random.choice([0, 0.5, 1.0, 1.0]), 2)
            unpaid = round(amount - paid, 2)
            status = "completed" if unpaid == 0 else ("partial" if paid > 0 else "pending")
            rows.append((
                pb_id, account_set_id, random.choice(supplier_ids),
                random.choice(po_ids),
                f"ST-AP-{i+1:05d}", dt.date().isoformat(),
                amount, paid, unpaid, status,
                None, None, f"[STRESS_TEST]", random.choice(user_ids), dt, dt
            ))
            pb_id += 1
        copy_batch(cur, "payable_bills", (
            "id", "account_set_id", "supplier_id", "purchase_order_id",
            "bill_no", "bill_date", "total_amount", "paid_amount",
            "unpaid_amount", "status",
            "voucher_id", "voucher_no", "remark", "creator_id", "created_at", "updated_at"
        ), rows)
        conn.commit()
    set_sequence(cur, "payable_bills")
    conn.commit()
    print(f"  ✓ 应付单完成 ({time.time()-t0:.1f}s)")

    # ===== 15. Operation Logs =====
    print(f"\n[15/14] 生成操作日志 {OPERATION_LOGS} 条...")
    actions = ["创建", "编辑", "审核", "删除", "导出"]
    target_types = ["order", "purchase_order", "product", "customer", "payment"]
    for batch_start in range(0, OPERATION_LOGS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, OPERATION_LOGS)
        rows = []
        ol_id = BASE_ID + batch_start
        for i in range(batch_start, batch_end):
            dt = random_date()
            rows.append((
                ol_id, random.choice(user_ids),
                random.choice(actions), random.choice(target_types),
                random.randint(1, 100000),
                f"[STRESS_TEST] 压测操作日志", dt
            ))
            ol_id += 1
        copy_batch(cur, "operation_logs", (
            "id", "operator_id", "action", "target_type", "target_id", "detail", "created_at"
        ), rows)
        conn.commit()
        if (batch_start // BATCH_SIZE) % 5 == 0:
            print(f"  ... {batch_end}/{OPERATION_LOGS}")
    set_sequence(cur, "operation_logs")
    conn.commit()
    print(f"  ✓ 操作日志完成 ({time.time()-t0:.1f}s)")

    # ===== 完成 =====
    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print(f"数据生成完成！总耗时: {elapsed:.1f}s")
    print("=" * 60)

    # 统计
    cur.execute("SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20")
    print("\n各表数据量（TOP 20）:")
    total = 0
    for name, count in cur.fetchall():
        print(f"  {name:30s} {count:>10,}")
        total += count
    print(f"  {'总计':30s} {total:>10,}")

    # 强制 ANALYZE 以更新统计
    print("\n执行 ANALYZE 更新统计信息...")
    conn.autocommit = True
    cur.execute("ANALYZE")
    print("  ✓ ANALYZE 完成")

    cur.close()
    conn.close()
    print("\n全部完成！")


if __name__ == "__main__":
    main()
```

**Step 2: 验证语法**

```bash
cd /Users/lin/Desktop/erp-4 && python3 -c "import ast; ast.parse(open('backend/scripts/generate_stress_data.py').read()); print('语法OK')"
```

**Step 3: 提交**

```bash
git add backend/scripts/generate_stress_data.py
git commit -m "feat: 压力测试数据生成脚本 — COPY 协议批量导入 ~120 万条"
```

---

### Task 2: 创建数据清除脚本

**Files:**
- Create: `backend/scripts/cleanup_stress_data.py`

**Step 1: 创建清除脚本**

```python
#!/usr/bin/env python3
"""
ERP 压力测试数据清除器
按 FK 依赖逆序删除所有 id >= 100000 的测试数据，重置序列

用法: docker exec erp-4-erp-1 python /app/scripts/cleanup_stress_data.py
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
            cur.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 1)
                )
            """)
            conn.commit()
        except Exception:
            conn.rollback()

    elapsed = time.time() - t0
    print(f"\n清除完成！共删除 {total_deleted:,} 条数据，耗时 {elapsed:.1f}s")

    # 执行 VACUUM ANALYZE
    print("\n执行 VACUUM ANALYZE 释放空间...")
    conn.autocommit = True
    cur.execute("VACUUM ANALYZE")
    print("  ✓ VACUUM ANALYZE 完成")

    # 输出当前数据量
    cur.execute("SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20")
    print("\n当前各表数据量:")
    for name, count in cur.fetchall():
        if count > 0:
            print(f"  {name:30s} {count:>10,}")

    cur.close()
    conn.close()
    print("\n全部完成！")


if __name__ == "__main__":
    main()
```

**Step 2: 验证语法**

```bash
python3 -c "import ast; ast.parse(open('backend/scripts/cleanup_stress_data.py').read()); print('语法OK')"
```

**Step 3: 提交**

```bash
git add backend/scripts/cleanup_stress_data.py
git commit -m "feat: 压力测试数据清除脚本 — 按 FK 逆序清除 + VACUUM"
```

---

### Task 3: 执行数据生成并验证

**Step 1: 在 Docker 容器内运行生成脚本**

```bash
docker exec erp-4-erp-1 python /app/scripts/generate_stress_data.py
```

预期耗时约 2-5 分钟，输出各表生成进度和最终统计。

**Step 2: 验证数据量**

```bash
docker exec erp-4-db-1 psql -U erp -d erp -c "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20"
```

预期 order_items ~300k, stock_logs ~200k, orders ~100k 等。

**Step 3: 验证应用正常**

重启容器后访问仪表盘，确认页面可以正常加载：

```bash
docker compose restart erp
```

**Step 4: 提交**

```bash
git add -A && git commit -m "chore: 压测数据生成验证完成"
```

---

### Task 4: 性能验证（压测关键页面）

**Step 1: 检查仪表盘加载时间**

登录系统，检查 `/api/dashboard/stats` 响应时间。

**Step 2: 检查列表页分页**

访问订单列表、客户列表、采购列表，确认分页正常、响应时间 < 2s。

**Step 3: 检查导出功能**

尝试导出商品、采购单 CSV，确认流式响应正常。

**Step 4: 若发现性能瓶颈**

记录具体接口和响应时间，制定进一步优化方案。
