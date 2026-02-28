"""期末处理路由"""
from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth.dependencies import get_current_user, require_permission
from app.services.period_end_service import (
    preview_carry_forward, execute_carry_forward,
    close_check, close_period, reopen_period, year_close,
)

router = APIRouter(prefix="/api/period-end", tags=["期末处理"])


@router.post("/carry-forward/preview")
async def api_carry_forward_preview(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("period_end")),
):
    try:
        return await preview_carry_forward(account_set_id, period_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/carry-forward")
async def api_carry_forward(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("period_end")),
):
    try:
        return await execute_carry_forward(account_set_id, period_name, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/close-check")
async def api_close_check(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("period_end")),
):
    return await close_check(account_set_id, period_name)


@router.post("/close")
async def api_close_period(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("period_end")),
):
    try:
        return await close_period(account_set_id, period_name, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reopen")
async def api_reopen_period(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("admin")),
):
    try:
        return await reopen_period(account_set_id, period_name, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/year-close")
async def api_year_close(
    account_set_id: int = Query(...),
    year: int = Query(...),
    user=Depends(require_permission("period_end")),
):
    try:
        return await year_close(account_set_id, year, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
