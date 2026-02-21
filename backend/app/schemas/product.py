from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    brand: Optional[str] = None
    category: Optional[str] = None
    retail_price: Decimal = Field(ge=0)
    cost_price: Decimal = Field(ge=0)
    unit: str = "个"

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    brand: Optional[str] = None
    category: Optional[str] = None
    retail_price: Optional[Decimal] = Field(default=None, ge=0)
    cost_price: Optional[Decimal] = Field(default=None, ge=0)
    unit: Optional[str] = None
