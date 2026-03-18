"""账簿查询 API"""
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.auth.dependencies import require_permission
from app.models import User
from app.services.ledger_service import (
    get_general_ledger, get_detail_ledger, get_trial_balance,
)
from app.services.ledger_export import (
    export_general_ledger_excel, export_detail_ledger_excel,
    export_trial_balance_excel,
)
from app.services.operation_log_service import log_operation
from app.logger import get_logger

logger = get_logger("ledgers")

router = APIRouter(prefix="/api/ledgers", tags=["账簿查询"])

_EXCEL_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/general-ledger")
async def general_ledger_api(
    account_set_id: int = Query(...),
    account_id: int = Query(...),
    start_period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    end_period: str = Query(None, pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(require_permission("accounting_view")),
):
    result = await get_general_ledger(
        account_set_id, account_id, start_period, end_period or start_period
    )
    if not result:
        raise HTTPException(status_code=404, detail="科目不存在")
    return result


@router.get("/detail-ledger")
async def detail_ledger_api(
    account_set_id: int = Query(...),
    account_id: int = Query(...),
    start_period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    end_period: str = Query(None, pattern=r"^\d{4}-\d{2}$"),
    customer_id: int = Query(None),
    supplier_id: int = Query(None),
    user: User = Depends(require_permission("accounting_view")),
):
    result = await get_detail_ledger(
        account_set_id, account_id, start_period, end_period or start_period,
        customer_id=customer_id, supplier_id=supplier_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="科目不存在")
    return result


@router.get("/trial-balance")
async def trial_balance_api(
    account_set_id: int = Query(...),
    period_name: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(require_permission("accounting_view")),
):
    return await get_trial_balance(account_set_id, period_name)


@router.get("/general-ledger/export")
async def export_general_ledger_api(
    account_set_id: int = Query(...),
    account_id: int = Query(...),
    start_period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    end_period: str = Query(None, pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(require_permission("accounting_view")),
):
    result = await get_general_ledger(
        account_set_id, account_id, start_period, end_period or start_period
    )
    if not result:
        raise HTTPException(status_code=404, detail="科目不存在")
    output = export_general_ledger_excel(result)
    fname = f"总分类账_{result['account_code']}_{start_period}.xlsx"
    await log_operation(user, "LEDGER_EXPORT", "LEDGER", None, f"导出总分类账 {result['account_code']} {start_period}")
    return StreamingResponse(
        output, media_type=_EXCEL_MEDIA,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"},
    )


@router.get("/detail-ledger/export")
async def export_detail_ledger_api(
    account_set_id: int = Query(...),
    account_id: int = Query(...),
    start_period: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    end_period: str = Query(None, pattern=r"^\d{4}-\d{2}$"),
    customer_id: int = Query(None),
    supplier_id: int = Query(None),
    user: User = Depends(require_permission("accounting_view")),
):
    result = await get_detail_ledger(
        account_set_id, account_id, start_period, end_period or start_period,
        customer_id=customer_id, supplier_id=supplier_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="科目不存在")
    output = export_detail_ledger_excel(result)
    fname = f"明细分类账_{result['account_code']}_{start_period}.xlsx"
    await log_operation(user, "LEDGER_EXPORT", "LEDGER", None, f"导出明细分类账 {result['account_code']} {start_period}")
    return StreamingResponse(
        output, media_type=_EXCEL_MEDIA,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"},
    )


@router.get("/trial-balance/export")
async def export_trial_balance_api(
    account_set_id: int = Query(...),
    period_name: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(require_permission("accounting_view")),
):
    result = await get_trial_balance(account_set_id, period_name)
    output = export_trial_balance_excel(result)
    fname = f"科目余额表_{period_name}.xlsx"
    await log_operation(user, "LEDGER_EXPORT", "LEDGER", None, f"导出科目余额表 {period_name}")
    return StreamingResponse(
        output, media_type=_EXCEL_MEDIA,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fname)}"},
    )
