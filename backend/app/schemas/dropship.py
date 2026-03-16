"""代采代发 Schema"""
from __future__ import annotations

from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field


class DropshipOrderCreate(BaseModel):
    account_set_id: int
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None  # 快速新建供应商
    product_id: Optional[int] = None
    product_name: str
    purchase_price: Decimal = Field(gt=0)
    quantity: int = Field(gt=0)
    invoice_type: str = "special"  # special | normal
    purchase_tax_rate: Decimal = Decimal("13")
    customer_id: int
    platform_order_no: str
    sale_price: Decimal = Field(gt=0)
    sale_tax_rate: Decimal = Decimal("13")
    settlement_type: str = "credit"  # prepaid | credit
    advance_receipt_id: Optional[int] = None
    shipping_mode: str = "direct"  # direct | transit
    note: Optional[str] = None


class DropshipOrderUpdate(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    quantity: Optional[int] = None
    invoice_type: Optional[str] = None
    purchase_tax_rate: Optional[Decimal] = None
    customer_id: Optional[int] = None
    platform_order_no: Optional[str] = None
    sale_price: Optional[Decimal] = None
    sale_tax_rate: Optional[Decimal] = None
    settlement_type: Optional[str] = None
    advance_receipt_id: Optional[int] = None
    shipping_mode: Optional[str] = None
    note: Optional[str] = None


class DropshipShipRequest(BaseModel):
    carrier_code: str
    carrier_name: str
    tracking_no: str


class DropshipPaymentRequest(BaseModel):
    order_ids: List[int] = Field(min_length=1)
    payment_method: str
    employee_id: Optional[int] = None


class DropshipCancelRequest(BaseModel):
    reason: Optional[str] = None
