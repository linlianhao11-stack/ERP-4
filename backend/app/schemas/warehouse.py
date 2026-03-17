from typing import Optional, Literal
from pydantic import BaseModel, Field

LocationColor = Literal["blue", "green", "red", "yellow", "purple", "gray", "orange"]
DEFAULT_LOCATION_COLOR = "blue"

class WarehouseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_default: bool = False
    account_set_id: Optional[int] = None

class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_default: Optional[bool] = None
    account_set_id: Optional[int] = None

class LocationCreate(BaseModel):
    warehouse_id: int
    code: str = Field(min_length=1, max_length=50)
    name: Optional[str] = None
    color: LocationColor = DEFAULT_LOCATION_COLOR

class LocationUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = None
    color: Optional[LocationColor] = None
