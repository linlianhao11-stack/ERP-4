"""寄售管理路由"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from tortoise.expressions import F

from app.auth.dependencies import get_current_user, require_permission
from app.models import (
    User, Order, OrderItem, Customer, Product, Warehouse, Location,
    WarehouseStock, StockLog
)
from app.schemas.consignment import ConsignmentReturnRequest
from app.services.stock_service import get_or_create_consignment_warehouse, update_weighted_entry_date
from app.logger import get_logger

logger = get_logger("consignment")

router = APIRouter(prefix="/api/consignment", tags=["寄售管理"])


@router.get("/summary")
async def get_consignment_summary(user: User = Depends(require_permission("sales"))):
    """获取寄售汇总数据"""
    stocks = await WarehouseStock.filter(warehouse__is_virtual=True, quantity__gt=0).select_related("product")

    consign_orders = await Order.filter(order_type="CONSIGN_OUT").select_related("customer").distinct()
    customer_ids = list(set(o.customer_id for o in consign_orders if o.customer_id))

    # 批量查询客户和订单（避免 N+1）
    customers = await Customer.filter(id__in=customer_ids) if customer_ids else []
    customer_map = {c.id: c for c in customers}

    all_consign_orders = await Order.filter(
        customer_id__in=customer_ids,
        order_type__in=["CONSIGN_OUT", "CONSIGN_SETTLE", "CONSIGN_RETURN"]
    ) if customer_ids else []

    # 按客户+类型分组
    orders_by_customer_type = {}
    for o in all_consign_orders:
        key = (o.customer_id, o.order_type)
        orders_by_customer_type.setdefault(key, []).append(o)

    # 批量查询旧退货日志
    old_return_logs = await StockLog.filter(
        change_type="CONSIGN_RETURN", reference_type="CONSIGN_RETURN",
        reference_id__in=customer_ids, warehouse__is_virtual=True, quantity__lt=0
    ).select_related("product") if customer_ids else []
    return_logs_by_customer = {}
    for log in old_return_logs:
        return_logs_by_customer.setdefault(log.reference_id, []).append(log)

    customer_stats = {}
    total_settle_unpaid = 0

    for cid in customer_ids:
        customer = customer_map.get(cid)
        if customer:
            out_orders = orders_by_customer_type.get((cid, "CONSIGN_OUT"), [])
            settle_orders = orders_by_customer_type.get((cid, "CONSIGN_SETTLE"), [])
            return_orders = orders_by_customer_type.get((cid, "CONSIGN_RETURN"), [])

            total_out = sum(float(o.total_cost) for o in out_orders)
            total_settle = sum(float(o.total_cost) for o in settle_orders)
            total_return = sum(float(o.total_cost) for o in return_orders)

            for log in return_logs_by_customer.get(cid, []):
                if log.product:
                    total_return += abs(log.quantity) * float(log.product.cost_price)

            settle_unpaid = sum(float(o.total_amount - o.paid_amount) for o in settle_orders if not o.is_cleared)
            total_settle_unpaid += settle_unpaid

            customer_stats[cid] = {
                "customer_id": cid,
                "customer_name": customer.name,
                "total_out_cost": total_out,
                "total_settle_cost": total_settle,
                "total_return_cost": total_return,
                "remaining_cost": total_out - total_settle - total_return,
                "settle_unpaid": settle_unpaid,
                "balance": float(customer.balance)
            }

    product_stock_map = {}
    for s in stocks:
        pid = s.product_id
        if pid not in product_stock_map:
            product_stock_map[pid] = {
                "product_id": pid,
                "product_sku": s.product.sku,
                "product_name": s.product.name,
                "quantity": 0,
                "cost_price": float(s.product.cost_price),
                "retail_price": float(s.product.retail_price),
            }
        product_stock_map[pid]["quantity"] += s.quantity
    stock_details = []
    for item in product_stock_map.values():
        item["total_cost"] = item["quantity"] * item["cost_price"]
        item["total_retail"] = item["quantity"] * item["retail_price"]
        stock_details.append(item)

    total_cost_value = sum(item["total_cost"] for item in stock_details)
    total_retail_value = sum(item["total_retail"] for item in stock_details)

    return {
        "total_cost_value": total_cost_value,
        "total_retail_value": total_retail_value,
        "total_settle_unpaid": total_settle_unpaid,
        "total_items": len(stock_details),
        "total_quantity": sum(s.quantity for s in stocks),
        "customer_stats": list(customer_stats.values()),
        "stock_details": stock_details
    }


@router.get("/customer/{customer_id}")
async def get_customer_consignment(customer_id: int, user: User = Depends(require_permission("sales"))):
    """获取指定客户的寄售详情"""
    customer = await Customer.filter(id=customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    consignment_wh = await get_or_create_consignment_warehouse(customer_id)

    out_orders = await Order.filter(customer_id=customer_id, order_type="CONSIGN_OUT").order_by("-created_at")
    settle_orders = await Order.filter(customer_id=customer_id, order_type="CONSIGN_SETTLE").order_by("-created_at")

    product_stats = {}

    # 批量查询所有订单的明细（避免 N+1）
    all_order_ids = [o.id for o in out_orders] + [o.id for o in settle_orders]
    return_orders = await Order.filter(customer_id=customer_id, order_type="CONSIGN_RETURN")
    all_order_ids += [o.id for o in return_orders]

    all_items = await OrderItem.filter(order_id__in=all_order_ids).select_related("product") if all_order_ids else []
    items_by_order = {}
    for item in all_items:
        items_by_order.setdefault(item.order_id, []).append(item)

    for order in out_orders:
        for item in items_by_order.get(order.id, []):
            pid = item.product_id
            if pid not in product_stats:
                product_stats[pid] = {
                    "product_id": pid,
                    "product_sku": item.product.sku,
                    "product_name": item.product.name,
                    "out_quantity": 0,
                    "settle_quantity": 0,
                    "return_quantity": 0,
                    "remaining_quantity": 0,
                    "cost_price": float(item.cost_price),
                    "retail_price": float(item.product.retail_price)
                }
            product_stats[pid]["out_quantity"] += item.quantity

    for order in settle_orders:
        for item in items_by_order.get(order.id, []):
            pid = item.product_id
            if pid in product_stats:
                product_stats[pid]["settle_quantity"] += abs(item.quantity)

    for order in return_orders:
        for item in items_by_order.get(order.id, []):
            pid = item.product_id
            if pid in product_stats:
                product_stats[pid]["return_quantity"] += abs(item.quantity)

    return_logs = await StockLog.filter(
        change_type="CONSIGN_RETURN", reference_type="CONSIGN_RETURN",
        reference_id=customer_id, warehouse__is_virtual=True, quantity__lt=0
    ).select_related("product")
    for log in return_logs:
        pid = log.product_id
        if pid in product_stats:
            product_stats[pid]["return_quantity"] += abs(log.quantity)

    for pid in product_stats:
        product_stats[pid]["remaining_quantity"] = (
            product_stats[pid]["out_quantity"]
            - product_stats[pid]["settle_quantity"]
            - product_stats[pid]["return_quantity"]
        )

    remaining_products = [p for p in product_stats.values() if p["remaining_quantity"] > 0]

    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "balance": float(customer.balance)
        },
        "total_out_orders": len(out_orders),
        "total_settle_orders": len(settle_orders),
        "remaining_products": remaining_products,
        "out_orders": [{
            "id": o.id,
            "order_no": o.order_no,
            "total_amount": float(o.total_amount),
            "total_cost": float(o.total_cost),
            "created_at": o.created_at.isoformat()
        } for o in out_orders[:20]],
        "settle_orders": [{
            "id": o.id,
            "order_no": o.order_no,
            "total_amount": float(o.total_amount),
            "paid_amount": float(o.paid_amount),
            "is_cleared": o.is_cleared,
            "created_at": o.created_at.isoformat()
        } for o in settle_orders[:20]]
    }


@router.get("/customers")
async def get_consignment_customers(user: User = Depends(require_permission("sales"))):
    """获取有寄售记录的客户列表"""
    orders = await Order.filter(order_type="CONSIGN_OUT").select_related("customer")
    customer_ids = list(set(o.customer_id for o in orders if o.customer_id))

    # 批量查询客户和订单（避免 N+1）
    customers = await Customer.filter(id__in=customer_ids) if customer_ids else []
    customer_map = {c.id: c for c in customers}

    all_consign_orders = await Order.filter(
        customer_id__in=customer_ids,
        order_type__in=["CONSIGN_OUT", "CONSIGN_SETTLE", "CONSIGN_RETURN"]
    ) if customer_ids else []
    orders_by_cust_type = {}
    for o in all_consign_orders:
        orders_by_cust_type.setdefault((o.customer_id, o.order_type), []).append(o)

    old_return_logs = await StockLog.filter(
        change_type="CONSIGN_RETURN", reference_type="CONSIGN_RETURN",
        reference_id__in=customer_ids, warehouse__is_virtual=True, quantity__lt=0
    ).select_related("product") if customer_ids else []
    logs_by_customer = {}
    for log in old_return_logs:
        logs_by_customer.setdefault(log.reference_id, []).append(log)

    result = []
    for cid in customer_ids:
        customer = customer_map.get(cid)
        if customer:
            out_orders = orders_by_cust_type.get((cid, "CONSIGN_OUT"), [])
            settle_orders = orders_by_cust_type.get((cid, "CONSIGN_SETTLE"), [])
            return_orders = orders_by_cust_type.get((cid, "CONSIGN_RETURN"), [])

            total_out = sum(float(o.total_cost) for o in out_orders)
            total_settle = sum(float(o.total_cost) for o in settle_orders)
            total_return = sum(float(o.total_cost) for o in return_orders)

            for log in logs_by_customer.get(cid, []):
                if log.product:
                    total_return += abs(log.quantity) * float(log.product.cost_price)

            result.append({
                "id": customer.id,
                "name": customer.name,
                "phone": customer.phone,
                "balance": float(customer.balance),
                "consign_out_count": len(out_orders),
                "consign_settle_count": len(settle_orders),
                "consign_out_cost": total_out,
                "consign_settle_cost": total_settle,
                "consign_return_cost": total_return,
                "consign_remaining_cost": total_out - total_settle - total_return
            })

    return result


@router.post("/return")
async def consignment_return(
    data: ConsignmentReturnRequest,
    user: User = Depends(require_permission("sales"))
):
    """寄售退货：从虚拟仓调回实际仓库，同时生成寄售退货订单"""
    try:
        customer_id = data.customer_id
        items = data.items

        customer = await Customer.filter(id=customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="客户不存在")

        consignment_wh = await get_or_create_consignment_warehouse(customer_id)
        from app.utils.generators import generate_order_no
        order_no = generate_order_no("CSR")

        async with transactions.in_transaction():
            order = await Order.create(
                order_no=order_no, order_type="CONSIGN_RETURN",
                customer=customer, warehouse=None,
                total_amount=Decimal("0"), total_cost=Decimal("0"), total_profit=Decimal("0"),
                is_cleared=True, creator=user
            )
            total_cost = Decimal("0")

            for item in items:
                product_id = item.product_id
                quantity = item.quantity
                warehouse_id = item.warehouse_id
                location_id = item.location_id

                product = await Product.filter(id=product_id).first()
                if not product:
                    raise HTTPException(status_code=404, detail=f"商品不存在: {product_id}")

                warehouse = await Warehouse.filter(id=warehouse_id, is_active=True).first()
                if not warehouse or warehouse.is_virtual:
                    raise HTTPException(status_code=400, detail="必须选择实体仓库")

                location = await Location.filter(id=location_id, is_active=True).first()
                if not location:
                    raise HTTPException(status_code=404, detail="仓位不存在")
                if location.warehouse_id != warehouse_id:
                    raise HTTPException(status_code=400, detail="仓位不属于所选仓库")

                cost_price = product.cost_price
                item_cost = cost_price * quantity
                total_cost += item_cost

                await OrderItem.create(
                    order=order, product=product, quantity=quantity,
                    unit_price=cost_price, cost_price=cost_price,
                    amount=item_cost, profit=Decimal("0"),
                    warehouse_id=warehouse_id, location_id=location_id
                )

                updated = await WarehouseStock.filter(
                    warehouse_id=consignment_wh.id, product_id=product_id, quantity__gte=quantity
                ).update(quantity=F('quantity') - quantity)
                if not updated:
                    raise HTTPException(status_code=400, detail=f"商品 {product.name} 在虚拟仓库存不足")
                virtual_stock = await WarehouseStock.filter(warehouse_id=consignment_wh.id, product_id=product_id).first()
                if not virtual_stock:
                    raise HTTPException(status_code=500, detail=f"虚拟仓库存记录异常: {product.name}")

                await StockLog.create(
                    product=product, warehouse=consignment_wh,
                    change_type="CONSIGN_RETURN", quantity=-quantity,
                    before_qty=virtual_stock.quantity + quantity, after_qty=virtual_stock.quantity,
                    reference_type="ORDER", reference_id=order.id,
                    creator=user, remark=f"寄售退货-{customer.name}"
                )

                # 使用 select_for_update 保护实际仓库库存并发安全
                real_stock = await WarehouseStock.filter(
                    warehouse_id=warehouse_id, product_id=product_id, location_id=location_id
                ).select_for_update().first()
                before_qty = real_stock.quantity if real_stock else 0

                await update_weighted_entry_date(warehouse_id, product_id, quantity, location_id=location_id)

                # 重新获取更新后的库存
                real_stock = await WarehouseStock.filter(
                    warehouse_id=warehouse_id, product_id=product_id, location_id=location_id
                ).first()

                await StockLog.create(
                    product=product, warehouse=warehouse,
                    change_type="CONSIGN_RETURN", quantity=quantity,
                    before_qty=before_qty, after_qty=real_stock.quantity if real_stock else quantity,
                    reference_type="ORDER", reference_id=order.id,
                    creator=user, remark=f"寄售退货-{customer.name}"
                )

            order.total_amount = total_cost
            order.total_cost = total_cost
            await order.save()

            return {"message": "寄售退货成功", "count": len(items), "order_no": order_no}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("寄售退货失败", exc_info=e)
        raise HTTPException(status_code=500, detail="寄售退货失败，请重试")
