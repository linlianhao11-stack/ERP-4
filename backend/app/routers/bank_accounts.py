"""银行账户管理路由"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth.dependencies import require_permission
from app.models import User, BankAccount

router = APIRouter(prefix="/api/bank-accounts", tags=["bank-accounts"])

class BankAccountCreate(BaseModel):
    account_set_id: int
    bank_name: str = Field(min_length=1, max_length=100)
    account_number: str = Field(min_length=1, max_length=50)
    short_name: str = Field(default="", max_length=50)

class BankAccountUpdate(BaseModel):
    bank_name: Optional[str] = Field(default=None, max_length=100)
    account_number: Optional[str] = Field(default=None, max_length=50)
    short_name: Optional[str] = Field(default=None, max_length=50)

@router.get("")
async def list_bank_accounts(
    account_set_id: Optional[int] = Query(default=None),
    user: User = Depends(require_permission("accounting_view")),
):
    filters = {"is_active": True}
    if account_set_id is not None:
        filters["account_set_id"] = account_set_id
    items = await BankAccount.filter(**filters).order_by("sort_order", "id")
    return [
        {
            "id": b.id,
            "account_set_id": b.account_set_id,
            "bank_name": b.bank_name,
            "account_number": b.account_number,
            "short_name": b.short_name or b.bank_name,
            "sort_order": b.sort_order,
        }
        for b in items
    ]

@router.post("")
async def create_bank_account(
    data: BankAccountCreate,
    user: User = Depends(require_permission("accounting_edit")),
):
    if await BankAccount.filter(
        account_set_id=data.account_set_id, account_number=data.account_number
    ).exists():
        raise HTTPException(status_code=400, detail="该账号已存在")
    max_sort = await BankAccount.filter(account_set_id=data.account_set_id).order_by("-sort_order").first()
    sort_order = (max_sort.sort_order + 1) if max_sort else 1
    b = await BankAccount.create(
        account_set_id=data.account_set_id,
        bank_name=data.bank_name.strip(),
        account_number=data.account_number.strip(),
        short_name=(data.short_name or "").strip(),
        sort_order=sort_order,
    )
    return {"id": b.id, "message": "添加成功"}

@router.put("/{bank_account_id}")
async def update_bank_account(
    bank_account_id: int,
    data: BankAccountUpdate,
    user: User = Depends(require_permission("accounting_edit")),
):
    b = await BankAccount.filter(id=bank_account_id, is_active=True).first()
    if not b:
        raise HTTPException(status_code=404, detail="银行账户不存在")
    if data.bank_name is not None:
        b.bank_name = data.bank_name.strip()
    if data.account_number is not None:
        if data.account_number != b.account_number:
            if await BankAccount.filter(
                account_set_id=b.account_set_id, account_number=data.account_number
            ).exists():
                raise HTTPException(status_code=400, detail="该账号已存在")
        b.account_number = data.account_number.strip()
    if data.short_name is not None:
        b.short_name = data.short_name.strip()
    await b.save()
    return {"message": "更新成功"}

@router.delete("/{bank_account_id}")
async def delete_bank_account(
    bank_account_id: int,
    user: User = Depends(require_permission("accounting_edit")),
):
    b = await BankAccount.filter(id=bank_account_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="银行账户不存在")
    b.is_active = False
    await b.save()
    return {"message": "删除成功"}
