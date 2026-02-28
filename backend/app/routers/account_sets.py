"""账套管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from tortoise import transactions
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.schemas.accounting import AccountSetCreate, AccountSetUpdate
from app.services.accounting_init import init_chart_of_accounts, init_accounting_periods
from app.logger import get_logger

logger = get_logger("account_sets")

router = APIRouter(prefix="/api/account-sets", tags=["账套管理"])


@router.get("")
async def list_account_sets(user: User = Depends(get_current_user)):
    sets = await AccountSet.filter(is_active=True).order_by("id")
    return [{
        "id": s.id, "code": s.code, "name": s.name,
        "company_name": s.company_name, "tax_id": s.tax_id,
        "current_period": s.current_period, "is_active": s.is_active,
    } for s in sets]


@router.get("/{set_id}")
async def get_account_set(set_id: int, user: User = Depends(get_current_user)):
    s = await AccountSet.filter(id=set_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="账套不存在")
    return {
        "id": s.id, "code": s.code, "name": s.name,
        "company_name": s.company_name, "tax_id": s.tax_id,
        "legal_person": s.legal_person, "address": s.address,
        "bank_name": s.bank_name, "bank_account": s.bank_account,
        "start_year": s.start_year, "start_month": s.start_month,
        "current_period": s.current_period, "is_active": s.is_active,
    }


@router.post("")
async def create_account_set(data: AccountSetCreate, user: User = Depends(require_permission("admin"))):
    if await AccountSet.filter(code=data.code).exists():
        raise HTTPException(status_code=400, detail="账套编码已存在")
    current_period = f"{data.start_year}-{data.start_month:02d}"
    async with transactions.in_transaction():
        s = await AccountSet.create(
            code=data.code, name=data.name, company_name=data.company_name,
            tax_id=data.tax_id, legal_person=data.legal_person,
            address=data.address, bank_name=data.bank_name,
            bank_account=data.bank_account,
            start_year=data.start_year, start_month=data.start_month,
            current_period=current_period,
        )
        coa_count = await init_chart_of_accounts(s.id)
        period_count = await init_accounting_periods(s.id, data.start_year, data.start_month)
    logger.info(f"创建账套: {s.code} ({s.name}), 科目 {coa_count} 个, 期间 {period_count} 个")
    return {"id": s.id, "message": f"创建成功，已初始化 {coa_count} 个科目和 {period_count} 个会计期间"}


@router.put("/{set_id}")
async def update_account_set(set_id: int, data: AccountSetUpdate, user: User = Depends(require_permission("admin"))):
    s = await AccountSet.filter(id=set_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="账套不存在")
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if update_data:
        await AccountSet.filter(id=set_id).update(**update_data)
    return {"message": "更新成功"}
