"""默认 Few-shot 示例 — 引导 LLM 生成正确的 SQL"""
from __future__ import annotations

DEFAULT_FEW_SHOTS = [
    {
        "question": "这个月启领的毛利怎么样",
        "sql": "SELECT year_month, total_amount, total_cost, total_profit, profit_rate FROM vw_sales_summary WHERE account_set_name = '启领' AND year_month = TO_CHAR(CURRENT_DATE, 'YYYY-MM')",
        "source": "manual",
    },
    {
        "question": "客户A在1-3月的手机壳销售",
        "sql": "SELECT customer_name, product_name, brand, SUM(quantity) AS total_qty, SUM(amount) AS total_amount, SUM(profit) AS total_profit, ROUND(SUM(profit)/NULLIF(SUM(amount),0)*100, 2) AS profit_rate FROM vw_sales_detail WHERE customer_name LIKE '%A%' AND order_date BETWEEN '2024-01-01' AND '2024-03-31' AND (product_name LIKE '%手机壳%' OR category LIKE '%手机壳%') GROUP BY customer_name, product_name, brand ORDER BY total_amount DESC",
        "source": "manual",
    },
    {
        "question": "各品牌的应收账款汇总",
        "sql": "SELECT customer_name, COUNT(*) AS bill_count, SUM(total_amount) AS total_receivable, SUM(received_amount) AS total_received, SUM(unreceived_amount) AS total_unreceived FROM vw_receivables WHERE status != 'completed' GROUP BY customer_name ORDER BY total_unreceived DESC",
        "source": "manual",
    },
    {
        "question": "SKU ABC123 的库存管理做得怎么样",
        "sql": "SELECT s.sku, s.product_name, s.brand, s.warehouse_name, s.quantity, s.available_qty, s.stock_value, t.sold_30d, t.sold_90d, t.turnover_rate FROM vw_inventory_status s LEFT JOIN vw_inventory_turnover t ON s.sku = t.sku WHERE s.sku = 'ABC123'",
        "source": "manual",
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
