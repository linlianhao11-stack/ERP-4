from __future__ import annotations

"""凭证管理 API"""
from decimal import Decimal
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from tortoise import transactions
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.models.system_setting import SystemSetting
from app.schemas.accounting import VoucherCreate, VoucherUpdate
from app.logger import get_logger
from app.services.operation_log_service import log_operation
from tortoise.expressions import Q
from io import BytesIO
from starlette.responses import StreamingResponse as _StreamingResponse
import openpyxl


class BatchPdfRequest(BaseModel):
    ids: List[int]


class BatchVoucherRequest(BaseModel):
    voucher_ids: List[int]

logger = get_logger("vouchers")

router = APIRouter(prefix="/api/vouchers", tags=["凭证管理"])


from app.utils.voucher_no import next_voucher_no as _next_voucher_no, extract_sequence_no


@router.get("")
async def list_vouchers(
    account_set_id: int = Query(...),
    period_name: str = Query(None),
    status: str = Query(None),
    voucher_type: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_view"))
):
    query = Voucher.filter(account_set_id=account_set_id)
    if period_name:
        query = query.filter(period_name=period_name)
    if status:
        query = query.filter(status=status)
    if voucher_type:
        query = query.filter(voucher_type=voucher_type)
    if search:
        query = query.filter(
            Q(voucher_no__icontains=search) | Q(summary__icontains=search)
        )

    total = await query.count()
    vouchers = await query.order_by("voucher_no").offset((page - 1) * page_size).limit(page_size)

    result = []
    for v in vouchers:
        result.append({
            "id": v.id, "voucher_type": v.voucher_type,
            "voucher_no": v.voucher_no, "voucher_date": str(v.voucher_date),
            "period_name": v.period_name, "summary": v.summary,
            "total_debit": str(v.total_debit), "total_credit": str(v.total_credit),
            "status": v.status, "attachment_count": v.attachment_count,
            "sequence_no": extract_sequence_no(v.voucher_no),
            "creator_id": v.creator_id,
            "approved_by_id": v.approved_by_id,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        })
    return {"items": result, "total": total, "page": page, "page_size": page_size}


@router.get("/next-number")
async def get_next_voucher_number(
    account_set_id: int = Query(...),
    period: str = Query(...),
    voucher_type: str = Query("记"),
    user: User = Depends(require_permission("accounting_view")),
):
    """预览下一个凭证号（仅供前端显示，非最终分配，不加行锁）"""
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise HTTPException(status_code=404, detail="账套不存在")
    prefix = f"{account_set.code}-{voucher_type}-{period.replace('-', '')}-"
    last = await Voucher.filter(
        voucher_no__startswith=prefix,
    ).order_by("-voucher_no").first()
    seq = (int(last.voucher_no[len(prefix):]) + 1) if last else 1
    voucher_no = f"{prefix}{seq:03d}"
    return {"voucher_no": voucher_no, "sequence_no": seq}


@router.post("/batch-submit")
async def batch_submit_vouchers(
    req: BatchVoucherRequest,
    user: User = Depends(require_permission("accounting_edit")),
):
    success = []
    failed = []
    async with transactions.in_transaction():
        vouchers = await Voucher.filter(id__in=req.voucher_ids).all()
        for v in vouchers:
            if v.status != "draft":
                failed.append({"id": v.id, "reason": f"凭证状态为{v.status}，不是草稿"})
                continue
            v.status = "pending"
            await v.save()
            success.append(v.id)
    await log_operation(user, "VOUCHER_BATCH_SUBMIT", "VOUCHER", None, f"批量提交 {len(success)} 张凭证")
    return {"success": success, "failed": failed}


@router.post("/batch-approve")
async def batch_approve_vouchers(
    req: BatchVoucherRequest,
    user: User = Depends(require_permission("accounting_approve")),
):
    success = []
    failed = []
    async with transactions.in_transaction():
        strict = await SystemSetting.filter(key="voucher_maker_checker").first()
        vouchers = await Voucher.filter(id__in=req.voucher_ids).all()
        for v in vouchers:
            if v.status != "pending":
                failed.append({"id": v.id, "reason": f"凭证状态为{v.status}，不是待审核"})
                continue
            if strict and strict.value == "true" and v.creator_id == user.id:
                failed.append({"id": v.id, "reason": "制单人不能审核自己的凭证"})
                continue
            v.status = "approved"
            v.approved_by = user
            v.approved_at = datetime.now(timezone.utc)
            await v.save()
            success.append(v.id)
    await log_operation(user, "VOUCHER_BATCH_APPROVE", "VOUCHER", None, f"批量审核 {len(success)} 张凭证")
    return {"success": success, "failed": failed}


