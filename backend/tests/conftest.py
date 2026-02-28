"""测试配置"""
import pytest
from httpx import AsyncClient, ASGITransport
from tortoise import Tortoise


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


async def init_test_db():
    """初始化测试数据库（SQLite 内存模式）"""
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models"]},
    )
    await Tortoise.generate_schemas()


async def cleanup_test_db():
    await Tortoise.close_connections()


@pytest.fixture(autouse=True)
async def setup_db():
    await init_test_db()
    yield
    await cleanup_test_db()


@pytest.fixture
async def client():
    """异步测试客户端"""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
