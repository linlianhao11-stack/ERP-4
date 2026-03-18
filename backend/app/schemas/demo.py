from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Literal

from pydantic import BaseModel, Field


# ── 样机常量 ──

DEMO_UNIT_STATUSES = ("in_stock", "lent_out", "repairing", "sold", "scrapped", "lost", "converted")
DEMO_CONDITIONS = ("new", "good", "fair", "poor")
DEMO_LOAN_TYPES = ("customer_trial", "salesperson", "exhibition")
DEMO_LOAN_STATUSES = ("pending_approval", "approved", "rejected", "lent_out", "returned", "closed")
DEMO_DISPOSAL_TYPES = ("sale", "scrap", "loss_compensation", "conversion")

DemoUnitStatus = Literal["in_stock", "lent_out", "repairing", "sold", "scrapped", "lost", "converted"]
DemoCondition = Literal["new", "good", "fair", "poor"]
DemoLoanType = Literal["customer_trial", "salesperson", "exhibition"]
DemoLoanStatus = Literal["pending_approval", "approved", "rejected", "lent_out", "returned", "closed"]


# ── 样机台账 ──

class DemoUnitCreate(BaseModel):
    """新增样机（两种来源共用）"""
    source: Literal["stock_transfer", "new_purchase"]
    product_id: int
    sn_code: str = Field(max_length=200)
    warehouse_id: int  # 目标样机仓
    condition: DemoCondition = "new"
    notes: Optional[str] = None
    # stock_transfer 专用
    source_warehouse_id: Optional[int] = None
    source_location_id: Optional[int] = None
    # new_purchase 专用
    cost_price: Optional[Decimal] = Field(default=None, gt=0)


class DemoUnitUpdate(BaseModel):
    condition: Optional[DemoCondition] = None
    notes: Optional[str] = None


# ── 借还记录 ──

class DemoLoanCreate(BaseModel):
    demo_unit_id: int
    loan_type: DemoLoanType
    borrower_type: Literal["customer", "employee"]
    borrower_id: int
    handler_id: Optional[int] = None
    expected_return_date: date
    purpose: Optional[str] = None


class DemoLoanReturn(BaseModel):
    condition_on_return: DemoCondition
    return_notes: Optional[str] = None


# ── 处置 ──

class DemoSellRequest(BaseModel):
    """转销售"""
    customer_id: int
    sale_price: Decimal = Field(gt=0)
    account_set_id: int
    employee_id: Optional[int] = None
    remark: Optional[str] = None


class DemoConvertRequest(BaseModel):
    """翻新转良品"""
    target_warehouse_id: int
    target_location_id: Optional[int] = None
    refurbish_cost: Optional[Decimal] = Field(default=None, ge=0)


class DemoScrapRequest(BaseModel):
    """报废"""
    reason: str
    residual_value: Optional[Decimal] = Field(default=None, ge=0)
    account_set_id: int


class DemoLossRequest(BaseModel):
    """丢失赔偿"""
    description: str
    compensation_amount: Decimal = Field(gt=0)
    account_set_id: int
