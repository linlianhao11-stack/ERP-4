"""代采代发路由"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from tortoise.queryset import Q

from app.auth.dependencies import require_permission
from app.logger import get_logger
from app.models import User, Supplier, Product, Customer
from app.models.ar_ap import PayableBill, ReceivableBill
from app.models.dropship import DropshipOrder
from app.schemas.dropship import (
    DropshipOrderCreate, DropshipOrderUpdate,
    DropshipShipRequest, DropshipPaymentRequest, DropshipCancelRequest,
)
from app.services.dropship_service import (
    create_dropship_order, submit_dropship_order, calculate_gross_profit,
    batch_pay_dropship, ship_dropship_order, cancel_dropship_order,
)
from app.utils.time import now
from app.utils.errors import parse_date
from app.services.operation_log_service import log_operation

logger = get_logger("dropship")


def _parse_tracking_status(last_tracking_info, order_status):
    """从 last_tracking_info JSON 解析最新物流状态文本"""
    if not last_tracking_info:
        if order_status == "shipped":
            return "待查询"
        return None
    try:
        data = json.loads(last_tracking_info)
        if isinstance(data, dict):
            if str(data.get("ischeck")) == "1":
                return "已签收"
            state = str(data.get("state", ""))
            from app.config import KD100_STATE_MAP
            if state in KD100_STATE_MAP:
                return KD100_STATE_MAP[state][1]
        return "运输中"
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


router = APIRouter(prefix="/api/dropship", tags=["代采代发"])


# ── 报表端点（放在 /{id} 之前，防止路径冲突） ──


@router.get("/reports/summary")
async def report_summary(
    account_set_id: Optional[int] = None,
    month: Optional[str] = None,
    user: User = Depends(require_permission("dropship")),
):
    """报表：月度汇总 — 按客户/供应商维度聚合订单数、采购额、销售额、毛利"""
    # 默认当月
    if month:
        try:
            year, mon = month.split("-")
            month_start = date(int(year), int(mon), 1)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="month 格式错误，请使用 YYYY-MM 格式")
    else:
        today = date.today()
        month_start = date(today.year, today.month, 1)
        month = month_start.strftime("%Y-%m")

    # 下个月第一天，用于 < 比较
    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1)

    # 查询指定月份的所有非取消订单
    q = Q(status__not="cancelled", created_at__gte=month_start, created_at__lt=month_end)
    if account_set_id:
        q &= Q(account_set_id=account_set_id)
    orders = await (
        DropshipOrder.filter(q)
        .select_related("supplier", "customer")
    )

    # 按客户维度汇总
    customer_map: dict = defaultdict(lambda: {
        "count": 0, "purchase_total": Decimal("0"),
        "sale_total": Decimal("0"), "profit": Decimal("0"),
    })
    # 按供应商维度汇总
    supplier_map: dict = defaultdict(lambda: {
        "count": 0, "purchase_total": Decimal("0"),
        "sale_total": Decimal("0"), "profit": Decimal("0"),
    })

    total_count = 0
    total_purchase = Decimal("0")
    total_sale = Decimal("0")
    total_profit = Decimal("0")

    for o in orders:
        total_count += 1
        total_purchase += o.purchase_total
        total_sale += o.sale_total
        total_profit += o.gross_profit

        # 客户维度
        cg = customer_map[o.customer_id]
        cg["customer_id"] = o.customer_id
        cg["customer_name"] = o.customer.name if o.customer else ""
        cg["count"] += 1
        cg["purchase_total"] += o.purchase_total
        cg["sale_total"] += o.sale_total
        cg["profit"] += o.gross_profit

        # 供应商维度
        sg = supplier_map[o.supplier_id]
        sg["supplier_id"] = o.supplier_id
        sg["supplier_name"] = o.supplier.name if o.supplier else ""
        sg["count"] += 1
        sg["purchase_total"] += o.purchase_total
        sg["sale_total"] += o.sale_total
        sg["profit"] += o.gross_profit

    by_customer = [
        {
            "customer_id": v["customer_id"],
            "customer_name": v["customer_name"],
            "count": v["count"],
            "purchase_total": float(v["purchase_total"]),
            "sale_total": float(v["sale_total"]),
            "profit": float(v["profit"]),
        }
        for v in customer_map.values()
    ]
    by_supplier = [
        {
            "supplier_id": v["supplier_id"],
            "supplier_name": v["supplier_name"],
            "count": v["count"],
            "purchase_total": float(v["purchase_total"]),
            "sale_total": float(v["sale_total"]),
            "profit": float(v["profit"]),
        }
        for v in supplier_map.values()
    ]

    # 按订单数降序
    by_customer.sort(key=lambda x: x["count"], reverse=True)
    by_supplier.sort(key=lambda x: x["count"], reverse=True)

    return {
        "month": month,
        "total_count": total_count,
        "total_purchase": float(total_purchase),
        "total_sale": float(total_sale),
        "total_profit": float(total_profit),
        "by_customer": by_customer,
        "by_supplier": by_supplier,
    }


@router.get("/reports/profit")
async def report_profit(
    account_set_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: User = Depends(require_permission("dropship")),
):
    """报表：毛利分析 — 已发货/已完成订单的逐单毛利明细与汇总"""
    query = DropshipOrder.filter(
        status__in=["shipped", "completed"],
    )
    if account_set_id:
        query = query.filter(account_set_id=account_set_id)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lt=parse_date(end_date, "end_date") + timedelta(days=1))

    orders = await query.select_related("supplier", "customer").order_by("-created_at")

    items = []
    sum_purchase = Decimal("0")
    sum_sale = Decimal("0")
    sum_profit = Decimal("0")

    for o in orders:
        items.append({
            "ds_no": o.ds_no,
            "product_name": o.product_name,
            "supplier_name": o.supplier.name if o.supplier else "",
            "customer_name": o.customer.name if o.customer else "",
            "purchase_total": float(o.purchase_total),
            "sale_total": float(o.sale_total),
            "gross_profit": float(o.gross_profit),
            "gross_margin": float(o.gross_margin),
            "created_at": o.created_at.isoformat(),
        })
        sum_purchase += o.purchase_total
        sum_sale += o.sale_total
        sum_profit += o.gross_profit

    count = len(items)
    avg_margin = float(sum_profit / sum_sale * 100) if sum_sale else 0.0

    return {
        "items": items,
        "summary": {
            "count": count,
            "total_purchase": float(sum_purchase),
            "total_sale": float(sum_sale),
            "total_profit": float(sum_profit),
            "avg_margin": round(avg_margin, 2),
        },
    }


@router.get("/reports/receivable")
async def report_receivable(
    account_set_id: Optional[int] = None,
    user: User = Depends(require_permission("dropship")),
):
    """报表：应收未收 — 已发货但客户未回款的订单"""
    # 查询关联了代采代发订单且未完成的应收单
    q = Q(dropship_order_id__isnull=False, status__in=["pending", "partial"])
    if account_set_id:
        q &= Q(dropship_order__account_set_id=account_set_id)
    receivables = await (
        ReceivableBill.filter(q)
        .select_related("dropship_order", "customer")
    )

    today = date.today()
    items = []
    total_unreceived = Decimal("0")

    for rb in receivables:
        order = rb.dropship_order
        if not order:
            continue

        # 发货天数：优先使用 shipped_at，兼容历史数据回退 updated_at
        if order.shipped_at:
            shipped_days = (today - order.shipped_at.date()).days
        elif order.updated_at:
            shipped_days = (today - order.updated_at.date()).days
        else:
            shipped_days = (today - order.created_at.date()).days

        items.append({
            "ds_no": order.ds_no,
            "customer_name": rb.customer.name if rb.customer else "",
            "platform_order_no": order.platform_order_no,
            "sale_total": float(order.sale_total),
            "receivable_bill_no": rb.bill_no,
            "received_amount": float(rb.received_amount),
            "unreceived_amount": float(rb.unreceived_amount),
            "created_at": order.created_at.isoformat(),
            "shipped_days": shipped_days,
        })
        total_unreceived += rb.unreceived_amount

    # 按发货天数降序（欠款最久的排前面）
    items.sort(key=lambda x: x["shipped_days"], reverse=True)

    return {
        "items": items,
        "total_unreceived": float(total_unreceived),
        "total_count": len(items),
    }


@router.get("/payment-workbench")
async def payment_workbench(
    account_set_id: Optional[int] = None,
    user: User = Depends(require_permission("dropship")),
):
    """付款工作台：按供应商分组显示待付款订单"""
    orders = await (
        DropshipOrder.filter(status="pending_payment", **({'account_set_id': account_set_id} if account_set_id else {}))
        .select_related("supplier", "customer")
        .order_by("-created_at")
    )

    # 按供应商分组
    supplier_map: dict = defaultdict(lambda: {"orders": [], "subtotal": Decimal("0")})

    for o in orders:
        group = supplier_map[o.supplier_id]
        group["supplier_id"] = o.supplier_id
        group["supplier_name"] = o.supplier.name if o.supplier else ""
        group["subtotal"] += o.purchase_total
        group["orders"].append({
            "id": o.id,
            "ds_no": o.ds_no,
            "account_set_id": o.account_set_id,
            "product_name": f"{o.product_name} \u00d7{o.quantity}",
            "purchase_total": float(o.purchase_total),
            "sale_total": float(o.sale_total),
            "gross_profit": float(o.gross_profit),
            "customer_name": o.customer.name if o.customer else "",
            "settlement_type": o.settlement_type,
            "urged_at": o.urged_at.isoformat() if o.urged_at else None,
        })

    groups = []
    for sid, data in supplier_map.items():
        groups.append({
            "supplier_id": data["supplier_id"],
            "supplier_name": data["supplier_name"],
            "order_count": len(data["orders"]),
            "subtotal": float(data["subtotal"]),
            "orders": data["orders"],
        })

    # 按订单数降序排列
    groups.sort(key=lambda g: g["order_count"], reverse=True)

    total_amount = sum(g["subtotal"] for g in groups)
    prepaid_count = sum(
        1 for o in orders if o.settlement_type == "prepaid"
    )

    return {
        "groups": groups,
        "total_count": len(orders),
        "total_amount": total_amount,
        "prepaid_count": prepaid_count,
    }


# ── 列表 ──


@router.get("")
async def list_dropship_orders(
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    account_set_id: Optional[int] = None,
    offset: int = 0,
    limit: int = 200,
    user: User = Depends(require_permission("dropship")),
):
    """代采代发订单列表"""
    query = DropshipOrder.all()
    if status:
        query = query.filter(status=status)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lt=parse_date(end_date, "end_date") + timedelta(days=1))
    if search:
        query = query.filter(
            Q(ds_no__icontains=search)
            | Q(product_name__icontains=search)
            | Q(platform_order_no__icontains=search)
            | Q(supplier__name__icontains=search)
            | Q(customer__name__icontains=search)
        )
    if account_set_id:
        query = query.filter(account_set_id=account_set_id)

    limit = min(limit, 1000)
    total = await query.count()
    orders = await (
        query.order_by("-created_at")
        .offset(offset)
        .limit(limit)
        .select_related("supplier", "customer", "creator", "account_set")
    )

    return {
        "items": [
            {
                "id": o.id,
                "ds_no": o.ds_no,
                "status": o.status,
                "account_set_id": o.account_set_id,
                "account_set_name": o.account_set.name if o.account_set else None,
                "supplier_id": o.supplier_id,
                "supplier_name": o.supplier.name if o.supplier else "",
                "product_name": o.product_name,
                "purchase_price": float(o.purchase_price),
                "quantity": o.quantity,
                "purchase_total": float(o.purchase_total),
                "invoice_type": o.invoice_type,
                "customer_id": o.customer_id,
                "customer_name": o.customer.name if o.customer else "",
                "platform_order_no": o.platform_order_no,
                "sale_price": float(o.sale_price),
                "sale_total": float(o.sale_total),
                "gross_profit": float(o.gross_profit),
                "gross_margin": float(o.gross_margin),
                "shipping_mode": o.shipping_mode,
                "tracking_no": o.tracking_no,
                "carrier_name": o.carrier_name,
                "tracking_status": _parse_tracking_status(o.last_tracking_info, o.status),
                "settlement_type": o.settlement_type,
                "creator_name": o.creator.display_name if o.creator else None,
                "created_at": o.created_at.isoformat(),
                "urged_at": o.urged_at.isoformat() if o.urged_at else None,
            }
            for o in orders
        ],
        "total": total,
    }


# ── 详情 ──


@router.get("/{order_id}")
async def get_dropship_order(
    order_id: int,
    user: User = Depends(require_permission("dropship")),
):
    """代采代发订单详情"""
    order = await DropshipOrder.filter(id=order_id).select_related(
        "supplier", "customer", "creator", "account_set",
        "product", "payment_employee",
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    # 单独查询关联的应付单（payable_bill_id 是 IntField 非外键）
    payable_bill_no = None
    if order.payable_bill_id:
        pb = await PayableBill.filter(id=order.payable_bill_id).first()
        payable_bill_no = pb.bill_no if pb else None

    return {
        "id": order.id,
        "ds_no": order.ds_no,
        "status": order.status,
        "account_set_id": order.account_set_id,
        "account_set_name": order.account_set.name if order.account_set else None,
        # 采购信息
        "supplier_id": order.supplier_id,
        "supplier_name": order.supplier.name if order.supplier else "",
        "product_id": order.product_id,
        "product_name": order.product_name,
        "purchase_price": float(order.purchase_price),
        "quantity": order.quantity,
        "purchase_total": float(order.purchase_total),
        "invoice_type": order.invoice_type,
        "purchase_tax_rate": float(order.purchase_tax_rate),
        # 销售信息
        "customer_id": order.customer_id,
        "customer_name": order.customer.name if order.customer else "",
        "platform_order_no": order.platform_order_no,
        "sale_price": float(order.sale_price),
        "sale_total": float(order.sale_total),
        "sale_tax_rate": float(order.sale_tax_rate),
        "settlement_type": order.settlement_type,
        "advance_receipt_id": order.advance_receipt_id,
        # 毛利
        "gross_profit": float(order.gross_profit),
        "gross_margin": float(order.gross_margin),
        # 物流
        "shipping_mode": order.shipping_mode,
        "carrier_code": order.carrier_code,
        "carrier_name": order.carrier_name,
        "tracking_no": order.tracking_no,
        "last_tracking_info": order.last_tracking_info,
        "phone": order.phone,
        # 状态管理
        "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
        "urged_at": order.urged_at.isoformat() if order.urged_at else None,
        "cancel_reason": order.cancel_reason,
        "note": order.note,
        # 财务单据
        "payable_bill_id": order.payable_bill_id,
        "payable_bill_no": payable_bill_no,
        "disbursement_bill_id": order.disbursement_bill_id,
        "receivable_bill_id": order.receivable_bill_id,
        # 付款
        "payment_method": order.payment_method,
        "payment_employee_name": order.payment_employee.name if order.payment_employee else None,
        # 元数据
        "creator_name": order.creator.display_name if order.creator else None,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }


# ── 创建 ──


@router.post("")
async def create_order(
    data: DropshipOrderCreate,
    submit: bool = False,
    user: User = Depends(require_permission("dropship")),
):
    """创建代采代发订单，submit=true 时自动提交"""
    order = await create_dropship_order(data, user, submit=submit)
    await log_operation(user, "DROPSHIP_CREATE", "DROPSHIP_ORDER", target_id=order.id, detail=f"创建代发订单 {order.ds_no}")

    return {
        "id": order.id,
        "ds_no": order.ds_no,
        "status": order.status,
    }


# ── 更新（仅草稿） ──


@router.put("/{order_id}")
async def update_order(
    order_id: int,
    data: DropshipOrderUpdate,
    user: User = Depends(require_permission("dropship")),
):
    """更新代采代发订单（仅限草稿状态）"""
    order = await DropshipOrder.filter(id=order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿状态的订单可以编辑")

    update_data = data.dict(exclude_unset=True)

    # 处理供应商快速新建
    if "supplier_name" in update_data and update_data["supplier_name"] and "supplier_id" not in update_data:
        supplier = await Supplier.create(name=update_data["supplier_name"])
        update_data["supplier_id"] = supplier.id
        logger.info(f"快速新建供应商: {supplier.name} (id={supplier.id})")
    update_data.pop("supplier_name", None)

    # 处理商品更新
    if "product_id" in update_data and update_data["product_id"]:
        product = await Product.filter(id=update_data["product_id"]).first()
        if not product:
            raise HTTPException(status_code=400, detail="商品不存在")

    # 应用更新（exclude_unset 已确保只有用户显式传入的字段）
    for field, value in update_data.items():
        setattr(order, field, value)

    # 重新计算金额和毛利
    price_fields = {"purchase_price", "quantity", "sale_price", "purchase_tax_rate", "sale_tax_rate", "invoice_type"}
    if price_fields & set(update_data.keys()):
        order.purchase_total = order.purchase_price * order.quantity
        order.sale_total = order.sale_price * order.quantity
        order.gross_profit, order.gross_margin = calculate_gross_profit(
            order.purchase_total, order.sale_total,
            order.purchase_tax_rate, order.sale_tax_rate,
            order.invoice_type,
        )

    await order.save()
    logger.info(f"更新代采代发订单: {order.ds_no}")
    await log_operation(user, "DROPSHIP_UPDATE", "DROPSHIP_ORDER", target_id=order.id, detail=f"更新代发订单 {order.ds_no}")

    return {
        "id": order.id,
        "ds_no": order.ds_no,
        "status": order.status,
        "purchase_total": float(order.purchase_total),
        "sale_total": float(order.sale_total),
        "gross_profit": float(order.gross_profit),
        "gross_margin": float(order.gross_margin),
    }


# ── 提交 ──


@router.post("/{order_id}/submit")
async def submit_order(
    order_id: int,
    user: User = Depends(require_permission("dropship")),
):
    """提交代采代发订单（草稿 → 待付款）"""
    order = await submit_dropship_order(order_id, user)
    await log_operation(user, "DROPSHIP_SUBMIT", "DROPSHIP_ORDER", target_id=order.id, detail=f"提交代发订单 {order.ds_no}")

    return {
        "id": order.id,
        "ds_no": order.ds_no,
        "status": order.status,
        "payable_bill_id": order.payable_bill_id,
    }


# ── 催付 ──


@router.post("/{order_id}/urge")
async def urge_payment(
    order_id: int,
    user: User = Depends(require_permission("dropship")),
):
    """催付"""
    order = await DropshipOrder.filter(id=order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "pending_payment":
        raise HTTPException(status_code=400, detail="只有待付款状态的订单可以催付")

    order.urged_at = now()
    await order.save()
    logger.info(f"代采代发催付: {order.ds_no}")
    await log_operation(user, "DROPSHIP_URGE", "DROPSHIP_ORDER", target_id=order.id, detail=f"催付代发订单 {order.ds_no}")

    return {
        "id": order.id,
        "ds_no": order.ds_no,
        "urged_at": order.urged_at.isoformat(),
    }


# ── 批量付款 ──


@router.post("/batch-pay")
async def batch_pay(
    data: DropshipPaymentRequest,
    user: User = Depends(require_permission("dropship_pay")),
):
    """批量付款：创建付款单 + 更新应付单 + 生成凭证A"""
    result = await batch_pay_dropship(
        order_ids=data.order_ids,
        payment_method=data.payment_method,
        employee_id=data.employee_id,
        user=user,
    )
    await log_operation(user, "DROPSHIP_BATCH_PAY", "DROPSHIP_ORDER", detail=f"批量支付代发订单 {len(data.order_ids)} 笔")

    return result


# ── 发货 ──


@router.post("/{order_id}/ship")
async def ship_order(
    order_id: int,
    data: DropshipShipRequest,
    user: User = Depends(require_permission("dropship")),
):
    """确认发货：更新物流信息 + 创建应收单 + 出入库 + 订阅快递100"""
    order = await ship_dropship_order(
        order_id=order_id,
        carrier_code=data.carrier_code,
        carrier_name=data.carrier_name,
        tracking_no=data.tracking_no,
        phone=data.phone,
        user=user,
    )
    await log_operation(user, "DROPSHIP_SHIP", "DROPSHIP_ORDER", target_id=order.id, detail=f"代发订单 {order.ds_no} 确认发货")

    return {
        "id": order.id,
        "ds_no": order.ds_no,
        "status": order.status,
        "receivable_bill_id": order.receivable_bill_id,
        "tracking_no": order.tracking_no,
    }


# ── 物流刷新 ──


@router.post("/{order_id}/refresh-tracking")
async def refresh_tracking(
    order_id: int,
    user: User = Depends(require_permission("dropship")),
):
    """刷新代采代发订单的物流信息（查询快递100）"""
    order = await DropshipOrder.filter(id=order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if not order.tracking_no or not order.carrier_code:
        raise HTTPException(status_code=400, detail="该订单没有物流信息")

    try:
        from app.services.logistics_service import query_kd100
        resp = await query_kd100(order.carrier_code, order.tracking_no, phone=order.phone)

        if resp.get("message") == "ok" and resp.get("data"):
            order.last_tracking_info = json.dumps(resp, ensure_ascii=False)

            # 检查是否已签收
            if str(resp.get("ischeck")) == "1":
                if order.status == "shipped":
                    order.status = "completed"
                    logger.info(f"快递已签收，自动完成: {order.ds_no}")
            await order.save()

            await log_operation(user, "DROPSHIP_REFRESH", "DROPSHIP_ORDER", target_id=order.id, detail=f"刷新代发订单 {order.ds_no} 物流信息")

            return {
                "id": order.id,
                "ds_no": order.ds_no,
                "status": order.status,
                "last_tracking_info": order.last_tracking_info,
                "tracking_status": _parse_tracking_status(order.last_tracking_info, order.status),
            }
        else:
            await log_operation(user, "DROPSHIP_REFRESH", "DROPSHIP_ORDER", target_id=order.id, detail=f"刷新代发订单 {order.ds_no} 物流信息")

            return {
                "id": order.id,
                "message": resp.get("message", "查询无结果"),
            }
    except Exception as e:
        logger.warning(f"物流刷新失败: {order.ds_no}, 错误: {e}")
        raise HTTPException(status_code=500, detail=f"物流查询失败: {str(e)}")


# ── 手动完成 ──


@router.post("/{order_id}/complete")
async def complete_order(
    order_id: int,
    user: User = Depends(require_permission("dropship")),
):
    """手动完成订单"""
    order = await DropshipOrder.filter(id=order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status not in ("shipped", "paid_pending_ship"):
        raise HTTPException(
            status_code=400,
            detail=f"只有已发货或已付待发状态的订单可以手动完成，当前状态: {order.status}",
        )

    order.status = "completed"
    await order.save()
    logger.info(f"代采代发手动完成: {order.ds_no}")
    await log_operation(user, "DROPSHIP_COMPLETE", "DROPSHIP_ORDER", target_id=order.id, detail=f"完成代发订单 {order.ds_no}")

    return {
        "id": order.id,
        "ds_no": order.ds_no,
        "status": order.status,
    }


# ── 取消 ──


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    data: DropshipCancelRequest,
    user: User = Depends(require_permission("dropship")),
):
    """取消订单：按状态分别处理冲销逻辑"""
    order = await cancel_dropship_order(order_id, data.reason, user)
    await log_operation(user, "DROPSHIP_CANCEL", "DROPSHIP_ORDER", target_id=order.id, detail=f"取消代发订单 {order.ds_no}")

    return {
        "id": order.id,
        "ds_no": order.ds_no,
        "status": order.status,
        "cancel_reason": order.cancel_reason,
    }
