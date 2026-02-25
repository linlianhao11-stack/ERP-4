from decimal import Decimal
from datetime import timedelta
from tortoise.functions import Sum
from fastapi import HTTPException

from tortoise.exceptions import IntegrityError, OperationalError

from app.models import Product, Warehouse, WarehouseStock
from app.utils.time import now, to_naive, days_between
from app.config import CONSIGNMENT_WAREHOUSE_NAME
from app.models import Customer


async def get_or_create_consignment_warehouse(customer_id: int = None):
    """获取或创建客户独立寄售仓（并发安全）"""
    if customer_id:
        wh = await Warehouse.filter(customer_id=customer_id, is_virtual=True).first()
        if not wh:
            customer = await Customer.filter(id=customer_id).first()
            cname = customer.name if customer else str(customer_id)
            try:
                wh = await Warehouse.create(
                    name=f"__寄售仓_{cname}__", is_virtual=True, is_default=False, customer_id=customer_id
                )
            except IntegrityError:
                wh = await Warehouse.filter(customer_id=customer_id, is_virtual=True).first()
        return wh
    wh = await Warehouse.filter(name=CONSIGNMENT_WAREHOUSE_NAME).first()
    if not wh:
        try:
            wh = await Warehouse.create(name=CONSIGNMENT_WAREHOUSE_NAME, is_virtual=True, is_default=False)
        except IntegrityError:
            wh = await Warehouse.filter(name=CONSIGNMENT_WAREHOUSE_NAME).first()
    return wh


async def get_product_total_stock(product_id: int, exclude_virtual: bool = False) -> int:
    query = WarehouseStock.filter(product_id=product_id)
    if exclude_virtual:
        query = query.filter(warehouse__is_virtual=False)
    result = await query.annotate(total=Sum("quantity")).values("total")
    return result[0]["total"] or 0 if result else 0


def calculate_inventory_age(weighted_entry_date) -> int:
    """计算库龄天数（纯计算，无需 async）"""
    if not weighted_entry_date:
        return 0
    return days_between(now(), weighted_entry_date)


async def update_weighted_entry_date(warehouse_id: int, product_id: int, add_qty: int,
                                      cost_price: Decimal = None, location_id: int = None):
    """更新加权入库日期和加权成本（使用行锁防止并发冲突）"""
    try:
        stock = await WarehouseStock.filter(
            warehouse_id=warehouse_id, product_id=product_id, location_id=location_id
        ).select_for_update().first()
    except OperationalError:
        raise HTTPException(status_code=409, detail="该库存记录正在被其他操作处理，请稍后重试")
    product = await Product.filter(id=product_id).first()

    if not stock:
        try:
            stock = await WarehouseStock.create(
                warehouse_id=warehouse_id,
                product_id=product_id,
                location_id=location_id,
                quantity=0,
                weighted_cost=cost_price or (product.cost_price if product else Decimal("0")),
                weighted_entry_date=now()
            )
        except IntegrityError:
            # Another request created it concurrently, fetch it
            stock = await WarehouseStock.filter(
                warehouse_id=warehouse_id, product_id=product_id, location_id=location_id
            ).first()
        # Re-acquire with lock
        try:
            stock = await WarehouseStock.filter(id=stock.id).select_for_update().first()
        except OperationalError:
            raise HTTPException(status_code=409, detail="该库存记录正在被其他操作处理，请稍后重试")

    old_qty = stock.quantity

    if old_qty + add_qty < 0:
        p_name = product.name if product else str(product_id)
        raise HTTPException(status_code=400, detail=f"商品 {p_name} 库存不足，无法扣减")

    old_date = to_naive(stock.weighted_entry_date) or now()
    old_cost = stock.weighted_cost or Decimal("0")
    new_cost = cost_price if cost_price else old_cost

    if add_qty > 0 and old_qty + add_qty > 0:
        # 仅在新增库存时重新计算加权入库日期，卖出时保持不变
        old_days = days_between(now(), old_date) if old_date else 0
        new_days = Decimal(str(old_qty)) * Decimal(str(old_days)) / Decimal(str(old_qty + add_qty))
        stock.weighted_entry_date = now() - timedelta(days=float(new_days))

        if cost_price:
            weighted_cost = (Decimal(str(old_qty)) * old_cost + Decimal(str(add_qty)) * new_cost) / Decimal(str(old_qty + add_qty))
            stock.weighted_cost = Decimal(str(weighted_cost)).quantize(Decimal("0.01"))
    elif old_qty + add_qty <= 0:
        # 库存清零，重置入库日期（下次入库时重新开始计算）
        stock.weighted_entry_date = now()
        if cost_price:
            stock.weighted_cost = cost_price
    # else: 卖出但仍有库存，保持加权入库日期和成本不变

    stock.quantity = old_qty + add_qty
    await stock.save()
    return stock


async def get_product_weighted_cost(product_id: int) -> Decimal:
    """获取商品的加权平均成本（所有仓库）"""
    stocks = await WarehouseStock.filter(product_id=product_id, quantity__gt=0).all()
    total_qty = sum(s.quantity for s in stocks)
    if total_qty <= 0:
        product = await Product.filter(id=product_id).first()
        return product.cost_price if product else Decimal("0")

    total_cost = sum(Decimal(str(s.quantity)) * (s.weighted_cost or Decimal("0")) for s in stocks)
    return (total_cost / Decimal(str(total_qty))).quantize(Decimal("0.01"))
