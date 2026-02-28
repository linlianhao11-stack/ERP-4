"""出入库单请求模型"""
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date
from typing import Optional


class SalesDeliveryItemCreate(BaseModel):
    order_item_id: Optional[int] = None
    product_id: int
    product_name: str
    quantity: int
    cost_price: Decimal = Field(max_digits=18, decimal_places=2)
    sale_price: Decimal = Field(max_digits=18, decimal_places=2)


class SalesDeliveryBillCreate(BaseModel):
    customer_id: int
    order_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    bill_date: Optional[date] = None
    remark: str = ""
    items: list[SalesDeliveryItemCreate]


class PurchaseReceiptItemCreate(BaseModel):
    purchase_order_item_id: Optional[int] = None
    product_id: int
    product_name: str
    quantity: int
    tax_inclusive_price: Decimal = Field(max_digits=18, decimal_places=2)
    tax_exclusive_price: Decimal = Field(max_digits=18, decimal_places=2)
    tax_rate: Decimal = Field(max_digits=5, decimal_places=2, default=Decimal("13"))


class PurchaseReceiptBillCreate(BaseModel):
    supplier_id: int
    purchase_order_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    bill_date: Optional[date] = None
    remark: str = ""
    items: list[PurchaseReceiptItemCreate]
