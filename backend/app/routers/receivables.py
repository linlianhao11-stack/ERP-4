"""应收管理 API"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from tortoise import transactions
from app.auth.dependencies import require_permission
from app.models import User, Customer
from app.models.order import Order
from app.models.accounting import AccountSet
from app.models.ar_ap import ReceivableBill, ReceiptBill, ReceiptRefundBill, ReceivableWriteOff
from app.schemas.ar_ap import (
    ReceivableBillCreate, ReceiptBillCreate, ReceiptRefundBillCreate, ReceivableWriteOffCreate,
)
from app.services.ar_service import (
    create_receivable_bill, confirm_receipt_bill, confirm_receipt_refund,
    confirm_write_off, generate_ar_vouchers,
)
from app.utils.generators import generate_order_no
from app.logger import get_logger

logger = get_logger("receivables")

router = APIRouter(prefix="/api/receivables", tags=["应收管理"])


# ── 应收单 ──

@router.get("/receivable-bills")
async def list_receivable_bills(
    account_set_id: int = Query(...),
    customer_id: int = Query(None),
    status: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ar_view")),
):
    query = ReceivableBill.filter(account_set_id=account_set_id)
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if status:
        query = query.filter(status=status)
    if start_date:
        query = query.filter(bill_date__gte=start_date)
    if end_date:
        query = query.filter(bill_date__lte=end_date)

    total = await query.count()
    bills = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("customer", "order")

    items = []
    for b in bills:
        items.append({
            "id": b.id, "bill_no": b.bill_no,
            "customer_id": b.customer_id,
            "customer_name": b.customer.name if b.customer else None,
            "order_id": b.order_id,
            "order_no": b.order.order_no if b.order else None,
            "bill_date": str(b.bill_date),
            "total_amount": str(b.total_amount),
            "received_amount": str(b.received_amount),
            "unreceived_amount": str(b.unreceived_amount),
            "status": b.status,
            "voucher_no": b.voucher_no,
            "remark": b.remark,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/receivable-bills/{bill_id}")
async def get_receivable_bill(
    bill_id: int,
    account_set_id: int = Query(None),
    user: User = Depends(require_permission("accounting_ar_view")),
):
    q = {"id": bill_id}
    if account_set_id:
        q["account_set_id"] = account_set_id
    b = await ReceivableBill.filter(**q).prefetch_related("customer", "order").first()
    if not b:
        raise HTTPException(status_code=404, detail="应收单不存在")
    return {
        "id": b.id, "bill_no": b.bill_no,
        "customer_id": b.customer_id,
        "customer_name": b.customer.name if b.customer else None,
        "order_id": b.order_id,
        "order_no": b.order.order_no if b.order else None,
        "bill_date": str(b.bill_date),
        "total_amount": str(b.total_amount),
        "received_amount": str(b.received_amount),
        "unreceived_amount": str(b.unreceived_amount),
        "status": b.status,
        "voucher_no": b.voucher_no,
        "remark": b.remark,
        "creator_id": b.creator_id,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


@router.post("/receivable-bills")
async def create_receivable_bill_endpoint(
    account_set_id: int = Query(...),
    data: ReceivableBillCreate = ...,
    user: User = Depends(require_permission("accounting_ar_edit")),
):
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise HTTPException(status_code=404, detail="账套不存在")
    customer = await Customer.filter(id=data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    rb = await create_receivable_bill(
        account_set_id=account_set_id,
        customer_id=data.customer_id,
        order_id=data.order_id,
        total_amount=data.total_amount,
        status="pending",
        creator=user,
        remark=data.remark,
        bill_date=data.bill_date,
    )
    return {"id": rb.id, "bill_no": rb.bill_no, "message": "创建成功"}


@router.post("/receivable-bills/{bill_id}/cancel")
async def cancel_receivable_bill(
    bill_id: int,
    user: User = Depends(require_permission("accounting_ar_edit")),
):
    async with transactions.in_transaction():
        b = await ReceivableBill.filter(id=bill_id).select_for_update().first()
        if not b:
            raise HTTPException(status_code=404, detail="应收单不存在")
        if b.status not in ("pending", "partial"):
            raise HTTPException(status_code=400, detail="只有待收款/部分收款状态的应收单可以取消")
        b.status = "cancelled"
        await b.save()
    return {"message": "已取消"}


# ── 收款单 ──

@router.get("/receipt-bills")
async def list_receipt_bills(
    account_set_id: int = Query(...),
    customer_id: int = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ar_view")),
):
    query = ReceiptBill.filter(account_set_id=account_set_id)
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if status:
        query = query.filter(status=status)

    total = await query.count()
    bills = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("customer")

    items = []
    for b in bills:
        items.append({
            "id": b.id, "bill_no": b.bill_no,
            "customer_id": b.customer_id,
            "customer_name": b.customer.name if b.customer else None,
            "receivable_bill_id": b.receivable_bill_id,
            "receipt_date": str(b.receipt_date),
            "amount": str(b.amount),
            "payment_method": b.payment_method,
            "is_advance": b.is_advance,
            "bill_type": getattr(b, 'bill_type', 'normal'),
            "status": b.status,
            "voucher_no": b.voucher_no,
            "remark": b.remark,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/receipt-bills")
async def create_receipt_bill_endpoint(
    account_set_id: int = Query(...),
    data: ReceiptBillCreate = ...,
    user: User = Depends(require_permission("accounting_ar_edit")),
):
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise HTTPException(status_code=404, detail="账套不存在")
    customer = await Customer.filter(id=data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    if data.receivable_bill_id:
        rb = await ReceivableBill.filter(id=data.receivable_bill_id, account_set_id=account_set_id).first()
        if not rb:
            raise HTTPException(status_code=404, detail="关联应收单不存在")

    receipt = await ReceiptBill.create(
        bill_no=generate_order_no("SK"),
        account_set_id=account_set_id,
        customer_id=data.customer_id,
        receivable_bill_id=data.receivable_bill_id,
        receipt_date=data.receipt_date,
        amount=data.amount,
        payment_method=data.payment_method,
        is_advance=data.is_advance,
        status="draft",
        remark=data.remark,
        creator=user,
    )
    return {"id": receipt.id, "bill_no": receipt.bill_no, "message": "创建成功"}


@router.post("/receipt-bills/{bill_id}/confirm")
async def confirm_receipt_bill_endpoint(
    bill_id: int,
    user: User = Depends(require_permission("accounting_ar_confirm")),
):
    try:
        receipt = await confirm_receipt_bill(bill_id, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "确认成功", "bill_no": receipt.bill_no}


# ── 收款退款单 ──

@router.get("/receipt-refund-bills")
async def list_receipt_refund_bills(
    account_set_id: int = Query(...),
    customer_id: int = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ar_view")),
):
    query = ReceiptRefundBill.filter(account_set_id=account_set_id)
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if status:
        query = query.filter(status=status)

    total = await query.count()
    bills = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("customer")

    items = []
    for b in bills:
        items.append({
            "id": b.id, "bill_no": b.bill_no,
            "customer_id": b.customer_id,
            "customer_name": b.customer.name if b.customer else None,
            "original_receipt_id": b.original_receipt_id,
            "refund_date": str(b.refund_date),
            "amount": str(b.amount),
            "reason": b.reason,
            "status": b.status,
            "voucher_no": b.voucher_no,
            "remark": b.remark,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/receipt-refund-bills")
async def create_receipt_refund_bill_endpoint(
    account_set_id: int = Query(...),
    data: ReceiptRefundBillCreate = ...,
    user: User = Depends(require_permission("accounting_ar_edit")),
):
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise HTTPException(status_code=404, detail="账套不存在")
    original = await ReceiptBill.filter(id=data.original_receipt_id, account_set_id=account_set_id, status="confirmed").first()
    if not original:
        raise HTTPException(status_code=404, detail="原收款单不存在或未确认")
    if data.amount > original.amount:
        raise HTTPException(status_code=400, detail="退款金额不能超过原收款金额")

    refund = await ReceiptRefundBill.create(
        bill_no=generate_order_no("SKTK"),
        account_set_id=account_set_id,
        customer_id=data.customer_id,
        original_receipt_id=data.original_receipt_id,
        refund_date=data.refund_date,
        amount=data.amount,
        reason=data.reason,
        status="draft",
        remark=data.remark,
        creator=user,
    )
    return {"id": refund.id, "bill_no": refund.bill_no, "message": "创建成功"}


@router.post("/receipt-refund-bills/{bill_id}/confirm")
async def confirm_receipt_refund_endpoint(
    bill_id: int,
    user: User = Depends(require_permission("accounting_ar_confirm")),
):
    try:
        refund = await confirm_receipt_refund(bill_id, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "确认成功", "bill_no": refund.bill_no}


# ── 应收核销单 ──

@router.get("/receivable-write-offs")
async def list_write_offs(
    account_set_id: int = Query(...),
    customer_id: int = Query(None),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ar_view")),
):
    query = ReceivableWriteOff.filter(account_set_id=account_set_id)
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if status:
        query = query.filter(status=status)

    total = await query.count()
    items_raw = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("customer")

    items = []
    for wo in items_raw:
        items.append({
            "id": wo.id, "bill_no": wo.bill_no,
            "customer_id": wo.customer_id,
            "customer_name": wo.customer.name if wo.customer else None,
            "advance_receipt_id": wo.advance_receipt_id,
            "receivable_bill_id": wo.receivable_bill_id,
            "write_off_date": str(wo.write_off_date),
            "amount": str(wo.amount),
            "status": wo.status,
            "voucher_no": wo.voucher_no,
            "remark": wo.remark,
            "created_at": wo.created_at.isoformat() if wo.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/receivable-write-offs")
async def create_write_off_endpoint(
    account_set_id: int = Query(...),
    data: ReceivableWriteOffCreate = ...,
    user: User = Depends(require_permission("accounting_ar_edit")),
):
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise HTTPException(status_code=404, detail="账套不存在")

    advance = await ReceiptBill.filter(
        id=data.advance_receipt_id, account_set_id=account_set_id,
        is_advance=True, status="confirmed"
    ).first()
    if not advance:
        raise HTTPException(status_code=400, detail="预收款单不存在或不符合条件")

    rb = await ReceivableBill.filter(
        id=data.receivable_bill_id, account_set_id=account_set_id
    ).first()
    if not rb:
        raise HTTPException(status_code=404, detail="应收单不存在")
    if rb.status in ("completed", "cancelled"):
        raise HTTPException(status_code=400, detail="应收单已完成或已取消")

    wo = await ReceivableWriteOff.create(
        bill_no=generate_order_no("YSHX"),
        account_set_id=account_set_id,
        customer_id=data.customer_id,
        advance_receipt_id=data.advance_receipt_id,
        receivable_bill_id=data.receivable_bill_id,
        write_off_date=data.write_off_date,
        amount=data.amount,
        status="draft",
        remark=data.remark,
        creator=user,
    )
    return {"id": wo.id, "bill_no": wo.bill_no, "message": "创建成功"}


@router.post("/receivable-write-offs/{bill_id}/confirm")
async def confirm_write_off_endpoint(
    bill_id: int,
    user: User = Depends(require_permission("accounting_ar_confirm")),
):
    try:
        wo = await confirm_write_off(bill_id, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "确认成功", "bill_no": wo.bill_no}


# ── 销售退货单（凭证视角） ──

@router.get("/sales-returns")
async def list_sales_returns(
    account_set_id: int = Query(...),
    customer_id: int = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ar_view")),
):
    query = Order.filter(account_set_id=account_set_id, order_type="RETURN")
    if customer_id:
        query = query.filter(customer_id=customer_id)

    total = await query.count()
    orders = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("customer")

    items = []
    for o in orders:
        items.append({
            "id": o.id,
            "order_no": o.order_no,
            "customer_id": o.customer_id,
            "customer_name": o.customer.name if o.customer else None,
            "total_amount": str(abs(o.total_amount)),
            "total_cost": str(abs(o.total_cost)),
            "return_date": o.created_at.strftime("%Y-%m-%d") if o.created_at else None,
            "voucher_no": o.voucher_no,
            "has_voucher": o.voucher_id is not None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ── 期末凭证生成 ──

class GenerateVouchersRequest(BaseModel):
    period_names: list[str]

@router.post("/generate-ar-vouchers")
async def generate_ar_vouchers_endpoint(
    account_set_id: int = Query(...),
    data: GenerateVouchersRequest = ...,
    user: User = Depends(require_permission("accounting_ar_confirm")),
):
    try:
        result = await generate_ar_vouchers(account_set_id, data.period_names, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    total_count = len(result["vouchers"])
    return {"message": f"生成 {total_count} 张凭证", "vouchers": result["vouchers"], "summary": result["summary"]}
