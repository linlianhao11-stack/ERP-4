"""默认业务词典 — 帮助 LLM 理解业务术语"""
from __future__ import annotations

DEFAULT_BUSINESS_DICT = [
    {"term": "毛利", "meaning": "销售额 - 成本，在视图中为 profit 字段"},
    {"term": "毛利率", "meaning": "毛利 / 销售额 * 100，在视图中为 profit_rate 字段"},
    {"term": "账期", "meaning": "赊销，order_type = 'account_period'"},
    {"term": "现结", "meaning": "现款结算，order_type = 'normal'"},
    {"term": "启领", "meaning": "账套名称，account_set_name = '启领'"},
    {"term": "链雾", "meaning": "账套名称，account_set_name = '链雾'"},
    {"term": "应收", "meaning": "客户欠我们的钱，查 vw_receivables"},
    {"term": "应付", "meaning": "我们欠供应商的钱，查 vw_payables"},
    {"term": "周转率", "meaning": "近30天出库量 / 当前库存，在 vw_inventory_turnover 中"},
    {"term": "手机壳", "meaning": "产品分类 category 或品牌 brand，需模糊匹配"},
    {"term": "SKU", "meaning": "产品唯一编码，products.sku 字段"},
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
