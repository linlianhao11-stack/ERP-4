"""发票管理 API"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from urllib.parse import quote
from tortoise import transactions
from tortoise.expressions import Q
from app.auth.dependencies import require_permission
from app.models import User
from app.models.invoice import Invoice, InvoiceItem
from app.schemas.invoice import InvoiceFromReceivable, InvoiceCreate, InvoiceUpdate
from app.services.invoice_service import (
    push_invoice_from_receivable, create_input_invoice, confirm_invoice, cancel_invoice,
)
from app.config import UPLOAD_ROOT
from app.logger import get_logger

logger = get_logger("invoices")

router = APIRouter(prefix="/api/invoices", tags=["发票管理"])


def _safe_filepath(base_dir: str, relative_path: str) -> str:
    """拼接路径并校验不会逃逸出 base_dir（防止路径遍历攻击）"""
    full = os.path.join(base_dir, relative_path)
    if not os.path.realpath(full).startswith(os.path.realpath(base_dir)):
        raise HTTPException(status_code=400, detail="非法文件路径")
    return full


@router.get("")
async def list_invoices(
    account_set_id: int = Query(...),
    direction: str = Query(None),
    status: str = Query(None),
    customer_id: int = Query(None),
    supplier_id: int = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    search: str = Query(None),
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
    if search:
        q_filter = Q(invoice_no__icontains=search)
        if direction == 'output':
            q_filter = q_filter | Q(customer__name__icontains=search)
        elif direction == 'input':
            q_filter = q_filter | Q(supplier__name__icontains=search)
        else:
            q_filter = q_filter | Q(customer__name__icontains=search) | Q(supplier__name__icontains=search)
        query = query.filter(q_filter)

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
            "pdf_count": len(inv.pdf_files or []),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: int,
    account_set_id: int = Query(None),
    user: User = Depends(require_permission("accounting_view")),
):
    q = {"id": invoice_id}
    if account_set_id:
        q["account_set_id"] = account_set_id
    inv = await Invoice.filter(**q).prefetch_related(
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
        "customer_tax_id": inv.customer.tax_id if inv.customer else None,
        "customer_bank_name": inv.customer.bank_name if inv.customer else None,
        "customer_bank_account": inv.customer.bank_account if inv.customer else None,
        "customer_address": inv.customer.address if inv.customer else None,
        "customer_phone": inv.customer.phone if inv.customer else None,
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
        "pdf_files": inv.pdf_files or [],
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
            items=[it.model_dump() for it in data.items] if data.items else [],
            creator=user,
            invoice_date=data.invoice_date,
            tax_rate=data.tax_rate,
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


@router.post("/{invoice_id}/upload-pdf")
async def upload_invoice_pdf(
    invoice_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("accounting_edit")),
):
    inv = await Invoice.filter(id=invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    if inv.status == "cancelled":
        raise HTTPException(status_code=400, detail="已作废的发票不能上传附件")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 格式文件")

    header = await file.read(5)
    if not header.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="文件内容不是有效的 PDF")
    await file.seek(0)

    current_files = inv.pdf_files or []
    if len(current_files) >= 5:
        raise HTTPException(status_code=400, detail="每张发票最多上传 5 个 PDF 文件")

    year = str(inv.invoice_date.year)
    month = f"{inv.invoice_date.month:02d}"
    save_dir = os.path.join(UPLOAD_ROOT, "invoices", year, month)
    os.makedirs(save_dir, exist_ok=True)

    # 文件名净化：只保留字母数字下划线短横线，加 UUID 片段防并发冲突
    safe_no = re.sub(r'[^a-zA-Z0-9_\-]', '_', inv.invoice_no)
    seq = len(current_files) + 1
    unique_id = uuid.uuid4().hex[:8]
    filename = f"{safe_no}_{seq}_{unique_id}.pdf"
    filepath = os.path.join(save_dir, filename)
    # 最终路径校验
    _safe_filepath(UPLOAD_ROOT, f"invoices/{year}/{month}/{filename}")

    MAX_SIZE = 10 * 1024 * 1024
    total_size = 0
    try:
        with open(filepath, "wb") as f:
            while True:
                chunk = await file.read(8192)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_SIZE:
                    raise HTTPException(status_code=400, detail="文件过大，最大支持 10MB")
                f.write(chunk)
    except HTTPException:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise

    relative_path = f"invoices/{year}/{month}/{filename}"
    current_files.append({
        "path": relative_path,
        "name": file.filename,
        "size": total_size,
        "uploaded_at": datetime.now().isoformat(),
    })
    inv.pdf_files = current_files
    await inv.save()

    return {"message": "上传成功", "pdf_count": len(current_files), "index": seq - 1}


@router.get("/{invoice_id}/pdf/{index}")
async def download_invoice_pdf(
    invoice_id: int,
    index: int,
    user: User = Depends(require_permission("accounting_view")),
):
    inv = await Invoice.filter(id=invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    files = inv.pdf_files or []
    if index < 0 or index >= len(files):
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    file_info = files[index]
    filepath = _safe_filepath(UPLOAD_ROOT, file_info["path"])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="PDF 文件已丢失")

    def iter_file():
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    original_name = file_info.get("name", f"invoice_{index}.pdf")
    return StreamingResponse(
        iter_file(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(original_name)}",
        },
    )


@router.delete("/{invoice_id}/pdf/{index}")
async def delete_invoice_pdf(
    invoice_id: int,
    index: int,
    user: User = Depends(require_permission("accounting_edit")),
):
    inv = await Invoice.filter(id=invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    files = inv.pdf_files or []
    if index < 0 or index >= len(files):
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    file_info = files[index]
    filepath = _safe_filepath(UPLOAD_ROOT, file_info["path"])
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        logger.warning(f"删除 PDF 文件失败: {file_info.get('path')}, {e}")

    files.pop(index)
    inv.pdf_files = files
    await inv.save()

    return {"message": "删除成功", "pdf_count": len(files)}
