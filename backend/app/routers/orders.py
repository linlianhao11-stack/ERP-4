from typing import Optional
from decimal import Decimal
from datetime import date, datetime, timedelta
import json

from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from tortoise.expressions import F

from app.auth.dependencies import get_current_user, require_permission
from app.models import (
    User, Product, Warehouse, Location, Customer,
    Order, OrderItem, WarehouseStock, StockLog, Payment, PaymentOrder,
    Shipment, ShipmentItem, RebateLog
)
from app.models.department import Employee
from app.models.customer_balance import CustomerAccountBalance
from app.models.accounting import AccountSet, AccountingPeriod
from app.schemas.order import OrderCreate, CancelRequest
from app.services.order_service import (
    validate_order_entities, resolve_item_entities, process_item_stock,
    process_rebate_deduction, process_order_settlement, release_cancelled_stock
)
from app.services.operation_log_service import log_operation
from app.utils.generators import generate_order_no, generate_sequential_no
from app.utils.errors import parse_date
from app.logger import get_logger

logger = get_logger("orders")

router = APIRouter(prefix="/api/orders", tags=["订单管理"])


@router.post("")
async def create_order(data: OrderCreate, user: User = Depends(require_permission("sales"))):
    async with transactions.in_transaction():
        try:
            order_no = await generate_sequential_no("SO", "orders", "order_no")
            total_amount = Decimal("0")
            total_cost = Decimal("0")
            total_profit = Decimal("0")

            # 1. 校验关联实体
            customer, warehouse, employee, consignment_wh = await validate_order_entities(data)

            # 2. 从订单行仓库自动推断账套
            # 批量预加载仓库（后续创建订单行时复用）
            _warehouse_ids = list(set(
                i.warehouse_id for i in data.items if i.warehouse_id
            ))
            if data.warehouse_id and data.warehouse_id not in _warehouse_ids:
                _warehouse_ids.append(data.warehouse_id)
            _warehouses_map = {w.id: w for w in await Warehouse.filter(id__in=_warehouse_ids, is_active=True)} if _warehouse_ids else {}

            account_set_ids = set()
            for item in data.items:
                wh = _warehouses_map.get(item.warehouse_id) if item.warehouse_id else warehouse
                if wh and wh.account_set_id:
                    account_set_ids.add(wh.account_set_id)

            if len(account_set_ids) == 1:
                account_set_id = next(iter(account_set_ids))
            elif len(account_set_ids) > 1:
                account_set_id = None  # 多账套订单
            else:
                account_set_id = data.account_set_id  # 回退到手动指定

            # 2.5 会计期间校验：确保相关账套的当前期间未关闭
            _validate_as_ids = account_set_ids if account_set_ids else ({account_set_id} if account_set_id else set())
            for _as_id in _validate_as_ids:
                acct_set = await AccountSet.filter(id=_as_id).first()
                if acct_set and acct_set.current_period:
                    period = await AccountingPeriod.filter(
                        account_set_id=_as_id,
                        period_name=acct_set.current_period
                    ).first()
                    if period and period.is_closed:
                        raise HTTPException(
                            status_code=400,
                            detail=f"账套 {acct_set.name} 的当前期间 {acct_set.current_period} 已关闭，无法创建订单"
                        )

            # 3. 创建订单主记录
            is_cleared = data.order_type == "CASH" or (data.order_type == "RETURN" and data.refunded)
            shipping_status = "pending" if data.order_type in ["CASH", "CREDIT", "CONSIGN_OUT"] else "completed"
            order = await Order.create(
                order_no=order_no, order_type=data.order_type,
                customer=customer, warehouse=warehouse,
                related_order_id=data.related_order_id if data.order_type == "RETURN" else None,
                refunded=data.refunded if data.order_type == "RETURN" else False,
                remark=data.remark, employee=employee,
                creator=user, is_cleared=is_cleared,
                shipping_status=shipping_status,
                account_set_id=account_set_id
            )

            # 4. 创建订单行 + 库存处理
            # 批量预加载实体，避免 N+1 查询（_warehouses_map 已在步骤2中预加载）
            _product_ids = list(set(i.product_id for i in data.items))
            _location_ids = list(set(
                i.location_id for i in data.items if i.location_id
            ))
            if data.location_id and data.location_id not in _location_ids:
                _location_ids.append(data.location_id)

            _products_map = {p.id: p for p in await Product.filter(id__in=_product_ids, is_active=True)} if _product_ids else {}
            _locations_map = {l.id: l for l in await Location.filter(id__in=_location_ids, is_active=True)} if _location_ids else {}
            _entities_cache = {'products': _products_map, 'warehouses': _warehouses_map, 'locations': _locations_map}

            # 按账套汇总金额（用于多账套订单的财务单据拆分）
            amount_by_account_set = {}

            for item in data.items:
                product, working_warehouse, working_location, cost_price = await resolve_item_entities(
                    item, warehouse, data, entities_cache=_entities_cache
                )

                qty = item.quantity
                unit_price = Decimal(str(item.unit_price))
                amount = unit_price * qty
                item_rebate = Decimal(str(item.rebate_amount)) if item.rebate_amount else Decimal("0")

                if item_rebate > 0:
                    if item_rebate > amount:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 返利金额不能超过行金额")
                    amount = amount - item_rebate
                profit = amount - cost_price * qty

                if data.order_type == "RETURN":
                    # profit was already correctly calculated as (amount - cost_price * qty)
                    # before negation, so we negate the actual profit value, not abs(profit)
                    profit = -profit
                    amount = -abs(amount)
                    qty = abs(qty)
                    item_rebate = Decimal("0")

                total_amount += amount
                total_cost += cost_price * qty
                total_profit += profit

                await OrderItem.create(
                    order=order, product=product,
                    warehouse=working_warehouse, location=working_location,
                    quantity=qty if data.order_type != "RETURN" else -qty,
                    unit_price=unit_price, cost_price=cost_price,
                    amount=amount, profit=profit, rebate_amount=item_rebate
                )

                # 按账套汇总行金额
                item_as_id = working_warehouse.account_set_id if working_warehouse else account_set_id
                if item_as_id:
                    amount_by_account_set[item_as_id] = amount_by_account_set.get(item_as_id, Decimal("0")) + amount

                # 库存操作
                await process_item_stock(
                    data.order_type, product, working_warehouse, working_location,
                    qty, order, user, consignment_wh, cost_price=cost_price
                )

            # 4. 返利扣减
            await process_rebate_deduction(data, customer, order, order_no, user)

            # 5. 更新订单金额
            order.total_amount = total_amount
            order.total_cost = total_cost
            order.total_profit = total_profit
            if data.order_type == "RETURN" and data.refunded:
                order.is_cleared = True
                order.paid_amount = abs(total_amount)
            elif is_cleared:
                order.paid_amount = abs(total_amount)
            await order.save()

            # 6. 结算处理（挂账/收款/退款，多账套时拆分收款记录）
            credit_used = await process_order_settlement(
                data, customer, order, total_amount, user, order_no,
                amount_by_account_set=amount_by_account_set
            )

            actual_amount_due = total_amount - order.paid_amount

            # 6.5 钩子：寄售结算 → 应收单（pending，无发货流程所以在此创建）
            # 支持多账套：按账套拆分生成应收单
            if data.order_type == "CONSIGN_SETTLE" and amount_by_account_set:
                try:
                    from app.services.ar_service import create_receivable_bill
                    for as_id, group_amount in amount_by_account_set.items():
                        await create_receivable_bill(
                            account_set_id=as_id,
                            customer_id=order.customer_id,
                            order_id=order.id,
                            total_amount=abs(group_amount),
                            status="pending",
                            creator=user,
                        )
                except Exception as e:
                    logger.error(f"寄售结算自动生成应收单失败: {e}")

            # 6.5b 钩子：退货 → 红字应收单（按账套拆分）
            if data.order_type == "RETURN" and amount_by_account_set:
                try:
                    from app.services.ar_service import create_receivable_bill
                    for as_id, group_amount in amount_by_account_set.items():
                        await create_receivable_bill(
                            account_set_id=as_id,
                            customer_id=order.customer_id,
                            order_id=order.id,
                            total_amount=group_amount,  # 已为负数
                            status="completed",
                            creator=user,
                        )
                except Exception as e:
                    logger.error(f"退货自动生成红字应收单失败: {e}")
                    raise HTTPException(status_code=500, detail=f"订单已创建但财务单据生成失败: {e}")

            # 6.6 钩子：销售退货 + 已退款 → 自动生成收款退款单（按账套拆分）
            if data.order_type == "RETURN" and data.refunded and amount_by_account_set:
                try:
                    from app.models.ar_ap import ReceiptBill, ReceiptRefundBill
                    for as_id, group_amount in amount_by_account_set.items():
                        original_receipt = await ReceiptBill.filter(
                            account_set_id=as_id,
                            customer_id=order.customer_id,
                            status="confirmed",
                        ).order_by("-id").first()
                        if original_receipt:
                            refund_no = generate_order_no("SKTK")
                            await ReceiptRefundBill.create(
                                bill_no=refund_no,
                                account_set_id=as_id,
                                customer_id=order.customer_id,
                                original_receipt=original_receipt,
                                refund_date=datetime.now().date(),
                                amount=abs(group_amount),
                                reason=f"销售退货 {order.order_no}",
                                status="draft",
                                creator=user,
                            )
                except Exception as e:
                    logger.error(f"销售退货自动生成收款退款单失败: {e}")

            # 7. 操作日志
            order_type_names = {'CASH':'现款','CREDIT':'账期','CONSIGN_OUT':'寄售调拨','CONSIGN_SETTLE':'寄售结算','RETURN':'退货'}
            await log_operation(user, "ORDER_CREATE", "ORDER", order.id,
                f"创建{order_type_names.get(data.order_type, data.order_type)}订单 {order_no}，金额 ¥{float(total_amount):.2f}")

            return {
                "id": order.id, "order_no": order_no,
                "shipping_status": shipping_status,
                "total_amount": float(total_amount),
                "paid_amount": float(order.paid_amount),
                "rebate_used": float(order.rebate_used),
                "credit_used": credit_used,
                "amount_due": actual_amount_due,
                "message": "订单创建成功"
            }

        except HTTPException:
            raise


