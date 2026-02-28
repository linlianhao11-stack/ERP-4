"""应收应付请求模型"""
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field
from datetime import date


# === 应收 ===

class ReceivableBillCreate(BaseModel):
    customer_id: int
    order_id: Optional[int] = None
    bill_date: date
    total_amount: Decimal = Field(max_digits=18, decimal_places=2)
    remark: str = Field(default="", max_length=500)


class ReceiptBillCreate(BaseModel):
    customer_id: int
    receivable_bill_id: Optional[int] = None
    receipt_date: date
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    payment_method: str = Field(min_length=1, max_length=50)
    is_advance: bool = False
    remark: str = Field(default="", max_length=500)


class ReceiptRefundBillCreate(BaseModel):
    customer_id: int
    original_receipt_id: int
    refund_date: date
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reason: str = Field(default="", max_length=500)
    remark: str = Field(default="", max_length=500)


class ReceivableWriteOffCreate(BaseModel):
    customer_id: int
    advance_receipt_id: int
    receivable_bill_id: int
    write_off_date: date
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    remark: str = Field(default="", max_length=500)


# === 应付 ===

class PayableBillCreate(BaseModel):
    supplier_id: int
    purchase_order_id: Optional[int] = None
    bill_date: date
    total_amount: Decimal = Field(max_digits=18, decimal_places=2)
    remark: str = Field(default="", max_length=500)


class DisbursementBillCreate(BaseModel):
    supplier_id: int
    payable_bill_id: Optional[int] = None
    disbursement_date: date
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    disbursement_method: str = Field(min_length=1, max_length=50)
    remark: str = Field(default="", max_length=500)


class DisbursementRefundBillCreate(BaseModel):
    supplier_id: int
    original_disbursement_id: int
    refund_date: date
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reason: str = Field(default="", max_length=500)
    remark: str = Field(default="", max_length=500)
