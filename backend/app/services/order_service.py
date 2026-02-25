"""
订单业务逻辑服务层
从 routers/orders.py 提取，使路由层只负责参数接收和响应格式化
"""
from decimal import Decimal

from fastapi import HTTPException
from tortoise.expressions import F

from app.models import (
    User, Product, Warehouse, Location, Customer, Salesperson,
    Order, OrderItem, WarehouseStock, StockLog, Payment,
    RebateLog
)
from app.services.stock_service import (
    get_or_create_consignment_warehouse, update_weighted_entry_date,
    get_product_weighted_cost
)
from app.utils.generators import generate_order_no
from app.logger import get_logger

logger = get_logger("order_service")


async def validate_order_entities(data):
    """
    校验订单关联实体（客户、仓库、销售员、关联订单）的存在性和合法性。
    返回 (customer, warehouse, salesperson, consignment_wh)
    """
    customer = None
    if data.customer_id:
        customer = await Customer.filter(id=data.customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="客户不存在")

    salesperson = None
    if data.salesperson_id:
        salesperson = await Salesperson.filter(id=data.salesperson_id, is_active=True).first()
        if not salesperson:
            raise HTTPException(status_code=404, detail="销售员不存在")

    warehouse = None
    if data.warehouse_id:
        warehouse = await Warehouse.filter(id=data.warehouse_id, is_active=True).first()
        if not warehouse:
            raise HTTPException(status_code=404, detail="仓库不存在")

    # 需要实体仓库的订单类型
    if data.order_type in ["CASH", "CREDIT", "CONSIGN_OUT"]:
        if not warehouse:
            for idx, item in enumerate(data.items):
                if not item.warehouse_id or not item.location_id:
                    raise HTTPException(status_code=400, detail=f"商品 {idx+1} 需要选择仓库和仓位")
        elif warehouse.is_virtual:
            raise HTTPException(status_code=400, detail="需要选择实体仓库")

    # 需要客户的订单类型
    if data.order_type in ["CASH", "CREDIT", "CONSIGN_OUT", "CONSIGN_SETTLE", "RETURN"]:
        if not customer:
            raise HTTPException(status_code=400, detail="需要选择客户")

    # 寄售虚拟仓
    consignment_wh = None
    if data.order_type in ["CONSIGN_OUT", "CONSIGN_SETTLE"]:
        consignment_wh = await get_or_create_consignment_warehouse(customer.id)
    if data.order_type == "CONSIGN_SETTLE":
        warehouse = consignment_wh

    # 退货校验
    if data.order_type == "RETURN":
        if not data.related_order_id:
            raise HTTPException(status_code=400, detail="退货需要选择原始销售订单")
        if not warehouse:
            for idx, item in enumerate(data.items):
                if not item.warehouse_id or not item.location_id:
                    raise HTTPException(status_code=400, detail=f"商品 {idx+1} 需要选择退货仓库和仓位")
        else:
            if not data.location_id:
                raise HTTPException(status_code=400, detail="退货需要选择仓位")
            location = await Location.filter(id=data.location_id, is_active=True).first()
            if not location:
                raise HTTPException(status_code=404, detail="仓位不存在")
        related_order = await Order.filter(id=data.related_order_id, order_type__in=["CASH", "CREDIT"]).first()
        if not related_order:
            raise HTTPException(status_code=404, detail="关联的销售订单不存在或类型错误")
        if related_order.customer_id != customer.id:
            raise HTTPException(status_code=400, detail="退货客户必须与原订单客户一致")

    return customer, warehouse, salesperson, consignment_wh


async def resolve_item_entities(item, warehouse, data, entities_cache=None):
    """
    解析单个订单行的商品、仓库、仓位。
    返回 (product, working_warehouse, working_location, cost_price)
    """
    if entities_cache and 'products' in entities_cache:
        product = entities_cache['products'].get(item.product_id)
    else:
        product = await Product.filter(id=item.product_id, is_active=True).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"商品不存在: {item.product_id}")

    item_warehouse = None
    item_location = None
    if item.warehouse_id:
        if entities_cache and 'warehouses' in entities_cache:
            item_warehouse = entities_cache['warehouses'].get(item.warehouse_id)
        else:
            item_warehouse = await Warehouse.filter(id=item.warehouse_id, is_active=True).first()
        if not item_warehouse:
            raise HTTPException(status_code=404, detail=f"商品的仓库不存在: {item.warehouse_id}")
    if item.location_id:
        if entities_cache and 'locations' in entities_cache:
            item_location = entities_cache['locations'].get(item.location_id)
        else:
            item_location = await Location.filter(id=item.location_id, is_active=True).first()
        if not item_location:
            raise HTTPException(status_code=404, detail=f"商品的仓位不存在: {item.location_id}")
        check_wh = item_warehouse if item_warehouse else warehouse
        if check_wh and item_location.warehouse_id != check_wh.id:
            raise HTTPException(status_code=400, detail=f"商品 {item.product_id} 的仓位不属于所选仓库")

    working_warehouse = item_warehouse if item_warehouse else warehouse
    working_location = item_location if item_location else (
        await Location.filter(id=data.location_id).first() if data.location_id else None
    )

    if data.order_type in ["CASH", "CREDIT", "CONSIGN_OUT", "RETURN"]:
        if working_warehouse and working_warehouse.is_virtual:
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 不能从寄售虚拟仓出库，请选择实体仓库")

    # 成本价
    if working_warehouse and not working_warehouse.is_virtual:
        stock_for_cost = await WarehouseStock.filter(
            warehouse_id=working_warehouse.id, product_id=product.id,
            location_id=working_location.id if working_location else None
        ).first()
        cost_price = stock_for_cost.weighted_cost if stock_for_cost and stock_for_cost.weighted_cost else product.cost_price
    else:
        cost_price = await get_product_weighted_cost(product.id)

    return product, working_warehouse, working_location, cost_price


