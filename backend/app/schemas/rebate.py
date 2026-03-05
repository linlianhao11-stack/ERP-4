from typing import Optional, Literal
from decimal import Decimal
from pydantic import BaseModel, Field


class RebateChargeRequest(BaseModel):
    target_type: Literal["customer", "supplier"]
    target_id: int
    amount: Decimal = Field(gt=0)
    account_set_id: Optional[int] = None
    remark: Optional[str] = None
