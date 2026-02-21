from typing import Optional
from pydantic import BaseModel, Field

class WarehouseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_default: bool = False

class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    is_default: Optional[bool] = None

class LocationCreate(BaseModel):
    warehouse_id: int
    code: str = Field(min_length=1, max_length=50)
    name: Optional[str] = None

class LocationUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
