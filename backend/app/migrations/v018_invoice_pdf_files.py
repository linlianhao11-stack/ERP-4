"""v018 — 发票 PDF 文件列

为 invoices 表添加 pdf_files JSONB 列。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'invoices'"
    )
    if not any(col["name"] == "pdf_files" for col in columns):
        await conn.execute_query(
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS pdf_files JSONB DEFAULT '[]'"
        )
        logger.info("迁移: invoices 表添加 pdf_files 列")
