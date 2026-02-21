from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

class SupplierRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    tax_id: Optional[str] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    address: Optional[str] = None

class CreditRefundRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    remark: Optional[str] = None
