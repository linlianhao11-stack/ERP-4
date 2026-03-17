"""批量关联加载工具 — 消除重复的 collect-query-group 模式"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


async def batch_load_related(
    model,
    filter_field: str,
    ids: list,
    select_related: Optional[List[str]] = None,
) -> Dict[Any, List]:
    """
    批量加载关联记录并按外键分组

    Args:
        model: Tortoise ORM 模型类
        filter_field: 过滤字段名（如 'order_id'）
        ids: 外键值列表
        select_related: 可选的 select_related 字段列表

    Returns:
        {外键值: [记录列表]} 字典

    Example:
        items_by_order = await batch_load_related(OrderItem, 'order_id', order_ids, ['product'])
    """
    if not ids:
        return {}
    query = model.filter(**{f"{filter_field}__in": ids})
    if select_related:
        query = query.select_related(*select_related)
    records = await query.all()
    result: Dict[Any, List] = {}
    for record in records:
        key = getattr(record, filter_field)
        result.setdefault(key, []).append(record)
    return result
