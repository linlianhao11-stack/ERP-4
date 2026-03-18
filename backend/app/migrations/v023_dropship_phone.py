"""v023 — 代采代发手机号字段

代采代发订单新增 phone 字段（收/寄件人手机号，顺丰/中通查询需要）。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE dropship_orders ADD COLUMN phone VARCHAR(11);
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    logger.info("代采代发: phone 字段已添加")
