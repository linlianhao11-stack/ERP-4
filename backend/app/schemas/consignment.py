from typing import List
from pydantic import BaseModel, Field

class ConsignmentReturnItem(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    warehouse_id: int
    location_id: int

class ConsignmentReturnRequest(BaseModel):
    customer_id: int
    items: List[ConsignmentReturnItem] = Field(min_length=1)
