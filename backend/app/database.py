"""数据库初始化"""
import os
from tortoise import Tortoise
from app.config import DATABASE_URL


def _get_db_url():
    """为 PostgreSQL 连接添加连接池参数"""
    url = DATABASE_URL
    if url.startswith("postgres") and "?" not in url:
        min_size = os.environ.get("DB_POOL_MIN", "5")
        max_size = os.environ.get("DB_POOL_MAX", "50")
        url += f"?minsize={min_size}&maxsize={max_size}&command_timeout=15&timeout=10"
    return url


async def init_db():
    await Tortoise.init(
        db_url=_get_db_url(),
        modules={"models": ["app.models"]}
    )
    await Tortoise.generate_schemas(safe=True)


async def close_db():
    await Tortoise.close_connections()