@router.get("")
async def list_orders(order_type: Optional[str] = None, customer_id: Optional[int] = None,
                      start_date: Optional[str] = None, end_date: Optional[str] = None,
                      shipping_status: Optional[str] = None, account_set_id: Optional[int] = None,
                      offset: int = 0, limit: int = 100, user: User = Depends(require_permission("sales", "finance", "logistics"))):
    limit = min(limit, 1000)
    query = Order.all()
    if order_type:
        query = query.filter(order_type=order_type)
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))
    if shipping_status:
        query = query.filter(shipping_status=shipping_status)
    if account_set_id:
        query = query.filter(account_set_id=account_set_id)

    total = await query.count()
    orders = await query.order_by("-created_at").offset(offset).limit(limit).select_related("customer", "warehouse", "creator", "related_order", "employee")
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])

    result = []
    for o in orders:
        item = {
            "id": o.id, "order_no": o.order_no, "order_type": o.order_type,
            "customer_name": o.customer.name if o.customer else None,
            "customer_id": o.customer_id,
            "warehouse_name": o.warehouse.name if o.warehouse else None,
            "total_amount": float(o.total_amount),
            "paid_amount": float(o.paid_amount),
            "is_cleared": o.is_cleared, "remark": o.remark,
            "employee_name": o.employee.name if o.employee else None,
            "creator_name": o.creator.display_name if o.creator else None,
            "created_at": o.created_at.isoformat(),
            "related_order_no": o.related_order.order_no if o.related_order else None,
            "related_order_id": o.related_order_id,
            "shipping_status": o.shipping_status,
            "account_set_id": o.account_set_id,
        }
        if has_finance:
            item["total_cost"] = float(o.total_cost)
            item["total_profit"] = float(o.total_profit)
        result.append(item)
    return {"items": result, "total": total}


