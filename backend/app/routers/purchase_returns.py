"""采购退货单路由"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import require_permission
from app.models import User
from app.models.purchase import PurchaseReturn, PurchaseReturnItem

router = APIRouter(prefix="/api/purchase-returns", tags=["purchase-returns"])


@router.get("")
async def list_purchase_returns(
    supplier_id: int | None = None,
    purchase_order_id: int | None = None,
    offset: int = 0,
    limit: int = 50,
    user: User = Depends(require_permission("purchase")),
):
    """退货单列表（分页）"""
    q = PurchaseReturn.all()
    if supplier_id:
        q = q.filter(supplier_id=supplier_id)
    if purchase_order_id:
        q = q.filter(purchase_order_id=purchase_order_id)
    total = await q.count()
    items = await q.order_by("-created_at").offset(offset).limit(limit).select_related(
        "purchase_order", "supplier", "created_by"
    )
    result = []
    for pr in items:
        pr_items = await PurchaseReturnItem.filter(purchase_return=pr).select_related("product")
        result.append({
            "id": pr.id,
            "return_no": pr.return_no,
            "purchase_order_id": pr.purchase_order_id,
            "po_no": pr.purchase_order.po_no,
            "supplier_name": pr.supplier.name,
            "total_amount": float(pr.total_amount),
            "is_refunded": pr.is_refunded,
            "refund_status": pr.refund_status,
            "tracking_no": pr.tracking_no,
            "reason": pr.reason,
            "created_by_name": pr.created_by.display_name if pr.created_by else None,
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
            "items": [{
                "id": it.id,
                "product_name": it.product.name,
                "product_sku": it.product.sku,
                "quantity": it.quantity,
                "unit_price": float(it.unit_price),
                "amount": float(it.amount),
            } for it in pr_items],
        })
    return {"items": result, "total": total}


@router.get("/{return_id}")
async def get_purchase_return(return_id: int, user: User = Depends(require_permission("purchase"))):
    """退货单详情"""
    pr = await PurchaseReturn.get_or_none(id=return_id).select_related(
        "purchase_order", "supplier", "created_by"
    )
    if not pr:
        raise HTTPException(status_code=404, detail="退货单不存在")
    pr_items = await PurchaseReturnItem.filter(purchase_return=pr).select_related("product")
    return {
        "id": pr.id,
        "return_no": pr.return_no,
        "purchase_order_id": pr.purchase_order_id,
        "po_no": pr.purchase_order.po_no,
        "supplier_id": pr.supplier_id,
        "supplier_name": pr.supplier.name,
        "total_amount": float(pr.total_amount),
        "is_refunded": pr.is_refunded,
        "refund_status": pr.refund_status,
        "tracking_no": pr.tracking_no,
        "reason": pr.reason,
        "created_by_name": pr.created_by.display_name if pr.created_by else None,
        "created_at": pr.created_at.isoformat() if pr.created_at else None,
        "items": [{
            "id": it.id,
            "product_name": it.product.name,
            "product_sku": it.product.sku,
            "quantity": it.quantity,
            "unit_price": float(it.unit_price),
            "amount": float(it.amount),
        } for it in pr_items],
    }
