"""返利管理路由"""
from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from tortoise.expressions import F

from app.auth.dependencies import require_permission
from app.models import User, Customer, Supplier, RebateLog
from app.models.supplier_balance import SupplierAccountBalance
from app.models.customer_balance import CustomerAccountBalance
from app.schemas.rebate import RebateChargeRequest
from app.services.operation_log_service import log_operation
from app.utils.response import paginated_response

router = APIRouter(prefix="/api/rebates", tags=["返利管理"])


@router.get("/summary")
async def get_rebate_summary(target_type: str, account_set_id: int = None, user: User = Depends(require_permission("finance"))):
    """返利汇总"""
    if target_type == "customer":
        if not account_set_id:
            raise HTTPException(status_code=400, detail="客户返利需要指定账套")
        balances = await CustomerAccountBalance.filter(
            account_set_id=account_set_id
        ).all()
        balance_map = {b.customer_id: b for b in balances}
        customers = await Customer.filter(is_active=True).order_by("name")
        return paginated_response([{
            "id": c.id, "name": c.name,
            "rebate_balance": float(balance_map[c.id].rebate_balance) if c.id in balance_map else 0,
        } for c in customers])
    elif target_type == "supplier":
        if not account_set_id:
            raise HTTPException(status_code=400, detail="供应商返利需要指定账套")
        balances = await SupplierAccountBalance.filter(
            account_set_id=account_set_id
        ).all()
        balance_map = {b.supplier_id: b for b in balances}
        suppliers = await Supplier.filter(is_active=True).order_by("-created_at")
        return paginated_response([{
            "id": s.id, "name": s.name,
            "rebate_balance": float(balance_map[s.id].rebate_balance) if s.id in balance_map else 0,
            "credit_balance": float(balance_map[s.id].credit_balance) if s.id in balance_map else 0,
        } for s in suppliers])
    else:
        raise HTTPException(status_code=400, detail="target_type 必须是 customer 或 supplier")


@router.get("/logs")
async def get_rebate_logs(target_type: str, target_id: int, account_set_id: int = None, user: User = Depends(require_permission("finance"))):
    """返利流水明细"""
    query = RebateLog.filter(target_type=target_type, target_id=target_id)
    if account_set_id:
        query = query.filter(account_set_id=account_set_id)
    logs = await query.order_by("-created_at").select_related("creator")
    return paginated_response([{
        "id": l.id, "type": l.type, "amount": float(l.amount),
        "balance_after": float(l.balance_after),
        "reference_type": l.reference_type, "reference_id": l.reference_id,
        "remark": l.remark,
        "creator_name": l.creator.display_name if l.creator else None,
        "created_at": l.created_at.isoformat()
    } for l in logs])


@router.post("/charge")
async def charge_rebate(data: RebateChargeRequest, user: User = Depends(require_permission("finance_rebate"))):
    """返利充值"""
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="充值金额必须大于0")
    async with transactions.in_transaction():
        if data.target_type == "customer":
            if not data.account_set_id:
                raise HTTPException(status_code=400, detail="客户返利充值需要指定账套")
            target = await Customer.filter(id=data.target_id, is_active=True).first()
            if not target:
                raise HTTPException(status_code=404, detail="客户不存在")
            target_name = target.name
            bal = await CustomerAccountBalance.filter(
                customer_id=data.target_id, account_set_id=data.account_set_id
            ).first()
            if not bal:
                bal = await CustomerAccountBalance.create(
                    customer_id=data.target_id, account_set_id=data.account_set_id,
                    rebate_balance=0
                )
            await CustomerAccountBalance.filter(id=bal.id).update(
                rebate_balance=F('rebate_balance') + data.amount
            )
            await bal.refresh_from_db()
            balance_after = bal.rebate_balance
            account_set_id = data.account_set_id
        elif data.target_type == "supplier":
            if not data.account_set_id:
                raise HTTPException(status_code=400, detail="供应商返利充值需要指定账套")
            target = await Supplier.filter(id=data.target_id, is_active=True).first()
            if not target:
                raise HTTPException(status_code=404, detail="供应商不存在")
            target_name = target.name
            bal = await SupplierAccountBalance.filter(
                supplier_id=data.target_id, account_set_id=data.account_set_id
            ).first()
            if not bal:
                bal = await SupplierAccountBalance.create(
                    supplier_id=data.target_id, account_set_id=data.account_set_id,
                    rebate_balance=0, credit_balance=0
                )
            await SupplierAccountBalance.filter(id=bal.id).update(
                rebate_balance=F('rebate_balance') + data.amount
            )
            await bal.refresh_from_db()
            balance_after = bal.rebate_balance
            account_set_id = data.account_set_id
        else:
            raise HTTPException(status_code=400, detail="target_type 必须是 customer 或 supplier")

        await RebateLog.create(
            target_type=data.target_type, target_id=data.target_id,
            type="charge", amount=data.amount,
            balance_after=balance_after,
            account_set_id=account_set_id,
            remark=data.remark, creator=user
        )
        await log_operation(user, "REBATE_CHARGE", data.target_type.upper(), data.target_id,
            f"返利充值 {target_name} ¥{float(data.amount):.2f}，余额 ¥{float(balance_after):.2f}")
    return {"message": "充值成功", "balance": float(balance_after)}
