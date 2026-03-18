"""财务报表路由"""
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
import io
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.services.report_service import get_balance_sheet, get_income_statement, get_cash_flow
from app.services.operation_log_service import log_operation
from app.services.report_export import (
    export_balance_sheet_excel, export_income_statement_excel, export_cash_flow_excel,
    export_balance_sheet_pdf, export_income_statement_pdf, export_cash_flow_pdf,
)

router = APIRouter(prefix="/api/financial-reports", tags=["财务报表"])


@router.get("/balance-sheet")
async def api_balance_sheet(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("accounting_view")),
):
    return await get_balance_sheet(account_set_id, period_name)


@router.get("/income-statement")
async def api_income_statement(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("accounting_view")),
):
    return await get_income_statement(account_set_id, period_name)


@router.get("/cash-flow")
async def api_cash_flow(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    user=Depends(require_permission("accounting_view")),
):
    return await get_cash_flow(account_set_id, period_name)


@router.get("/balance-sheet/export")
async def api_export_balance_sheet(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    format: str = Query("excel", regex="^(excel|pdf)$"),
    user=Depends(require_permission("accounting_view")),
):
    data = await get_balance_sheet(account_set_id, period_name)
    await log_operation(user, "REPORT_EXPORT", "REPORT", None, f"导出资产负债表 {period_name}")
    if format == "pdf":
        pdf_bytes = export_balance_sheet_pdf(data)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=balance_sheet_{period_name}.pdf"},
        )
    else:
        output = export_balance_sheet_excel(data)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=balance_sheet_{period_name}.xlsx"},
        )


@router.get("/income-statement/export")
async def api_export_income_statement(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    format: str = Query("excel", regex="^(excel|pdf)$"),
    user=Depends(require_permission("accounting_view")),
):
    data = await get_income_statement(account_set_id, period_name)
    await log_operation(user, "REPORT_EXPORT", "REPORT", None, f"导出利润表 {period_name}")
    if format == "pdf":
        pdf_bytes = export_income_statement_pdf(data)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=income_statement_{period_name}.pdf"},
        )
    else:
        output = export_income_statement_excel(data)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=income_statement_{period_name}.xlsx"},
        )


@router.get("/cash-flow/export")
async def api_export_cash_flow(
    account_set_id: int = Query(...),
    period_name: str = Query(...),
    format: str = Query("excel", regex="^(excel|pdf)$"),
    user=Depends(require_permission("accounting_view")),
):
    data = await get_cash_flow(account_set_id, period_name)
    await log_operation(user, "REPORT_EXPORT", "REPORT", None, f"导出现金流量表 {period_name}")
    if format == "pdf":
        pdf_bytes = export_cash_flow_pdf(data)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=cash_flow_{period_name}.pdf"},
        )
    else:
        output = export_cash_flow_excel(data)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=cash_flow_{period_name}.xlsx"},
        )
