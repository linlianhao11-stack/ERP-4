"""发票请求模型"""
from __future__ import annotations

from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date
from typing import List, Optional


class InvoiceItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    tax_rate: Decimal = Field(max_digits=5, decimal_places=2, default=Decimal("13"))


class InvoiceFromReceivable(BaseModel):
    receivable_bill_id: int
    invoice_type: str = "special"
    invoice_date: Optional[date] = None
    tax_rate: Decimal = Field(max_digits=5, decimal_places=2, default=Decimal("13"))
    items: List[InvoiceItemCreate] = []
    remark: str = ""


class InvoiceFromReceivableBatch(BaseModel):
    """多张应收单合并推送销项发票"""
    receivable_bill_ids: List[int]
    invoice_type: str = "special"
    invoice_date: Optional[date] = None
    tax_rate: Decimal = Field(max_digits=5, decimal_places=2, default=Decimal("13"))
    items: List[InvoiceItemCreate] = []
    remark: str = ""


class InvoiceFromPayable(BaseModel):
    """从应付单推送进项发票"""
    payable_bill_ids: List[int]
    invoice_type: str = "special"
    invoice_date: Optional[date] = None
    tax_rate: Decimal = Field(max_digits=5, decimal_places=2, default=Decimal("13"))
    items: List[InvoiceItemCreate] = []
    remark: str = ""


class InvoiceCreate(BaseModel):
    invoice_type: str = "special"
    supplier_id: int
    payable_bill_id: Optional[int] = None
    invoice_date: Optional[date] = None
    items: List[InvoiceItemCreate] = []
    remark: str = ""


class InvoiceUpdate(BaseModel):
    invoice_type: Optional[str] = None
    invoice_date: Optional[date] = None
    items: Optional[List[InvoiceItemCreate]] = None
    remark: Optional[str] = None
