"""供应商路由"""
from decimal import Decimal
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from tortoise.expressions import F

from app.auth.dependencies import require_permission
from app.models import User, Supplier, PurchaseOrder, RebateLog
from app.schemas.supplier import SupplierRequest, CreditRefundRequest
from app.services.operation_log_service import log_operation

router = APIRouter(prefix="/api/suppliers", tags=["供应商管理"])


@router.get("")
async def list_suppliers(user: User = Depends(require_permission("purchase"))):
    suppliers = await Supplier.filter(is_active=True).order_by("-created_at")
    return [{"id": s.id, "name": s.name, "contact_person": s.contact_person, "phone": s.phone,
             "tax_id": s.tax_id, "bank_account": s.bank_account, "bank_name": s.bank_name,
             "address": s.address, "rebate_balance": float(s.rebate_balance),
             "credit_balance": float(s.credit_balance), "created_at": s.created_at.isoformat()} for s in suppliers]


@router.post("")
async def create_supplier(data: SupplierRequest, user: User = Depends(require_permission("purchase"))):
    s = await Supplier.create(**data.model_dump())
    await log_operation(user, "SUPPLIER_CREATE", "SUPPLIER", s.id, f"新增供应商 {data.name}")
    return {"id": s.id, "message": "创建成功"}


@router.put("/{supplier_id}")
async def update_supplier(supplier_id: int, data: SupplierRequest, user: User = Depends(require_permission("purchase"))):
    s = await Supplier.filter(id=supplier_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="供应商不存在")
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await Supplier.filter(id=supplier_id).update(**update_data)
    return {"message": "更新成功"}


@router.delete("/{supplier_id}")
async def delete_supplier(supplier_id: int, user: User = Depends(require_permission("purchase"))):
    s = await Supplier.filter(id=supplier_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="供应商不存在")
    if s.rebate_balance != 0 or s.credit_balance != 0:
        raise HTTPException(status_code=400, detail="供应商有未结清返利或在账资金，无法删除")
    pending_count = await PurchaseOrder.filter(
        supplier_id=supplier_id, status__in=["pending_review", "pending", "paid", "partial"]
    ).count()
    if pending_count > 0:
        raise HTTPException(status_code=400, detail=f"该供应商有 {pending_count} 个未完成的采购单，无法删除")
    s.is_active = False
    await s.save()
    return {"message": "删除成功"}


@router.get("/{supplier_id}/transactions")
async def get_supplier_transactions(
    supplier_id: int,
    month: Optional[str] = None,
    user: User = Depends(require_permission("purchase"))
):
    supplier = await Supplier.filter(id=supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    # 采购记录查询
    po_query = PurchaseOrder.filter(supplier_id=supplier_id)
    if month:
        try:
            year, mon = month.split("-")
            start = datetime(int(year), int(mon), 1)
            if int(mon) == 12:
                end = datetime(int(year) + 1, 1, 1)
            else:
                end = datetime(int(year), int(mon) + 1, 1)
            po_query = po_query.filter(created_at__gte=start, created_at__lt=end)
        except Exception:
            pass

    orders = await po_query.order_by("-created_at").select_related("creator")

    # 统计（使用数据库聚合）
    from tortoise.functions import Count, Sum, Coalesce
    stats_result = await PurchaseOrder.filter(supplier_id=supplier_id).annotate(
        total_count=Count("id"),
        total_amount=Coalesce(Sum("total_amount"), 0),
    ).values("total_count", "total_amount")
    total_count = stats_result[0]["total_count"] if stats_result else 0
    total_amount = float(stats_result[0]["total_amount"]) if stats_result else 0

    completed_result = await PurchaseOrder.filter(supplier_id=supplier_id, status="completed").count()
    completed_count = completed_result

    returned_result = await PurchaseOrder.filter(supplier_id=supplier_id, status="returned").annotate(
        cnt=Count("id"),
        amt=Coalesce(Sum("return_amount"), 0),
    ).values("cnt", "amt")
    returned_count = returned_result[0]["cnt"] if returned_result else 0
    returned_amount = float(returned_result[0]["amt"]) if returned_result else 0

    # 在账资金流水
    credit_logs = await RebateLog.filter(
        target_type="supplier", target_id=supplier_id,
        type__in=["credit_charge", "credit_use", "credit_refund"]
    ).order_by("-created_at").select_related("creator")

    # 使用数据库聚合获取月份列表（避免拉取全量日期数据）
    from tortoise import connections
    conn = connections.get("default")
    month_rows = await conn.execute_query_dict(
        "SELECT DISTINCT TO_CHAR(created_at, 'YYYY-MM') as month FROM purchase_orders WHERE supplier_id = $1 ORDER BY month DESC",
        [supplier_id]
    )
    available_months = [r["month"] for r in month_rows]

    return {
        "supplier": {
            "id": supplier.id, "name": supplier.name,
            "contact_person": supplier.contact_person,
            "phone": supplier.phone,
            "rebate_balance": float(supplier.rebate_balance),
            "credit_balance": float(supplier.credit_balance),
        },
        "stats": {
            "total_count": total_count,
            "total_amount": round(total_amount, 2),
            "completed_count": completed_count,
            "returned_count": returned_count,
            "returned_amount": round(returned_amount, 2),
        },
        "orders": [{
            "id": o.id, "po_no": o.po_no, "status": o.status,
            "total_amount": float(o.total_amount),
            "return_amount": float(o.return_amount) if o.return_amount else 0,
            "creator_name": o.creator.display_name if o.creator else None,
            "created_at": o.created_at.isoformat(),
        } for o in orders],
        "credit_logs": [{
            "id": log.id, "type": log.type,
            "amount": float(log.amount),
            "balance_after": float(log.balance_after),
            "remark": log.remark,
            "creator_name": log.creator.display_name if log.creator else None,
            "created_at": log.created_at.isoformat(),
        } for log in credit_logs],
        "available_months": available_months,
    }


@router.post("/{supplier_id}/credit-refund")
async def refund_supplier_credit(
    supplier_id: int,
    data: CreditRefundRequest,
    user: User = Depends(require_permission("purchase"))
):
    amount = Decimal(str(data.amount))

    async with transactions.in_transaction():
        supplier = await Supplier.filter(id=supplier_id).select_for_update().first()
        if not supplier:
            raise HTTPException(status_code=404, detail="供应商不存在")
        if amount > supplier.credit_balance:
            raise HTTPException(status_code=400, detail=f"退款金额超过在账资金余额（可用: ¥{float(supplier.credit_balance):.2f}）")

        await Supplier.filter(id=supplier_id).update(credit_balance=F('credit_balance') - amount)
        await supplier.refresh_from_db()

        await RebateLog.create(
            target_type="supplier", target_id=supplier_id,
            type="credit_refund", amount=-amount,
            balance_after=supplier.credit_balance,
            remark=data.remark or f"在账资金退款 ¥{float(amount):.2f}",
            creator=user
        )

        await log_operation(user, "CREDIT_REFUND", "SUPPLIER", supplier_id,
            f"供应商 {supplier.name} 在账资金退款 ¥{float(amount):.2f}，余额 ¥{float(supplier.credit_balance):.2f}")

    return {"message": "退款成功", "credit_balance": float(supplier.credit_balance)}
