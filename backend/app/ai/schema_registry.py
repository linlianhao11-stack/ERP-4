"""Schema 注册器 — 从 ORM models 和视图定义生成 LLM 可读的 schema 描述"""
from __future__ import annotations
from tortoise import Tortoise
from app.logger import get_logger

logger = get_logger("ai.schema_registry")

# 排除的表和列
EXCLUDED_TABLES = frozenset({"users", "system_settings", "aerich"})
SENSITIVE_COLUMNS = frozenset({
    "password_hash", "tax_id", "bank_account", "bank_name",
    "token_version", "must_change_password",
})

# 语义视图 schema（手动维护，与 views.sql 同步）
VIEW_SCHEMAS = {
    "vw_sales_detail": {
        "description": "销售明细宽表 — 每行一个订单商品",
        "columns": [
            ("order_no", "VARCHAR", "销售单号"),
            ("order_date", "DATE", "订单日期"),
            ("order_type", "VARCHAR", "订单类型: normal/account_period"),
            ("customer_name", "VARCHAR", "客户名称"),
            ("salesperson_name", "VARCHAR", "业务员"),
            ("sku", "VARCHAR", "产品SKU"),
            ("product_name", "VARCHAR", "产品名称"),
            ("brand", "VARCHAR", "品牌"),
            ("category", "VARCHAR", "分类"),
            ("quantity", "INT", "数量"),
            ("unit_price", "DECIMAL", "单价"),
            ("amount", "DECIMAL", "金额"),
            ("cost", "DECIMAL", "成本"),
            ("profit", "DECIMAL", "毛利"),
            ("profit_rate", "DECIMAL", "毛利率(%)"),
            ("account_set_name", "VARCHAR", "账套名称"),
        ],
    },
    "vw_sales_summary": {
        "description": "销售按月汇总",
        "columns": [
            ("year_month", "VARCHAR", "年月 如 2024-03"),
            ("order_count", "INT", "订单数"),
            ("total_amount", "DECIMAL", "总销售额"),
            ("total_cost", "DECIMAL", "总成本"),
            ("total_profit", "DECIMAL", "总毛利"),
            ("profit_rate", "DECIMAL", "毛利率(%)"),
            ("customer_count", "INT", "客户数"),
            ("account_set_name", "VARCHAR", "账套名称"),
        ],
    },
    "vw_purchase_detail": {
        "description": "采购明细宽表 — 每行一个采购商品",
        "columns": [
            ("po_no", "VARCHAR", "采购单号"),
            ("purchase_date", "DATE", "采购日期"),
            ("supplier_name", "VARCHAR", "供应商名称"),
            ("sku", "VARCHAR", "产品SKU"),
            ("product_name", "VARCHAR", "产品名称"),
            ("brand", "VARCHAR", "品牌"),
            ("quantity", "INT", "数量"),
            ("tax_inclusive_price", "DECIMAL", "含税单价"),
            ("tax_exclusive_price", "DECIMAL", "去税单价"),
            ("amount", "DECIMAL", "金额"),
            ("status", "VARCHAR", "采购单状态"),
            ("account_set_name", "VARCHAR", "账套名称"),
        ],
    },
    "vw_inventory_status": {
        "description": "当前库存状态快照",
        "columns": [
            ("sku", "VARCHAR", "产品SKU"),
            ("product_name", "VARCHAR", "产品名称"),
            ("brand", "VARCHAR", "品牌"),
            ("warehouse_name", "VARCHAR", "仓库名称"),
            ("location_name", "VARCHAR", "库位名称"),
            ("quantity", "INT", "库存数量"),
            ("reserved_qty", "INT", "预留数量"),
            ("available_qty", "INT", "可用数量"),
            ("avg_cost", "DECIMAL", "加权平均成本"),
            ("stock_value", "DECIMAL", "库存金额"),
        ],
    },
    "vw_inventory_turnover": {
        "description": "库存周转分析",
        "columns": [
            ("sku", "VARCHAR", "产品SKU"),
            ("product_name", "VARCHAR", "产品名称"),
            ("brand", "VARCHAR", "品牌"),
            ("current_stock", "INT", "当前库存"),
            ("sold_30d", "INT", "近30天出库量"),
            ("sold_90d", "INT", "近90天出库量"),
            ("turnover_rate", "DECIMAL", "月周转率"),
        ],
    },
    "vw_receivables": {
        "description": "应收账款明细",
        "columns": [
            ("bill_no", "VARCHAR", "应收单号"),
            ("customer_name", "VARCHAR", "客户名称"),
            ("bill_date", "DATE", "开单日期"),
            ("total_amount", "DECIMAL", "应收金额"),
            ("received_amount", "DECIMAL", "已收金额"),
            ("unreceived_amount", "DECIMAL", "未收金额"),
            ("status", "VARCHAR", "状态: pending/partial/completed"),
            ("age_days", "INT", "账龄天数"),
            ("account_set_name", "VARCHAR", "账套名称"),
        ],
    },
    "vw_payables": {
        "description": "应付账款明细",
        "columns": [
            ("bill_no", "VARCHAR", "应付单号"),
            ("supplier_name", "VARCHAR", "供应商名称"),
            ("bill_date", "DATE", "开单日期"),
            ("total_amount", "DECIMAL", "应付金额"),
            ("paid_amount", "DECIMAL", "已付金额"),
            ("unpaid_amount", "DECIMAL", "未付金额"),
            ("status", "VARCHAR", "状态: pending/partial/completed"),
            ("age_days", "INT", "账龄天数"),
            ("account_set_name", "VARCHAR", "账套名称"),
        ],
    },
}

