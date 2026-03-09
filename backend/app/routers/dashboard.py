"""Dashboard路由 (PostgreSQL 专用 - 使用原生 SQL 聚合以获得最佳性能)"""
from datetime import timedelta

from fastapi import APIRouter, Depends
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

    # 今日销售额（DB 聚合）
    sales_agg = await conn.execute_query_dict("""
        SELECT COALESCE(SUM(total_amount), 0) as total_sales,
               COALESCE(SUM(total_profit), 0) as total_profit
        FROM orders WHERE created_at >= $1
          AND order_type IN ('CASH', 'CREDIT', 'CONSIGN_SETTLE')
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

    # Top 10 畅销商品（DB 聚合 + GROUP BY）
    top_products = await conn.execute_query_dict("""
        SELECT p.name, p.sku,
               SUM(oi.quantity) as quantity,
               SUM(oi.amount) as amount
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN products p ON oi.product_id = p.id
        WHERE o.created_at >= $1
          AND o.order_type IN ('CASH', 'CREDIT', 'CONSIGN_SETTLE')
        GROUP BY p.id, p.name, p.sku
        ORDER BY quantity DESC
        LIMIT 10
    """, [thirty_days_ago])
    top_products = [
        {"name": r["name"], "sku": r["sku"], "quantity": int(r["quantity"]), "amount": float(r["amount"])}
        for r in top_products
    ]

    result = {
        "today_sales": today_sales,
        "total_receivable": total_receivable,
        "inventory_age": {"normal": normal_count, "slow": slow_count, "dead": dead_count},
        "top_products": top_products
    }

    if has_finance:
        result["today_profit"] = today_profit
        result["stock_value"] = total_stock_value
        result["consignment_value"] = consignment_value

    return result
