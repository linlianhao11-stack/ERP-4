from __future__ import annotations
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class ProductCreate(BaseModel):
    # SKU 由系统自动生成，前端无需传入
    name: str = Field(min_length=1, max_length=200)
    brand: str = Field(min_length=1, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    retail_price: Decimal = Field(ge=0, le=99999999)
    cost_price: Decimal = Field(ge=0, le=99999999)
    unit: str = Field(min_length=1, max_length=20)

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    brand: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    retail_price: Optional[Decimal] = Field(default=None, ge=0, le=99999999)
    cost_price: Optional[Decimal] = Field(default=None, ge=0, le=99999999)
    unit: Optional[str] = Field(default=None, max_length=20)
