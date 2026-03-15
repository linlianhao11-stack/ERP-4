from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel


class BillRef(BaseModel):
    id: int
    type: str


class GenerateVouchersRequest(BaseModel):
    period_names: Optional[List[str]] = None
    bills: Optional[List[BillRef]] = None
    merge_by_partner: bool = False
