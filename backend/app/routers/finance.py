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
    StockLog, Shipment, ShipmentItem
)
from app.constants import (
    OrderType, ShippingStatus, PaymentSource,
    ORDER_TYPE_NAMES, STOCK_CHANGE_TYPE_NAMES,
)
from app.schemas.finance import PaymentCreate
from app.services.operation_log_service import log_operation
from app.utils.generators import generate_order_no
from app.utils.pagination import apply_cursor_pagination, build_next_cursor
from app.utils.time import now
from app.utils.errors import parse_date
from app.utils.batch_load import batch_load_related
from app.utils.response import paginated_response

router = APIRouter(prefix="/api/finance", tags=["财务管理"])


@router.get("/all-orders")
async def get_all_orders(
    order_type: Optional[str] = None,
    payment_status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    account_set_id: Optional[int] = None,
    unpaid_only: bool = False,
    cursor: Optional[str] = None,
    offset: int = 0,
    limit: int = 200,
    user: User = Depends(require_permission("finance"))
):
    """获取所有订单（财务视角）"""
    limit = min(limit, 1000)
    query = Order.all()
    if unpaid_only:
        # 未结清 或 有待确认收款的订单都算欠款（用 SQL 子查询代替 Python 内存 set）
        from tortoise import connections
        conn = connections.get("default")
        uc_rows = await conn.execute_query_dict(
            "SELECT DISTINCT order_id FROM payments WHERE is_confirmed = false AND order_id IS NOT NULL "
            "UNION "
            "SELECT DISTINCT po.order_id FROM payment_orders po JOIN payments p ON p.id = po.payment_id WHERE p.is_confirmed = false"
        )
        uc_ids = [r["order_id"] for r in uc_rows]
        if uc_ids:
            query = query.filter(Q(is_cleared=False) | Q(id__in=uc_ids))
        else:
            query = query.filter(is_cleared=False)
    if order_type:
        query = query.filter(order_type=order_type)
    if payment_status:
        if payment_status == "cancelled":
            query = query.filter(shipping_status=ShippingStatus.CANCELLED.value)
        elif payment_status == "cleared":
            query = query.filter(is_cleared=True).exclude(shipping_status=ShippingStatus.CANCELLED.value)
        elif payment_status == "uncleared":
            query = query.filter(is_cleared=False).exclude(shipping_status=ShippingStatus.CANCELLED.value)
        elif payment_status == "unconfirmed":
            from tortoise import connections
            conn = connections.get("default")
            uc_rows = await conn.execute_query_dict(
                "SELECT DISTINCT order_id FROM payments WHERE is_confirmed = false AND order_id IS NOT NULL "
                "UNION "
                "SELECT DISTINCT po.order_id FROM payment_orders po JOIN payments p ON p.id = po.payment_id WHERE p.is_confirmed = false"
            )
            uc_ids = [r["order_id"] for r in uc_rows]
            if uc_ids:
                query = query.filter(id__in=uc_ids)
            else:
                query = query.filter(id=-1)
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
    base_query = query.select_related("customer", "warehouse", "creator", "related_order", "employee")
    orders = await apply_cursor_pagination(base_query, cursor, "created_at", limit, offset)

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

    # 批量查询品项数（使用数据库聚合代替逐行拉取）
    from app.models import AccountSet
    from tortoise import connections
    item_counts = {}
    if order_ids:
        conn = connections.get("default")
        placeholders = ",".join(f"${i+1}" for i in range(len(order_ids)))
        rows = await conn.execute_query_dict(
            f"SELECT order_id, COUNT(*) as cnt FROM order_items WHERE order_id IN ({placeholders}) GROUP BY order_id",
            order_ids
        )
        for r in rows:
            item_counts[r["order_id"]] = r["cnt"]

    # 批量查询账套名称（account_set_id 直接可用，无需 select_related）
    as_ids = list(set(o.account_set_id for o in filtered_orders if o.account_set_id))
    as_map = {}
    if as_ids:
        for a in await AccountSet.filter(id__in=as_ids):
            as_map[a.id] = a.name

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
            "shipping_status": o.shipping_status,
            "refunded": o.refunded,
            "remark": o.remark,
            "employee_name": o.employee.name if o.employee else "-",
            "creator_name": o.creator.display_name if o.creator else "-",
            "created_at": o.created_at.isoformat(),
            "related_order_no": o.related_order.order_no if o.related_order else None,
            "related_order_id": o.related_order_id,
            # 新增字段
            "item_count": item_counts.get(o.id, 0),
            "rebate_used": float(o.rebate_used) if o.rebate_used else 0,
            "account_set_name": as_map.get(o.account_set_id) if o.account_set_id else None,
        })
    return {"items": result, "total": total, "next_cursor": build_next_cursor(filtered_orders, "created_at")}


