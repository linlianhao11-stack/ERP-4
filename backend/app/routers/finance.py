"""财务/回款路由"""
import io
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from tortoise.expressions import F, Q

from app.auth.dependencies import get_current_user, require_permission
from app.utils.csv import csv_safe
from app.models import (
    User, Order, OrderItem, Payment, PaymentOrder, Customer,
    StockLog, Shipment
)
from app.schemas.finance import PaymentCreate
from app.services.operation_log_service import log_operation
from app.utils.generators import generate_order_no
from app.utils.time import now
from app.utils.errors import parse_date

router = APIRouter(prefix="/api/finance", tags=["财务管理"])


@router.get("/all-orders")
async def get_all_orders(
    order_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    account_set_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 200,
    user: User = Depends(require_permission("finance"))
):
    """获取所有订单（财务视角）"""
    limit = min(limit, 1000)
    query = Order.all()
    if order_type:
        query = query.filter(order_type=order_type)
    if account_set_id:
        query = query.filter(account_set_id=account_set_id)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))

    if search:
        keywords = search.lower().split()
        # 数据库层面筛选物流记录（避免加载全表）
        shipment_query = Shipment.all()
        for word in keywords:
            shipment_query = shipment_query.filter(
                Q(tracking_no__icontains=word) | Q(sn_code__icontains=word)
            )
        matching_shipments = await shipment_query.values_list("order_id", flat=True)
        search_order_ids = set(matching_shipments)

        # 将订单号/客户名搜索也推到数据库层
        order_q = Q()
        for word in keywords:
            order_q &= (Q(order_no__icontains=word) | Q(customer__name__icontains=word))
        if search_order_ids:
            query = query.filter(Q(order_q) | Q(id__in=list(search_order_ids)))
        else:
            query = query.filter(order_q)

    total = await query.count()
    orders = await query.order_by("-created_at").offset(offset).limit(limit).select_related(
        "customer", "warehouse", "creator", "related_order", "salesperson")

    filtered_orders = list(orders)

    order_ids = [o.id for o in filtered_orders]
    unconfirmed_order_ids = set()
    if order_ids:
        cash_payments = await Payment.filter(order_id__in=order_ids, is_confirmed=False).all()
        for p in cash_payments:
            unconfirmed_order_ids.add(p.order_id)
        po_links = await PaymentOrder.filter(order_id__in=order_ids).select_related("payment").all()
        for po in po_links:
            if not po.payment.is_confirmed:
                unconfirmed_order_ids.add(po.order_id)

    result = []
    for o in filtered_orders:
        result.append({
            "id": o.id, "order_no": o.order_no, "order_type": o.order_type,
            "customer_name": o.customer.name if o.customer else "-",
            "customer_id": o.customer_id,
            "warehouse_name": o.warehouse.name if o.warehouse else "-",
            "total_amount": float(o.total_amount),
            "total_cost": float(o.total_cost),
            "total_profit": float(o.total_profit),
            "paid_amount": float(o.paid_amount),
            "is_cleared": o.is_cleared,
            "has_unconfirmed_payment": o.id in unconfirmed_order_ids,
            "refunded": o.refunded,
            "remark": o.remark,
            "salesperson_name": o.salesperson.name if o.salesperson else "-",
            "creator_name": o.creator.display_name if o.creator else "-",
            "created_at": o.created_at.isoformat(),
            "related_order_no": o.related_order.order_no if o.related_order else None,
            "related_order_id": o.related_order_id
        })
    return {"items": result, "total": total}


@router.get("/all-orders/export")
async def export_orders(
    order_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: User = Depends(require_permission("finance"))
):
    """导出订单到Excel"""
    query = Order.all()
    if order_type:
        query = query.filter(order_type=order_type)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))

    orders = await query.order_by("-created_at").limit(10000).select_related(
        "customer", "warehouse", "creator", "related_order", "salesperson")

    output = io.StringIO()
    output.write('\ufeff')

    headers = ["订单号", "订单类型", "客户", "仓库", "金额", "成本", "毛利", "已付", "状态", "退款状态", "备注", "销售员", "创建人", "创建时间", "关联订单",
               "商品SKU", "商品名称", "数量", "单价", "成本价", "小计", "利润"]
    output.write(','.join(headers) + '\n')

    type_names = {
        "CASH": "现款", "CREDIT": "账期",
        "CONSIGN_OUT": "寄售调拨", "CONSIGN_SETTLE": "寄售结算",
        "CONSIGN_RETURN": "寄售退货",
        "RETURN": "退货"
    }

    # 批量查询所有订单明细（避免 N+1）
    order_ids = [o.id for o in orders]
    all_items = await OrderItem.filter(order_id__in=order_ids).select_related("product") if order_ids else []
    items_by_order = {}
    for item in all_items:
        items_by_order.setdefault(item.order_id, []).append(item)

    for o in orders:
        order_base = [
            o.order_no,
            type_names.get(o.order_type, o.order_type),
            o.customer.name if o.customer else "-",
            o.warehouse.name if o.warehouse else "-",
            f"{float(o.total_amount):.2f}",
            f"{float(o.total_cost):.2f}",
            f"{float(o.total_profit):.2f}",
            f"{float(o.paid_amount):.2f}",
            "已结清" if o.is_cleared else "未结清",
            ("已退款" if o.refunded else "未退款") if o.order_type == "RETURN" else "-",
            (o.remark or "").replace('\n', ' '),
            o.salesperson.name if o.salesperson else "-",
            o.creator.display_name if o.creator else "-",
            o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            o.related_order.order_no if o.related_order else "-"
        ]
        items = items_by_order.get(o.id, [])
        if items:
            for it in items:
                row = order_base + [
                    it.product.sku if it.product else "-",
                    it.product.name if it.product else "-",
                    str(it.quantity),
                    f"{float(it.unit_price):.2f}",
                    f"{float(it.cost_price):.2f}",
                    f"{float(it.amount):.2f}",
                    f"{float(it.profit):.2f}"
                ]
                output.write(','.join(csv_safe(item) for item in row) + '\n')
        else:
            row = order_base + ["-"] * 7
            output.write(','.join(csv_safe(item) for item in row) + '\n')

    output.seek(0)
    filename = f"订单明细_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue().encode('utf-8')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    )


