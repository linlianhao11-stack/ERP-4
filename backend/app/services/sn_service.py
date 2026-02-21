from typing import List
from decimal import Decimal
from fastapi import HTTPException
from tortoise.exceptions import IntegrityError
from tortoise.transactions import in_transaction

from app.models import Product, SnConfig, SnCode
from app.utils.time import now


async def check_sn_required(warehouse_id: int, product_id: int) -> bool:
    product = await Product.filter(id=product_id).first()
    if not product or not product.brand:
        return False
    return await SnConfig.filter(warehouse_id=warehouse_id, brand=product.brand, is_active=True).exists()


async def validate_and_add_sn_codes(sn_codes: List[str], warehouse_id: int, product_id: int,
                                     location_id: int, quantity: int, entry_type: str,
                                     entry_cost: Decimal, user, reference_id: int = None):
    if len(sn_codes) != quantity:
        raise HTTPException(status_code=400, detail=f"SN码数量({len(sn_codes)})与入库数量({quantity})不匹配")
    seen = set()
    for sn in sn_codes:
        if sn in seen:
            raise HTTPException(status_code=400, detail=f"SN码重复: {sn}")
        seen.add(sn)

    async with in_transaction():
        existing = await SnCode.filter(sn_code__in=sn_codes).all()
        if existing:
            codes = ", ".join(s.sn_code for s in existing)
            raise HTTPException(status_code=400, detail=f"SN码已存在: {codes}")
        try:
            await SnCode.bulk_create([
                SnCode(
                    sn_code=sn, warehouse_id=warehouse_id, product_id=product_id,
                    location_id=location_id, status="in_stock", entry_type=entry_type,
                    entry_reference_id=reference_id, entry_cost=entry_cost,
                    entry_date=now(), entry_user=user
                )
                for sn in sn_codes
            ])
        except IntegrityError as e:
            raise HTTPException(status_code=400, detail=f"SN码已存在（并发冲突）: {e}")


async def validate_and_consume_sn_codes(sn_codes: List[str], shipment, user,
                                         product_id: int = None, warehouse_id: int = None):
    """验证并消费 SN 码（事务+行锁保证并发安全），可选校验产品和仓库归属"""
    async with in_transaction():
        for sn in sn_codes:
            filters = {"sn_code": sn, "status": "in_stock"}
            if product_id:
                filters["product_id"] = product_id
            if warehouse_id:
                filters["warehouse_id"] = warehouse_id
            sn_obj = await SnCode.filter(**filters).select_for_update().first()
            if not sn_obj:
                detail = f"SN码不可用(不存在或已发货): {sn}"
                if product_id or warehouse_id:
                    detail = f"SN码不可用(不存在、已发货或不属于当前商品/仓库): {sn}"
                raise HTTPException(status_code=400, detail=detail)
            sn_obj.status = "shipped"
            sn_obj.shipment = shipment
            sn_obj.ship_date = now()
            sn_obj.ship_user = user
            await sn_obj.save()
