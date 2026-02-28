"""发票请求模型"""
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date
from typing import Optional


class InvoiceItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    quantity: int
    unit_price: Decimal = Field(max_digits=18, decimal_places=2)
    tax_rate: Decimal = Field(max_digits=5, decimal_places=2, default=Decimal("13"))


class InvoiceFromReceivable(BaseModel):
    receivable_bill_id: int
    invoice_type: str = "special"
    invoice_date: Optional[date] = None
    items: list[InvoiceItemCreate]
    remark: str = ""


class InvoiceCreate(BaseModel):
    invoice_type: str = "special"
    supplier_id: int
    payable_bill_id: Optional[int] = None
    invoice_date: Optional[date] = None
    items: list[InvoiceItemCreate]
    remark: str = ""


class InvoiceUpdate(BaseModel):
    invoice_type: Optional[str] = None
    invoice_date: Optional[date] = None
    items: Optional[list[InvoiceItemCreate]] = None
    remark: Optional[str] = None