@router.get("/stock-logs")
async def get_finance_stock_logs(
    change_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
    user: User = Depends(require_permission("finance"))
):
    """获取所有出入库日志（财务视角）"""
    limit = min(limit, 1000)
    type_names = {
        "RESTOCK": "入库",
        "SALE": "销售出库",
        "RETURN": "退货入库",
        "CONSIGN_OUT": "寄售调拨",
        "CONSIGN_SETTLE": "寄售结算",
        "CONSIGN_RETURN": "寄售退货",
        "ADJUST": "库存调整",
        "PURCHASE_IN": "采购入库",
        "PURCHASE_RETURN": "采购退货",
        "TRANSFER_OUT": "调拨出库",
        "TRANSFER_IN": "调拨入库",
        "RESERVE": "库存预留",
        "RESERVE_CANCEL": "取消预留",
    }

    query = StockLog.all()
    if change_type:
        query = query.filter(change_type=change_type)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))

    logs = await query.order_by("-created_at").limit(limit).select_related("product", "warehouse", "creator")

    return [{
        "id": l.id,
        "product_sku": l.product.sku,
        "product_name": l.product.name,
        "warehouse_name": l.warehouse.name,
        "change_type": l.change_type,
        "change_type_name": type_names.get(l.change_type, l.change_type),
        "quantity": l.quantity,
        "before_qty": l.before_qty,
        "after_qty": l.after_qty,
        "reference_type": l.reference_type,
        "reference_id": l.reference_id,
        "remark": l.remark,
        "creator_name": l.creator.display_name if l.creator else "-",
        "created_at": l.created_at.isoformat()
    } for l in logs]


@router.get("/unpaid-orders")
async def get_unpaid_orders(
    customer_id: Optional[int] = None,
    user: User = Depends(require_permission("finance"))
):
    """获取未结清的账期/寄售结算订单"""
    query = Order.filter(is_cleared=False, order_type__in=["CREDIT", "CONSIGN_SETTLE"])
    if customer_id:
        query = query.filter(customer_id=customer_id)
    orders = await query.order_by("created_at").select_related("customer", "salesperson")
    return [{
        "id": o.id, "order_no": o.order_no, "order_type": o.order_type,
        "customer_id": o.customer_id, "customer_name": o.customer.name if o.customer else None,
        "salesperson_name": o.salesperson.name if o.salesperson else None,
        "total_amount": float(o.total_amount), "paid_amount": float(o.paid_amount),
        "unpaid_amount": float(o.total_amount - o.paid_amount),
        "created_at": o.created_at.isoformat()
    } for o in orders]


