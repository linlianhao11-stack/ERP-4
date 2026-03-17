"""编号生成工具"""
from __future__ import annotations

import secrets
from datetime import datetime

from tortoise import connections
from tortoise.transactions import in_transaction


def generate_order_no(prefix: str = "ORD"):
    """生成编号：前缀 + 时间戳 + 6字节随机串。用于财务单据等不需要可读序号的场景。"""
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(6).upper()}"


async def generate_sequential_no(prefix: str, table: str, field: str) -> str:
    """
    生成可读顺序编号：PREFIX-YYYYMMDD-NNN
    示例：SO-20260309-001, PO-20260309-012, SH-20260309-003

    使用 PostgreSQL advisory lock 防止并发竞态，DB unique 约束是最终防线。
    """
    today = datetime.now().strftime('%Y%m%d')
    pattern = f"{prefix}-{today}-%"

    # lock key 基于 prefix+日期 的 hash，不同 prefix 不互斥
    lock_key = abs(hash(f"{prefix}-{today}")) % (2**31)

    async with in_transaction() as conn:
        # 事务级 advisory lock，事务结束自动释放
        await conn.execute_query(f"SELECT pg_advisory_xact_lock({lock_key})")

        rows = await conn.execute_query_dict(
            f'SELECT "{field}" FROM "{table}" WHERE "{field}" LIKE $1 ORDER BY "{field}" DESC LIMIT 1',
            [pattern]
        )

        seq = 1
        if rows:
            last_no = rows[0][field]
            parts = last_no.split('-')
            if len(parts) >= 3:
                try:
                    seq = int(parts[2]) + 1
                except ValueError:
                    pass

        return f"{prefix}-{today}-{seq:03d}"
