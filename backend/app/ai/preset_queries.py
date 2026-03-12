"""默认预设快捷查询 — 高频问题直接匹配 SQL 模板，跳过 API 调用"""
from __future__ import annotations

DEFAULT_PRESET_QUERIES = [
    {
        "display": "本月销售概况",
        "keywords": ["本月", "销售"],
        "sql": "SELECT COUNT(DISTINCT order_no) AS 订单数, ROUND(SUM(amount),2) AS 销售额, ROUND(SUM(cost),2) AS 成本, ROUND(SUM(profit),2) AS 毛利, ROUND(SUM(profit)/NULLIF(SUM(amount),0)*100,2) AS 毛利率 FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE)",
    },
    {
        "display": "本月毛利多少",
        "keywords": ["毛利"],
        "sql": "SELECT ROUND(SUM(amount),2) AS 销售额, ROUND(SUM(profit),2) AS 毛利, ROUND(SUM(profit)/NULLIF(SUM(amount),0)*100,2) AS 毛利率 FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE)",
    },
    {
        "display": "这周的销售",
        "keywords": ["这周", "销售"],
        "sql": "SELECT order_no AS 单号, order_date AS 日期, customer_name AS 客户, product_name AS 产品, quantity AS 数量, ROUND(amount,2) AS 金额, ROUND(profit,2) AS 毛利, account_set_name AS 账套 FROM vw_sales_detail WHERE order_date >= date_trunc('week', CURRENT_DATE) AND order_date < date_trunc('week', CURRENT_DATE) + INTERVAL '7 days' ORDER BY order_date DESC",
    },
    {
        "display": "今天的销售",
        "keywords": ["今天", "销售"],
        "sql": "SELECT order_no AS 单号, customer_name AS 客户, product_name AS 产品, quantity AS 数量, ROUND(amount,2) AS 金额, account_set_name AS 账套 FROM vw_sales_detail WHERE order_date = CURRENT_DATE ORDER BY order_no",
    },
    {
        "display": "待收应收款总额",
        "keywords": ["应收"],
        "sql": "SELECT customer_name AS 客户, COUNT(*) AS 笔数, ROUND(SUM(total_amount),2) AS 应收总额, ROUND(SUM(received_amount),2) AS 已收, ROUND(SUM(unreceived_amount),2) AS 未收 FROM vw_receivables WHERE status != 'completed' GROUP BY customer_name ORDER BY SUM(unreceived_amount) DESC",
    },
    {
        "display": "哪些产品快缺货了",
        "keywords": ["缺货"],
        "sql": "SELECT sku AS SKU, product_name AS 产品, brand AS 品牌, warehouse_name AS 仓库, available_qty AS 可用库存 FROM vw_inventory_status WHERE available_qty <= 0 ORDER BY available_qty",
    },
    {
        "display": "本月热销产品Top10",
        "keywords": ["热销"],
        "sql": "SELECT product_name AS 产品, brand AS 品牌, SUM(quantity) AS 销量, ROUND(SUM(amount),2) AS 销售额 FROM vw_sales_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) GROUP BY product_name, brand ORDER BY SUM(amount) DESC LIMIT 10",
    },
    {
        "display": "客户欠款排名",
        "keywords": ["客户", "欠款"],
        "sql": "SELECT customer_name AS 客户, COUNT(*) AS 笔数, ROUND(SUM(unreceived_amount),2) AS 欠款总额 FROM vw_receivables WHERE status != 'completed' GROUP BY customer_name ORDER BY SUM(unreceived_amount) DESC LIMIT 20",
    },
    {
        "display": "库存状态总览",
        "keywords": ["库存", "总览"],
        "sql": "SELECT product_name AS 产品, brand AS 品牌, warehouse_name AS 仓库, quantity AS 库存, available_qty AS 可用, ROUND(stock_value,2) AS 库存金额 FROM vw_inventory_status WHERE quantity > 0 ORDER BY stock_value DESC",
    },
    {
        "display": "应付账款汇总",
        "keywords": ["应付"],
        "sql": "SELECT supplier_name AS 供应商, COUNT(*) AS 笔数, ROUND(SUM(unpaid_amount),2) AS 未付总额 FROM vw_payables WHERE status != 'completed' GROUP BY supplier_name ORDER BY SUM(unpaid_amount) DESC",
    },
    {
        "display": "本月采购汇总",
        "keywords": ["采购"],
        "sql": "SELECT supplier_name AS 供应商, COUNT(*) AS 采购单数, ROUND(SUM(amount),2) AS 采购金额 FROM vw_purchase_detail WHERE purchase_date >= date_trunc('month', CURRENT_DATE) GROUP BY supplier_name ORDER BY SUM(amount) DESC",
    },
    {
        "display": "库存周转率",
        "keywords": ["周转"],
        "sql": "SELECT product_name AS 产品, brand AS 品牌, current_stock AS 库存, sold_30d AS 近30天出库, ROUND(turnover_rate,2) AS 周转率 FROM vw_inventory_turnover WHERE current_stock > 0 ORDER BY turnover_rate DESC LIMIT 20",
    },
]
