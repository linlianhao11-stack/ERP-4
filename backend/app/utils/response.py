"""统一 API 响应格式"""
from __future__ import annotations


def paginated_response(items: list, total: int = None) -> dict:
    """统一分页响应格式

    Args:
        items: 数据列表
        total: 总数，为 None 时取 len(items)

    Returns:
        {"items": [...], "total": N}
    """
    if total is None:
        total = len(items)
    return {"items": items, "total": total}