async def process_item_stock(order_type, product, working_warehouse, working_location,
                             qty, order, user, consignment_wh=None, cost_price=None):
    """
    根据订单类型处理单个商品的库存操作（使用行锁保证并发安全）：
    预留(CASH/CREDIT)、寄售调拨(CONSIGN_OUT)、寄售结算(CONSIGN_SETTLE)、退货入库(RETURN)。
    """
    if order_type in ["CASH", "CREDIT"]:
        if not working_warehouse:
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定仓库")
        if not working_location:
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定仓位")
        stock = await WarehouseStock.filter(
            warehouse_id=working_warehouse.id, product_id=product.id,
            location_id=working_location.id
        ).select_for_update().first()
        available = (stock.quantity - stock.reserved_qty) if stock else 0
        if available < qty:
            raise HTTPException(status_code=400,
                detail=f"商品 {product.name} 在 {working_warehouse.name}-{working_location.code} "
                       f"可用库存不足（可用 {available}，需要 {qty}）")
        before_qty = stock.quantity - stock.reserved_qty
        await WarehouseStock.filter(id=stock.id).update(reserved_qty=F('reserved_qty') + qty)
        await StockLog.create(
            product=product, warehouse=working_warehouse, change_type="RESERVE",
            quantity=-qty, before_qty=before_qty, after_qty=before_qty - qty,
            reference_type="ORDER", reference_id=order.id,
            remark=f"预留库存 {qty}", creator=user
        )

    elif order_type == "CONSIGN_OUT":
        if not working_warehouse:
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定仓库")
        if not working_location:
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定仓位")
        stock = await WarehouseStock.filter(
            warehouse_id=working_warehouse.id, product_id=product.id,
            location_id=working_location.id
        ).select_for_update().first()
        available = (stock.quantity - stock.reserved_qty) if stock else 0
        if available < qty:
            raise HTTPException(status_code=400,
                detail=f"商品 {product.name} 在 {working_warehouse.name}-{working_location.code} "
                       f"可用库存不足（可用 {available}，需要 {qty}）")
        before_qty = stock.quantity - stock.reserved_qty
        await WarehouseStock.filter(id=stock.id).update(reserved_qty=F('reserved_qty') + qty)
        await StockLog.create(
            product=product, warehouse=working_warehouse, change_type="RESERVE",
            quantity=-qty, before_qty=before_qty, after_qty=before_qty - qty,
            reference_type="ORDER", reference_id=order.id,
            remark=f"寄售调拨预留库存 {qty}", creator=user
        )

    elif order_type == "CONSIGN_SETTLE":
        stock = await WarehouseStock.filter(
            warehouse_id=consignment_wh.id, product_id=product.id
        ).select_for_update().first()
        if not stock or stock.quantity < qty:
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 寄售库存不足")
        before_qty = stock.quantity
        await WarehouseStock.filter(id=stock.id).update(quantity=F('quantity') - qty)
        await StockLog.create(
            product=product, warehouse=consignment_wh, change_type="CONSIGN_SETTLE",
            quantity=-qty, before_qty=before_qty, after_qty=before_qty - qty,
            reference_type="ORDER", reference_id=order.id, creator=user
        )

    elif order_type == "RETURN":
        if not working_warehouse:
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定退货仓库")
        if not working_location:
            raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定退货仓位")
        await update_weighted_entry_date(working_warehouse.id, product.id, qty, cost_price=cost_price, location_id=working_location.id)
        stock = await WarehouseStock.filter(
            warehouse_id=working_warehouse.id, product_id=product.id, location_id=working_location.id
        ).select_for_update().first()
        await StockLog.create(
            product=product, warehouse=working_warehouse, change_type="RETURN",
            quantity=qty, before_qty=stock.quantity - qty, after_qty=stock.quantity,
            reference_type="ORDER", reference_id=order.id, creator=user
        )


