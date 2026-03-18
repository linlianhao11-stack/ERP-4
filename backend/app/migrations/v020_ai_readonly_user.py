"""v020 — AI 只读数据库用户 + 语义视图

创建 erp_ai_readonly PostgreSQL 用户并执行 ai/views.sql。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # 检查用户是否已存在
    result = await conn.execute_query_dict(
        "SELECT 1 FROM pg_roles WHERE rolname = 'erp_ai_readonly'"
    )
    if not result:
        from app.config import AI_DB_PASSWORD
        if not AI_DB_PASSWORD:
            logger.warning("AI_DB_PASSWORD 未设置，跳过创建 AI 只读用户（AI 功能将不可用）")
            return
        try:
            # 使用单引号 + 转义防止密码中的特殊字符
            safe_password = AI_DB_PASSWORD.replace("'", "''")
            await conn.execute_query(f"CREATE USER erp_ai_readonly WITH PASSWORD '{safe_password}'")
            # 动态获取当前数据库名
            db_name_rows = await conn.execute_query_dict("SELECT current_database() AS db")
            db_name = db_name_rows[0]["db"] if db_name_rows else "erp"
            await conn.execute_query(f"GRANT CONNECT ON DATABASE {db_name} TO erp_ai_readonly")
            await conn.execute_query("GRANT USAGE ON SCHEMA public TO erp_ai_readonly")
            await conn.execute_query("GRANT SELECT ON ALL TABLES IN SCHEMA public TO erp_ai_readonly")
            await conn.execute_query("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO erp_ai_readonly")
            await conn.execute_query("REVOKE SELECT ON users FROM erp_ai_readonly")
            await conn.execute_query("REVOKE SELECT ON system_settings FROM erp_ai_readonly")
            await conn.execute_query("ALTER USER erp_ai_readonly SET statement_timeout = '30s'")
            await conn.execute_query("ALTER USER erp_ai_readonly SET work_mem = '16MB'")
            await conn.execute_query("ALTER USER erp_ai_readonly SET temp_file_limit = '100MB'")
            await conn.execute_query("ALTER USER erp_ai_readonly CONNECTION LIMIT 5")
            logger.info(f"AI 只读用户 erp_ai_readonly 已创建（密码: {AI_DB_PASSWORD[:4]}...）")
        except Exception as e:
            logger.warning(f"创建 AI 只读用户失败（可能权限不足）: {e}")

    # 创建/更新语义视图
    try:
        import os
        views_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ai", "views.sql")
        if os.path.exists(views_path):
            with open(views_path, "r", encoding="utf-8") as f:
                views_sql = f.read()
            # 逐条执行（按分号分割，跳过纯注释段落）
            for stmt in views_sql.split(";"):
                stmt = stmt.strip()
                if not stmt:
                    continue
                # 跳过只有注释的段落
                non_comment_lines = [l for l in stmt.split("\n")
                                     if l.strip() and not l.strip().startswith("--")]
                if not non_comment_lines:
                    continue
                try:
                    await conn.execute_query(stmt)
                except Exception as ve:
                    logger.warning(f"视图语句执行失败: {ve}")
            logger.info("AI 语义视图已创建/更新")
    except Exception as e:
        logger.warning(f"语义视图创建失败: {e}")
