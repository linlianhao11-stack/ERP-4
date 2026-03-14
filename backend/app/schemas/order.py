from typing import Optional, List, Literal
from decimal import Decimal
from pydantic import BaseModel, Field

class OrderItemRequest(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=999999)
    unit_price: Decimal = Field(ge=0, le=99999999)
    warehouse_id: Optional[int] = None
    location_id: Optional[int] = None
    rebate_amount: Optional[Decimal] = Field(default=None, ge=0)

class OrderCreate(BaseModel):
    order_type: Literal["CASH", "CREDIT", "RETURN", "CONSIGN_OUT", "CONSIGN_SETTLE"]
    customer_id: Optional[int] = None
    employee_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    location_id: Optional[int] = None
    related_order_id: Optional[int] = None
    refunded: Optional[bool] = False
    use_credit: Optional[bool] = False
    payment_method: Optional[str] = None
    items: List[OrderItemRequest] = Field(min_length=1, max_length=100)
    remark: Optional[str] = Field(None, max_length=2000)
    rebate_amount: Optional[Decimal] = Field(default=None, ge=0)
    account_set_id: Optional[int] = None
    refund_method: Optional[str] = None
    refund_amount: Optional[Decimal] = None

class CancelItemAllocation(BaseModel):
    order_item_id: int
    paid_amount: Decimal = Field(default=Decimal("0"), ge=0)
    rebate_amount: Decimal = Field(default=Decimal("0"), ge=0)

class CancelRequest(BaseModel):
    new_order_paid_amount: Optional[Decimal] = Field(default=None, ge=0)
    new_order_rebate_used: Optional[Decimal] = Field(default=None, ge=0)
    item_allocations: Optional[List[CancelItemAllocation]] = None
    refund_amount: Optional[Decimal] = Field(default=None, ge=0)
    refund_rebate: Optional[Decimal] = Field(default=None, ge=0)
    refund_method: Literal["balance", "cash"] = "balance"
    refund_payment_method: Optional[str] = None
