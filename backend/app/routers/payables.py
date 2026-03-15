"""应付管理 API"""
from __future__ import annotations

import calendar
from datetime import date as _date, datetime as _datetime, timezone as _tz

from fastapi import APIRouter, Depends, HTTPException, Query
from tortoise.expressions import Q
from tortoise import transactions
from app.auth.dependencies import require_permission
from app.models import User, Supplier
from app.models.accounting import AccountSet
from app.models.ar_ap import PayableBill, DisbursementBill, DisbursementRefundBill
from app.models.purchase import PurchaseReturn
from app.schemas.ar_ap import (
    PayableBillCreate, DisbursementBillCreate, DisbursementRefundBillCreate,
)
from app.schemas.voucher_gen import BillRef, GenerateVouchersRequest
from app.services.ap_service import (
    create_payable_bill, confirm_disbursement_bill,
    confirm_disbursement_refund, generate_ap_vouchers,
)
from app.utils.generators import generate_order_no
from app.logger import get_logger

logger = get_logger("payables")

router = APIRouter(prefix="/api/payables", tags=["应付管理"])


# ── 应付单 ──

@router.get("/payable-bills")
async def list_payable_bills(
    account_set_id: int = Query(...),
    supplier_id: int = Query(None),
    status: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ap_view")),
):
    query = PayableBill.filter(account_set_id=account_set_id)
    if supplier_id:
        query = query.filter(supplier_id=supplier_id)
    if status:
        query = query.filter(status=status)
    if start_date:
        query = query.filter(bill_date__gte=start_date)
    if end_date:
        query = query.filter(bill_date__lte=end_date)
    if search:
        query = query.filter(
            Q(bill_no__icontains=search) | Q(supplier__name__icontains=search)
        )

    total = await query.count()
    bills = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("supplier", "purchase_order")

    items = []
    for b in bills:
        items.append({
            "id": b.id, "bill_no": b.bill_no,
            "supplier_id": b.supplier_id,
            "supplier_name": b.supplier.name if b.supplier else None,
            "purchase_order_id": b.purchase_order_id,
            "purchase_order_no": b.purchase_order.po_no if b.purchase_order else None,
            "bill_date": str(b.bill_date),
            "total_amount": str(b.total_amount),
            "paid_amount": str(b.paid_amount),
            "unpaid_amount": str(b.unpaid_amount),
            "status": b.status,
            "voucher_no": b.voucher_no,
            "remark": b.remark,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/payable-bills/{bill_id}")
async def get_payable_bill(
    bill_id: int,
    account_set_id: int = Query(None),
    user: User = Depends(require_permission("accounting_ap_view")),
):
    q = {"id": bill_id}
    if account_set_id:
        q["account_set_id"] = account_set_id
    b = await PayableBill.filter(**q).prefetch_related("supplier", "purchase_order").first()
    if not b:
        raise HTTPException(status_code=404, detail="应付单不存在")
    return {
        "id": b.id, "bill_no": b.bill_no,
        "supplier_id": b.supplier_id,
        "supplier_name": b.supplier.name if b.supplier else None,
        "purchase_order_id": b.purchase_order_id,
        "purchase_order_no": b.purchase_order.po_no if b.purchase_order else None,
        "bill_date": str(b.bill_date),
        "total_amount": str(b.total_amount),
        "paid_amount": str(b.paid_amount),
        "unpaid_amount": str(b.unpaid_amount),
        "status": b.status,
        "voucher_no": b.voucher_no,
        "remark": b.remark,
        "creator_id": b.creator_id,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }


@router.post("/payable-bills")
async def create_payable_bill_endpoint(
    account_set_id: int = Query(...),
    data: PayableBillCreate = ...,
    user: User = Depends(require_permission("accounting_ap_edit")),
):
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise HTTPException(status_code=404, detail="账套不存在")
    supplier = await Supplier.filter(id=data.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    pb = await create_payable_bill(
        account_set_id=account_set_id,
        supplier_id=data.supplier_id,
        purchase_order_id=data.purchase_order_id,
        total_amount=data.total_amount,
        status="pending",
        creator=user,
        remark=data.remark,
        bill_date=data.bill_date,
    )
    return {"id": pb.id, "bill_no": pb.bill_no, "message": "创建成功"}


@router.post("/payable-bills/{bill_id}/cancel")
async def cancel_payable_bill(
    bill_id: int,
    user: User = Depends(require_permission("accounting_ap_edit")),
):
    async with transactions.in_transaction():
        b = await PayableBill.filter(id=bill_id).select_for_update().first()
        if not b:
            raise HTTPException(status_code=404, detail="应付单不存在")
        if b.status not in ("pending", "partial"):
            raise HTTPException(status_code=400, detail="只有待付款/部分付款状态的应付单可以取消")
        b.status = "cancelled"
        await b.save()
    return {"message": "已取消"}


# ── 付款单 ──

@router.get("/disbursement-bills")
async def list_disbursement_bills(
    account_set_id: int = Query(...),
    supplier_id: int = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ap_view")),
):
    query = DisbursementBill.filter(account_set_id=account_set_id)
    if supplier_id:
        query = query.filter(supplier_id=supplier_id)
    if status:
        query = query.filter(status=status)
    if search:
        query = query.filter(
            Q(bill_no__icontains=search) | Q(supplier__name__icontains=search)
        )

    total = await query.count()
    bills = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("supplier")

    items = []
    for b in bills:
        items.append({
            "id": b.id, "bill_no": b.bill_no,
            "supplier_id": b.supplier_id,
            "supplier_name": b.supplier.name if b.supplier else None,
            "payable_bill_id": b.payable_bill_id,
            "disbursement_date": str(b.disbursement_date),
            "amount": str(b.amount),
            "disbursement_method": b.disbursement_method,
            "bill_type": getattr(b, 'bill_type', 'normal'),
            "status": b.status,
            "voucher_no": b.voucher_no,
            "remark": b.remark,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/disbursement-bills")
async def create_disbursement_bill_endpoint(
    account_set_id: int = Query(...),
    data: DisbursementBillCreate = ...,
    user: User = Depends(require_permission("accounting_ap_edit")),
):
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise HTTPException(status_code=404, detail="账套不存在")
    supplier = await Supplier.filter(id=data.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    if data.payable_bill_id:
        pb = await PayableBill.filter(id=data.payable_bill_id, account_set_id=account_set_id).first()
        if not pb:
            raise HTTPException(status_code=404, detail="关联应付单不存在")

    disbursement = await DisbursementBill.create(
        bill_no=generate_order_no("FK"),
        account_set_id=account_set_id,
        supplier_id=data.supplier_id,
        payable_bill_id=data.payable_bill_id,
        disbursement_date=data.disbursement_date,
        amount=data.amount,
        disbursement_method=data.disbursement_method,
        status="draft",
        remark=data.remark,
        creator=user,
    )
    return {"id": disbursement.id, "bill_no": disbursement.bill_no, "message": "创建成功"}


@router.post("/disbursement-bills/{bill_id}/confirm")
async def confirm_disbursement_bill_endpoint(
    bill_id: int,
    user: User = Depends(require_permission("accounting_ap_confirm")),
):
    try:
        db = await confirm_disbursement_bill(bill_id, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "确认成功", "bill_no": db.bill_no}


# ── 付款退款单 ──

@router.get("/disbursement-refund-bills")
async def list_disbursement_refund_bills(
    account_set_id: int = Query(...),
    supplier_id: int = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ap_view")),
):
    query = DisbursementRefundBill.filter(account_set_id=account_set_id)
    if supplier_id:
        query = query.filter(supplier_id=supplier_id)
    if status:
        query = query.filter(status=status)
    if search:
        query = query.filter(
            Q(bill_no__icontains=search) | Q(supplier__name__icontains=search)
        )

    total = await query.count()
    bills = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("supplier")

    items = []
    for b in bills:
        items.append({
            "id": b.id, "bill_no": b.bill_no,
            "supplier_id": b.supplier_id,
            "supplier_name": b.supplier.name if b.supplier else None,
            "original_disbursement_id": b.original_disbursement_id,
            "refund_date": str(b.refund_date),
            "amount": str(b.amount),
            "reason": b.reason,
            "status": b.status,
            "voucher_no": b.voucher_no,
            "remark": b.remark,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/disbursement-refund-bills")
async def create_disbursement_refund_bill_endpoint(
    account_set_id: int = Query(...),
    data: DisbursementRefundBillCreate = ...,
    user: User = Depends(require_permission("accounting_ap_edit")),
):
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise HTTPException(status_code=404, detail="账套不存在")
    original = await DisbursementBill.filter(
        id=data.original_disbursement_id, account_set_id=account_set_id, status="confirmed"
    ).first()
    if not original:
        raise HTTPException(status_code=404, detail="原付款单不存在或未确认")
    if data.amount > original.amount:
        raise HTTPException(status_code=400, detail="退款金额不能超过原付款金额")

    refund = await DisbursementRefundBill.create(
        bill_no=generate_order_no("FKTK"),
        account_set_id=account_set_id,
        supplier_id=data.supplier_id,
        original_disbursement_id=data.original_disbursement_id,
        refund_date=data.refund_date,
        amount=data.amount,
        reason=data.reason,
        status="draft",
        remark=data.remark,
        creator=user,
    )
    return {"id": refund.id, "bill_no": refund.bill_no, "message": "创建成功"}


@router.post("/disbursement-refund-bills/{bill_id}/confirm")
async def confirm_disbursement_refund_endpoint(
    bill_id: int,
    user: User = Depends(require_permission("accounting_ap_confirm")),
):
    try:
        refund = await confirm_disbursement_refund(bill_id, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "确认成功", "bill_no": refund.bill_no}


# ── 采购退货单（凭证视角） ──

@router.get("/purchase-returns")
async def list_purchase_returns_for_ap(
    account_set_id: int = Query(...),
    supplier_id: int = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_ap_view")),
):
    query = PurchaseReturn.filter(account_set_id=account_set_id)
    if supplier_id:
        query = query.filter(supplier_id=supplier_id)
    if search:
        query = query.filter(
            Q(return_no__icontains=search) | Q(supplier__name__icontains=search)
        )

    total = await query.count()
    returns = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("supplier", "purchase_order")

    items = []
    for pr in returns:
        items.append({
            "id": pr.id,
            "return_no": pr.return_no,
            "supplier_id": pr.supplier_id,
            "supplier_name": pr.supplier.name if pr.supplier else None,
            "purchase_order_no": pr.purchase_order.po_no if pr.purchase_order else None,
            "total_amount": str(pr.total_amount),
            "return_date": pr.created_at.strftime("%Y-%m-%d") if pr.created_at else None,
            "refund_status": pr.refund_status,
            "voucher_no": getattr(pr, 'voucher_no', None),
            "has_voucher": getattr(pr, 'voucher_id', None) is not None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ── 待处理单据查询 ──

@router.get("/pending-voucher-bills")
async def list_pending_voucher_bills(
    account_set_id: int = Query(...),
    period: str = Query(...),
    user: User = Depends(require_permission("accounting_ap_view")),
):
    """查询指定期间待生成凭证的单据"""
    year, month = int(period[:4]), int(period[5:7])
    _, last_day = calendar.monthrange(year, month)
    period_start = _date(year, month, 1)
    period_end = _date(year, month, last_day)
    result = []

    # 付款单
    disbursements = await DisbursementBill.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None,
        disbursement_date__gte=period_start, disbursement_date__lte=period_end,
    ).select_related("supplier").all()
    for d in disbursements:
        result.append({
            "id": d.id, "type": "disbursement",
            "bill_no": d.bill_no,
            "type_label": "退款" if getattr(d, 'bill_type', '') == "return_refund" else "付款",
            "partner_name": d.supplier.name if d.supplier else "",
            "partner_id": d.supplier_id,
            "amount": float(d.amount),
            "date": str(d.disbursement_date),
        })

    # 付款退款单
    refunds = await DisbursementRefundBill.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None,
        refund_date__gte=period_start, refund_date__lte=period_end,
    ).select_related("supplier").all()
    for rf in refunds:
        result.append({
            "id": rf.id, "type": "refund",
            "bill_no": rf.bill_no,
            "type_label": "付款退款",
            "partner_name": rf.supplier.name if rf.supplier else "",
            "partner_id": rf.supplier_id,
            "amount": float(-rf.amount),
            "date": str(rf.refund_date),
        })

    # 采购退货单
    purchase_returns = await PurchaseReturn.filter(
        account_set_id=account_set_id,
        voucher_id=None,
        created_at__gte=_datetime(year, month, 1, 0, 0, 0, tzinfo=_tz.utc),
        created_at__lte=_datetime(year, month, last_day, 23, 59, 59, tzinfo=_tz.utc),
    ).select_related("supplier").all()
    for pr in purchase_returns:
        if pr.total_amount <= 0:
            continue
        result.append({
            "id": pr.id, "type": "purchase_return",
            "bill_no": pr.return_no,
            "type_label": "采购退货",
            "partner_name": pr.supplier.name if pr.supplier else "",
            "partner_id": pr.supplier_id,
            "amount": float(-pr.total_amount),
            "date": str(pr.created_at.date()) if hasattr(pr.created_at, 'date') else str(pr.created_at),
        })

    return {"items": result, "total": len(result)}


# ── 期末凭证生成 ──

@router.post("/generate-ap-vouchers")
async def generate_ap_vouchers_endpoint(
    account_set_id: int = Query(...),
    data: GenerateVouchersRequest = ...,
    user: User = Depends(require_permission("accounting_ap_confirm")),
):
    try:
        result = await generate_ap_vouchers(
            account_set_id,
            data.period_names or [],
            user,
            bills=[{"id": b.id, "type": b.type} for b in (data.bills or [])],
            merge_by_partner=data.merge_by_partner,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    total_count = len(result["vouchers"])
    return {"message": f"生成 {total_count} 张凭证", "vouchers": result["vouchers"], "summary": result["summary"]}
