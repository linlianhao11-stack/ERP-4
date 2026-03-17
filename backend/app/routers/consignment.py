"""寄售管理路由"""
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from tortoise.expressions import F

from app.auth.dependencies import get_current_user, require_permission
from app.constants import OrderType, StockChangeType
from app.models import (
    User, Order, OrderItem, Customer, Product, Warehouse, Location,
    WarehouseStock, StockLog
)
from app.schemas.consignment import ConsignmentReturnRequest
from app.services.stock_service import get_or_create_consignment_warehouse, update_weighted_entry_date
from app.utils.batch_load import batch_load_related
from app.logger import get_logger
from app.utils.response import paginated_response

logger = get_logger("consignment")

router = APIRouter(prefix="/api/consignment", tags=["寄售管理"])


@router.get("/summary")
async def get_consignment_summary(user: User = Depends(require_permission("sales"))):
    """获取寄售汇总数据（全部使用原生 SQL 避免 ORM 对象构造开销）"""
    from tortoise import connections
    conn = connections.get("default")

    # ---- 1. 按 (客户, 类型) 聚合订单统计（替代加载 12,500+ Order 对象）----
    order_agg = await conn.execute_query_dict("""
        SELECT customer_id, order_type,
               COUNT(*) as order_count,
               COALESCE(SUM(total_cost), 0) as total_cost,
               COALESCE(SUM(CASE WHEN is_cleared = false THEN total_amount - paid_amount ELSE 0 END), 0) as settle_unpaid
        FROM orders
        WHERE order_type IN ('CONSIGN_OUT', 'CONSIGN_SETTLE', 'CONSIGN_RETURN')
          AND customer_id IS NOT NULL
        GROUP BY customer_id, order_type
    """)
    # 收集有 CONSIGN_OUT 记录的客户
    customer_ids = list(set(r["customer_id"] for r in order_agg if r["order_type"] == OrderType.CONSIGN_OUT))
    if not customer_ids:
        return {
            "total_cost_value": 0, "total_sales_value": 0, "total_settle_unpaid": 0,
            "total_items": 0, "total_quantity": 0, "customer_stats": [], "stock_details": []
        }
    agg_map = {}
    for r in order_agg:
        agg_map[(r["customer_id"], r["order_type"])] = r

    # ---- 2. 批量查询客户信息 ----
    customers = await Customer.filter(id__in=customer_ids)
    customer_map = {c.id: c for c in customers}

    # ---- 3. 旧退货日志按客户聚合退货成本 ----
    return_cost_rows = await conn.execute_query_dict("""
        SELECT sl.reference_id as customer_id,
               COALESCE(SUM(ABS(sl.quantity) * p.cost_price), 0) as return_cost
        FROM stock_logs sl
        JOIN warehouses w ON w.id = sl.warehouse_id
        JOIN products p ON p.id = sl.product_id
        WHERE sl.change_type = 'CONSIGN_RETURN' AND sl.reference_type = 'CONSIGN_RETURN'
          AND w.is_virtual = true AND sl.quantity < 0
        GROUP BY sl.reference_id
    """)
    return_cost_map = {r["customer_id"]: float(r["return_cost"]) for r in return_cost_rows}

    # ---- 4. 构建客户统计 ----
    customer_stats = {}
    total_settle_unpaid = 0
    for cid in customer_ids:
        customer = customer_map.get(cid)
        if not customer:
            continue
        out_agg = agg_map.get((cid, OrderType.CONSIGN_OUT), {})
        settle_agg = agg_map.get((cid, OrderType.CONSIGN_SETTLE), {})
        return_agg = agg_map.get((cid, OrderType.CONSIGN_RETURN), {})

        total_out = float(out_agg.get("total_cost", 0))
        total_settle = float(settle_agg.get("total_cost", 0))
        total_return = float(return_agg.get("total_cost", 0))
        total_return += return_cost_map.get(cid, 0)

        settle_unpaid = float(settle_agg.get("settle_unpaid", 0))
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

    # ---- 5. 虚拟仓库存明细（按 product_id 聚合，含商品信息）----
    stock_rows = await conn.execute_query_dict("""
        SELECT ws.product_id, SUM(ws.quantity) as quantity,
               p.sku, p.name, p.cost_price, p.retail_price
        FROM warehouse_stocks ws
        JOIN warehouses w ON w.id = ws.warehouse_id
        JOIN products p ON p.id = ws.product_id
        WHERE w.is_virtual = true AND ws.quantity > 0
        GROUP BY ws.product_id, p.sku, p.name, p.cost_price, p.retail_price
    """)
    product_remaining = {}
    total_stock_quantity = 0
    for r in stock_rows:
        product_remaining[r["product_id"]] = {
            "quantity": r["quantity"],
            "sku": r["sku"], "name": r["name"],
            "cost_price": float(r["cost_price"]),
            "retail_price": float(r["retail_price"]),
        }
        total_stock_quantity += r["quantity"]

    # ---- 6. 预聚合价格批次（替代加载 37,510 OrderItem + select_related）----
    batch_rows = await conn.execute_query_dict("""
        SELECT oi.product_id, oi.unit_price, SUM(oi.quantity) as total_qty,
               MIN(o.created_at) as earliest_date,
               p.sku, p.name, p.cost_price, p.retail_price
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id
        WHERE o.order_type = 'CONSIGN_OUT'
        GROUP BY oi.product_id, oi.unit_price, p.sku, p.name, p.cost_price, p.retail_price
    """)
    price_batches = {}  # pid -> [{unit_price, total_qty, earliest_date, ...}]
    for r in batch_rows:
        pid = r["product_id"]
        if pid not in price_batches:
            price_batches[pid] = []
        price_batches[pid].append({
            "unit_price": float(r["unit_price"]),
            "total_qty": r["total_qty"],
            "earliest_date": r["earliest_date"],
            "sku": r["sku"], "name": r["name"],
            "cost_price": float(r["cost_price"]),
            "retail_price": float(r["retail_price"]),
        })

    # ---- 7. FIFO 分配剩余库存到各价格批次 ----
    stock_details = []
    for pid, info in product_remaining.items():
        remaining_qty = info["quantity"]

        if pid not in price_batches:
            # 有库存但无调拨记录，用零售价兜底
            stock_details.append({
                "product_id": pid,
                "product_sku": info["sku"],
                "product_name": info["name"],
                "quantity": remaining_qty,
                "cost_price": info["cost_price"],
                "unit_price": info["retail_price"],
                "total_cost": remaining_qty * info["cost_price"],
                "total_sales": remaining_qty * info["retail_price"],
            })
            continue

        batches = sorted(price_batches[pid], key=lambda b: b["earliest_date"])
        total_out = sum(b["total_qty"] for b in batches)
        deduction_left = max(0, total_out - remaining_qty)
        for batch in batches:
            deduct = min(deduction_left, batch["total_qty"])
            batch["remaining"] = batch["total_qty"] - deduct
            deduction_left -= deduct

        for batch in batches:
            qty = batch.get("remaining", batch["total_qty"])
            if qty > 0:
                stock_details.append({
                    "product_id": pid,
                    "product_sku": batch["sku"],
                    "product_name": batch["name"],
                    "quantity": qty,
                    "cost_price": batch["cost_price"],
                    "unit_price": batch["unit_price"],
                    "total_cost": qty * batch["cost_price"],
                    "total_sales": qty * batch["unit_price"],
                })

    total_cost_value = sum(item["total_cost"] for item in stock_details)
    total_sales_value = sum(item["total_sales"] for item in stock_details)

    return {
        "total_cost_value": total_cost_value,
        "total_sales_value": total_sales_value,
        "total_settle_unpaid": total_settle_unpaid,
        "total_items": len(stock_details),
        "total_quantity": total_stock_quantity,
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

    out_orders = await Order.filter(customer_id=customer_id, order_type=OrderType.CONSIGN_OUT.value).order_by("-created_at")
    settle_orders = await Order.filter(customer_id=customer_id, order_type=OrderType.CONSIGN_SETTLE.value).order_by("-created_at")

    product_stats = {}  # key: (product_id, unit_price)

    # 批量查询所有订单的明细（避免 N+1）
    all_order_ids = [o.id for o in out_orders] + [o.id for o in settle_orders]
    return_orders = await Order.filter(customer_id=customer_id, order_type=OrderType.CONSIGN_RETURN.value)
    all_order_ids += [o.id for o in return_orders]

    items_by_order = await batch_load_related(OrderItem, 'order_id', all_order_ids, ['product'])

    # 按 (product_id, unit_price) 分组调拨记录
    for order in out_orders:
        for item in items_by_order.get(order.id, []):
            pid = item.product_id
            up = float(item.unit_price)
            key = (pid, up)
            if key not in product_stats:
                product_stats[key] = {
                    "product_id": pid,
                    "product_sku": item.product.sku,
                    "product_name": item.product.name,
                    "out_quantity": 0,
                    "remaining_quantity": 0,
                    "cost_price": float(item.cost_price),
                    "unit_price": up,
                    "earliest_date": order.created_at,
                }
            product_stats[key]["out_quantity"] += item.quantity
            if order.created_at < product_stats[key]["earliest_date"]:
                product_stats[key]["earliest_date"] = order.created_at

    # 按 product_id 汇总结算/退货总量（结算退货不区分价格批次）
    deductions_by_product = defaultdict(int)
    for order in settle_orders:
        for item in items_by_order.get(order.id, []):
            deductions_by_product[item.product_id] += abs(item.quantity)

    for order in return_orders:
        for item in items_by_order.get(order.id, []):
            deductions_by_product[item.product_id] += abs(item.quantity)

    return_logs = await StockLog.filter(
        change_type=StockChangeType.CONSIGN_RETURN.value, reference_type="CONSIGN_RETURN",
        reference_id=customer_id, warehouse__is_virtual=True, quantity__lt=0
    ).select_related("product")
    for log in return_logs:
        deductions_by_product[log.product_id] += abs(log.quantity)

    # FIFO 分配扣减量到各价格批次
    product_keys = defaultdict(list)
    for key in product_stats:
        product_keys[key[0]].append(key)

    for pid, keys in product_keys.items():
        keys.sort(key=lambda k: product_stats[k]["earliest_date"])
        deduction_left = deductions_by_product.get(pid, 0)
        for key in keys:
            stats = product_stats[key]
            deduct = min(deduction_left, stats["out_quantity"])
            stats["remaining_quantity"] = stats["out_quantity"] - deduct
            deduction_left -= deduct

    remaining_products = [
        {k: v for k, v in p.items() if k != "earliest_date"}
        for p in product_stats.values()
        if p["remaining_quantity"] > 0
    ]

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
    """获取有寄售记录的客户列表（原生 SQL 聚合）"""
    from tortoise import connections
    conn = connections.get("default")

    # 按 (客户, 类型) 聚合订单统计
    order_agg = await conn.execute_query_dict("""
        SELECT customer_id, order_type,
               COUNT(*) as order_count,
               COALESCE(SUM(total_cost), 0) as total_cost
        FROM orders
        WHERE order_type IN ('CONSIGN_OUT', 'CONSIGN_SETTLE', 'CONSIGN_RETURN')
          AND customer_id IS NOT NULL
        GROUP BY customer_id, order_type
    """)
    out_customer_ids = set()
    agg_map = {}
    for r in order_agg:
        agg_map[(r["customer_id"], r["order_type"])] = r
        if r["order_type"] == OrderType.CONSIGN_OUT:
            out_customer_ids.add(r["customer_id"])

    customer_ids = list(out_customer_ids)
    if not customer_ids:
        return paginated_response([])

    customers = await Customer.filter(id__in=customer_ids)
    customer_map = {c.id: c for c in customers}

    # 旧退货日志按客户聚合
    return_cost_rows = await conn.execute_query_dict("""
        SELECT sl.reference_id as customer_id,
               COALESCE(SUM(ABS(sl.quantity) * p.cost_price), 0) as return_cost
        FROM stock_logs sl
        JOIN warehouses w ON w.id = sl.warehouse_id
        JOIN products p ON p.id = sl.product_id
        WHERE sl.change_type = 'CONSIGN_RETURN' AND sl.reference_type = 'CONSIGN_RETURN'
          AND w.is_virtual = true AND sl.quantity < 0
        GROUP BY sl.reference_id
    """)
    return_cost_map = {r["customer_id"]: float(r["return_cost"]) for r in return_cost_rows}

    result = []
    for cid in customer_ids:
        customer = customer_map.get(cid)
        if not customer:
            continue
        out_agg = agg_map.get((cid, OrderType.CONSIGN_OUT), {})
        settle_agg = agg_map.get((cid, OrderType.CONSIGN_SETTLE), {})
        return_agg = agg_map.get((cid, OrderType.CONSIGN_RETURN), {})

        total_out = float(out_agg.get("total_cost", 0))
        total_settle = float(settle_agg.get("total_cost", 0))
        total_return = float(return_agg.get("total_cost", 0))
        total_return += return_cost_map.get(cid, 0)

        result.append({
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "balance": float(customer.balance),
            "consign_out_count": out_agg.get("order_count", 0),
            "consign_settle_count": settle_agg.get("order_count", 0),
            "consign_out_cost": total_out,
            "consign_settle_cost": total_settle,
            "consign_return_cost": total_return,
            "consign_remaining_cost": total_out - total_settle - total_return
        })

    return paginated_response(result)


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
        from app.utils.generators import generate_sequential_no
        order_no = await generate_sequential_no("CR", "orders", "order_no")

        async with transactions.in_transaction():
            order = await Order.create(
                order_no=order_no, order_type=OrderType.CONSIGN_RETURN.value,
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
                    change_type=StockChangeType.CONSIGN_RETURN.value, quantity=-quantity,
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
                    change_type=StockChangeType.CONSIGN_RETURN.value, quantity=quantity,
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
