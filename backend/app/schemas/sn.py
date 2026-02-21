from pydantic import BaseModel, Field

class SnConfigCreate(BaseModel):
    warehouse_id: int
    brand: str = Field(min_length=1, max_length=100)
