from typing import Optional
from pydantic import BaseModel, Field

class SalespersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    phone: Optional[str] = None

class SalespersonUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=50)
