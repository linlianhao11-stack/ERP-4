from typing import Optional, List
from pydantic import BaseModel, Field

class ShipmentUpdate(BaseModel):
    carrier_code: str = Field(min_length=1)
    carrier_name: str = Field(min_length=1)
    tracking_no: Optional[str] = None
    phone: Optional[str] = None
    sn_code: Optional[str] = None
    sn_codes: Optional[List[str]] = None

class SNCodeUpdate(BaseModel):
    sn_code: Optional[str] = None
    sn_codes: Optional[List[str]] = None

class ShipItemRequest(BaseModel):
    order_item_id: int
    quantity: int = Field(gt=0)
    sn_codes: Optional[List[str]] = None

class ShipRequest(BaseModel):
    carrier_code: str = Field(min_length=1)
    carrier_name: str = Field(min_length=1)
    tracking_no: Optional[str] = None
    phone: Optional[str] = None
    is_self_pickup: bool = False
    items: List[ShipItemRequest] = Field(min_length=1)
