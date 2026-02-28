"""发票管理 API"""
from __future__ import annotations

from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from tortoise import transactions
from app.auth.dependencies import require_permission
from app.models import User
from app.models.invoice import Invoice, InvoiceItem
from app.schemas.invoice import InvoiceFromReceivable, InvoiceCreate, InvoiceUpdate
from app.services.invoice_service import (
    push_invoice_from_receivable, create_input_invoice, confirm_invoice, cancel_invoice,
)

router = APIRouter(prefix="/api/invoices", tags=["发票管理"])


@router.get("")
async def list_invoices(
    account_set_id: int = Query(...),
    direction: str = Query(None),
    status: str = Query(None),
    customer_id: int = Query(None),
    supplier_id: int = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_view")),
):
    query = Invoice.filter(account_set_id=account_set_id)
    if direction:
        query = query.filter(direction=direction)
    if status:
        query = query.filter(status=status)
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if supplier_id:
        query = query.filter(supplier_id=supplier_id)
    if start_date:
        query = query.filter(invoice_date__gte=start_date)
    if end_date:
        query = query.filter(invoice_date__lte=end_date)

    total = await query.count()
    invoices = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("customer", "supplier")

    items = []
    for inv in invoices:
        items.append({
            "id": inv.id, "invoice_no": inv.invoice_no,
            "invoice_type": inv.invoice_type,
            "direction": inv.direction,
            "customer_id": inv.customer_id,
            "customer_name": inv.customer.name if inv.customer else None,
            "supplier_id": inv.supplier_id,
            "supplier_name": inv.supplier.name if inv.supplier else None,
            "receivable_bill_id": inv.receivable_bill_id,
            "payable_bill_id": inv.payable_bill_id,
            "invoice_date": str(inv.invoice_date),
            "total_amount": str(inv.total_amount),
            "amount_without_tax": str(inv.amount_without_tax),
            "tax_amount": str(inv.tax_amount),
            "status": inv.status,
            "voucher_no": inv.voucher_no,
            "remark": inv.remark,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: int,
    user: User = Depends(require_permission("accounting_view")),
):
    inv = await Invoice.filter(id=invoice_id).prefetch_related(
        "customer", "supplier", "receivable_bill", "payable_bill"
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")

    inv_items = await InvoiceItem.filter(invoice_id=inv.id).all()

    return {
        "id": inv.id, "invoice_no": inv.invoice_no,
        "invoice_type": inv.invoice_type,
        "direction": inv.direction,
        "customer_id": inv.customer_id,
        "customer_name": inv.customer.name if inv.customer else None,
        "supplier_id": inv.supplier_id,
        "supplier_name": inv.supplier.name if inv.supplier else None,
        "receivable_bill_id": inv.receivable_bill_id,
        "receivable_bill_no": inv.receivable_bill.bill_no if inv.receivable_bill else None,
        "payable_bill_id": inv.payable_bill_id,
        "payable_bill_no": inv.payable_bill.bill_no if inv.payable_bill else None,
        "invoice_date": str(inv.invoice_date),
        "total_amount": str(inv.total_amount),
        "amount_without_tax": str(inv.amount_without_tax),
        "tax_amount": str(inv.tax_amount),
        "status": inv.status,
        "voucher_no": inv.voucher_no,
        "remark": inv.remark,
        "creator_id": inv.creator_id,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
        "items": [
            {
                "id": it.id,
                "product_id": it.product_id,
                "product_name": it.product_name,
                "quantity": it.quantity,
                "unit_price": str(it.unit_price),
                "tax_rate": str(it.tax_rate),
                "tax_amount": str(it.tax_amount),
                "amount_without_tax": str(it.amount_without_tax),
                "amount": str(it.amount),
            }
            for it in inv_items
        ],
    }


@router.post("/from-receivable")
async def create_invoice_from_receivable(
    account_set_id: int = Query(...),
    data: InvoiceFromReceivable = ...,
    user: User = Depends(require_permission("accounting_edit")),
):
    try:
        inv = await push_invoice_from_receivable(
            account_set_id=account_set_id,
            receivable_bill_id=data.receivable_bill_id,
            invoice_type=data.invoice_type,
            items=[it.model_dump() for it in data.items],
            creator=user,
            invoice_date=data.invoice_date,
            remark=data.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": inv.id, "invoice_no": inv.invoice_no, "message": "创建成功"}


@router.post("")
async def create_input_invoice_endpoint(
    account_set_id: int = Query(...),
    data: InvoiceCreate = ...,
    user: User = Depends(require_permission("accounting_edit")),
):
    try:
        inv = await create_input_invoice(
            account_set_id=account_set_id,
            supplier_id=data.supplier_id,
            invoice_type=data.invoice_type,
            items=[it.model_dump() for it in data.items],
            payable_bill_id=data.payable_bill_id,
            creator=user,
            invoice_date=data.invoice_date,
            remark=data.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": inv.id, "invoice_no": inv.invoice_no, "message": "创建成功"}


@router.put("/{invoice_id}")
async def update_invoice(
    invoice_id: int,
    data: InvoiceUpdate = ...,
    user: User = Depends(require_permission("accounting_edit")),
):
    async with transactions.in_transaction():
        inv = await Invoice.filter(id=invoice_id).select_for_update().first()
        if not inv:
            raise HTTPException(status_code=404, detail="发票不存在")
        if inv.status != "draft":
            raise HTTPException(status_code=400, detail="只有草稿状态的发票可以编辑")

        if data.invoice_type is not None:
            inv.invoice_type = data.invoice_type
        if data.invoice_date is not None:
            inv.invoice_date = data.invoice_date
        if data.remark is not None:
            inv.remark = data.remark

        if data.items is not None:
            # 删除旧明细
            await InvoiceItem.filter(invoice_id=inv.id).delete()

            # 重新计算并创建新明细
            total_without_tax = Decimal("0")
            total_tax = Decimal("0")
            total_amount = Decimal("0")
            for it in data.items:
                unit_price = it.unit_price
                quantity = it.quantity
                tax_rate = it.tax_rate
                without_tax = (unit_price * quantity).quantize(Decimal("0.01"))
                tax = (without_tax * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
                amount = without_tax + tax
                total_without_tax += without_tax
                total_tax += tax
                total_amount += amount

                await InvoiceItem.create(
                    invoice=inv,
                    product_id=it.product_id,
                    product_name=it.product_name,
                    quantity=quantity,
                    unit_price=unit_price,
                    tax_rate=tax_rate,
                    tax_amount=tax,
                    amount_without_tax=without_tax,
                    amount=amount,
                )

            inv.total_amount = total_amount
            inv.amount_without_tax = total_without_tax
            inv.tax_amount = total_tax

        await inv.save()

    return {"id": inv.id, "invoice_no": inv.invoice_no, "message": "更新成功"}


@router.post("/{invoice_id}/confirm")
async def confirm_invoice_endpoint(
    invoice_id: int,
    user: User = Depends(require_permission("accounting_approve")),
):
    try:
        inv = await confirm_invoice(invoice_id, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "确认成功", "invoice_no": inv.invoice_no}


@router.post("/{invoice_id}/cancel")
async def cancel_invoice_endpoint(
    invoice_id: int,
    user: User = Depends(require_permission("accounting_edit")),
):
    try:
        inv = await cancel_invoice(invoice_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "已作废", "invoice_no": inv.invoice_no}