@router.post("/batch-post")
async def batch_post_vouchers(
    req: BatchVoucherRequest,
    user: User = Depends(require_permission("accounting_post")),
):
    success = []
    failed = []
    async with transactions.in_transaction():
        vouchers = await Voucher.filter(id__in=req.voucher_ids).all()
        for v in vouchers:
            if v.status != "approved":
                failed.append({"id": v.id, "reason": f"凭证状态为{v.status}，不是已审核"})
                continue
            period = await AccountingPeriod.filter(
                account_set_id=v.account_set_id, period_name=v.period_name
            ).first()
            if period and period.is_closed:
                failed.append({"id": v.id, "reason": "该期间已结账"})
                continue
            v.status = "posted"
            v.posted_by = user
            v.posted_at = datetime.now(timezone.utc)
            await v.save()
            success.append(v.id)
    await log_operation(user, "VOUCHER_BATCH_POST", "VOUCHER", None, f"批量过账 {len(success)} 张凭证")
    return {"success": success, "failed": failed}


def _build_aux_info(entry) -> str:
    """从分录对象构建辅助核算字符串"""
    parts = []
    if entry.aux_customer:
        parts.append(f"客户:{entry.aux_customer.name}")
    if entry.aux_supplier:
        parts.append(f"供应商:{entry.aux_supplier.name}")
    if entry.aux_employee:
        parts.append(f"员工:{entry.aux_employee.name}")
    if entry.aux_department:
        parts.append(f"部门:{entry.aux_department.name}")
    if entry.aux_product:
        parts.append(f"商品:{entry.aux_product.name}")
    if entry.aux_bank_account:
        parts.append(f"银行:{entry.aux_bank_account.short_name or entry.aux_bank_account.bank_name}")
    return " | ".join(parts)