@router.get("/{order_id}")
async def get_order(order_id: int, user: User = Depends(require_permission("sales", "finance", "logistics"))):
    order = await Order.filter(id=order_id).select_related("customer", "warehouse", "creator", "related_order", "employee").first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    items = await OrderItem.filter(order_id=order_id).select_related("product", "warehouse")
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])

    # 批量加载订单行仓库的账套名称
    _item_as_ids = list(set(
        i.warehouse.account_set_id for i in items
        if i.warehouse and i.warehouse.account_set_id
    ))
    _as_name_map = {}
    if _item_as_ids:
        for _as in await AccountSet.filter(id__in=_item_as_ids):
            _as_name_map[_as.id] = _as.name

    returned_quantities = {}
    if order.order_type in ["CASH", "CREDIT"]:
        return_orders = await Order.filter(related_order_id=order_id, order_type="RETURN")
        if return_orders:
            ret_order_ids = [r.id for r in return_orders]
            ret_items = await OrderItem.filter(order_id__in=ret_order_ids)
            for ret_item in ret_items:
                if ret_item.product_id not in returned_quantities:
                    returned_quantities[ret_item.product_id] = 0
                returned_quantities[ret_item.product_id] += abs(ret_item.quantity)

    credit_used = 0
    other_payment = 0
    if order.order_type == "CASH":
        if order.paid_amount > 0:
            credit_used = float(order.paid_amount)
            if order.paid_amount < order.total_amount:
                other_payment = float(order.total_amount) - float(order.paid_amount)
    elif order.order_type in ["CREDIT", "CONSIGN_SETTLE"]:
        if order.paid_amount > 0:
            credit_used = float(order.paid_amount)
            other_payment = float(order.total_amount) - float(order.paid_amount)

    payment_records = []
    direct_payments = await Payment.filter(order_id=order.id).all()
    for dp in direct_payments:
        payment_records.append({
            "id": dp.id, "payment_no": dp.payment_no,
            "amount": float(dp.amount), "payment_method": dp.payment_method,
            "source": dp.source, "is_confirmed": dp.is_confirmed,
            "created_at": dp.created_at.isoformat()
        })
    po_links = await PaymentOrder.filter(order_id=order.id).select_related("payment").all()
    seen_ids = {dp.id for dp in direct_payments}
    for link in po_links:
        if link.payment_id not in seen_ids:
            seen_ids.add(link.payment_id)
            payment_records.append({
                "id": link.payment.id, "payment_no": link.payment.payment_no,
                "amount": float(link.amount), "payment_method": link.payment.payment_method,
                "source": link.payment.source, "is_confirmed": link.payment.is_confirmed,
                "created_at": link.payment.created_at.isoformat()
            })

    rebate_refund_records = []
    refund_rebate_logs = await RebateLog.filter(
        reference_type="ORDER", reference_id=order.id, type="refund"
    ).all()
    for rl in refund_rebate_logs:
        rebate_refund_records.append({
            "id": rl.id, "amount": float(rl.amount),
            "remark": rl.remark, "created_at": rl.created_at.isoformat()
        })

    child_orders = await Order.filter(related_order_id=order.id).all()
    related_children = [{"id": co.id, "order_no": co.order_no, "order_type": co.order_type} for co in child_orders]

    shipment_list = await Shipment.filter(order_id=order_id).order_by("id").all()
    shipment_ids = [sh.id for sh in shipment_list]
    all_si = await ShipmentItem.filter(shipment_id__in=shipment_ids).select_related("product").all() if shipment_ids else []
    si_by_shipment = {}
    for si in all_si:
        si_by_shipment.setdefault(si.shipment_id, []).append(si)

    shipments_info = []
    for sh in shipment_list:
        ti = []
        if sh.last_tracking_info:
            try:
                ti = json.loads(sh.last_tracking_info)
            except Exception:
                pass
        si_list = si_by_shipment.get(sh.id, [])
        shipments_info.append({
            "id": sh.id, "shipment_no": sh.shipment_no,
            "carrier_name": sh.carrier_name,
            "tracking_no": sh.tracking_no, "sn_code": sh.sn_code,
            "status": sh.status, "status_text": sh.status_text,
            "last_info": ti[0].get("context", "") if ti else None,
            "tracking_info": ti,
            "items": [{
                "product_name": si.product.name,
                "product_sku": si.product.sku,
                "quantity": si.quantity,
                "sn_codes": si.sn_codes
            } for si in si_list]
        })

    # 加载关联的应收单
    receivable_bills = []
    if has_finance:
        try:
            from app.models.ar_ap import ReceivableBill
            _ar_bills = await ReceivableBill.filter(order_id=order.id).select_related("account_set").all()
            for rb in _ar_bills:
                receivable_bills.append({
                    "id": rb.id,
                    "bill_no": rb.bill_no,
                    "account_set_id": rb.account_set_id,
                    "account_set_name": rb.account_set.name if rb.account_set else None,
                    "total_amount": float(rb.total_amount),
                    "received_amount": float(rb.received_amount),
                    "status": rb.status,
                })
        except Exception:
            pass

    return {
        "id": order.id, "order_no": order.order_no, "order_type": order.order_type,
        "customer": {"id": order.customer.id, "name": order.customer.name} if order.customer else None,
        "warehouse": {"id": order.warehouse.id, "name": order.warehouse.name} if order.warehouse else None,
        "account_set_id": order.account_set_id,
        "total_amount": float(order.total_amount),
        "total_cost": float(order.total_cost) if has_finance else None,
        "total_profit": float(order.total_profit) if has_finance else None,
        "paid_amount": float(order.paid_amount),
        "rebate_used": float(order.rebate_used),
        "credit_used": credit_used, "other_payment": other_payment,
        "payment_records": payment_records,
        "is_cleared": order.is_cleared,
        "shipping_status": order.shipping_status,
        "refunded": order.refunded, "remark": order.remark,
        "employee_name": order.employee.name if order.employee else None,
        "creator_name": order.creator.display_name if order.creator else None,
        "created_at": order.created_at.isoformat(),
        "related_order": {"id": order.related_order.id, "order_no": order.related_order.order_no} if order.related_order else None,
        "related_children": related_children,
        "rebate_refund_records": rebate_refund_records,
        "receivable_bills": receivable_bills,
        "shipments": shipments_info,
        "items": [{
            "product_id": i.product_id, "product_sku": i.product.sku,
            "product_name": i.product.name, "quantity": i.quantity,
            "id": i.id,
            "shipped_qty": i.shipped_qty,
            "returned_quantity": returned_quantities.get(i.product_id, 0),
            "available_return_quantity": max(0, abs(i.quantity) - returned_quantities.get(i.product_id, 0)),
            "unit_price": float(i.unit_price),
            "cost_price": float(i.cost_price) if has_finance else None,
            "amount": float(i.amount),
            "profit": float(i.profit) if has_finance else None,
            "rebate_amount": float(i.rebate_amount) if i.rebate_amount else 0,
            "warehouse_id": i.warehouse_id,
            "warehouse_name": i.warehouse.name if i.warehouse else None,
            "account_set_id": i.warehouse.account_set_id if i.warehouse else None,
            "account_set_name": _as_name_map.get(i.warehouse.account_set_id) if (i.warehouse and i.warehouse.account_set_id) else None,
        } for i in items]
    }


