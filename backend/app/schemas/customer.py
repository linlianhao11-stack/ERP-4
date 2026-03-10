from typing import Optional
from pydantic import BaseModel, Field

class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact_person: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = None
    tax_id: Optional[str] = Field(default=None, max_length=50)
    bank_name: Optional[str] = Field(default=None, max_length=100)
    bank_account: Optional[str] = Field(default=None, max_length=50)
