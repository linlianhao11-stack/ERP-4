"""默认业务词典 — 帮助 LLM 理解业务术语"""
from __future__ import annotations

DEFAULT_BUSINESS_DICT = [
    {"term": "毛利/毛利率", "meaning": "profit / profit_rate 字段，毛利=销售额-成本"},
    {"term": "销售额", "meaning": "amount 或 total_amount 字段"},
    {"term": "账期/赊销", "meaning": "order_type = account_period"},
    {"term": "现结", "meaning": "order_type = normal"},
    {"term": "业务员", "meaning": "salesperson_name 字段"},
    {"term": "含税价/去税价", "meaning": "tax_inclusive_price / tax_exclusive_price"},
    {"term": "库存/可用库存", "meaning": "quantity / available_qty，预留 reserved_qty"},
    {"term": "库存金额", "meaning": "stock_value 字段 = quantity × avg_cost"},
    {"term": "周转率", "meaning": "turnover_rate = sold_30d/current_stock，在 vw_inventory_turnover"},
    {"term": "滞销", "meaning": "turnover_rate < 0.5 或 sold_30d = 0"},
    {"term": "缺货", "meaning": "available_qty <= 0"},
    {"term": "应收/应付", "meaning": "vw_receivables / vw_payables"},
    {"term": "欠款", "meaning": "unreceived_amount(应收) 或 unpaid_amount(应付)"},
    {"term": "账龄", "meaning": "age_days 字段，开单至今天数"},
    {"term": "结清", "meaning": "status = completed"},
    {"term": "启领/002", "meaning": "账套名称，account_set_name 过滤"},
    {"term": "SKU", "meaning": "产品唯一编码，sku 字段"},
    {"term": "Top/排名", "meaning": "ORDER BY DESC LIMIT N"},
]


def format_business_dict(custom_dict: list | None = None) -> str:
    """格式化业务词典为 prompt 文本"""
    items = custom_dict if custom_dict else DEFAULT_BUSINESS_DICT
    if not items:
        return ""
    lines = ["## 业务词典\n"]
    for item in items:
        lines.append(f"- {item['term']}：{item['meaning']}")
    return "\n".join(lines)
