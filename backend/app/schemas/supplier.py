from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class SupplierRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    contact_person: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    tax_id: Optional[str] = Field(None, max_length=50)
    bank_account: Optional[str] = Field(None, max_length=50)
    bank_name: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=500)

class CreditRefundRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    remark: Optional[str] = None
