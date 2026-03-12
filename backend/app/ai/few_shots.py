"""默认 Few-shot 示例 — 引导 LLM 生成正确的 SQL"""
from __future__ import annotations

DEFAULT_FEW_SHOTS = [
    {
        "question": "这个月的销售情况怎么样",
        "sql": "SELECT COUNT(DISTINCT order_no) AS 订单数, ROUND(SUM(amount),2) AS 销售额, ROUND(SUM(cost),2) AS 成本, ROUND(SUM(profit),2) AS 毛利, ROUND(SUM(profit)/NULLIF(SUM(amount),0)*100,2) AS 毛利率 FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) AND order_date < date_trunc('month', CURRENT_DATE) + INTERVAL '1 month'",
    },
    {
        "question": "启领这个月毛利多少",
        "sql": "SELECT ROUND(SUM(amount),2) AS 销售额, ROUND(SUM(profit),2) AS 毛利, ROUND(SUM(profit)/NULLIF(SUM(amount),0)*100,2) AS 毛利率 FROM vw_sales_detail WHERE account_set_name = '启领' AND order_date >= date_trunc('month', CURRENT_DATE)",
    },
    {
        "question": "哪个客户买得最多",
        "sql": "SELECT customer_name AS 客户, COUNT(DISTINCT order_no) AS 订单数, ROUND(SUM(amount),2) AS 销售额, ROUND(SUM(profit),2) AS 毛利 FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) GROUP BY customer_name ORDER BY 销售额 DESC LIMIT 20",
    },
    {
        "question": "本月卖得最好的产品Top10",
        "sql": "SELECT product_name AS 产品, brand AS 品牌, SUM(quantity) AS 销量, ROUND(SUM(amount),2) AS 销售额 FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) GROUP BY product_name, brand ORDER BY 销售额 DESC LIMIT 10",
    },
    {
        "question": "这周有什么销售",
        "sql": "SELECT order_no AS 单号, order_date AS 日期, customer_name AS 客户, product_name AS 产品, quantity AS 数量, ROUND(amount,2) AS 金额 FROM vw_sales_detail WHERE order_date >= date_trunc('week', CURRENT_DATE) AND order_date < date_trunc('week', CURRENT_DATE) + INTERVAL '7 days' ORDER BY order_date DESC",
    },
    {
        "question": "这个月采购了多少",
        "sql": "SELECT supplier_name AS 供应商, COUNT(*) AS 采购单数, ROUND(SUM(amount),2) AS 采购金额 FROM vw_purchase_detail WHERE purchase_date >= date_trunc('month', CURRENT_DATE) GROUP BY supplier_name ORDER BY 采购金额 DESC",
    },
    {
        "question": "哪些产品快缺货了",
        "sql": "SELECT sku AS SKU, product_name AS 产品, brand AS 品牌, warehouse_name AS 仓库, available_qty AS 可用库存 FROM vw_inventory_status WHERE available_qty <= 0 ORDER BY available_qty",
    },
    {
        "question": "库存周转率排名",
        "sql": "SELECT sku AS SKU, product_name AS 产品, brand AS 品牌, current_stock AS 库存, sold_30d AS 近30天出库, ROUND(turnover_rate,2) AS 周转率 FROM vw_inventory_turnover ORDER BY 周转率 DESC LIMIT 20",
    },
    {
        "question": "哪些客户欠款最多",
        "sql": "SELECT customer_name AS 客户, COUNT(*) AS 笔数, ROUND(SUM(unreceived_amount),2) AS 欠款总额 FROM vw_receivables WHERE status != 'completed' GROUP BY customer_name ORDER BY 欠款总额 DESC LIMIT 20",
    },
    {
        "question": "应收账龄分析",
        "sql": "SELECT CASE WHEN age_days<=30 THEN '0-30天' WHEN age_days<=60 THEN '31-60天' WHEN age_days<=90 THEN '61-90天' ELSE '90天以上' END AS 账龄, COUNT(*) AS 笔数, ROUND(SUM(unreceived_amount),2) AS 未收金额 FROM vw_receivables WHERE status != 'completed' GROUP BY 1 ORDER BY MIN(age_days)",
    },
    {
        "question": "应付账款汇总",
        "sql": "SELECT supplier_name AS 供应商, COUNT(*) AS 笔数, ROUND(SUM(unpaid_amount),2) AS 未付总额 FROM vw_payables WHERE status != 'completed' GROUP BY supplier_name ORDER BY 未付总额 DESC",
    },
    {
        "question": "查一下所有账套本月的销售对比",
        "sql": "SELECT account_set_name AS 账套, COUNT(DISTINCT order_no) AS 订单数, ROUND(SUM(amount),2) AS 销售额, ROUND(SUM(profit),2) AS 毛利 FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) GROUP BY account_set_name ORDER BY 销售额 DESC",
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