@router.get("/all-orders/{order_id}/items")
async def get_order_items(order_id: int, user: User = Depends(require_permission("finance"))):
    """获取订单商品明细（用于列表行展开）"""
    order = await Order.filter(id=order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    items = await OrderItem.filter(order_id=order_id).select_related("product")
    return paginated_response([{
        "id": i.id,
        "product_sku": i.product.sku if i.product else "",
        "product_name": i.product.name if i.product else "",
        "quantity": i.quantity,
        "unit_price": float(i.unit_price),
        "cost_price": float(i.cost_price),
        "amount": float(i.amount),
        "profit": float(i.profit),
        "shipped_qty": i.shipped_qty,
    } for i in items])


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
        "customer", "warehouse", "creator", "related_order", "employee")

    output = io.StringIO()
    output.write('\ufeff')

    headers = ["订单号", "订单类型", "客户", "仓库", "金额", "成本", "毛利", "已付", "状态", "退款状态", "备注", "业务员", "创建人", "创建时间", "关联订单",
               "商品SKU", "商品名称", "数量", "单价", "成本价", "小计", "利润", "SN码"]
    output.write(','.join(headers) + '\n')

    type_names = ORDER_TYPE_NAMES

    # 批量查询所有订单明细（避免 N+1）
    order_ids = [o.id for o in orders]
    items_by_order = await batch_load_related(OrderItem, 'order_id', order_ids, ['product'])

    # 批量查询 SN 码：通过 Shipment → ShipmentItem 关联，按 (order_id, product_id) 聚合
    # 同时回退到 Shipment.sn_code（通过"更新SN"功能写入的聚合字段）
    import json as _json

    def _parse_sn(raw):
        """解析 SN 码字符串，兼容 JSON 数组和逗号/空格分隔"""
        if not raw:
            return []
        try:
            parsed = _json.loads(raw)
            if isinstance(parsed, list):
                return [str(c) for c in parsed]
        except Exception:
            pass
        return [c.strip() for c in str(raw).split(',') if c.strip()]

    sn_by_order_product = {}
    if order_ids:
        shipments = await Shipment.filter(order_id__in=order_ids).all()
        shipment_order_map = {s.id: s.order_id for s in shipments}
        shipment_ids = list(shipment_order_map.keys())

        # 记录每个 shipment 是否已有 item 级 SN
        shipments_with_item_sn = set()

        if shipment_ids:
            all_si = await ShipmentItem.filter(shipment_id__in=shipment_ids).all()
            si_by_shipment = {}
            for si in all_si:
                si_by_shipment.setdefault(si.shipment_id, []).append(si)

            for si in all_si:
                codes = _parse_sn(si.sn_codes)
                if codes:
                    shipments_with_item_sn.add(si.shipment_id)
                    oid = shipment_order_map[si.shipment_id]
                    key = (oid, si.product_id)
                    sn_by_order_product.setdefault(key, []).extend(codes)

            # 回退：Shipment.sn_code 有值但 ShipmentItem 无 SN 的，按商品关联
            for s in shipments:
                if s.id in shipments_with_item_sn or not s.sn_code:
                    continue
                codes = _parse_sn(s.sn_code)
                if not codes:
                    continue
                oid = s.order_id
                si_list = si_by_shipment.get(s.id, [])
                if si_list:
                    # 有 ShipmentItem 时关联到第一个商品
                    key = (oid, si_list[0].product_id)
                    sn_by_order_product.setdefault(key, []).extend(codes)
                else:
                    # 无 ShipmentItem：尝试关联到订单的第一个商品
                    order_items = items_by_order.get(oid, [])
                    if order_items:
                        key = (oid, order_items[0].product_id)
                        sn_by_order_product.setdefault(key, []).extend(codes)

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
            "已取消" if o.shipping_status == ShippingStatus.CANCELLED else ("已结清" if o.is_cleared else "未结清"),
            ("已退款" if o.refunded else "未退款") if o.order_type == OrderType.RETURN else "-",
            (o.remark or "").replace('\n', ' '),
            o.employee.name if o.employee else "-",
            o.creator.display_name if o.creator else "-",
            o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            o.related_order.order_no if o.related_order else "-"
        ]
        items = items_by_order.get(o.id, [])
        if items:
            for it in items:
                sn_codes = sn_by_order_product.get((o.id, it.product_id), [])
                row = order_base + [
                    it.product.sku if it.product else "-",
                    it.product.name if it.product else "-",
                    str(it.quantity),
                    f"{float(it.unit_price):.2f}",
                    f"{float(it.cost_price):.2f}",
                    f"{float(it.amount):.2f}",
                    f"{float(it.profit):.2f}",
                    " / ".join(sn_codes) if sn_codes else "-"
                ]
                output.write(','.join(csv_safe(item) for item in row) + '\n')
        else:
            row = order_base + ["-"] * 8
            output.write(','.join(csv_safe(item) for item in row) + '\n')

    output.seek(0)
    filename = f"订单明细_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    await log_operation(user, "ORDER_EXPORT", "ORDER", None, "导出订单列表 CSV")
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
    search: Optional[str] = None,
    cursor: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
    user: User = Depends(require_permission("finance"))
):
    """获取所有出入库日志（财务视角）"""
    limit = min(limit, 200)
    type_names = STOCK_CHANGE_TYPE_NAMES

    query = StockLog.all()
    if change_type:
        query = query.filter(change_type=change_type)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))

    if search:
        query = query.filter(
            Q(product__name__icontains=search) | Q(product__sku__icontains=search) | Q(warehouse__name__icontains=search)
        )

    total = await query.count()
    base_query = query.select_related("product", "warehouse", "creator")
    logs = await apply_cursor_pagination(base_query, cursor, "created_at", limit, offset)

    return {"items": [{
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
    } for l in logs], "total": total, "next_cursor": build_next_cursor(logs, "created_at")}


