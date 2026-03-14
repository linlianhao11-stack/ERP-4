"""会计模块请求/响应模型"""
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field
from datetime import date


# === 账套 ===

class AccountSetCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    company_name: str = Field(default="", max_length=200)
    tax_id: str = Field(default="", max_length=30)
    legal_person: str = Field(default="", max_length=50)
    address: str = Field(default="")
    bank_name: str = Field(default="", max_length=100)
    bank_account: str = Field(default="", max_length=50)
    start_year: int = Field(ge=2000, le=2099)
    start_month: int = Field(ge=1, le=12, default=1)


class AccountSetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    company_name: Optional[str] = Field(None, max_length=200)
    tax_id: Optional[str] = Field(None, max_length=30)
    legal_person: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    bank_name: Optional[str] = Field(None, max_length=100)
    bank_account: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


# === 科目 ===

class ChartOfAccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    parent_code: Optional[str] = Field(None, max_length=20)
    category: str = Field(pattern=r"^(asset|liability|equity|cost|profit_loss)$")
    direction: str = Field(pattern=r"^(debit|credit)$")
    is_leaf: bool = True
    aux_customer: bool = False
    aux_supplier: bool = False
    aux_employee: bool = False
    aux_department: bool = False


class ChartOfAccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_leaf: Optional[bool] = None
    is_active: Optional[bool] = None
    aux_customer: Optional[bool] = None
    aux_supplier: Optional[bool] = None
    aux_employee: Optional[bool] = None
    aux_department: Optional[bool] = None


# === 凭证 ===

class VoucherEntryInput(BaseModel):
    account_id: int
    summary: str = Field(default="", max_length=200)
    debit_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    credit_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    aux_customer_id: Optional[int] = None
    aux_supplier_id: Optional[int] = None
    aux_employee_id: Optional[int] = None
    aux_department_id: Optional[int] = None


class VoucherCreate(BaseModel):
    voucher_type: str = Field(pattern=r"^(记|收|付|转)$")
    voucher_date: date
    summary: str = Field(default="", max_length=200)
    attachment_count: int = Field(default=0, ge=0)
    entries: List[VoucherEntryInput] = Field(min_length=2)


class VoucherUpdate(BaseModel):
    voucher_date: Optional[date] = None
    summary: Optional[str] = Field(None, max_length=200)
    attachment_count: Optional[int] = Field(None, ge=0)
    entries: Optional[List[VoucherEntryInput]] = None
