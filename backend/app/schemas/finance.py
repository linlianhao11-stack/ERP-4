from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field

class PaymentCreate(BaseModel):
    customer_id: int
    amount: Decimal = Field(gt=0)
    order_ids: List[int]
    payment_method: str = Field(default="cash", min_length=1)
    remark: Optional[str] = None
