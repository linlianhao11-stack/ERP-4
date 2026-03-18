"""v019 — 发货单号列

为 shipments 表添加 shipment_no 列。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'shipments'"
    )
    if not any(col["name"] == "shipment_no" for col in columns):
        logger.info("迁移: 为 shipments 表添加 shipment_no 列")
        await conn.execute_query(
            "ALTER TABLE shipments ADD COLUMN shipment_no VARCHAR(30) UNIQUE"
        )
        logger.info("迁移完成: shipment_no 列已添加")
