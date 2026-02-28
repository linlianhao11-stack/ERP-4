"""销售出库单 API"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
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
    user: User = Depends(require_permission("accounting_view")),
):
    b = await SalesDeliveryBill.filter(id=bill_id).prefetch_related("customer", "order").first()
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
async def download_sales_delivery_pdf(
    bill_id: int,
    user: User = Depends(require_permission("accounting_view")),
):
    raise HTTPException(status_code=404, detail="PDF 功能尚未实现")


@router.post("/batch-pdf")
async def batch_sales_delivery_pdf(
    user: User = Depends(require_permission("accounting_view")),
):
    raise HTTPException(status_code=404, detail="批量 PDF 功能尚未实现")