@router.get("/entries")
async def list_voucher_entries(
    account_set_id: int = Query(...),
    period_name: str = Query(None),
    voucher_type: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_view")),
):
    query = VoucherEntry.filter(voucher__account_set_id=account_set_id)
    if period_name:
        query = query.filter(voucher__period_name=period_name)
    if voucher_type:
        query = query.filter(voucher__voucher_type=voucher_type)
    if status:
        query = query.filter(voucher__status=status)
    if search:
        query = query.filter(
            Q(summary__icontains=search) | Q(account__name__icontains=search) | Q(account__code__icontains=search)
        )
    total = await query.count()
    entries = await query.offset((page - 1) * page_size).limit(page_size) \
        .select_related("voucher", "account", "aux_customer", "aux_supplier", "aux_employee", "aux_department", "aux_product", "aux_bank_account") \
        .order_by("voucher__voucher_no", "line_no")

    items = []
    for e in entries:
        v = e.voucher
        aux_info = _build_aux_info(e)
        items.append({
            "id": e.id,
            "voucher_id": v.id,
            "voucher_date": str(v.voucher_date),
            "period_name": v.period_name,
            "voucher_type": v.voucher_type,
            "voucher_no": v.voucher_no,
            "sequence_no": extract_sequence_no(v.voucher_no),
            "entry_summary": e.summary,
            "account_code": e.account.code,
            "account_name": e.account.name,
            "aux_info": aux_info,
            "debit_amount": str(e.debit_amount),
            "credit_amount": str(e.credit_amount),
            "status": v.status,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/entries/export")
async def export_voucher_entries(
    account_set_id: int = Query(...),
    period_name: str = Query(None),
    voucher_type: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    user: User = Depends(require_permission("accounting_view")),
):
    query = VoucherEntry.filter(voucher__account_set_id=account_set_id)
    if period_name:
        query = query.filter(voucher__period_name=period_name)
    if voucher_type:
        query = query.filter(voucher__voucher_type=voucher_type)
    if status:
        query = query.filter(voucher__status=status)
    if search:
        query = query.filter(
            Q(summary__icontains=search) | Q(account__name__icontains=search) | Q(account__code__icontains=search)
        )
    entries = await query.limit(10000) \
        .select_related("voucher", "account", "aux_customer", "aux_supplier", "aux_employee", "aux_department", "aux_product", "aux_bank_account") \
        .order_by("voucher__voucher_no", "line_no")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "凭证分录"
    headers = ["日期", "期间", "凭证字", "凭证号", "摘要", "科目编码", "科目名称", "核算维度", "借方金额", "贷方金额", "状态"]
    ws.append(headers)
    for e in entries:
        v = e.voucher
        aux_info = _build_aux_info(e)
        ws.append([
            str(v.voucher_date), v.period_name, v.voucher_type,
            extract_sequence_no(v.voucher_no),
            e.summary, e.account.code, e.account.name,
            aux_info,
            float(e.debit_amount), float(e.credit_amount),
            v.status,
        ])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    await log_operation(user, "VOUCHER_EXPORT", "VOUCHER", None, "导出凭证分录 Excel")
    return _StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=voucher_entries.xlsx"},
    )


@router.get("/{voucher_id}")
async def get_voucher(
    voucher_id: int,
    account_set_id: int = Query(None),
    user: User = Depends(require_permission("accounting_view"))
):
    q = {"id": voucher_id}
    if account_set_id:
        q["account_set_id"] = account_set_id
    v = await Voucher.filter(**q).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    entries = await VoucherEntry.filter(voucher=v).order_by("line_no").prefetch_related(
        "account", "aux_customer", "aux_supplier", "aux_employee", "aux_department", "aux_product", "aux_bank_account"
    )
    return {
        "id": v.id, "voucher_type": v.voucher_type,
        "voucher_no": v.voucher_no, "voucher_date": str(v.voucher_date),
        "period_name": v.period_name, "summary": v.summary,
        "total_debit": str(v.total_debit), "total_credit": str(v.total_credit),
        "status": v.status, "attachment_count": v.attachment_count,
        "creator_id": v.creator_id,
        "approved_by_id": v.approved_by_id, "approved_at": v.approved_at,
        "posted_by_id": v.posted_by_id, "posted_at": v.posted_at,
        "sequence_no": extract_sequence_no(v.voucher_no),
        "entries": [{
            "id": e.id, "line_no": e.line_no,
            "account_id": e.account_id,
            "account_code": e.account.code,
            "account_name": e.account.name,
            "summary": e.summary,
            "debit_amount": str(e.debit_amount),
            "credit_amount": str(e.credit_amount),
            "aux_customer_id": e.aux_customer_id,
            "aux_supplier_id": e.aux_supplier_id,
            "aux_employee_id": e.aux_employee_id,
            "aux_department_id": e.aux_department_id,
            "aux_product_id": e.aux_product_id,
            "aux_bank_account_id": e.aux_bank_account_id,
            "aux_customer_name": e.aux_customer.name if e.aux_customer else None,
            "aux_supplier_name": e.aux_supplier.name if e.aux_supplier else None,
            "aux_employee_name": e.aux_employee.name if e.aux_employee else None,
            "aux_department_name": e.aux_department.name if e.aux_department else None,
            "aux_product_name": e.aux_product.name if e.aux_product else None,
            "aux_bank_account_name": (e.aux_bank_account.short_name or e.aux_bank_account.bank_name) if e.aux_bank_account else None,
        } for e in entries],
    }


@router.post("")
async def create_voucher(
    account_set_id: int = Query(...),
    data: VoucherCreate = ...,
    user: User = Depends(require_permission("accounting_edit"))
):
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise HTTPException(status_code=404, detail="账套不存在")

    period_name = data.voucher_date.strftime("%Y-%m")
    period = await AccountingPeriod.filter(
        account_set_id=account_set_id, period_name=period_name
    ).first()
    if not period:
        raise HTTPException(status_code=400, detail=f"会计期间 {period_name} 不存在")
    if period.is_closed:
        raise HTTPException(status_code=400, detail=f"会计期间 {period_name} 已结账，不能新增凭证")

    total_debit = sum(e.debit_amount for e in data.entries)
    total_credit = sum(e.credit_amount for e in data.entries)
    if total_debit != total_credit:
        raise HTTPException(status_code=400, detail=f"借贷不平衡：借方 {total_debit}，贷方 {total_credit}")
    if total_debit == 0:
        raise HTTPException(status_code=400, detail="借贷金额不能全部为零")

    for i, entry in enumerate(data.entries):
        if entry.debit_amount == 0 and entry.credit_amount == 0:
            raise HTTPException(status_code=400, detail=f"第 {i+1} 行借贷金额不能同时为零")
        if entry.debit_amount > 0 and entry.credit_amount > 0:
            raise HTTPException(status_code=400, detail=f"第 {i+1} 行不能同时填写借方和贷方金额")

    account_ids = [e.account_id for e in data.entries]
    accounts = await ChartOfAccount.filter(
        id__in=account_ids, account_set_id=account_set_id, is_active=True
    )
    valid_ids = {a.id for a in accounts}
    leaf_check = {a.id: a.is_leaf for a in accounts}
    for e in data.entries:
        if e.account_id not in valid_ids:
            raise HTTPException(status_code=400, detail=f"科目 ID {e.account_id} 不存在或不属于当前账套")
        if not leaf_check.get(e.account_id, False):
            raise HTTPException(status_code=400, detail=f"科目 ID {e.account_id} 不是末级科目，不能录入凭证")

    async with transactions.in_transaction():
        voucher_no = await _next_voucher_no(account_set_id, data.voucher_type, period_name)
        v = await Voucher.create(
            account_set_id=account_set_id,
            voucher_type=data.voucher_type,
            voucher_no=voucher_no,
            period_name=period_name,
            voucher_date=data.voucher_date,
            summary=data.summary,
            total_debit=total_debit,
            total_credit=total_credit,
            status="draft",
            attachment_count=data.attachment_count,
            creator=user,
        )
        for i, entry in enumerate(data.entries):
            await VoucherEntry.create(
                voucher=v, line_no=i + 1,
                account_id=entry.account_id,
                summary=entry.summary,
                debit_amount=entry.debit_amount,
                credit_amount=entry.credit_amount,
                aux_customer_id=entry.aux_customer_id,
                aux_supplier_id=entry.aux_supplier_id,
                aux_employee_id=entry.aux_employee_id,
                aux_department_id=entry.aux_department_id,
                aux_product_id=entry.aux_product_id,
                aux_bank_account_id=entry.aux_bank_account_id,
            )

    logger.info(f"创建凭证: {voucher_no}")
    await log_operation(user, "VOUCHER_CREATE", "VOUCHER", v.id, f"创建凭证 {voucher_no}")
    return {"id": v.id, "voucher_no": voucher_no, "message": "创建成功"}


@router.put("/{voucher_id}")
async def update_voucher(
    voucher_id: int,
    data: VoucherUpdate,
    user: User = Depends(require_permission("accounting_edit"))
):
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿状态的凭证可以编辑")

    async with transactions.in_transaction():
        update_fields = {}
        if data.voucher_date is not None:
            new_period = data.voucher_date.strftime("%Y-%m")
            period = await AccountingPeriod.filter(
                account_set_id=v.account_set_id, period_name=new_period
            ).first()
            if not period:
                raise HTTPException(status_code=400, detail=f"会计期间 {new_period} 不存在")
            if period.is_closed:
                raise HTTPException(status_code=400, detail=f"会计期间 {new_period} 已结账")
            update_fields["voucher_date"] = data.voucher_date
            update_fields["period_name"] = new_period
        if data.summary is not None:
            update_fields["summary"] = data.summary
        if data.attachment_count is not None:
            update_fields["attachment_count"] = data.attachment_count

        if data.entries is not None:
            total_debit = sum(e.debit_amount for e in data.entries)
            total_credit = sum(e.credit_amount for e in data.entries)
            if total_debit != total_credit:
                raise HTTPException(status_code=400, detail=f"借贷不平衡：借方 {total_debit}，贷方 {total_credit}")
            if total_debit == 0:
                raise HTTPException(status_code=400, detail="借贷金额不能全部为零")

            account_ids = [e.account_id for e in data.entries]
            accounts = await ChartOfAccount.filter(
                id__in=account_ids, account_set_id=v.account_set_id, is_active=True, is_leaf=True
            )
            valid_ids = {a.id for a in accounts}
            for e in data.entries:
                if e.account_id not in valid_ids:
                    raise HTTPException(status_code=400, detail=f"科目 ID {e.account_id} 无效")

            await VoucherEntry.filter(voucher=v).delete()
            for i, entry in enumerate(data.entries):
                await VoucherEntry.create(
                    voucher=v, line_no=i + 1,
                    account_id=entry.account_id,
                    summary=entry.summary,
                    debit_amount=entry.debit_amount,
                    credit_amount=entry.credit_amount,
                    aux_customer_id=entry.aux_customer_id,
                    aux_supplier_id=entry.aux_supplier_id,
                    aux_employee_id=entry.aux_employee_id,
                    aux_department_id=entry.aux_department_id,
                    aux_product_id=entry.aux_product_id,
                    aux_bank_account_id=entry.aux_bank_account_id,
                )
            update_fields["total_debit"] = total_debit
            update_fields["total_credit"] = total_credit

        if update_fields:
            await Voucher.filter(id=voucher_id).update(**update_fields)

    await log_operation(user, "VOUCHER_UPDATE", "VOUCHER", v.id, f"更新凭证 {v.voucher_no}")
    return {"message": "更新成功"}


@router.delete("/{voucher_id}")
async def delete_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_edit"))
):
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿状态的凭证可以删除")
    voucher_no = v.voucher_no
    async with transactions.in_transaction():
        await VoucherEntry.filter(voucher=v).delete()
        await v.delete()
    await log_operation(user, "VOUCHER_DELETE", "VOUCHER", v.id, f"删除凭证 {voucher_no}")
    return {"message": "删除成功"}


