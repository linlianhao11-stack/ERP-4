"""商品品牌路由"""
from fastapi import APIRouter, Depends
from tortoise import Tortoise

from app.auth.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/api", tags=["商品管理"])


@router.get("/product-brands")
async def list_product_brands(user: User = Depends(get_current_user)):
    """返回products表中distinct brand列表"""
    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query(
        "SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != '' AND is_active=true ORDER BY brand"
    )
    return [row["brand"] if isinstance(row, dict) else (row[0] if hasattr(row, '__getitem__') else str(row)) for row in (rows[1] if rows else [])]
