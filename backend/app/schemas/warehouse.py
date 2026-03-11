from typing import Optional
from pydantic import BaseModel, Field

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

class LocationUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = None