@router.post("/payment")
async def create_payment(data: PaymentCreate, user: User = Depends(require_permission("finance"))):
    """回款核销"""
    from tortoise import transactions
    async with transactions.in_transaction():
        customer = await Customer.filter(id=data.customer_id).select_for_update().first()
        if not customer:
            raise HTTPException(status_code=404, detail="客户不存在")

        orders = await Order.filter(id__in=data.order_ids, customer_id=data.customer_id, is_cleared=False).select_for_update().all()
        if len(orders) != len(data.order_ids):
            raise HTTPException(status_code=400, detail="部分订单不存在或已结清")

        total_unpaid = sum(((o.total_amount - o.paid_amount) for o in orders), Decimal("0"))
        if data.amount > total_unpaid:
            raise HTTPException(status_code=400, detail=f"付款金额超过欠款总额 {total_unpaid}")

        payment_no = generate_order_no("PAY")
        payment = await Payment.create(
            payment_no=payment_no,
            customer=customer,
            amount=Decimal(str(data.amount)),
            payment_method=data.payment_method,
            source="CREDIT",
            is_confirmed=False,
            remark=data.remark,
            creator=user,
            account_set_id=orders[0].account_set_id if orders else None
        )

        remaining = Decimal(str(data.amount))
        for order in sorted(orders, key=lambda x: x.created_at):
            unpaid = order.total_amount - order.paid_amount
            if remaining <= 0:
                break
            pay_this = min(remaining, unpaid)
            await Order.filter(id=order.id).update(paid_amount=F('paid_amount') + pay_this)
            # Reload with lock to check if cleared (prevents race with concurrent payments)
            order = await Order.filter(id=order.id).select_for_update().first()
            if order.paid_amount >= order.total_amount:
                await Order.filter(id=order.id).update(is_cleared=True)

            await PaymentOrder.create(payment=payment, order=order, amount=pay_this)
            remaining -= pay_this

        await Customer.filter(id=customer.id).update(balance=F('balance') - Decimal(str(data.amount)).quantize(Decimal('0.01')))

        await log_operation(user, "PAYMENT_CREATE", "PAYMENT", payment.id,
            f"账期收款 {payment_no}，客户 {customer.name}，金额 ¥{float(data.amount):.2f}")

        return {"id": payment.id, "payment_no": payment_no, "message": "收款成功"}


@router.get("/payments")
async def list_payments(
    customer_id: Optional[int] = None,
    source: Optional[str] = None,
    limit: int = 100,
    user: User = Depends(require_permission("finance"))
):
    limit = min(limit, 1000)
    query = Payment.all()
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if source:
        query = query.filter(source=source)
    payments = await query.order_by("-created_at").limit(limit).select_related(
        "customer", "creator", "confirmed_by", "order")

    # 批量查询关联订单（避免 N+1）
    payment_ids_need_links = [p.id for p in payments if not (p.order_id and p.order)]
    all_po_links = await PaymentOrder.filter(payment_id__in=payment_ids_need_links).select_related("order") if payment_ids_need_links else []
    po_links_by_payment = {}
    for link in all_po_links:
        po_links_by_payment.setdefault(link.payment_id, []).append(link)

    result = []
    for p in payments:
        order_nos = []
        if p.order_id and p.order:
            order_nos.append({"id": p.order.id, "order_no": p.order.order_no})
        else:
            for link in po_links_by_payment.get(p.id, []):
                if link.order:
                    order_nos.append({"id": link.order.id, "order_no": link.order.order_no})
        result.append({
            "id": p.id, "payment_no": p.payment_no,
            "customer_name": p.customer.name, "customer_id": p.customer_id,
            "amount": float(p.amount), "payment_method": p.payment_method,
            "source": p.source,
            "is_confirmed": p.is_confirmed,
            "confirmed_by_name": p.confirmed_by.display_name if p.confirmed_by else None,
            "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
            "remark": p.remark,
            "creator_name": p.creator.display_name if p.creator else None,
            "created_at": p.created_at.isoformat(),
            "order_nos": order_nos
        })
    return result


@router.post("/payment/{payment_id}/confirm")
async def confirm_payment(payment_id: int, user: User = Depends(require_permission("finance_confirm", "finance"))):
    """确认收款到账"""
    from tortoise import transactions
    async with transactions.in_transaction():
        payment = await Payment.filter(id=payment_id).select_related("customer").first()
        if not payment:
            raise HTTPException(status_code=404, detail="收款记录不存在")
        if payment.is_confirmed:
            raise HTTPException(status_code=400, detail="该收款已确认")
        payment.is_confirmed = True
        payment.confirmed_by = user
        payment.confirmed_at = now()
        await payment.save()

        await log_operation(user, "PAYMENT_CONFIRM", "PAYMENT", payment.id,
            f"确认收款 {payment.payment_no}，客户 {payment.customer.name}，金额 ¥{float(payment.amount):.2f}")

    return {"message": "确认成功"}


@router.get("/customer-statement/{customer_id}")
async def get_customer_statement(customer_id: int, user: User = Depends(require_permission("finance"))):
    """客户对账单"""
    customer = await Customer.filter(id=customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    orders = await Order.filter(customer_id=customer_id).order_by("created_at")
    payments = await Payment.filter(customer_id=customer_id).order_by("created_at")

    records = []
    for o in orders:
        records.append({
            "type": "order", "date": o.created_at.isoformat(),
            "order_no": o.order_no, "order_type": o.order_type,
            "amount": float(o.total_amount), "description": f"{o.order_type}订单"
        })
    for p in payments:
        records.append({
            "type": "payment", "date": p.created_at.isoformat(),
            "payment_no": p.payment_no,
            "amount": -float(p.amount), "description": f"回款-{p.payment_method}"
        })

    records.sort(key=lambda x: x["date"])

    return {
        "customer": {"id": customer.id, "name": customer.name, "balance": float(customer.balance)},
        "records": records
    }
