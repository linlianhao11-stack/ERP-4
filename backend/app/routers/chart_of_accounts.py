"""会计科目管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from tortoise import transactions
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.models.accounting import AccountSet, ChartOfAccount
from app.models.voucher import VoucherEntry
from app.schemas.accounting import ChartOfAccountCreate, ChartOfAccountUpdate
from app.utils.response import paginated_response

router = APIRouter(prefix="/api/chart-of-accounts", tags=["会计科目"])


@router.get("")
async def list_accounts(
    account_set_id: int = Query(...),
    user: User = Depends(get_current_user)
):
    accounts = await ChartOfAccount.filter(
        account_set_id=account_set_id, is_active=True
    ).order_by("code")
    return paginated_response([{
        "id": a.id, "code": a.code, "name": a.name,
        "parent_code": a.parent_code, "level": a.level,
        "category": a.category, "direction": a.direction,
        "is_leaf": a.is_leaf, "aux_customer": a.aux_customer,
        "aux_supplier": a.aux_supplier,
        "aux_employee": a.aux_employee,
        "aux_department": a.aux_department,
        "aux_product": a.aux_product,
        "aux_bank": a.aux_bank,
    } for a in accounts])


@router.post("")
async def create_account(
    account_set_id: int = Query(...),
    data: ChartOfAccountCreate = ...,
    user: User = Depends(require_permission("accounting_edit"))
):
    if not await AccountSet.filter(id=account_set_id).exists():
        raise HTTPException(status_code=404, detail="账套不存在")
    if await ChartOfAccount.filter(account_set_id=account_set_id, code=data.code).exists():
        raise HTTPException(status_code=400, detail="科目编码已存在")

    level = 1
    if data.parent_code:
        parent = await ChartOfAccount.filter(
            account_set_id=account_set_id, code=data.parent_code
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="上级科目不存在")
        level = parent.level + 1
        if not data.code.startswith(data.parent_code):
            raise HTTPException(status_code=400, detail="子科目编码必须以上级科目编码开头")

    async with transactions.in_transaction():
        account = await ChartOfAccount.create(
            account_set_id=account_set_id,
            code=data.code, name=data.name,
            parent_code=data.parent_code, level=level,
            category=data.category, direction=data.direction,
            is_leaf=data.is_leaf,
            aux_customer=data.aux_customer, aux_supplier=data.aux_supplier,
            aux_employee=data.aux_employee, aux_department=data.aux_department,
            aux_product=data.aux_product, aux_bank=data.aux_bank,
        )
        if data.parent_code:
            await ChartOfAccount.filter(
                account_set_id=account_set_id, code=data.parent_code
            ).update(is_leaf=False)

    return {"id": account.id, "message": "创建成功"}


@router.put("/{account_id}")
async def update_account(
    account_id: int,
    data: ChartOfAccountUpdate,
    user: User = Depends(require_permission("accounting_edit"))
):
    account = await ChartOfAccount.filter(id=account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="科目不存在")
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if update_data:
        await ChartOfAccount.filter(id=account_id).update(**update_data)
    return {"message": "更新成功"}


@router.delete("/{account_id}")
async def deactivate_account(
    account_id: int,
    user: User = Depends(require_permission("accounting_edit"))
):
    account = await ChartOfAccount.filter(id=account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="科目不存在")
    children = await ChartOfAccount.filter(
        account_set_id=account.account_set_id, parent_code=account.code, is_active=True
    ).count()
    if children > 0:
        raise HTTPException(status_code=400, detail="该科目有活跃子科目，无法停用")
    has_entries = await VoucherEntry.filter(account_id=account_id).exists()
    if has_entries:
        raise HTTPException(status_code=400, detail="该科目已被凭证引用，无法停用")
    account.is_active = False
    await account.save()
    return {"message": "已停用"}
