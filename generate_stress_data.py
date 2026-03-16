#!/usr/bin/env python3
"""
ERP 压力测试数据生成器
通过 PostgreSQL COPY 协议批量导入 ~120 万条测试数据
所有测试数据 ID >= 100000，便于清除

用法: docker exec erp-4-erp-1 python /app/generate_stress_data.py
"""
import io
import os
import sys
import time
import random
from datetime import datetime, timedelta

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
ORDER_ITEMS_PER_ORDER = 3
PURCHASE_ORDERS = 20_000
PO_ITEMS_PER_PO = 3
WAREHOUSE_STOCKS = 20_000
STOCK_LOGS = 200_000
SHIPMENTS = 80_000
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
    cur.execute(
        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
        f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
    )


# ---------- 数据池 ----------
BRANDS = [
    "华为", "小米", "苹果", "联想", "戴尔", "惠普", "三星", "索尼", "佳能", "大疆",
    "罗技", "雷蛇", "飞利浦", "松下", "海尔", "格力", "美的", "TCL", "创维", "TP-Link",
]
CATEGORIES = [
    "手机", "笔记本", "平板", "显示器", "键盘", "鼠标", "耳机", "音箱", "摄像头", "路由器",
    "硬盘", "内存", "CPU", "显卡", "主板", "电源", "机箱", "线缆", "充电器", "保护壳",
]
UNITS = ["个", "台", "件", "套", "箱", "盒", "卷", "米", "条", "把"]
ORDER_TYPES = ["CASH", "CREDIT", "CONSIGN_OUT"]
ORDER_STATUSES = ["completed", "completed", "completed", "completed", "pending"]
SHIPPING_STATUSES = ["shipped", "shipped", "shipped", "pending", "partial"]
PO_STATUSES = ["completed", "completed", "completed", "pending_review", "paid"]
VOUCHER_TYPES = ["记", "收", "付", "转"]
CARRIERS = ["shunfeng", "yuantong", "zhongtong", "yunda", "shentong", "ems", "jd", "jtexpress"]
CARRIER_NAMES = {
    "shunfeng": "顺丰速运", "yuantong": "圆通速递", "zhongtong": "中通快递",
    "yunda": "韵达快递", "shentong": "申通快递", "ems": "EMS",
    "jd": "京东物流", "jtexpress": "极兔速递",
}


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
        print("ERROR: 没有找到可用仓库")
        sys.exit(1)

    cur.execute("SELECT id FROM users WHERE is_active LIMIT 3")
    user_ids = [r[0] for r in cur.fetchall()]
    if not user_ids:
        user_ids = [1]

    cur.execute("SELECT id FROM account_sets WHERE is_active LIMIT 1")
    row = cur.fetchone()
    account_set_id = row[0] if row else 1

    cur.execute(
        "SELECT id FROM chart_of_accounts WHERE account_set_id = %s AND is_leaf AND is_active LIMIT 20",
        (account_set_id,),
    )
    account_ids = [r[0] for r in cur.fetchall()]
    if not account_ids:
        account_ids = [1]

    t0 = time.time()

    # ===== 1. Products =====
    print(f"\n[1/15] 生成商品 {PRODUCTS} 条...")
    product_ids = list(range(BASE_ID, BASE_ID + PRODUCTS))
    rows = []
    for i, pid in enumerate(product_ids):
        brand = random.choice(BRANDS)
        cat = random.choice(CATEGORIES)
        cost = random_price(50, 2000)
        retail = round(cost * random.uniform(1.2, 2.5), 2)
        dt = random_date()
        rows.append((
            pid,
            f"ST-{brand[0]}{cat[0]}-{i + 1:05d}",
            f"{brand} {cat} 型号{i + 1}",
            brand, cat, retail, cost,
            random.choice(UNITS),
            f"[STRESS_TEST] 压测商品{i + 1}",
            13.00, True, dt, dt,
        ))
    copy_batch(cur, "products", (
        "id", "sku", "name", "brand", "category", "retail_price", "cost_price",
        "unit", "description", "tax_rate", "is_active", "created_at", "updated_at",
    ), rows)
    set_sequence(cur, "products")
    conn.commit()
    print(f"  ✓ 商品完成 ({time.time() - t0:.1f}s)")

    # ===== 2. Customers =====
    print(f"\n[2/15] 生成客户 {CUSTOMERS} 条...")
    customer_ids = list(range(BASE_ID, BASE_ID + CUSTOMERS))
    rows = []
    for i, cid in enumerate(customer_ids):
        dt = random_date()
        rows.append((
            cid,
            f"压测客户-{i + 1:04d}",
            f"联系人{i + 1}",
            f"138{random.randint(10000000, 99999999)}",
            f"测试地址{i + 1}号",
            0, 0, True, dt, dt,
        ))
    copy_batch(cur, "customers", (
        "id", "name", "contact_person", "phone", "address",
        "balance", "rebate_balance", "is_active", "created_at", "updated_at",
    ), rows)
    set_sequence(cur, "customers")
    conn.commit()
    print(f"  ✓ 客户完成 ({time.time() - t0:.1f}s)")

    # ===== 3. Suppliers =====
    print(f"\n[3/15] 生成供应商 {SUPPLIERS} 条...")
    supplier_ids = list(range(BASE_ID, BASE_ID + SUPPLIERS))
    rows = []
    for i, sid in enumerate(supplier_ids):
        dt = random_date()
        rows.append((
            sid,
            f"压测供应商-{i + 1:03d}",
            f"供联系人{i + 1}",
            f"139{random.randint(10000000, 99999999)}",
            f"供应商地址{i + 1}号",
            0, 0, True, dt, dt,
        ))
    copy_batch(cur, "suppliers", (
        "id", "name", "contact_person", "phone", "address",
        "rebate_balance", "credit_balance", "is_active", "created_at", "updated_at",
    ), rows)
    set_sequence(cur, "suppliers")
    conn.commit()
    print(f"  ✓ 供应商完成 ({time.time() - t0:.1f}s)")

    # ===== 4. Warehouse Stocks =====
    print(f"\n[4/15] 生成库存记录 {WAREHOUSE_STOCKS} 条...")
    ws_id = BASE_ID
    used_combos = set()
    rows = []
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
        rows.append((
            ws_id, wid, pid, None, qty, 0, cost, dt, dt, dt,
        ))
        ws_id += 1
    copy_batch(cur, "warehouse_stocks", (
        "id", "warehouse_id", "product_id", "location_id",
        "quantity", "reserved_qty", "weighted_cost",
        "weighted_entry_date", "last_activity_at", "created_at",
    ), rows)
    set_sequence(cur, "warehouse_stocks")
    conn.commit()
    print(f"  ✓ 库存完成 ({time.time() - t0:.1f}s)")

    # ===== 5. Orders =====
    # orders 表列: id, order_no, order_type, total_amount, total_cost, total_profit,
    #   paid_amount, rebate_used, is_cleared, refunded, remark, created_at,
    #   creator_id, customer_id, warehouse_id, shipping_status, updated_at, account_set_id
    print(f"\n[5/15] 生成订单 {ORDERS} 条...")
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
                oid,
                f"ST-SO-{dt.strftime('%Y%m%d')}-{i + 1:06d}",
                otype, total, cost, profit, paid, 0,
                status == "completed",  # is_cleared
                False,  # refunded
                "[STRESS_TEST]",  # remark
                dt,  # created_at
                random.choice(user_ids),  # creator_id
                random.choice(customer_ids),  # customer_id
                random.choice(warehouse_ids),  # warehouse_id
                ship_status,  # shipping_status
                dt,  # updated_at
                account_set_id,  # account_set_id
            ))
        copy_batch(cur, "orders", (
            "id", "order_no", "order_type", "total_amount", "total_cost", "total_profit",
            "paid_amount", "rebate_used", "is_cleared", "refunded",
            "remark", "created_at", "creator_id", "customer_id", "warehouse_id",
            "shipping_status", "updated_at", "account_set_id",
        ), rows)
        conn.commit()
        if (batch_start // BATCH_SIZE) % 5 == 0:
            print(f"  ... {batch_end}/{ORDERS}")
    set_sequence(cur, "orders")
    conn.commit()
    print(f"  ✓ 订单完成 ({time.time() - t0:.1f}s)")

    # ===== 6. Order Items =====
    total_items = ORDERS * ORDER_ITEMS_PER_ORDER
    print(f"\n[6/15] 生成订单明细 ~{total_items} 条...")
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
                cost_p = round(price * random.uniform(0.4, 0.8), 2)
                amount = round(price * qty, 2)
                profit = round((price - cost_p) * qty, 2)
                rows.append((
                    oi_id, oid, pid, qty, price, cost_p, amount, profit,
                    0, qty, random.choice(warehouse_ids), None,
                ))
                oi_id += 1
        copy_batch(cur, "order_items", (
            "id", "order_id", "product_id", "quantity", "unit_price", "cost_price",
            "amount", "profit", "rebate_amount", "shipped_qty", "warehouse_id", "location_id",
        ), rows)
        conn.commit()
        if (batch_start // BATCH_SIZE) % 5 == 0:
            print(f"  ... {batch_end}/{ORDERS} 订单已处理")
    set_sequence(cur, "order_items")
    conn.commit()
    actual_oi = oi_id - BASE_ID
    print(f"  ✓ 订单明细完成: {actual_oi} 条 ({time.time() - t0:.1f}s)")

    # ===== 7. Purchase Orders =====
    # purchase_orders 列: id, po_no, status, total_amount, rebate_used, remark,
    #   created_at, updated_at, creator_id, supplier_id, target_warehouse_id
    print(f"\n[7/15] 生成采购单 {PURCHASE_ORDERS} 条...")
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
                poid,
                f"ST-PO-{dt.strftime('%Y%m%d')}-{i + 1:05d}",
                status, total, 0,
                "[STRESS_TEST]",  # remark
                dt, dt,  # created_at, updated_at
                random.choice(user_ids),  # creator_id
                random.choice(supplier_ids),  # supplier_id
                random.choice(warehouse_ids),  # target_warehouse_id
                account_set_id,  # account_set_id
            ))
        copy_batch(cur, "purchase_orders", (
            "id", "po_no", "status", "total_amount", "rebate_used",
            "remark", "created_at", "updated_at",
            "creator_id", "supplier_id", "target_warehouse_id", "account_set_id",
        ), rows)
        conn.commit()
    set_sequence(cur, "purchase_orders")
    conn.commit()
    print(f"  ✓ 采购单完成 ({time.time() - t0:.1f}s)")

    # ===== 8. Purchase Order Items =====
    total_poi = PURCHASE_ORDERS * PO_ITEMS_PER_PO
    print(f"\n[8/15] 生成采购明细 ~{total_poi} 条...")
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
                    qty, 0, random.choice(warehouse_ids),
                ))
                poi_id += 1
        copy_batch(cur, "purchase_order_items", (
            "id", "purchase_order_id", "product_id", "quantity",
            "tax_inclusive_price", "tax_rate", "tax_exclusive_price", "amount",
            "received_quantity", "rebate_amount", "target_warehouse_id",
        ), rows)
        conn.commit()
    set_sequence(cur, "purchase_order_items")
    conn.commit()
    actual_poi = poi_id - BASE_ID
    print(f"  ✓ 采购明细完成: {actual_poi} 条 ({time.time() - t0:.1f}s)")

    # ===== 9. Shipments =====
    print(f"\n[9/15] 生成物流记录 {SHIPMENTS} 条...")
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
                sid,
                f"ST-SH-{i + 1:06d}",
                carrier, CARRIER_NAMES[carrier],
                tracking, "signed", "已签收",
                None, None, False, None,
                dt, dt, oid,
            ))
        copy_batch(cur, "shipments", (
            "id", "shipment_no",
            "carrier_code", "carrier_name",
            "tracking_no", "status", "status_text",
            "last_tracking_info", "phone", "kd100_subscribed", "sn_code",
            "created_at", "updated_at", "order_id",
        ), rows)
        conn.commit()
    set_sequence(cur, "shipments")
    conn.commit()
    print(f"  ✓ 物流完成 ({time.time() - t0:.1f}s)")

    # ===== 10. Shipment Items =====
    print(f"\n[10/15] 生成物流明细...")
    oi_max_id = oi_id - 1
    si_id = BASE_ID
    for batch_start in range(0, SHIPMENTS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, SHIPMENTS)
        rows = []
        for i in range(batch_start, batch_end):
            sid = shipment_ids[i]
            n_items = random.choice([1, 1, 1, 2, 2, 3])
            for _ in range(n_items):
                dt = random_date()
                rows.append((
                    si_id, sid,
                    random.randint(BASE_ID, oi_max_id),
                    random.choice(product_ids),
                    random.randint(1, 10), None, dt,
                ))
                si_id += 1
        copy_batch(cur, "shipment_items", (
            "id", "shipment_id", "order_item_id", "product_id",
            "quantity", "sn_codes", "created_at",
        ), rows)
        conn.commit()
    set_sequence(cur, "shipment_items")
    conn.commit()
    actual_si = si_id - BASE_ID
    print(f"  ✓ 物流明细完成: {actual_si} 条 ({time.time() - t0:.1f}s)")

    # ===== 11. Stock Logs =====
    print(f"\n[11/15] 生成库存日志 {STOCK_LOGS} 条...")
    change_types = ["sale", "purchase", "adjustment", "return", "transfer"]
    for batch_start in range(0, STOCK_LOGS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, STOCK_LOGS)
        rows = []
        sl_id = BASE_ID + batch_start
        for i in range(batch_start, batch_end):
            pid = random.choice(product_ids)
            wid = random.choice(warehouse_ids)
            qty = random.randint(-50, 100)
            before = random.randint(0, 500)
            after = max(0, before + qty)
            dt = random_date()
            rows.append((
                sl_id, random.choice(change_types), qty, before, after,
                "order", random.randint(1, ORDERS),
                "[STRESS_TEST]", dt, random.choice(user_ids), pid, wid,
            ))
            sl_id += 1
        copy_batch(cur, "stock_logs", (
            "id", "change_type", "quantity", "before_qty", "after_qty",
            "reference_type", "reference_id",
            "remark", "created_at", "creator_id", "product_id", "warehouse_id",
        ), rows)
        conn.commit()
        if (batch_start // BATCH_SIZE) % 5 == 0:
            print(f"  ... {batch_end}/{STOCK_LOGS}")
    set_sequence(cur, "stock_logs")
    conn.commit()
    print(f"  ✓ 库存日志完成 ({time.time() - t0:.1f}s)")

    # ===== 12. Vouchers =====
    print(f"\n[12/15] 生成凭证 {VOUCHERS} 条...")
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
                vid, vtype,
                f"ST-V-{period}-{i + 1:06d}",
                period, dt.date().isoformat(),
                f"[STRESS_TEST] 压测凭证{i + 1}",
                amount, amount, "posted", 0,
                None, None, None, None,
                dt, dt, account_set_id, None, random.choice(user_ids), None,
            ))
        copy_batch(cur, "vouchers", (
            "id", "voucher_type", "voucher_no",
            "period_name", "voucher_date", "summary",
            "total_debit", "total_credit", "status", "attachment_count",
            "approved_at", "posted_at", "source_type", "source_bill_id",
            "created_at", "updated_at", "account_set_id", "approved_by_id",
            "creator_id", "posted_by_id",
        ), rows)
        conn.commit()
    set_sequence(cur, "vouchers")
    conn.commit()
    print(f"  ✓ 凭证完成 ({time.time() - t0:.1f}s)")

    # ===== 13. Voucher Entries =====
    total_ve = VOUCHERS * VOUCHER_ENTRIES_PER_V
    print(f"\n[13/15] 生成凭证分录 {total_ve} 条...")
    ve_id = BASE_ID
    for batch_start in range(0, VOUCHERS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, VOUCHERS)
        rows = []
        for i in range(batch_start, batch_end):
            vid = voucher_ids[i]
            amount = random_price(100, 50000)
            # 借方
            rows.append((
                ve_id, 1, "[STRESS_TEST]", amount, 0,
                random.choice(account_ids),
                None, None, vid, None, None, None, None,
            ))
            ve_id += 1
            # 贷方
            rows.append((
                ve_id, 2, "[STRESS_TEST]", 0, amount,
                random.choice(account_ids),
                None, None, vid, None, None, None, None,
            ))
            ve_id += 1
        copy_batch(cur, "voucher_entries", (
            "id", "line_no", "summary", "debit_amount", "credit_amount",
            "account_id",
            "aux_customer_id", "aux_supplier_id", "voucher_id",
            "aux_employee_id", "aux_department_id", "aux_product_id", "aux_bank_account_id",
        ), rows)
        conn.commit()
    set_sequence(cur, "voucher_entries")
    conn.commit()
    print(f"  ✓ 凭证分录完成 ({time.time() - t0:.1f}s)")

    # ===== 14. Receivable Bills =====
    print(f"\n[14/15] 生成应收单 {RECEIVABLE_BILLS} 条...")
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
                rb_id,
                f"ST-AR-{i + 1:06d}",
                dt.date().isoformat(), amount, received, unreceived, status,
                None, "[STRESS_TEST]",
                dt, dt,
                account_set_id, random.choice(user_ids),
                random.choice(customer_ids), random.choice(order_ids), None,
            ))
            rb_id += 1
        copy_batch(cur, "receivable_bills", (
            "id", "bill_no", "bill_date", "total_amount", "received_amount",
            "unreceived_amount", "status",
            "voucher_no", "remark",
            "created_at", "updated_at",
            "account_set_id", "creator_id", "customer_id", "order_id", "voucher_id",
        ), rows)
        conn.commit()
    set_sequence(cur, "receivable_bills")
    conn.commit()
    print(f"  ✓ 应收单完成 ({time.time() - t0:.1f}s)")

    # ===== 15. Payable Bills =====
    print(f"\n[15a/15] 生成应付单 {PAYABLE_BILLS} 条...")
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
                pb_id,
                f"ST-AP-{i + 1:05d}",
                dt.date().isoformat(), amount, paid, unpaid, status,
                None, "[STRESS_TEST]",
                dt, dt,
                account_set_id, random.choice(user_ids),
                random.choice(po_ids), random.choice(supplier_ids), None,
            ))
            pb_id += 1
        copy_batch(cur, "payable_bills", (
            "id", "bill_no", "bill_date", "total_amount", "paid_amount",
            "unpaid_amount", "status",
            "voucher_no", "remark",
            "created_at", "updated_at",
            "account_set_id", "creator_id", "purchase_order_id", "supplier_id", "voucher_id",
        ), rows)
        conn.commit()
    set_sequence(cur, "payable_bills")
    conn.commit()
    print(f"  ✓ 应付单完成 ({time.time() - t0:.1f}s)")

    # ===== 16. Operation Logs =====
    print(f"\n[15b/15] 生成操作日志 {OPERATION_LOGS} 条...")
    actions = ["创建", "编辑", "审核", "删除", "导出"]
    target_types = ["order", "purchase_order", "product", "customer", "payment"]
    for batch_start in range(0, OPERATION_LOGS, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, OPERATION_LOGS)
        rows = []
        ol_id = BASE_ID + batch_start
        for i in range(batch_start, batch_end):
            dt = random_date()
            rows.append((
                ol_id,
                random.choice(actions), random.choice(target_types),
                random.randint(1, 100000),
                "[STRESS_TEST] 压测操作日志",
                dt, random.choice(user_ids),
            ))
            ol_id += 1
        copy_batch(cur, "operation_logs", (
            "id", "action", "target_type", "target_id", "detail",
            "created_at", "operator_id",
        ), rows)
        conn.commit()
        if (batch_start // BATCH_SIZE) % 5 == 0:
            print(f"  ... {batch_end}/{OPERATION_LOGS}")
    set_sequence(cur, "operation_logs")
    conn.commit()
    print(f"  ✓ 操作日志完成 ({time.time() - t0:.1f}s)")

    # ===== 完成 =====
    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print(f"数据生成完成！总耗时: {elapsed:.1f}s")
    print("=" * 60)

    # 强制 ANALYZE 更新统计
    print("\n执行 ANALYZE 更新统计信息...")
    conn.autocommit = True
    cur.execute("ANALYZE")
    print("  ✓ ANALYZE 完成")

    # 统计
    cur.execute(
        "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20"
    )
    print("\n各表数据量（TOP 20）:")
    total = 0
    for name, count in cur.fetchall():
        print(f"  {name:35s} {count:>10,}")
        total += count
    print(f"  {'总计':35s} {total:>10,}")

    cur.close()
    conn.close()
    print("\n全部完成！")


if __name__ == "__main__":
    main()
