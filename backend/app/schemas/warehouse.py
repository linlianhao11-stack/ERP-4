from typing import Optional, Literal
from pydantic import BaseModel, Field

WarehouseColor = Literal["blue", "green", "red", "yellow", "purple", "gray", "orange"]
DEFAULT_WAREHOUSE_COLOR = "blue"

class WarehouseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_default: bool = False
    account_set_id: Optional[int] = None
    color: WarehouseColor = DEFAULT_WAREHOUSE_COLOR

class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_default: Optional[bool] = None
    account_set_id: Optional[int] = None
    color: Optional[WarehouseColor] = None

class LocationCreate(BaseModel):
    warehouse_id: int
    code: str = Field(min_length=1, max_length=50)
    name: Optional[str] = None

class LocationUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = None
