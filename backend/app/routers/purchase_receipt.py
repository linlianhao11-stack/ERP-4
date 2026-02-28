"""采购入库单 API"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.dependencies import require_permission
from app.models import User
from app.models.delivery import PurchaseReceiptBill, PurchaseReceiptItem

router = APIRouter(prefix="/api/purchase-receipt", tags=["采购入库单"])


@router.get("")
async def list_purchase_receipts(
    account_set_id: int = Query(...),
    supplier_id: int = Query(None),
    purchase_order_id: int = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_view")),
):
    query = PurchaseReceiptBill.filter(account_set_id=account_set_id)
    if supplier_id:
        query = query.filter(supplier_id=supplier_id)
    if purchase_order_id:
        query = query.filter(purchase_order_id=purchase_order_id)
    if start_date:
        query = query.filter(bill_date__gte=start_date)
    if end_date:
        query = query.filter(bill_date__lte=end_date)

    total = await query.count()
    bills = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).prefetch_related("supplier", "purchase_order")

    items = []
    for b in bills:
        items.append({
            "id": b.id, "bill_no": b.bill_no,
            "supplier_id": b.supplier_id,
            "supplier_name": b.supplier.name if b.supplier else None,
            "purchase_order_id": b.purchase_order_id,
            "purchase_order_no": b.purchase_order.order_no if b.purchase_order else None,
            "warehouse_id": b.warehouse_id,
            "bill_date": str(b.bill_date),
            "total_amount": str(b.total_amount),
            "total_amount_without_tax": str(b.total_amount_without_tax),
            "total_tax": str(b.total_tax),
            "status": b.status,
            "voucher_no": b.voucher_no,
            "remark": b.remark,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{bill_id}")
async def get_purchase_receipt(
    bill_id: int,
    user: User = Depends(require_permission("accounting_view")),
):
    b = await PurchaseReceiptBill.filter(id=bill_id).prefetch_related("supplier", "purchase_order").first()
    if not b:
        raise HTTPException(status_code=404, detail="入库单不存在")
    return {
        "id": b.id, "bill_no": b.bill_no,
        "supplier_id": b.supplier_id,
        "supplier_name": b.supplier.name if b.supplier else None,
        "purchase_order_id": b.purchase_order_id,
        "warehouse_id": b.warehouse_id,
        "bill_date": str(b.bill_date),
        "total_amount": str(b.total_amount),
        "total_amount_without_tax": str(b.total_amount_without_tax),
        "total_tax": str(b.total_tax),
        "status": b.status,
        "voucher_no": b.voucher_no,
        "remark": b.remark,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "items": [
            {
                "id": it.id,
                "product_id": it.product_id,
                "product_name": it.product_name,
                "quantity": it.quantity,
                "tax_inclusive_price": str(it.tax_inclusive_price),
                "tax_exclusive_price": str(it.tax_exclusive_price),
                "tax_rate": str(it.tax_rate),
            }
            for it in await PurchaseReceiptItem.filter(receipt_bill_id=b.id).all()
        ],
    }


@router.get("/{bill_id}/pdf")
async def get_purchase_receipt_pdf(
    bill_id: int,
    user: User = Depends(require_permission("accounting_view")),
):
    from app.utils.pdf_print import generate_delivery_pdf
    b = await PurchaseReceiptBill.filter(id=bill_id).prefetch_related("supplier", "creator").first()
    if not b:
        raise HTTPException(status_code=404, detail="入库单不存在")
    items = await PurchaseReceiptItem.filter(receipt_bill_id=b.id).all()
    bill_dict = {
        "bill_no": b.bill_no, "bill_date": str(b.bill_date),
        "supplier_name": b.supplier.name if b.supplier else "",
        "total_amount": b.total_amount,
        "total_amount_without_tax": b.total_amount_without_tax,
        "total_tax": b.total_tax,
        "voucher_no": b.voucher_no or "",
        "creator_name": b.creator.username if b.creator else "",
    }
    item_list = [{"product_name": it.product_name, "quantity": it.quantity,
                  "tax_inclusive_price": it.tax_inclusive_price,
                  "tax_exclusive_price": it.tax_exclusive_price,
                  "tax_rate": it.tax_rate} for it in items]
    pdf_bytes = generate_delivery_pdf(bill_dict, item_list, "采购入库单")
    import io
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={b.bill_no}.pdf"})


@router.post("/batch-pdf")
async def batch_purchase_receipt_pdf(
    data: dict,
    user: User = Depends(require_permission("accounting_view")),
):
    from app.utils.pdf_print import generate_delivery_pdf, merge_pdfs
    import io
    from fastapi.responses import StreamingResponse
    ids = data.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="请选择入库单")
    pdf_list = []
    for bid in ids:
        b = await PurchaseReceiptBill.filter(id=bid).prefetch_related("supplier", "creator").first()
        if not b:
            continue
        items = await PurchaseReceiptItem.filter(receipt_bill_id=b.id).all()
        bill_dict = {
            "bill_no": b.bill_no, "bill_date": str(b.bill_date),
            "supplier_name": b.supplier.name if b.supplier else "",
            "total_amount": b.total_amount,
            "total_amount_without_tax": b.total_amount_without_tax,
            "total_tax": b.total_tax,
            "voucher_no": b.voucher_no or "",
            "creator_name": b.creator.username if b.creator else "",
        }
        item_list = [{"product_name": it.product_name, "quantity": it.quantity,
                      "tax_inclusive_price": it.tax_inclusive_price,
                      "tax_exclusive_price": it.tax_exclusive_price,
                      "tax_rate": it.tax_rate} for it in items]
        pdf_list.append(generate_delivery_pdf(bill_dict, item_list, "采购入库单"))
    if not pdf_list:
        raise HTTPException(status_code=404, detail="未找到入库单")
    merged = merge_pdfs(pdf_list)
    return StreamingResponse(
        io.BytesIO(merged), media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=receipt_batch.pdf"})
