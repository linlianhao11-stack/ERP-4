"""Dashboard路由 (PostgreSQL 专用 - 使用原生 SQL 聚合以获得最佳性能)"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from tortoise import connections

from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.utils.time import now

router = APIRouter(prefix="/api", tags=["仪表盘"])


@router.get("/dashboard")
async def get_dashboard(user: User = Depends(require_permission("dashboard"))):
    today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = today - timedelta(days=30)

    has_finance = user.role == "admin" or "finance" in (user.permissions or [])
    conn = connections.get("default")

    # 今日销售额 + 毛利（常规订单 + 代采代发 UNION 聚合）
    sales_agg = await conn.execute_query_dict("""
        SELECT COALESCE(SUM(total_sales), 0) as total_sales,
               COALESCE(SUM(total_profit), 0) as total_profit
        FROM (
            SELECT SUM(total_amount) as total_sales, SUM(total_profit) as total_profit
            FROM orders WHERE created_at >= $1
              AND order_type IN ('CASH', 'CREDIT', 'CONSIGN_SETTLE')
            UNION ALL
            SELECT SUM(sale_total), SUM(gross_profit)
            FROM dropship_orders WHERE created_at >= $1
              AND status NOT IN ('draft', 'cancelled')
        ) combined
    """, [today])
    today_sales = float(sales_agg[0]["total_sales"]) if sales_agg else 0

    # 今日毛利（DB 聚合）
    today_profit = None
    if has_finance:
        today_profit = float(sales_agg[0]["total_profit"]) if sales_agg else 0
        ret_agg = await conn.execute_query_dict("""
            SELECT COALESCE(SUM(total_profit), 0) as ret_profit
            FROM orders WHERE created_at >= $1 AND order_type = 'RETURN'
        """, [today])
        if ret_agg:
            today_profit += float(ret_agg[0]["ret_profit"])

    # 库存总值 + 库龄分布（单条 SQL 聚合，使用参数化日期阈值避免 INTERVAL 语法依赖）
    now_dt = now()
    thirty_days_threshold = now_dt - timedelta(days=30)
    ninety_days_threshold = now_dt - timedelta(days=90)
    stock_agg = await conn.execute_query_dict("""
        SELECT
            COALESCE(SUM(CASE WHEN NOT w.is_virtual THEN ws.quantity * p.cost_price ELSE 0 END), 0) as stock_value,
            COALESCE(SUM(CASE WHEN w.is_virtual THEN ws.quantity * p.cost_price ELSE 0 END), 0) as consignment_value,
            COALESCE(SUM(CASE WHEN NOT w.is_virtual AND (ws.weighted_entry_date IS NULL OR ws.weighted_entry_date > $1) THEN ws.quantity ELSE 0 END), 0) as normal_count,
            COALESCE(SUM(CASE WHEN NOT w.is_virtual AND ws.weighted_entry_date IS NOT NULL AND ws.weighted_entry_date <= $1 AND ws.weighted_entry_date > $2 THEN ws.quantity ELSE 0 END), 0) as slow_count,
            COALESCE(SUM(CASE WHEN NOT w.is_virtual AND ws.weighted_entry_date IS NOT NULL AND ws.weighted_entry_date <= $2 THEN ws.quantity ELSE 0 END), 0) as dead_count
        FROM warehouse_stocks ws
        JOIN products p ON ws.product_id = p.id
        JOIN warehouses w ON ws.warehouse_id = w.id
        WHERE ws.quantity > 0
    """, [thirty_days_threshold, ninety_days_threshold])
    row = stock_agg[0] if stock_agg else {}
    total_stock_value = float(row.get("stock_value", 0))
    consignment_value = float(row.get("consignment_value", 0))
    normal_count = int(row.get("normal_count", 0))
    slow_count = int(row.get("slow_count", 0))
    dead_count = int(row.get("dead_count", 0))

    # 总应收（DB 聚合）
    recv_agg = await conn.execute_query_dict(
        "SELECT COALESCE(SUM(balance), 0) as total FROM customers WHERE is_active = true"
    )
    total_receivable = float(recv_agg[0]["total"]) if recv_agg else 0

    # Top 10 畅销商品（常规订单 + 代采代发 UNION 聚合）
    top_products = await conn.execute_query_dict("""
        SELECT name, sku, SUM(quantity) as quantity, SUM(amount) as amount
        FROM (
            SELECT p.name, p.sku, oi.quantity, oi.amount
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            WHERE o.created_at >= $1
              AND o.order_type IN ('CASH', 'CREDIT', 'CONSIGN_SETTLE')
            UNION ALL
            SELECT d.product_name as name, '' as sku, d.quantity, d.sale_total as amount
            FROM dropship_orders d
            WHERE d.created_at >= $1
              AND d.status NOT IN ('draft', 'cancelled')
        ) combined
        GROUP BY name, sku
        ORDER BY quantity DESC
        LIMIT 10
    """, [thirty_days_ago])
    top_products = [
        {"name": r["name"], "sku": r["sku"], "quantity": int(r["quantity"]), "amount": float(r["amount"])}
        for r in top_products
    ]

    # 今日发货数量（已发货的发货单数）
    ship_agg = await conn.execute_query_dict("""
        SELECT COUNT(*) as cnt FROM shipments
        WHERE updated_at >= $1 AND status IN ('shipped', 'in_transit', 'signed')
    """, [today])
    today_shipments = int(ship_agg[0]["cnt"]) if ship_agg else 0

    result = {
        "today_sales": today_sales,
        "today_shipments": today_shipments,
        "total_receivable": total_receivable,
        "inventory_age": {"normal": normal_count, "slow": slow_count, "dead": dead_count},
        "top_products": top_products
    }

    if has_finance:
        result["today_profit"] = today_profit
        result["stock_value"] = total_stock_value
        result["consignment_value"] = consignment_value

    return result


@router.get("/todo-counts")
async def get_todo_counts(user: User = Depends(get_current_user)):
    """返回各模块待办数量，按用户权限过滤"""
    perms = user.permissions or []
    is_admin = user.role == "admin"
    conn = connections.get("default")
    counts = {}

    # 待发货（logistics 权限）
    if is_admin or "logistics" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM orders WHERE shipping_status IN ('pending', 'partial')"
            " AND order_type IN ('CASH', 'CREDIT', 'CONSIGN_OUT')"
        )
        counts["pending_shipment"] = int(r[0]["c"]) if r else 0

    # 待审核采购（purchase 权限）
    if is_admin or "purchase" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM purchase_orders WHERE status = 'pending_review'"
        )
        counts["pending_review"] = int(r[0]["c"]) if r else 0

    # 在途采购（purchase 权限）
    if is_admin or "purchase" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM purchase_orders WHERE status IN ('paid', 'partial')"
        )
        counts["in_transit"] = int(r[0]["c"]) if r else 0

    # 待付款采购单（finance 权限）
    if is_admin or "finance" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM purchase_orders WHERE status = 'pending'"
        )
        counts["pending_payment"] = int(r[0]["c"]) if r else 0

    # 待收款（finance 权限）
    if is_admin or "finance" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM customers WHERE balance > 0 AND is_active = true"
        )
        counts["pending_collection"] = int(r[0]["c"]) if r else 0

    # 低库存预警（stock_view 权限）— 非虚拟仓合计 < 10 的活跃产品
    if is_admin or "stock_view" in perms:
        r = await conn.execute_query_dict("""
            SELECT COUNT(*) as c FROM (
                SELECT ws.product_id
                FROM warehouse_stocks ws
                JOIN warehouses w ON ws.warehouse_id = w.id
                JOIN products p ON ws.product_id = p.id
                WHERE NOT w.is_virtual AND p.is_active = true AND ws.quantity >= 0
                GROUP BY ws.product_id
                HAVING SUM(ws.quantity) < 10
            ) sub
        """)
        counts["low_stock"] = int(r[0]["c"]) if r else 0

    # 待处理应收（accounting_view 权限）
    if is_admin or "accounting_view" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM receivable_bills WHERE status IN ('pending', 'partial')"
        )
        counts["pending_receivable"] = int(r[0]["c"]) if r else 0

    # 代采代发待付款（dropship 权限）
    if is_admin or "dropship" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM dropship_orders WHERE status = 'pending_payment'"
        )
        counts["ds_pending_payment"] = int(r[0]["c"]) if r else 0

    # 代采代发已付待发（dropship 权限）
    if is_admin or "dropship" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM dropship_orders WHERE status = 'paid_pending_ship'"
        )
        counts["ds_paid_pending_ship"] = int(r[0]["c"]) if r else 0

    # 代采代发催付未处理（dropship 权限）
    if is_admin or "dropship" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM dropship_orders WHERE status = 'pending_payment' AND urged_at IS NOT NULL"
        )
        counts["ds_urged_unpaid"] = int(r[0]["c"]) if r else 0

    return counts


@router.get("/dashboard/sales-trend")
async def get_sales_trend(
    days: int = Query(default=30, ge=7, le=90),
    user: User = Depends(require_permission("dashboard"))
):
    """返回最近 N 天的每日销售额趋势"""
    start_date = now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    conn = connections.get("default")
    rows = await conn.execute_query_dict("""
        SELECT date, COALESCE(SUM(amount), 0) as amount
        FROM (
            SELECT DATE(created_at) as date, total_amount as amount
            FROM orders
            WHERE created_at >= $1
              AND order_type IN ('CASH', 'CREDIT', 'CONSIGN_SETTLE')
            UNION ALL
            SELECT DATE(created_at) as date, sale_total as amount
            FROM dropship_orders
            WHERE created_at >= $1
              AND status NOT IN ('draft', 'cancelled')
        ) combined
        GROUP BY date
        ORDER BY date
    """, [start_date])

    # 填充没有数据的日期为 0
    result = []
    current = start_date
    end = now().replace(hour=0, minute=0, second=0, microsecond=0)
    date_map = {str(r["date"]): float(r["amount"]) for r in rows}
    while current <= end:
        d = str(current.date())
        result.append({"date": d, "amount": date_map.get(d, 0)})
        current += timedelta(days=1)

    return result


@router.get("/dashboard/recent-orders")
async def get_recent_orders(
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(require_permission("dashboard"))
):
    """返回最近的销售订单"""
    conn = connections.get("default")
    rows = await conn.execute_query_dict("""
        SELECT * FROM (
            SELECT o.id, o.order_no, o.order_type, o.total_amount,
                   o.shipping_status, o.is_cleared, o.created_at,
                   c.name as customer_name,
                   'order' as source
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            UNION ALL
            SELECT d.id, d.ds_no as order_no, 'DROPSHIP' as order_type, d.sale_total as total_amount,
                   d.status as shipping_status, false as is_cleared, d.created_at,
                   c2.name as customer_name,
                   'dropship' as source
            FROM dropship_orders d
            LEFT JOIN customers c2 ON d.customer_id = c2.id
            WHERE d.status NOT IN ('draft', 'cancelled')
        ) combined
        ORDER BY created_at DESC
        LIMIT $1
    """, [limit])

    return [
        {
            "id": r["id"],
            "order_no": r["order_no"],
            "order_type": r["order_type"],
            "total_amount": float(r["total_amount"]),
            "shipping_status": r["shipping_status"],
            "is_cleared": r["is_cleared"],
            "customer_name": r["customer_name"] or "-",
            "created_at": str(r["created_at"])[:19].replace("T", " ") if r["created_at"] else "",
            "source": r["source"],
        }
        for r in rows
    ]
