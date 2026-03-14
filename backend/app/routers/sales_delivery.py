"""销售出库单 API"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from tortoise.expressions import Q
from app.auth.dependencies import require_permission
from app.models import User
from app.models.delivery import SalesDeliveryBill, SalesDeliveryItem

router = APIRouter(prefix="/api/sales-delivery", tags=["销售出库单"])


@router.get("")
async def list_sales_deliveries(
    account_set_id: int = Query(...),
    customer_id: int = Query(None),
    order_id: int = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_view")),
):
    query = SalesDeliveryBill.filter(account_set_id=account_set_id)
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if order_id:
        query = query.filter(order_id=order_id)
    if start_date:
        query = query.filter(bill_date__gte=start_date)
    if end_date:
        query = query.filter(bill_date__lte=end_date)
    if search:
        query = query.filter(
            Q(bill_no__icontains=search) | Q(customer__name__icontains=search)
        )

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
            "warehouse_id": b.warehouse_id,
            "bill_date": str(b.bill_date),
            "total_cost": str(b.total_cost),
            "total_amount": str(b.total_amount),
            "status": b.status,
            "voucher_no": b.voucher_no,
            "remark": b.remark,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{bill_id}")
async def get_sales_delivery(
    bill_id: int,
    account_set_id: int = Query(None),
    user: User = Depends(require_permission("accounting_view")),
):
    q = {"id": bill_id}
    if account_set_id:
        q["account_set_id"] = account_set_id
    b = await SalesDeliveryBill.filter(**q).prefetch_related("customer", "order").first()
    if not b:
        raise HTTPException(status_code=404, detail="出库单不存在")
    return {
        "id": b.id, "bill_no": b.bill_no,
        "customer_id": b.customer_id,
        "customer_name": b.customer.name if b.customer else None,
        "order_id": b.order_id,
        "warehouse_id": b.warehouse_id,
        "bill_date": str(b.bill_date),
        "total_cost": str(b.total_cost),
        "total_amount": str(b.total_amount),
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
                "cost_price": str(it.cost_price),
                "sale_price": str(it.sale_price),
            }
            for it in await SalesDeliveryItem.filter(delivery_bill_id=b.id).all()
        ],
    }


@router.get("/{bill_id}/pdf")
async def get_sales_delivery_pdf(
    bill_id: int,
    user: User = Depends(require_permission("accounting_view")),
):
    from app.utils.pdf_print import generate_delivery_pdf
    b = await SalesDeliveryBill.filter(id=bill_id).prefetch_related("customer", "creator").first()
    if not b:
        raise HTTPException(status_code=404, detail="出库单不存在")
    items = await SalesDeliveryItem.filter(delivery_bill_id=b.id).all()
    bill_dict = {
        "bill_no": b.bill_no, "bill_date": str(b.bill_date),
        "customer_name": b.customer.name if b.customer else "",
        "total_cost": b.total_cost, "total_amount": b.total_amount,
        "voucher_no": b.voucher_no or "",
        "creator_name": b.creator.username if b.creator else "",
    }
    item_list = [{"product_name": it.product_name, "quantity": it.quantity,
                  "cost_price": it.cost_price, "sale_price": it.sale_price} for it in items]
    pdf_bytes = generate_delivery_pdf(bill_dict, item_list, "销售出库单")
    import io
    from urllib.parse import quote
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(b.bill_no + '.pdf')}"})


@router.post("/batch-pdf")
async def batch_sales_delivery_pdf(
    data: dict,
    user: User = Depends(require_permission("accounting_view")),
):
    from app.utils.pdf_print import generate_delivery_pdf, merge_pdfs
    import io
    from fastapi.responses import StreamingResponse
    ids = data.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail="请选择出库单")
    pdf_list = []
    for bid in ids:
        b = await SalesDeliveryBill.filter(id=bid).prefetch_related("customer", "creator").first()
        if not b:
            continue
        items = await SalesDeliveryItem.filter(delivery_bill_id=b.id).all()
        bill_dict = {
            "bill_no": b.bill_no, "bill_date": str(b.bill_date),
            "customer_name": b.customer.name if b.customer else "",
            "total_cost": b.total_cost, "total_amount": b.total_amount,
            "voucher_no": b.voucher_no or "",
            "creator_name": b.creator.username if b.creator else "",
        }
        item_list = [{"product_name": it.product_name, "quantity": it.quantity,
                      "cost_price": it.cost_price, "sale_price": it.sale_price} for it in items]
        pdf_list.append(generate_delivery_pdf(bill_dict, item_list, "销售出库单"))
    if not pdf_list:
        raise HTTPException(status_code=404, detail="未找到出库单")
    merged = merge_pdfs(pdf_list)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        io.BytesIO(merged), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=delivery_batch_{ts}.pdf"})
