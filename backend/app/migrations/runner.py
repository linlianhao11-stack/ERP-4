"""版本化迁移运行器

启动时：
1. 获取 pg_advisory_lock 防并发
2. 确保 migration_history 表存在
3. 扫描 v*.py 文件，对比已执行列表
4. 已有数据库：自动标记基线迁移为已执行
5. 按版本号顺序执行未运行的迁移
"""
from __future__ import annotations

import importlib
import os
import re

from tortoise import connections

from app.logger import get_logger

logger = get_logger("migrations")

# 匹配 vNNN_name.py 格式
_VERSION_RE = re.compile(r"^(v\d{3})_.+\.py$")

# 基线版本：v001-v028 是从旧 migrations.py 拆分出的，已有数据库不需要重新执行
# 版本号采用 3 位零填充（v001, v002, ...），确保字符串字典序与数字顺序一致
_BASELINE_MAX = "v028"


async def run_migrations():
    """迁移入口（与旧 API 保持一致）"""
    pool = connections.get("default")
    # pg_advisory_lock 是会话级锁，在连接池环境中 lock/unlock
    # 可能分配到不同连接导致锁失效。改用原始连接 + 阻塞式锁：
    # 第一个 worker 获取锁并执行迁移，第二个 worker 阻塞等待，
    # 等锁释放后所有迁移已完成，幂等检查会让它直接跳过。
    raw_conn = await pool._pool.acquire()
    try:
        await raw_conn.execute("SELECT pg_advisory_lock(20260315)")
        try:
            await _run_versioned_migrations()
        finally:
            await raw_conn.execute("SELECT pg_advisory_unlock(20260315)")
    finally:
        await pool._pool.release(raw_conn)


async def _ensure_history_table(conn):
    """确保 migration_history 表存在"""
    await conn.execute_query("""
        CREATE TABLE IF NOT EXISTS migration_history (
            id SERIAL PRIMARY KEY,
            version VARCHAR(10) NOT NULL UNIQUE,
            name VARCHAR(200) NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


async def _get_applied_versions(conn) -> set[str]:
    """获取已执行的迁移版本号集合"""
    rows = await conn.execute_query_dict(
        "SELECT version FROM migration_history"
    )
    return {row["version"] for row in rows}


def _discover_migrations() -> list[tuple[str, str]]:
    """扫描 migrations/ 目录，返回 [(version, module_name), ...] 按版本排序"""
    migrations_dir = os.path.dirname(__file__)
    results = []
    for filename in os.listdir(migrations_dir):
        match = _VERSION_RE.match(filename)
        if match:
            version = match.group(1)
            module_name = filename[:-3]  # 去掉 .py
            results.append((version, module_name))
    results.sort(key=lambda x: x[0])
    return results


async def _is_existing_database(conn) -> bool:
    """检测是否为已有数据库（基线标志：users.password_changed_at 列存在）"""
    rows = await conn.execute_query_dict(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'users' AND column_name = 'password_changed_at'"
    )
    return len(rows) > 0


async def _mark_baseline(conn, migrations):
    """将基线迁移（v001-v028）标记为已执行"""
    baseline = [(v, name) for v, name in migrations if v <= _BASELINE_MAX]
    if not baseline:
        return
    for version, name in baseline:
        await conn.execute_query(
            "INSERT INTO migration_history (version, name) VALUES ($1, $2) "
            "ON CONFLICT (version) DO NOTHING",
            [version, name]
        )
    logger.info(f"基线迁移已标记: {baseline[0][0]}-{baseline[-1][0]} ({len(baseline)} 个)")


async def _run_versioned_migrations():
    """执行版本化迁移"""
    conn = connections.get("default")

    await _ensure_history_table(conn)

    all_migrations = _discover_migrations()
    if not all_migrations:
        logger.info("无迁移文件")
        return

    applied = await _get_applied_versions(conn)

    # 已有数据库 + history 表为空 → 标记基线
    if not applied and await _is_existing_database(conn):
        await _mark_baseline(conn, all_migrations)
        applied = await _get_applied_versions(conn)

    # 筛选未执行的迁移
    pending = [(v, name) for v, name in all_migrations if v not in applied]
    if not pending:
        logger.info(f"数据库迁移已是最新 ({len(all_migrations)} 个迁移)")
        return

    logger.info(f"发现 {len(pending)} 个待执行迁移")
    for version, module_name in pending:
        logger.info(f"执行迁移: {module_name}")
        try:
            mod = importlib.import_module(f"app.migrations.{module_name}")
            if not hasattr(mod, "up"):
                raise AttributeError(
                    f"迁移模块 {module_name} 缺少 up() 函数"
                )
            await mod.up(conn)
            await conn.execute_query(
                "INSERT INTO migration_history (version, name) VALUES ($1, $2)",
                [version, module_name]
            )
            logger.info(f"迁移完成: {module_name}")
        except Exception as e:
            logger.error(f"迁移失败: {module_name} — {e}")
            raise  # 迁移失败应阻止启动

    logger.info(f"所有迁移执行完成 (新执行 {len(pending)} 个)")
