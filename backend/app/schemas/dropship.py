"""代采代发 Schema"""
from __future__ import annotations

from typing import Optional, List, Literal
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
    invoice_type: Literal["special", "normal"] = "special"
    purchase_tax_rate: Decimal = Field(default=Decimal("13"), ge=0, le=100)
    customer_id: int
    platform_order_no: str
    sale_price: Decimal = Field(gt=0)
    sale_tax_rate: Decimal = Field(default=Decimal("13"), ge=0, le=100)
    settlement_type: Literal["prepaid", "credit"] = "credit"
    advance_receipt_id: Optional[int] = None
    shipping_mode: Literal["direct", "transit"] = "direct"
    note: Optional[str] = None


class DropshipOrderUpdate(BaseModel):
    account_set_id: Optional[int] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    purchase_price: Optional[Decimal] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, gt=0)
    invoice_type: Optional[Literal["special", "normal"]] = None
    purchase_tax_rate: Optional[Decimal] = Field(default=None, ge=0, le=100)
    customer_id: Optional[int] = None
    platform_order_no: Optional[str] = None
    sale_price: Optional[Decimal] = Field(default=None, gt=0)
    sale_tax_rate: Optional[Decimal] = Field(default=None, ge=0, le=100)
    settlement_type: Optional[Literal["prepaid", "credit"]] = None
    advance_receipt_id: Optional[int] = None
    shipping_mode: Optional[Literal["direct", "transit"]] = None
    note: Optional[str] = None


class DropshipShipRequest(BaseModel):
    carrier_code: str
    carrier_name: str
    tracking_no: str
    phone: Optional[str] = None  # 收/寄件人手机号（顺丰/中通需要）


class DropshipPaymentRequest(BaseModel):
    order_ids: List[int] = Field(min_length=1)
    payment_method: Literal["bank_transfer", "employee_advance"]
    employee_id: Optional[int] = None


class DropshipCancelRequest(BaseModel):
    reason: Optional[str] = None
