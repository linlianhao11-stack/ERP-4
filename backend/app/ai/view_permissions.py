"""AI 视图-权限映射表"""
from __future__ import annotations

AI_VIEW_PERMISSIONS: dict[str, str] = {
    # 业务视图
    "vw_sales_detail": "ai_sales",
    "vw_sales_summary": "ai_sales",
    "vw_purchase_detail": "ai_purchase",
    "vw_inventory_status": "ai_stock",
    "vw_inventory_turnover": "ai_stock",
    "vw_receivables": "ai_finance",
    "vw_payables": "ai_finance",
    "vw_accounting_ledger": "ai_accounting",
    "vw_accounting_voucher_summary": "ai_accounting",
    # 基础参考表 — 主开关即可
    "customers": "ai_chat",
    "products": "ai_chat",
    "suppliers": "ai_chat",
    "warehouses": "ai_chat",
    "account_sets": "ai_chat",
}

AI_PERMISSION_KEYS = [
    "ai_chat", "ai_sales", "ai_purchase", "ai_stock",
    "ai_customer", "ai_finance", "ai_accounting",
]


def get_allowed_views(user_permissions: list[str]) -> set[str]:
    """根据用户权限列表返回允许访问的视图/表名集合"""
    allowed = set()
    for view_name, perm_key in AI_VIEW_PERMISSIONS.items():
        if perm_key in user_permissions:
            allowed.add(view_name)
    return allowed
