"""v003 — 用户表字段扩展

合并三个小迁移：must_change_password / token_version / password_changed_at。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # --- must_change_password ---
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'users'"
    )
    col_names = [col["name"] for col in columns]

    if "must_change_password" not in col_names:
        await conn.execute_query(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE"
        )
        logger.info("迁移: users 表添加 must_change_password 列")

    # --- token_version ---
    await conn.execute_query(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INT DEFAULT 0"
    )

    # --- password_changed_at ---
    try:
        await conn.execute_query("ALTER TABLE users ADD COLUMN password_changed_at TIMESTAMPTZ")
        logger.info("迁移: users 表添加 password_changed_at 列")
    except Exception:
        pass  # 列已存在，跳过