_cached_schema: str | None = None


def get_view_schema_text() -> str:
    """生成视图 schema 文本（供 system prompt 使用）"""
    lines = ["## 数据视图（优先使用这些视图查询）\n"]
    for view_name, info in VIEW_SCHEMAS.items():
        lines.append(f"### {view_name} — {info['description']}")
        for col_name, col_type, comment in info["columns"]:
            lines.append(f"  - {col_name} ({col_type}): {comment}")
        lines.append("")
    return "\n".join(lines)


async def get_table_schema_text() -> str:
    """从 Tortoise ORM models 生成原始表 schema 文本（作为 fallback）"""
    global _cached_schema
    if _cached_schema is not None:
        return _cached_schema

    lines = ["## 原始数据表（视图无法满足时使用）\n"]
    try:
        models_map = Tortoise.apps.get("models", {})
        for model_name, model_cls in sorted(models_map.items()):
            table_name = model_cls.Meta.table if hasattr(model_cls.Meta, "table") else model_name.lower() + "s"
            if table_name.lower() in EXCLUDED_TABLES:
                continue

            lines.append(f"### {table_name}")
            for field_name, field_obj in model_cls._meta.fields_map.items():
                if field_name in SENSITIVE_COLUMNS:
                    continue
                field_type = type(field_obj).__name__.replace("Field", "")
                desc = getattr(field_obj, "description", "") or ""
                lines.append(f"  - {field_name} ({field_type}){': ' + desc if desc else ''}")
            lines.append("")
    except Exception as e:
        logger.warning(f"生成表 schema 失败: {e}")
        lines.append("（表 schema 生成失败，请仅使用视图查询）\n")

    _cached_schema = "\n".join(lines)
    return _cached_schema


def get_full_schema_text() -> str:
    """返回 AI 可用的 schema 文本。

    当前仅包含语义视图 — 原始表 schema 不暴露给 AI，
    因为视图已涵盖所有业务查询需求，且避免泄露敏感表结构。
    如需支持更复杂查询，可在此合并 get_table_schema_text()。
    """
    return get_view_schema_text()


def invalidate_cache() -> None:
    """清除 schema 缓存（表结构变更时调用）"""
    global _cached_schema
    _cached_schema = None
