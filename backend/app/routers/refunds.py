"""退款确认路由 — 销售退款 & 采购退款"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions

from app.auth.dependencies import require_permission
from app.logger import get_logger
from app.models import User
from app.models.order import Order
from app.models.purchase import PurchaseReturn
from app.models.ar_ap import (
    ReceivableBill, ReceiptBill, ReceiptRefundBill,
    PayableBill, DisbursementRefundBill,
)
from app.services.operation_log_service import log_operation
from app.utils.generators import generate_order_no

logger = get_logger(__name__)

router = APIRouter(prefix="/api/finance/refunds", tags=["退款管理"])


# ---------------------------------------------------------------------------
# 业务逻辑函数（独立于 FastAPI，方便测试直接调用）
# ---------------------------------------------------------------------------

async def _confirm_sales_refund(order_id: int, user: User) -> dict:
    """确认销售退款：创建收款退款单，更新应收单，标记订单结清"""
    async with transactions.in_transaction():
        # 1. 查找并验证退货订单
        order = await Order.filter(
            id=order_id, order_type="RETURN", refunded=True, is_cleared=False,
        ).select_for_update().first()
        if not order:
            raise HTTPException(400, "退货订单不存在或已结清")

        # 2. 查找关联的红字 ReceivableBill
        ar_bill = await ReceivableBill.filter(order_id=order.id).order_by("-id").first()

        # 3. 查找原销售订单的 ReceiptBill（作为 original_receipt）
        original_receipt = None
        if order.related_order_id:
            original_receipt = await ReceiptBill.filter(
                receivable_bill__order_id=order.related_order_id,
            ).first()

        # 4. 创建 ReceiptRefundBill（直接 confirmed 状态）
        refund_bill = await ReceiptRefundBill.create(
            bill_no=generate_order_no("SKTK"),
            account_set_id=order.account_set_id,
            customer_id=order.customer_id,
            original_receipt=original_receipt,  # 可能为 null
            return_order=order,
            refund_date=date.today(),
            amount=abs(order.total_amount),
            reason=f"销售退货退款 | 退货单：{order.order_no}",
            refund_info=order.refund_info or "",
            status="confirmed",
            confirmed_by=user,
            confirmed_at=datetime.now(timezone.utc),
            remark=f"退款方式：{order.refund_method or '未指定'}",
            creator=user,
        )

        # 5. 更新红字 ReceivableBill 的 received_amount
        if ar_bill:
            ar_bill.received_amount -= abs(order.total_amount)  # 红字应收减少
            ar_bill.unreceived_amount = ar_bill.total_amount - ar_bill.received_amount
            if abs(ar_bill.unreceived_amount) < 0.01:
                ar_bill.status = "completed"
            await ar_bill.save()

        # 6. 标记退货订单已结清
        order.is_cleared = True
        order.paid_amount = abs(order.total_amount)
        await order.save()

        # 7. 操作日志
        await log_operation(
            user, "REFUND_CONFIRM", "ORDER", order.id,
            f"确认销售退款 | 退货单：{order.order_no}，金额 \u00a5{float(abs(order.total_amount)):.2f}",
        )

    return {"message": "退款确认成功", "refund_bill_no": refund_bill.bill_no}


async def _confirm_purchase_refund(return_id: int, user: User) -> dict:
    """确认采购退款：创建付款退款单，更新应付单，标记退货完成"""
    async with transactions.in_transaction():
        # 1. 查找并验证采购退货单
        pr = await PurchaseReturn.filter(
            id=return_id, is_refunded=True, refund_status="pending",
        ).select_for_update().first()
        if not pr:
            raise HTTPException(400, "采购退货单不存在或已确认退款")

        # 2. 查找关联的红字 PayableBill
        ap_bill = await PayableBill.filter(
            purchase_order_id=pr.purchase_order_id,
        ).order_by("-id").first()

        # 3. 创建 DisbursementRefundBill（直接 confirmed 状态）
        refund_bill = await DisbursementRefundBill.create(
            bill_no=generate_order_no("FKTK"),
            account_set_id=pr.account_set_id,
            supplier_id=pr.supplier_id,
            original_disbursement=None,  # 退货退款没有原付款单
            purchase_return=pr,
            refund_date=date.today(),
            amount=pr.total_amount,
            reason=f"采购退货退款 | 退货单：{pr.return_no}",
            refund_info=pr.refund_info or "",
            status="confirmed",
            confirmed_by=user,
            confirmed_at=datetime.now(timezone.utc),
            remark=f"退款方式：{pr.refund_method or '未指定'}",
            creator=user,
        )

        # 4. 更新红字 PayableBill 的 paid_amount
        if ap_bill and ap_bill.total_amount < 0:
            ap_bill.paid_amount -= pr.total_amount
            ap_bill.unpaid_amount = ap_bill.total_amount - ap_bill.paid_amount
            if abs(ap_bill.unpaid_amount) < 0.01:
                ap_bill.status = "completed"
            await ap_bill.save()

        # 5. 标记退货单退款完成
        pr.refund_status = "completed"
        await pr.save()

        # 6. 操作日志
        await log_operation(
            user, "REFUND_CONFIRM", "PURCHASE_RETURN", pr.id,
            f"确认采购退款 | 退货单：{pr.return_no}，金额 \u00a5{float(pr.total_amount):.2f}",
        )

    return {"message": "退款确认成功", "refund_bill_no": refund_bill.bill_no}


# ---------------------------------------------------------------------------
# HTTP 端点
# ---------------------------------------------------------------------------

@router.get("")
async def list_pending_refunds(user: User = Depends(require_permission("finance"))):
    """待退款列表（销售 + 采购合并，按创建时间降序）"""
    items: list[dict] = []

    # --- 销售退款 ---
    sales_returns = await Order.filter(
        order_type="RETURN", refunded=True, is_cleared=False,
    ).select_related("customer", "related_order").order_by("-created_at")
    for o in sales_returns:
        items.append({
            "id": o.id,
            "type": "sales",
            "order_no": o.order_no,
            "customer_name": o.customer.name if o.customer else None,
            "amount": float(abs(o.total_amount)),
            "refund_method": o.refund_method,
            "refund_info": o.refund_info,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "related_order_no": o.related_order.order_no if o.related_order else None,
        })

    # --- 采购退款 ---
    purchase_returns = await PurchaseReturn.filter(
        is_refunded=True, refund_status="pending",
    ).select_related("supplier", "purchase_order").order_by("-created_at")
    for pr in purchase_returns:
        items.append({
            "id": pr.id,
            "type": "purchase",
            "return_no": pr.return_no,
            "supplier_name": pr.supplier.name if pr.supplier else None,
            "amount": float(pr.total_amount),
            "refund_method": pr.refund_method,
            "refund_info": pr.refund_info,
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
            "po_no": pr.purchase_order.po_no if pr.purchase_order else None,
        })

    # 合并后按 created_at 降序
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return {"items": items, "total": len(items)}


@router.post("/confirm-sales/{order_id}")
async def confirm_sales_refund(
    order_id: int,
    user: User = Depends(require_permission("finance_confirm")),
):
    """确认销售退款"""
    return await _confirm_sales_refund(order_id, user)


@router.post("/confirm-purchase/{return_id}")
async def confirm_purchase_refund(
    return_id: int,
    user: User = Depends(require_permission("finance_confirm")),
):
    """确认采购退款"""
    return await _confirm_purchase_refund(return_id, user)