@router.post("/{voucher_id}/submit")
async def submit_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_edit"))
):
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿状态的凭证可以提交")
    v.status = "pending"
    await v.save()
    await log_operation(user, "VOUCHER_SUBMIT", "VOUCHER", v.id, f"提交凭证 {v.voucher_no}")
    return {"message": "已提交审核"}


@router.post("/{voucher_id}/approve")
async def approve_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_approve"))
):
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "pending":
        raise HTTPException(status_code=400, detail="只有待审核状态的凭证可以审核")

    strict = await SystemSetting.filter(key="voucher_maker_checker").first()
    if strict and strict.value == "true":
        if v.creator_id == user.id:
            raise HTTPException(status_code=400, detail="制单人不能审核自己的凭证")

    v.status = "approved"
    v.approved_by = user
    v.approved_at = datetime.now(timezone.utc)
    await v.save()
    await log_operation(user, "VOUCHER_APPROVE", "VOUCHER", v.id, f"审核凭证 {v.voucher_no}")
    return {"message": "审核通过"}


@router.post("/{voucher_id}/reject")
async def reject_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_approve"))
):
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "pending":
        raise HTTPException(status_code=400, detail="只有待审核状态的凭证可以驳回")
    v.status = "draft"
    await v.save()
    await log_operation(user, "VOUCHER_REJECT", "VOUCHER", v.id, f"驳回凭证 {v.voucher_no}")
    return {"message": "已驳回"}


