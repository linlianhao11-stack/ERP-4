"""返利管理路由"""
from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from tortoise.expressions import F

from app.auth.dependencies import require_permission
from app.models import User, Customer, Supplier, RebateLog
from app.schemas.rebate import RebateChargeRequest
from app.services.operation_log_service import log_operation

router = APIRouter(prefix="/api/rebates", tags=["返利管理"])


@router.get("/summary")
async def get_rebate_summary(target_type: str, user: User = Depends(require_permission("finance"))):
    """返利汇总"""
    if target_type == "customer":
        items = await Customer.filter(is_active=True).order_by("name")
        return [{"id": c.id, "name": c.name, "rebate_balance": float(c.rebate_balance)} for c in items]
    elif target_type == "supplier":
        items = await Supplier.filter(is_active=True).order_by("-created_at")
        return [{"id": s.id, "name": s.name, "rebate_balance": float(s.rebate_balance)} for s in items]
    else:
        raise HTTPException(status_code=400, detail="target_type 必须是 customer 或 supplier")


@router.get("/logs")
async def get_rebate_logs(target_type: str, target_id: int, user: User = Depends(require_permission("finance"))):
    """返利流水明细"""
    logs = await RebateLog.filter(target_type=target_type, target_id=target_id).order_by("-created_at").select_related("creator")
    return [{
        "id": l.id, "type": l.type, "amount": float(l.amount),
        "balance_after": float(l.balance_after),
        "reference_type": l.reference_type, "reference_id": l.reference_id,
        "remark": l.remark,
        "creator_name": l.creator.display_name if l.creator else None,
        "created_at": l.created_at.isoformat()
    } for l in logs]


@router.post("/charge")
async def charge_rebate(data: RebateChargeRequest, user: User = Depends(require_permission("finance"))):
    """返利充值"""
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="充值金额必须大于0")
    async with transactions.in_transaction():
        if data.target_type == "customer":
            target = await Customer.filter(id=data.target_id, is_active=True).first()
            if not target:
                raise HTTPException(status_code=404, detail="客户不存在")
            await Customer.filter(id=data.target_id).update(rebate_balance=F('rebate_balance') + data.amount)
            await target.refresh_from_db()
            target_name = target.name
        elif data.target_type == "supplier":
            target = await Supplier.filter(id=data.target_id, is_active=True).first()
            if not target:
                raise HTTPException(status_code=404, detail="供应商不存在")
            await Supplier.filter(id=data.target_id).update(rebate_balance=F('rebate_balance') + data.amount)
            await target.refresh_from_db()
            target_name = target.name
        else:
            raise HTTPException(status_code=400, detail="target_type 必须是 customer 或 supplier")

        await RebateLog.create(
            target_type=data.target_type, target_id=data.target_id,
            type="charge", amount=data.amount,
            balance_after=target.rebate_balance,
            remark=data.remark, creator=user
        )
        await log_operation(user, "REBATE_CHARGE", data.target_type.upper(), data.target_id,
            f"返利充值 {target_name} ¥{float(data.amount):.2f}，余额 ¥{float(target.rebate_balance):.2f}")
    return {"message": "充值成功", "balance": float(target.rebate_balance)}
