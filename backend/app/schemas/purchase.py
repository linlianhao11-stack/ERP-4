from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field

class PurchaseOrderItemRequest(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    tax_inclusive_price: Decimal = Field(gt=0)
    tax_rate: Decimal = Field(default=Decimal("0.13"), ge=0, le=1)
    target_warehouse_id: Optional[int] = None
    target_location_id: Optional[int] = None
    rebate_amount: Optional[Decimal] = Field(default=None, ge=0)

class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    target_warehouse_id: Optional[int] = None
    target_location_id: Optional[int] = None
    remark: Optional[str] = None
    items: List[PurchaseOrderItemRequest] = Field(min_length=1)
    rebate_amount: Optional[Decimal] = Field(default=None, ge=0)
    credit_amount: Optional[Decimal] = Field(default=None, ge=0)

class PurchaseReturnItemRequest(BaseModel):
    item_id: int
    return_quantity: int = Field(gt=0)

class PurchaseReturnRequest(BaseModel):
    items: List[PurchaseReturnItemRequest]
    is_refunded: bool = False
    tracking_no: Optional[str] = None


class ReceiveItemRequest(BaseModel):
    item_id: int
    receive_quantity: int = Field(gt=0)
    warehouse_id: Optional[int] = None
    location_id: Optional[int] = None
    sn_codes: Optional[List[str]] = None

class ReceiveRequest(BaseModel):
    items: List[ReceiveItemRequest]


class PurchasePayRequest(BaseModel):
    payment_method: Optional[str] = None