@router.post("/{voucher_id}/post")
async def post_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_post"))
):
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "approved":
        raise HTTPException(status_code=400, detail="只有已审核状态的凭证可以过账")
    v.status = "posted"
    v.posted_by = user
    v.posted_at = datetime.now(timezone.utc)
    await v.save()
    await log_operation(user, "VOUCHER_POST", "VOUCHER", v.id, f"过账凭证 {v.voucher_no}")
    return {"message": "过账成功"}


@router.post("/{voucher_id}/unpost")
async def unpost_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_post"))
):
    v = await Voucher.filter(id=voucher_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    if v.status != "posted":
        raise HTTPException(status_code=400, detail="只有已过账状态的凭证可以反过账")
    period = await AccountingPeriod.filter(
        account_set_id=v.account_set_id, period_name=v.period_name
    ).first()
    if period and period.is_closed:
        raise HTTPException(status_code=400, detail="该期间已结账，不能反过账")
    v.status = "approved"
    v.posted_by = None
    v.posted_at = None
    await v.save()
    await log_operation(user, "VOUCHER_UNPOST", "VOUCHER", v.id, f"反过账凭证 {v.voucher_no}")
    return {"message": "反过账成功"}


@router.get("/{voucher_id}/pdf")
async def get_voucher_pdf(
    voucher_id: int,
    user: User = Depends(require_permission("accounting_view")),
):
    """单张凭证PDF下载"""
    from app.utils.pdf_print import generate_voucher_pdf
    v = await Voucher.filter(id=voucher_id).prefetch_related("creator", "approved_by", "posted_by").first()
    if not v:
        raise HTTPException(status_code=404, detail="凭证不存在")
    entries = await VoucherEntry.filter(voucher_id=v.id).order_by("line_no").all()
    # 获取账套名称
    acct_set = await AccountSet.filter(id=v.account_set_id).first()
    # Build dicts
    voucher_dict = {
        "voucher_no": v.voucher_no,
        "voucher_type": v.voucher_type,
        "voucher_date": str(v.voucher_date),
        "attachment_count": v.attachment_count or 0,
        "total_debit": v.total_debit,
        "total_credit": v.total_credit,
        "account_set_name": acct_set.name if acct_set else "",
        "creator_name": v.creator.username if v.creator else "",
        "approved_by_name": v.approved_by.username if v.approved_by else "",
        "posted_by_name": v.posted_by.username if v.posted_by else "",
    }
    # 批量预加载科目（避免 N+1 查询）
    acct_ids = {e.account_id for e in entries}
    accounts = {a.id: a for a in await ChartOfAccount.filter(id__in=list(acct_ids)).all()} if acct_ids else {}
    entry_list = []
    for e in entries:
        acct = accounts.get(e.account_id)
        entry_list.append({
            "summary": e.summary,
            "account_name": f"{acct.code} {acct.name}" if acct else "",
            "debit_amount": e.debit_amount,
            "credit_amount": e.credit_amount,
        })
    pdf_bytes = generate_voucher_pdf(voucher_dict, entry_list)
    import io
    from urllib.parse import quote
    from fastapi.responses import StreamingResponse
    safe_name = quote(f"{v.voucher_no}.pdf")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}"}
    )