@router.get("/{order_id}/cancel-preview")
async def cancel_preview(order_id: int, user: User = Depends(require_permission("sales"))):
    """获取取消订单的预览信息"""
    order = await Order.filter(id=order_id).select_related("customer").first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.shipping_status not in ("pending", "partial"):
        raise HTTPException(status_code=400, detail="该订单不可取消")

    items = await OrderItem.filter(order_id=order_id).select_related("product").all()

    shipped_items = []
    cancel_items = []
    new_order_amount = Decimal("0")
    cancel_amount = Decimal("0")

    for item in items:
        shipped = item.shipped_qty
        total = abs(item.quantity)
        remaining = total - shipped

        if shipped > 0:
            item_amount = Decimal(str(shipped)) * item.unit_price
            new_order_amount += item_amount
            shipped_items.append({
                "order_item_id": item.id,
                "product_name": item.product.name,
                "product_sku": item.product.sku,
                "shipped_qty": shipped,
                "unit_price": float(item.unit_price),
                "amount": float(item_amount),
                "original_rebate_amount": float(item.rebate_amount) if item.rebate_amount else 0
            })
        if remaining > 0:
            item_amount = Decimal(str(remaining)) * item.unit_price
            cancel_amount += item_amount
            cancel_items.append({
                "order_item_id": item.id,
                "product_name": item.product.name,
                "product_sku": item.product.sku,
                "cancel_qty": remaining,
                "unit_price": float(item.unit_price),
                "amount": float(item_amount)
            })

    is_partial = len(shipped_items) > 0
    total = abs(order.total_amount) if order.total_amount else Decimal("0")
    paid = order.paid_amount or Decimal("0")
    rebate = order.rebate_used or Decimal("0")

    if is_partial and total > 0:
        ratio = new_order_amount / total
        default_new_paid = (paid * ratio).quantize(Decimal("0.01"))
        default_new_rebate = (rebate * ratio).quantize(Decimal("0.01"))
        if default_new_paid + default_new_rebate != new_order_amount:
            default_new_rebate = new_order_amount - default_new_paid
        if default_new_rebate > rebate:
            default_new_rebate = rebate
            default_new_paid = new_order_amount - default_new_rebate
        if default_new_paid > paid:
            default_new_paid = paid
            default_new_rebate = new_order_amount - default_new_paid
    else:
        default_new_paid = Decimal("0")
        default_new_rebate = Decimal("0")

    if is_partial and new_order_amount > 0:
        alloc_rebate_sum = Decimal("0")
        alloc_paid_sum = Decimal("0")
        for i, si in enumerate(shipped_items):
            item_amt = Decimal(str(si["amount"]))
            if i < len(shipped_items) - 1:
                ratio = item_amt / new_order_amount
                si_rebate = (default_new_rebate * ratio).quantize(Decimal("0.01"))
                si_paid = item_amt - si_rebate
            else:
                si_rebate = default_new_rebate - alloc_rebate_sum
                si_paid = item_amt - si_rebate
            si["default_paid"] = float(si_paid)
            si["default_rebate"] = float(si_rebate)
            alloc_rebate_sum += si_rebate
            alloc_paid_sum += si_paid

    default_refund = paid - default_new_paid
    default_refund_rebate = rebate - default_new_rebate

    # 检查是否有已确认的收款记录
    confirmed_payments = await Payment.filter(
        order_id=order.id, is_confirmed=True
    ).exclude(source="REFUND").count()
    has_confirmed_payment = confirmed_payments > 0

    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "order_type": order.order_type,
        "customer_name": order.customer.name if order.customer else None,
        "total_amount": float(total),
        "paid_amount": float(paid),
        "rebate_used": float(rebate),
        "shipped_items": shipped_items,
        "cancel_items": cancel_items,
        "new_order_amount": float(new_order_amount),
        "default_new_paid": float(default_new_paid),
        "default_new_rebate": float(default_new_rebate),
        "default_refund": float(default_refund),
        "default_refund_rebate": float(default_refund_rebate),
        "is_partial": is_partial,
        "has_payment": float(paid) > 0 or float(rebate) > 0,
        "has_confirmed_payment": has_confirmed_payment,
    }


