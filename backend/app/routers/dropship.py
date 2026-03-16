"""代采代发路由"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from tortoise.queryset import Q

from app.auth.dependencies import require_permission
from app.logger import get_logger
from app.models import User, Supplier, Product, Customer, AccountSet
from app.models.dropship import DropshipOrder
from app.schemas.dropship import (
    DropshipOrderCreate, DropshipOrderUpdate,
    DropshipShipRequest, DropshipPaymentRequest, DropshipCancelRequest,
)
from app.services.dropship_service import (
    create_dropship_order, submit_dropship_order, calculate_gross_profit,
)
from app.utils.time import now
from app.utils.errors import parse_date

logger = get_logger("dropship")

router = APIRouter(prefix="/api/dropship", tags=["代采代发"])


# ── 报表端点（放在 /{id} 之前，防止路径冲突） ──


@router.get("/reports/summary")
async def report_summary(
    user: User = Depends(require_permission("dropship")),
):
    """报表：汇总统计 (TODO)"""
    # Task 8 skeleton
    return {"message": "TODO"}


@router.get("/reports/profit")
async def report_profit(
    user: User = Depends(require_permission("dropship")),
):
    """报表：利润分析 (TODO)"""
    # Task 8 skeleton
    return {"message": "TODO"}


@router.get("/reports/receivable")
async def report_receivable(
    user: User = Depends(require_permission("dropship")),
):
    """报表：应收统计 (TODO)"""
    # Task 8 skeleton
    return {"message": "TODO"}


@router.get("/payment-workbench")
async def payment_workbench(
    user: User = Depends(require_permission("dropship")),
):
    """付款工作台 (TODO)"""
    # Task 4 skeleton
    return {"message": "TODO"}


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
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))
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

    # 批量查询账套名称
    as_ids = list(set(o.account_set_id for o in orders if o.account_set_id))
    as_map = {}
    if as_ids:
        for a in await AccountSet.filter(id__in=as_ids):
            as_map[a.id] = a.name

    return {
        "items": [
            {
                "id": o.id,
                "ds_no": o.ds_no,
                "status": o.status,
                "account_set_id": o.account_set_id,
                "account_set_name": as_map.get(o.account_set_id),
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
        "product", "payable_bill", "disbursement_bill", "receivable_bill",
        "payment_employee", "advance_receipt",
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

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
        # 状态管理
        "urged_at": order.urged_at.isoformat() if order.urged_at else None,
        "cancel_reason": order.cancel_reason,
        "note": order.note,
        # 财务单据
        "payable_bill_id": order.payable_bill_id,
        "payable_bill_no": order.payable_bill.bill_no if order.payable_bill else None,
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

    # 应用更新
    for field, value in update_data.items():
        if value is not None:
            setattr(order, field, value)

    # 重新计算金额和毛利
    price_fields = {"purchase_price", "quantity", "sale_price", "purchase_tax_rate", "sale_tax_rate", "invoice_type"}
    if price_fields & set(update_data.keys()):
        order.purchase_total = order.purchase_price * order.quantity
        order.sale_total = order.sale_price * order.quantity
        order.gross_profit, order.gross_margin = await calculate_gross_profit(
            order.purchase_total, order.sale_total,
            order.purchase_tax_rate, order.sale_tax_rate,
            order.invoice_type,
        )

    await order.save()
    logger.info(f"更新代采代发订单: {order.ds_no}")

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

    return {
        "id": order.id,
        "ds_no": order.ds_no,
        "urged_at": order.urged_at.isoformat(),
    }


# ── 批量付款 ──


@router.post("/batch-pay")
async def batch_pay(
    data: DropshipPaymentRequest,
    user: User = Depends(require_permission("dropship")),
):
    """批量付款 (TODO)"""
    # Task 4 skeleton
    return {"message": "TODO"}


# ── 发货 ──


@router.post("/{order_id}/ship")
async def ship_order(
    order_id: int,
    data: DropshipShipRequest,
    user: User = Depends(require_permission("dropship")),
):
    """发货 (TODO)"""
    # Task 5 skeleton
    return {"message": "TODO"}


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
    """取消订单 (TODO)"""
    # Task 7 skeleton
    return {"message": "TODO"}
