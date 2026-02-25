import os
import asyncio
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urlparse

from app.config import BACKUP_KEEP_DAYS, BACKUP_HOUR, DATABASE_URL
from app.logger import get_logger

logger = get_logger("backup")


def get_db_path():
    """从 DATABASE_URL 提取 SQLite 文件路径（PostgreSQL 时返回 None）"""
    url = DATABASE_URL
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        return url[len("sqlite://"):]
    return None


def is_postgres():
    return DATABASE_URL.startswith("postgres")


def _parse_pg_url():
    """解析 PostgreSQL 连接 URL 为组件，避免在命令行中暴露密码"""
    parsed = urlparse(DATABASE_URL)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "erp",
        "password": parsed.password or "",
        "dbname": (parsed.path or "/erp").lstrip("/"),
    }


def _pg_env():
    """构造包含 PGPASSWORD 的环境变量字典"""
    pg = _parse_pg_url()
    env = os.environ.copy()
    if pg["password"]:
        env["PGPASSWORD"] = pg["password"]
    return env


def _pg_conn_args(cmd="pg_dump"):
    """构造 pg_dump/psql 的连接参数（不含密码）"""
    pg = _parse_pg_url()
    return [cmd, "-h", pg["host"], "-p", pg["port"], "-U", pg["user"], "-d", pg["dbname"]]


def get_backup_dir():
    if is_postgres():
        backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backups")
    else:
        db_path = get_db_path()
        if not db_path:
            return None
        data_dir = os.path.dirname(db_path)
        backup_dir = os.path.join(os.path.dirname(data_dir), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def do_backup(tag="auto"):
    """数据库备份（支持 SQLite 和 PostgreSQL）"""
    backup_dir = get_backup_dir()
    if not backup_dir:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if is_postgres():
        backup_name = f"erp_{tag}_{timestamp}.sql"
        backup_path = os.path.join(backup_dir, backup_name)
        try:
            result = subprocess.run(
                _pg_conn_args("pg_dump") + [
                    "--clean", "--if-exists",
                    "--no-owner", "--no-privileges",
                    "-f", backup_path],
                capture_output=True, text=True, timeout=120,
                env=_pg_env()
            )
            if result.returncode != 0:
                raise RuntimeError(f"pg_dump 失败: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError("pg_dump 未安装或不在 PATH 中")
        return backup_path
    else:
        db_path = get_db_path()
        if not db_path:
            return None
        import sqlite3
        backup_name = f"erp_{tag}_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        return backup_path


def do_restore(filename):
    """从备份文件恢复数据库（恢复前自动创建安全备份）"""
    backup_dir = get_backup_dir()
    if not backup_dir:
        raise RuntimeError("备份目录不可用")
    import re
    if not re.match(r'^[a-zA-Z0-9_.\-]+$', filename):
        raise ValueError("文件名包含非法字符")
    filepath = os.path.join(backup_dir, filename)
    if os.path.realpath(filepath) != os.path.join(os.path.realpath(backup_dir), filename):
        raise ValueError("非法文件路径")
    if not os.path.exists(filepath):
        raise FileNotFoundError("备份文件不存在")

    # 恢复前自动备份当前数据（安全网）
    pre_backup = do_backup("pre_restore")
    if not pre_backup:
        raise RuntimeError("无法创建安全备份，取消恢复操作")

    if is_postgres():
        # 第1步：清空数据库（删除并重建 public schema）
        drop_result = subprocess.run(
            _pg_conn_args("psql") + ["-c",
             "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"],
            capture_output=True, text=True, timeout=30,
            env=_pg_env()
        )
        if drop_result.returncode != 0:
            logger.error("清理数据库失败", extra={"data": {"stderr": drop_result.stderr}})
            raise RuntimeError("清理数据库失败")

        # 第2步：导入备份（不使用 ON_ERROR_STOP，容忍非关键警告如 OWNER 不存在）
        result = subprocess.run(
            _pg_conn_args("psql") + ["-f", filepath],
            capture_output=True, text=True, timeout=300,
            env=_pg_env()
        )

        # 第3步：验证恢复结果 - 检查是否有数据表被成功创建
        verify = subprocess.run(
            _pg_conn_args("psql") + ["-t", "-A", "-c",
             "SELECT count(*) FROM information_schema.tables "
             "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"],
            capture_output=True, text=True, timeout=30,
            env=_pg_env()
        )
        table_count = 0
        if verify.returncode == 0 and verify.stdout.strip().isdigit():
            table_count = int(verify.stdout.strip())

        if table_count == 0:
            # 恢复失败，尝试从安全备份自动恢复
            logger.error("恢复验证失败（0张表），尝试自动恢复", extra={"data": {"file": filename}})
            recovery = subprocess.run(
                _pg_conn_args("psql") + ["-f", pre_backup],
                capture_output=True, text=True, timeout=300,
                env=_pg_env()
            )
            if recovery.returncode != 0:
                raise RuntimeError(
                    f"备份文件恢复失败且自动恢复也失败，请手动处理。"
                    f"安全备份文件: {os.path.basename(pre_backup)}"
                )
            raise RuntimeError("备份文件无法恢复（格式不兼容或文件损坏），已自动恢复到操作前状态")

        logger.info("数据库恢复成功", extra={"data": {
            "file": filename,
            "tables_restored": table_count,
            "psql_stderr": result.stderr[:500] if result.stderr else ""
        }})
    else:
        import shutil
        shutil.copy2(filepath, get_db_path())

    return pre_backup  # 返回安全备份路径


def cleanup_old_backups():
    backup_dir = get_backup_dir()
    if not backup_dir:
        return 0
    import glob
    cutoff = datetime.now().timestamp() - BACKUP_KEEP_DAYS * 86400
    removed = 0
    for pattern in ["erp_auto_*", "erp_pre_restore_*"]:
        for f in glob.glob(os.path.join(backup_dir, pattern)):
            if os.path.getmtime(f) < cutoff:
                os.remove(f)
                removed += 1
    return removed


async def auto_backup_loop():
    """自动备份定时任务。
    使用短间隔轮询（60秒）+ 墙钟时间检查，而非单次长 asyncio.sleep。
    这样即使 Docker Desktop VM 因 Mac 休眠导致单调时钟暂停，
    醒来后也能在 60 秒内检测到已过备份时间并立即执行。
    """
    last_backup_date = None
    logger.info("自动备份循环已启动", extra={"data": {"backup_hour": BACKUP_HOUR}})
    while True:
        await asyncio.sleep(60)
        _now = datetime.now()
        if _now.hour >= BACKUP_HOUR and last_backup_date != _now.date():
            try:
                path = await asyncio.to_thread(do_backup, "auto")
                removed = await asyncio.to_thread(cleanup_old_backups)
                last_backup_date = _now.date()
                if path:
                    logger.info("自动备份完成", extra={"data": {"file": os.path.basename(path), "removed": removed}})
            except Exception as e:
                logger.error("自动备份失败", exc_info=e)
