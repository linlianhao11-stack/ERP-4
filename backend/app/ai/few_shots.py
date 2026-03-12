"""默认 Few-shot 示例 — 引导 LLM 生成正确的 SQL"""
from __future__ import annotations

DEFAULT_FEW_SHOTS = [
    {
        "question": "这个月的销售情况怎么样",
        "sql": "SELECT COUNT(DISTINCT order_no) AS order_count, ROUND(SUM(amount),2) AS total_amount, ROUND(SUM(cost),2) AS total_cost, ROUND(SUM(profit),2) AS total_profit, ROUND(SUM(profit)/NULLIF(SUM(amount),0)*100,2) AS profit_rate FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) AND order_date < date_trunc('month', CURRENT_DATE) + INTERVAL '1 month'",
    },
    {
        "question": "启领这个月毛利多少",
        "sql": "SELECT ROUND(SUM(amount),2) AS total_amount, ROUND(SUM(profit),2) AS total_profit, ROUND(SUM(profit)/NULLIF(SUM(amount),0)*100,2) AS profit_rate FROM vw_sales_detail WHERE account_set_name = '启领' AND order_date >= date_trunc('month', CURRENT_DATE)",
    },
    {
        "question": "哪个客户买得最多",
        "sql": "SELECT customer_name, COUNT(DISTINCT order_no) AS order_count, ROUND(SUM(amount),2) AS total_amount, ROUND(SUM(profit),2) AS total_profit FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) GROUP BY customer_name ORDER BY total_amount DESC LIMIT 20",
    },
    {
        "question": "本月卖得最好的产品Top10",
        "sql": "SELECT product_name, brand, SUM(quantity) AS total_qty, ROUND(SUM(amount),2) AS total_amount FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) GROUP BY product_name, brand ORDER BY total_amount DESC LIMIT 10",
    },
    {
        "question": "这周有什么销售",
        "sql": "SELECT order_no, order_date, customer_name, product_name, quantity, ROUND(amount,2) AS amount FROM vw_sales_detail WHERE order_date >= date_trunc('week', CURRENT_DATE) AND order_date < date_trunc('week', CURRENT_DATE) + INTERVAL '7 days' ORDER BY order_date DESC",
    },
    {
        "question": "这个月采购了多少",
        "sql": "SELECT supplier_name, COUNT(*) AS po_count, ROUND(SUM(amount),2) AS total_amount FROM vw_purchase_detail WHERE purchase_date >= date_trunc('month', CURRENT_DATE) GROUP BY supplier_name ORDER BY total_amount DESC",
    },
    {
        "question": "哪些产品快缺货了",
        "sql": "SELECT sku, product_name, brand, warehouse_name, available_qty FROM vw_inventory_status WHERE available_qty <= 0 ORDER BY available_qty",
    },
    {
        "question": "库存周转率排名",
        "sql": "SELECT sku, product_name, brand, current_stock, sold_30d, ROUND(turnover_rate,2) AS turnover_rate FROM vw_inventory_turnover ORDER BY turnover_rate DESC LIMIT 20",
    },
    {
        "question": "哪些客户欠款最多",
        "sql": "SELECT customer_name, COUNT(*) AS bill_count, ROUND(SUM(unreceived_amount),2) AS total_unreceived FROM vw_receivables WHERE status != 'completed' GROUP BY customer_name ORDER BY total_unreceived DESC LIMIT 20",
    },
    {
        "question": "应收账龄分析",
        "sql": "SELECT CASE WHEN age_days<=30 THEN '0-30天' WHEN age_days<=60 THEN '31-60天' WHEN age_days<=90 THEN '61-90天' ELSE '90天以上' END AS age_range, COUNT(*) AS bill_count, ROUND(SUM(unreceived_amount),2) AS total FROM vw_receivables WHERE status != 'completed' GROUP BY 1 ORDER BY MIN(age_days)",
    },
    {
        "question": "应付账款汇总",
        "sql": "SELECT supplier_name, COUNT(*) AS bill_count, ROUND(SUM(unpaid_amount),2) AS total_unpaid FROM vw_payables WHERE status != 'completed' GROUP BY supplier_name ORDER BY total_unpaid DESC",
    },
    {
        "question": "查一下所有账套本月的销售对比",
        "sql": "SELECT account_set_name, COUNT(DISTINCT order_no) AS order_count, ROUND(SUM(amount),2) AS total_amount, ROUND(SUM(profit),2) AS total_profit FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) GROUP BY account_set_name ORDER BY total_amount DESC",
    },
]


def format_few_shots(custom_shots: list | None = None) -> str:
    """格式化 few-shot 示例为 prompt 文本"""
    items = custom_shots if custom_shots else DEFAULT_FEW_SHOTS
    if not items:
        return ""
    lines = ["## 查询示例\n"]
    for i, item in enumerate(items, 1):
        lines.append(f"### 示例 {i}")
        lines.append(f"用户: {item['question']}")
        lines.append(f"SQL: {item['sql']}")
        lines.append("")
    return "\n".join(lines)
