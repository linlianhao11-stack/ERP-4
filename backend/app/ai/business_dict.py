"""默认业务词典 — 帮助 LLM 理解业务术语"""
from __future__ import annotations

DEFAULT_BUSINESS_DICT = [
    {"term": "毛利/毛利率", "meaning": "毛利 = 销售额 - 成本，毛利率 = 毛利 ÷ 销售额 × 100%", "field_hint": "profit / profit_rate"},
    {"term": "销售额", "meaning": "一笔交易的总金额", "field_hint": "amount, total_amount"},
    {"term": "账期/赊销", "meaning": "先发货后收款的交易方式", "field_hint": "order_type = account_period"},
    {"term": "现结", "meaning": "货到付款、即时结清的交易方式", "field_hint": "order_type = normal"},
    {"term": "业务员", "meaning": "负责这笔交易的销售人员", "field_hint": "salesperson_name"},
    {"term": "含税价/去税价", "meaning": "含增值税的单价 / 不含税的单价", "field_hint": "tax_inclusive_price / tax_exclusive_price"},
    {"term": "库存/可用库存", "meaning": "仓库里的总数量 / 减去预留后实际可用的数量", "field_hint": "quantity / available_qty"},
    {"term": "库存金额", "meaning": "库存数量 × 平均成本价", "field_hint": "stock_value"},
    {"term": "周转率", "meaning": "近30天出库量 ÷ 当前库存，反映库存流转速度，越高越好", "field_hint": "turnover_rate"},
    {"term": "滞销", "meaning": "周转率很低（低于0.5）或近30天完全没有出库的产品"},
    {"term": "缺货", "meaning": "可用库存为零或负数的产品"},
    {"term": "应收/应付", "meaning": "客户欠我们的钱 / 我们欠供应商的钱"},
    {"term": "欠款", "meaning": "还没收到（应收）或还没付出去（应付）的金额", "field_hint": "unreceived_amount / unpaid_amount"},
    {"term": "账龄", "meaning": "从开单到今天过了多少天，天数越多说明欠款时间越久", "field_hint": "age_days"},
    {"term": "结清", "meaning": "这笔应收或应付已经全部收/付完毕"},
    {"term": "启领/002", "meaning": "账套名称，用来区分不同公司或业务线的数据"},
    {"term": "SKU", "meaning": "产品的唯一编码，每个产品都有一个独立的 SKU 编号"},
    {"term": "排名/Top", "meaning": "按某个指标从高到低排序，取前几名"},
]


def format_business_dict(custom_dict: list | None = None) -> str:
    """格式化业务词典为 prompt 文本

    词典分两部分呈现：
    1. 业务术语解释（中文大白话，给 AI 理解概念用）
    2. 字段映射提示（英文字段名，仅供 AI 生成 SQL 时内部参考）
    """
    items = custom_dict if custom_dict else DEFAULT_BUSINESS_DICT
    if not items:
        return ""
    # 第一部分：中文业务概念（AI 回复用户时参考这部分的措辞）
    lines = ["## 业务词典（回复用户时只用这里的中文说法，严禁暴露英文字段名）\n"]
    for item in items:
        lines.append(f"- {item['term']}：{item['meaning']}")

    # 第二部分：字段映射（仅供生成 SQL 用，不要在回复中出现）
    hints = [item for item in items if item.get("field_hint")]
    if hints:
        lines.append("\n## 字段映射（仅供内部生成 SQL 用，严禁在回复中出现以下任何英文）\n")
        for item in hints:
            lines.append(f"- {item['term']} → {item['field_hint']}")
    return "\n".join(lines)