@router.post("/{order_id}/cancel")
async def cancel_order(order_id: int, data: CancelRequest, user: User = Depends(require_permission("sales"))):
    """取消订单，支持完整财务闭环和部分发货拆单"""
    async with transactions.in_transaction():
        order = await Order.filter(id=order_id).select_for_update().first()
        if order:
            await order.fetch_related("customer", "warehouse")
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        if order.shipping_status not in ("pending", "partial"):
            raise HTTPException(status_code=400, detail="该订单不可取消")
        if order.order_type not in ("CASH", "CREDIT", "CONSIGN_OUT"):
            raise HTTPException(status_code=400, detail="该订单类型不支持取消")

        customer = order.customer
        items = await OrderItem.filter(order_id=order_id).select_related("product", "warehouse", "location").all()

        # 提前校验退款金额，避免不可逆操作后才发现参数错误
        if customer and order.order_type in ("CASH", "CREDIT"):
            if data.refund_amount is not None and Decimal(str(data.refund_amount)) > order.paid_amount:
                raise HTTPException(status_code=400, detail="退款金额不能超过已收款金额")
            if data.refund_rebate is not None and Decimal(str(data.refund_rebate)) > (order.rebate_used or Decimal("0")):
                raise HTTPException(status_code=400, detail="退回返利金额不能超过订单已使用的返利金额")

        has_shipped = any(item.shipped_qty > 0 for item in items)
        new_order = None

        # 1. 释放未发货库存预留
        await release_cancelled_stock(items, order, user)

        # 2. 部分发货：生成新订单
        if has_shipped:
            new_order_no = f"{order.order_no}-S"
            new_total = Decimal("0")
            new_cost = Decimal("0")
            new_profit = Decimal("0")

            new_order = await Order.create(
                order_no=new_order_no,
                order_type=order.order_type,
                customer=customer,
                warehouse=order.warehouse,
                related_order=order,
                shipping_status="completed",
                remark=f"由取消订单 {order.order_no} 拆分生成（已发货部分）",
                employee_id=order.employee_id,
                account_set_id=order.account_set_id,
                creator=user
            )

            alloc_map = {}
            if data.item_allocations:
                for alloc in data.item_allocations:
                    alloc_map[alloc.order_item_id] = alloc

            for item in items:
                if item.shipped_qty <= 0:
                    continue
                item_amount = Decimal(str(item.shipped_qty)) * item.unit_price
                item_cost = Decimal(str(item.shipped_qty)) * item.cost_price
                item_rebate = Decimal("0")
                if item.id in alloc_map:
                    item_rebate = alloc_map[item.id].rebate_amount
                item_profit = item_amount - item_cost - item_rebate  # subtract rebate from profit
                new_total += item_amount
                new_cost += item_cost
                new_profit += item_profit

                await OrderItem.create(
                    order=new_order,
                    product_id=item.product_id,
                    warehouse_id=item.warehouse_id,
                    location_id=item.location_id,
                    quantity=-item.shipped_qty if item.quantity < 0 else item.shipped_qty,
                    unit_price=item.unit_price,
                    cost_price=item.cost_price,
                    amount=item_amount,
                    profit=item_profit,
                    rebate_amount=item_rebate,
                    shipped_qty=item.shipped_qty
                )

            new_paid = Decimal(str(data.new_order_paid_amount or 0))
            new_rebate = Decimal(str(data.new_order_rebate_used or 0))
            new_order.total_amount = new_total
            new_order.total_cost = new_cost
            new_order.total_profit = new_profit
            new_order.paid_amount = new_paid
            new_order.rebate_used = new_rebate
            new_order.is_cleared = (new_paid + new_rebate) >= new_total
            await new_order.save()

            await Shipment.filter(order_id=order.id).update(order_id=new_order.id)
            await Payment.filter(order_id=order.id).update(order_id=new_order.id)

            await log_operation(user, "ORDER_CREATE", "ORDER", new_order.id,
                f"取消拆分生成订单 {new_order_no}（原订单 {order.order_no}）")

        # 3. 财务回退
        # 未发货且所有收款未确认时，直接删除未确认收款记录，无需退款
        if not has_shipped and customer and order.order_type in ("CASH", "CREDIT"):
            confirmed_count = await Payment.filter(
                order_id=order.id, is_confirmed=True
            ).exclude(source="REFUND").count()
            unconfirmed_count = await Payment.filter(
                order_id=order.id, is_confirmed=False
            ).exclude(source="REFUND").count()
            if confirmed_count == 0 and unconfirmed_count > 0:
                await Payment.filter(
                    order_id=order.id, is_confirmed=False
                ).exclude(source="REFUND").delete()
                order.paid_amount = Decimal("0")

                # 退回返利
                if order.rebate_used and order.rebate_used > 0:
                    account_set_id = order.account_set_id
                    if account_set_id:
                        bal = await CustomerAccountBalance.filter(
                            customer_id=customer.id, account_set_id=account_set_id
                        ).first()
                        if not bal:
                            bal = await CustomerAccountBalance.create(
                                customer_id=customer.id, account_set_id=account_set_id,
                                rebate_balance=0
                            )
                        await CustomerAccountBalance.filter(id=bal.id).update(
                            rebate_balance=F('rebate_balance') + order.rebate_used
                        )
                        await bal.refresh_from_db()
                        balance_after = bal.rebate_balance
                    else:
                        await Customer.filter(id=customer.id).update(
                            rebate_balance=F('rebate_balance') + order.rebate_used
                        )
                        await customer.refresh_from_db()
                        balance_after = customer.rebate_balance
                    await RebateLog.create(
                        target_type="customer", target_id=customer.id,
                        type="refund", amount=order.rebate_used,
                        balance_after=balance_after,
                        account_set_id=account_set_id,
                        reference_type="ORDER", reference_id=order.id,
                        remark=f"取消订单 {order.order_no} 退回返利",
                        creator=user
                    )

                # 账期订单退回挂账
                if order.order_type == "CREDIT":
                    cancel_balance_amount = abs(order.total_amount)
                    if cancel_balance_amount > 0:
                        await Customer.filter(id=customer.id).update(
                            balance=F('balance') - cancel_balance_amount
                        )

                # 跳过后续退款逻辑，直接到标记取消
                order.shipping_status = "cancelled"
                await order.save()
                await log_operation(user, "ORDER_CANCEL", "ORDER", order.id,
                    f"取消订单 {order.order_no}（未发货、收款未确认，直接取消）")
                return {"message": "订单已取消", "shipping_status": "cancelled"}

        if customer and order.order_type in ("CASH", "CREDIT"):
            refund_amount = Decimal(str(data.refund_amount or 0))
            refund_rebate = Decimal(str(data.refund_rebate or 0))

            if refund_rebate > 0:
                account_set_id = order.account_set_id
                if account_set_id:
                    bal = await CustomerAccountBalance.filter(
                        customer_id=customer.id, account_set_id=account_set_id
                    ).first()
                    if not bal:
                        bal = await CustomerAccountBalance.create(
                            customer_id=customer.id, account_set_id=account_set_id,
                            rebate_balance=0
                        )
                    await CustomerAccountBalance.filter(id=bal.id).update(
                        rebate_balance=F('rebate_balance') + refund_rebate
                    )
                    await bal.refresh_from_db()
                    balance_after = bal.rebate_balance
                else:
                    await Customer.filter(id=customer.id).update(
                        rebate_balance=F('rebate_balance') + refund_rebate
                    )
                    await customer.refresh_from_db()
                    balance_after = customer.rebate_balance
                await RebateLog.create(
                    target_type="customer", target_id=customer.id,
                    type="refund", amount=refund_rebate,
                    balance_after=balance_after,
                    account_set_id=account_set_id,
                    reference_type="ORDER", reference_id=order.id,
                    remark=f"取消订单 {order.order_no} 退回返利",
                    creator=user
                )

            if refund_amount > 0:
                if data.refund_method == "balance":
                    await Customer.filter(id=customer.id).update(
                        balance=F('balance') - refund_amount
                    )
                else:
                    pay_no = generate_order_no("REF")
                    await Payment.create(
                        payment_no=pay_no, customer=customer, order=order,
                        amount=-refund_amount,
                        payment_method=data.refund_payment_method or "cash",
                        source="REFUND", is_confirmed=False,
                        remark=f"取消订单 {order.order_no} 退款",
                        creator=user,
                        account_set_id=order.account_set_id
                    )
                    # 推送会计模块：创建收款退款单
                    if order.account_set_id:
                        try:
                            from app.models.ar_ap import ReceiptBill, ReceiptRefundBill
                            original_receipt = await ReceiptBill.filter(
                                account_set_id=order.account_set_id,
                                customer_id=customer.id,
                                status="confirmed",
                            ).order_by("-id").first()
                            if original_receipt:
                                await ReceiptRefundBill.create(
                                    bill_no=generate_order_no("SKTK"),
                                    account_set_id=order.account_set_id,
                                    customer_id=customer.id,
                                    original_receipt=original_receipt,
                                    refund_date=date.today(),
                                    amount=refund_amount,
                                    reason=f"取消订单 {order.order_no} 退款",
                                    status="draft",
                                    creator=user,
                                )
                        except Exception as e:
                            logger.error(f"取消订单自动生成收款退款单失败: {e}")

            if order.order_type == "CREDIT":
                cancel_balance_amount = abs(order.total_amount) - (abs(new_order.total_amount) if new_order else Decimal("0"))
                if cancel_balance_amount > 0:
                    await Customer.filter(id=customer.id).update(
                        balance=F('balance') - cancel_balance_amount
                    )

        # 4. 标记原订单取消
        order.shipping_status = "cancelled"
        await order.save()

        await log_operation(user, "ORDER_CANCEL", "ORDER", order.id,
            f"取消订单 {order.order_no}" + (f"，拆分生成 {new_order.order_no}" if new_order else ""))

    result = {
        "message": "订单已取消",
        "shipping_status": "cancelled"
    }
    if new_order:
        result["new_order_id"] = new_order.id
        result["new_order_no"] = new_order.order_no
        result["message"] = f"订单已取消，已发货部分生成新订单 {new_order.order_no}"

    return result