@router.get("/unpaid-orders")
async def get_unpaid_orders(
    customer_id: Optional[int] = None,
    order_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_permission("finance"))
):
    """获取未结清的账期/寄售结算订单（仅显示实际欠款 > 0 的订单）"""
    query = Order.filter(
        is_cleared=False,
        order_type__in=OrderType.credit_types(),
        total_amount__gt=F('paid_amount')
    )
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if order_type:
        query = query.filter(order_type=order_type)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))
    if search:
        query = query.filter(Q(order_no__icontains=search) | Q(customer__name__icontains=search))
    orders = await query.order_by("created_at").select_related("customer", "employee")
    return paginated_response([{
        "id": o.id, "order_no": o.order_no, "order_type": o.order_type,
        "customer_id": o.customer_id, "customer_name": o.customer.name if o.customer else None,
        "employee_name": o.employee.name if o.employee else None,
        "total_amount": float(o.total_amount), "paid_amount": float(o.paid_amount),
        "unpaid_amount": float(o.total_amount - o.paid_amount),
        "created_at": o.created_at.isoformat()
    } for o in orders])


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
            source=PaymentSource.CREDIT.value,
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
            # Lock the row FIRST to prevent concurrent payment race condition
            order = await Order.filter(id=order.id).select_for_update().first()
            await Order.filter(id=order.id).update(paid_amount=F('paid_amount') + pay_this)
            await order.refresh_from_db()
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
    is_confirmed: Optional[bool] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    user: User = Depends(require_permission("finance"))
):
    limit = min(limit, 1000)
    query = Payment.all()
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if source:
        query = query.filter(source=source)
    if is_confirmed is not None:
        query = query.filter(is_confirmed=is_confirmed)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))
    if search:
        matching_order_ids = set()
        order_matches = await Order.filter(order_no__icontains=search).values_list("id", flat=True)
        matching_order_ids.update(order_matches)
        po_links = await PaymentOrder.filter(order_id__in=list(matching_order_ids)).values_list("payment_id", flat=True) if matching_order_ids else []
        direct_payment_ids = await Payment.filter(order_id__in=list(matching_order_ids)).values_list("id", flat=True) if matching_order_ids else []
        search_payment_ids = set(po_links) | set(direct_payment_ids)
        if search_payment_ids:
            query = query.filter(Q(customer__name__icontains=search) | Q(id__in=list(search_payment_ids)))
        else:
            query = query.filter(customer__name__icontains=search)
    payments = await query.order_by("-created_at").limit(limit).select_related(
        "customer", "creator", "confirmed_by", "order")

    # 批量查询关联订单（避免 N+1）
    payment_ids_need_links = [p.id for p in payments if not (p.order_id and p.order)]
    po_links_by_payment = await batch_load_related(PaymentOrder, 'payment_id', payment_ids_need_links, ['order'])

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
    return paginated_response(result)


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