async def process_rebate_deduction(data, customer, order, order_no, user):
    """
    处理返利扣减。若订单使用了返利，校验余额并扣减。
    返回 total_rebate 金额。
    """
    total_rebate = sum(
        Decimal(str(it.rebate_amount)) if it.rebate_amount else Decimal("0")
        for it in data.items
    )
    if total_rebate > 0 and data.order_type != "RETURN":
        if not customer:
            raise HTTPException(status_code=400, detail="使用返利需要选择客户")
        customer = await Customer.filter(id=customer.id).select_for_update().first()
        if customer.rebate_balance < total_rebate:
            raise HTTPException(status_code=400,
                detail=f"客户返利余额不足，可用 ¥{float(customer.rebate_balance):.2f}，"
                       f"需要 ¥{float(total_rebate):.2f}")
        await Customer.filter(id=customer.id).update(rebate_balance=F('rebate_balance') - total_rebate)
        await customer.refresh_from_db()
        order.rebate_used = total_rebate
        rebate_remark = f"[返利抵扣] 使用返利 ¥{float(total_rebate):.2f}"
        order.remark = f"{order.remark}\n{rebate_remark}" if order.remark else rebate_remark
        await RebateLog.create(
            target_type="customer", target_id=customer.id,
            type="use", amount=total_rebate,
            balance_after=customer.rebate_balance,
            reference_type="ORDER", reference_id=order.id,
            remark=f"销售订单 {order_no} 使用返利", creator=user
        )
    return total_rebate


async def process_order_settlement(data, customer, order, total_amount, user, order_no):
    """
    处理订单结算：CREDIT 挂账、CASH 收款（含预付余额抵扣）、RETURN 退款到余额。
    返回 credit_used 金额。
    """
    actual_credit_used = 0

    if customer and data.order_type in ["CREDIT", "CONSIGN_SETTLE"]:
        customer = await Customer.filter(id=customer.id).select_for_update().first()
        old_balance = customer.balance
        await Customer.filter(id=customer.id).update(balance=F('balance') + total_amount)
        if old_balance < 0:
            available_credit = abs(old_balance)
            amount_to_deduct = min(available_credit, abs(total_amount))
            order.paid_amount = Decimal(str(amount_to_deduct))
            if order.paid_amount >= abs(total_amount):
                order.is_cleared = True
            await order.save()

    elif customer and data.order_type == "CASH":
        customer = await Customer.filter(id=customer.id).select_for_update().first()
        if data.use_credit and customer.balance < 0:
            available_credit = abs(customer.balance)
            amount_to_use = min(available_credit, abs(total_amount))
            await Customer.filter(id=customer.id).update(balance=F('balance') + Decimal(str(amount_to_use)))
            order.paid_amount = Decimal(str(amount_to_use))
            if amount_to_use >= abs(total_amount):
                order.is_cleared = True
            await order.save()
            actual_credit_used = amount_to_use

    elif customer and data.order_type == "RETURN":
        if not data.refunded:
            # 仅 CREDIT 退货需调整余额（减少应收），CASH 退货未退款无需改余额
            related_order = await Order.filter(id=data.related_order_id).first() if data.related_order_id else None
            if related_order and related_order.order_type == "CREDIT":
                await Customer.filter(id=customer.id).update(balance=F('balance') + total_amount)

    # 计算 credit_used 返回值
    credit_used = 0
    if data.order_type == "CASH":
        if actual_credit_used > 0:
            credit_used = float(actual_credit_used)
    elif data.order_type in ["CREDIT", "CONSIGN_SETTLE"]:
        if order.paid_amount > 0:
            credit_used = float(order.paid_amount)

    # CASH 订单创建收款记录
    if data.order_type == "CASH" and customer:
        actual_pay = abs(float(total_amount)) - float(credit_used)
        if actual_pay > 0:
            pay_no = generate_order_no("PAY")
            await Payment.create(
                payment_no=pay_no, customer=customer, order=order,
                amount=Decimal(str(actual_pay)),
                payment_method=data.payment_method or "cash",
                source="CASH", is_confirmed=False,
                remark=f"现款销售 {order_no}", creator=user
            )

    return credit_used


async def release_cancelled_stock(items, order, user):
    """
    取消订单时释放未发货商品的库存预留。
    """
    for item in items:
        remaining = abs(item.quantity) - item.shipped_qty
        if remaining <= 0:
            continue

        # 使用 ID 直接查询，避免依赖未加载的关系
        wh_id = item.warehouse_id or order.warehouse_id
        loc_id = item.location_id

        if wh_id and loc_id:
            stock = await WarehouseStock.filter(
                warehouse_id=wh_id, product_id=item.product_id, location_id=loc_id
            ).select_for_update().first()
            if stock:
                # 释放可用的预留量（即使 reserved_qty < remaining 也尽量释放）
                release_amount = min(remaining, stock.reserved_qty)
                if release_amount > 0:
                    before_available = stock.quantity - stock.reserved_qty
                    await WarehouseStock.filter(id=stock.id).update(
                        reserved_qty=F('reserved_qty') - release_amount
                    )
                    await StockLog.create(
                        product_id=item.product_id, warehouse_id=wh_id,
                        change_type="RESERVE_CANCEL",
                        quantity=release_amount,
                        before_qty=before_available, after_qty=before_available + release_amount,
                        reference_type="ORDER", reference_id=order.id,
                        remark=f"取消订单释放预留 {release_amount}",
                        creator=user
                    )
                if stock.reserved_qty < remaining:
                    logger.warning(
                        f"预留量不足: product_id={item.product_id}, "
                        f"reserved={stock.reserved_qty}, remaining={remaining}"
                    )
