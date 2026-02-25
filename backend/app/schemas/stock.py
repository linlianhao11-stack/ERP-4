from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field

class RestockRequest(BaseModel):
    warehouse_id: int
    product_id: int
    location_id: int
    quantity: int = Field(gt=0, le=999999)
    cost_price: Optional[Decimal] = Field(default=None, ge=0)
    remark: Optional[str] = None
    sn_codes: Optional[List[str]] = None

class StockAdjustRequest(BaseModel):
    warehouse_id: int
    product_id: int
    location_id: int
    new_quantity: int = Field(ge=0)
    remark: Optional[str] = None

class StockTransferRequest(BaseModel):
    product_id: int
    from_warehouse_id: int
    from_location_id: int
    to_warehouse_id: int
    to_location_id: int
    quantity: int = Field(gt=0, le=999999)
    remark: Optional[str] = None
