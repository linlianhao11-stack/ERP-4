"""游标分页工具 — 替代 OFFSET 实现 O(1) 翻页性能

用法:
    from app.utils.pagination import encode_cursor, apply_cursor_pagination

    # 在端点中:
    items = await apply_cursor_pagination(query, cursor, "created_at", limit, offset)
    next_cursor = build_next_cursor(items, "created_at")
    return {"items": [...], "total": total, "next_cursor": next_cursor}
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Optional

from tortoise.expressions import Q
from tortoise.queryset import QuerySet


def encode_cursor(record_id: int, sort_value) -> str:
    """将 (id, sort_value) 编码为 URL 安全的 cursor 字符串"""
    if isinstance(sort_value, datetime):
        v = sort_value.isoformat()
    else:
        v = str(sort_value)
    data = json.dumps({"i": record_id, "v": v}, separators=(",", ":"))
    return base64.urlsafe_b64encode(data.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple:
    """解码 cursor 字符串为 (id, sort_value_str)"""
    # 补回 base64 padding
    padding = 4 - len(cursor) % 4
    if padding != 4:
        cursor += "=" * padding
    data = json.loads(base64.urlsafe_b64decode(cursor))
    return data["i"], data["v"]


async def apply_cursor_pagination(
    query: QuerySet,
    cursor: Optional[str],
    sort_field: str,
    limit: int,
    offset: int = 0,
) -> list:
    """对查询应用游标分页（有 cursor 时）或 OFFSET 分页（无 cursor 时）

    Args:
        query: Tortoise ORM QuerySet（已应用 filter/select_related 等）
        cursor: 游标字符串，None 时退化为 OFFSET
        sort_field: 排序字段名（如 "created_at"、"updated_at"）
        limit: 每页条数
        offset: 传统 offset（仅 cursor 为 None 时使用）

    Returns:
        查询结果列表
    """
    if cursor:
        try:
            cursor_id, cursor_val = decode_cursor(cursor)
            # 对 DESC 排序：取 sort_value 小于游标的记录，或相同时取 id 小于游标的
            query = query.filter(
                Q(**{f"{sort_field}__lt": cursor_val})
                | (Q(**{sort_field: cursor_val}) & Q(id__lt=cursor_id))
            )
            return list(await query.order_by(f"-{sort_field}", "-id").limit(limit))
        except Exception:
            # cursor 解码失败，退化为 OFFSET
            pass

    return list(await query.order_by(f"-{sort_field}").offset(offset).limit(limit))


def build_next_cursor(items: list, sort_field: str) -> Optional[str]:
    """从结果集的最后一条记录生成下一页 cursor"""
    if not items:
        return None
    last = items[-1]
    # 支持 ORM 对象和 dict 两种格式
    if isinstance(last, dict):
        sort_value = last.get(sort_field)
        record_id = last.get("id")
    else:
        sort_value = getattr(last, sort_field, None)
        record_id = getattr(last, "id", None)
    if record_id is None or sort_value is None:
        return None
    return encode_cursor(record_id, sort_value)
