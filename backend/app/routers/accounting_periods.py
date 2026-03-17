"""会计期间管理 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.models.accounting import AccountSet, AccountingPeriod
from app.services.accounting_init import init_accounting_periods
from app.utils.response import paginated_response

router = APIRouter(prefix="/api/accounting-periods", tags=["会计期间"])


@router.get("")
async def list_periods(
    account_set_id: int = Query(...),
    year: int = Query(None),
    user: User = Depends(get_current_user)
):
    query = AccountingPeriod.filter(account_set_id=account_set_id)
    if year:
        query = query.filter(year=year)
    periods = await query.order_by("year", "month")
    return paginated_response([{
        "id": p.id, "period_name": p.period_name,
        "year": p.year, "month": p.month,
        "is_closed": p.is_closed, "closed_at": p.closed_at,
    } for p in periods])


@router.post("/init-year")
async def init_year_periods(
    account_set_id: int = Query(...),
    year: int = Query(...),
    user: User = Depends(require_permission("period_end"))
):
    s = await AccountSet.filter(id=account_set_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="账套不存在")
    count = await init_accounting_periods(account_set_id, year, 1)
    return {"message": f"已创建 {count} 个会计期间", "created": count}
