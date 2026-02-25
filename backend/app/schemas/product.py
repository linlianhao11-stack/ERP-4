from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9\u4e00-\u9fff\-_.]+$')
    name: str = Field(min_length=1, max_length=200)
    brand: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    retail_price: Decimal = Field(ge=0, le=99999999)
    cost_price: Decimal = Field(ge=0, le=99999999)
    unit: str = Field(default="个", max_length=20)

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    brand: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    retail_price: Optional[Decimal] = Field(default=None, ge=0, le=99999999)
    cost_price: Optional[Decimal] = Field(default=None, ge=0, le=99999999)
    unit: Optional[str] = Field(default=None, max_length=20)