@router.post("/batch-pdf")
async def batch_voucher_pdf(
    data: BatchPdfRequest,
    user: User = Depends(require_permission("accounting_view")),
):
    """批量凭证PDF下载"""
    from app.utils.pdf_print import generate_voucher_pdf, merge_pdfs
    import io
    from fastapi.responses import StreamingResponse

    ids = data.ids
    if not ids:
        raise HTTPException(status_code=400, detail="请选择凭证")

    # 批量加载所有凭证及关联
    vouchers = await Voucher.filter(id__in=ids).prefetch_related("creator", "approved_by", "posted_by").all()
    voucher_map = {v.id: v for v in vouchers}

    # 获取账套名称（批量凭证可能属于不同账套）
    acct_set_ids = {v.account_set_id for v in vouchers}
    acct_sets = {a.id: a for a in await AccountSet.filter(id__in=list(acct_set_ids)).all()}

    # 批量加载所有分录
    all_entries = await VoucherEntry.filter(voucher_id__in=ids).order_by("voucher_id", "line_no").all()

    # 批量加载所有科目
    acct_ids = {e.account_id for e in all_entries}
    accounts = {a.id: a for a in await ChartOfAccount.filter(id__in=list(acct_ids)).all()} if acct_ids else {}

    # 按 voucher_id 分组
    from collections import defaultdict
    entries_by_voucher = defaultdict(list)
    for e in all_entries:
        entries_by_voucher[e.voucher_id].append(e)

    pdf_list = []
    for vid in ids:
        v = voucher_map.get(vid)
        if not v:
            continue
        acct_set = acct_sets.get(v.account_set_id)
        voucher_dict = {
            "voucher_no": v.voucher_no,
            "voucher_type": v.voucher_type,
            "voucher_date": str(v.voucher_date),
            "attachment_count": v.attachment_count or 0,
            "total_debit": v.total_debit,
            "total_credit": v.total_credit,
            "account_set_name": acct_set.name if acct_set else "",
            "creator_name": v.creator.username if v.creator else "",
            "approved_by_name": v.approved_by.username if v.approved_by else "",
            "posted_by_name": v.posted_by.username if v.posted_by else "",
        }
        entry_list = []
        for e in entries_by_voucher.get(vid, []):
            acct = accounts.get(e.account_id)
            entry_list.append({
                "summary": e.summary,
                "account_name": f"{acct.code} {acct.name}" if acct else "",
                "debit_amount": e.debit_amount,
                "credit_amount": e.credit_amount,
            })
        pdf_list.append(generate_voucher_pdf(voucher_dict, entry_list))

    if not pdf_list:
        raise HTTPException(status_code=404, detail="未找到凭证")

    merged = merge_pdfs(pdf_list)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        io.BytesIO(merged),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=vouchers_batch_{ts}.pdf"}
    )
