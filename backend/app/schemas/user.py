from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator

VALID_PERMISSIONS = [
    "dashboard", "sales", "customer", "stock_view", "stock_edit",
    "finance", "finance_confirm", "logistics",
    "purchase", "purchase_approve", "purchase_pay", "purchase_receive",
    "settings", "logs", "admin"
]

class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = None
    role: Literal["admin", "user"] = "user"
    permissions: List[str] = []

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v):
        invalid = set(v) - set(VALID_PERMISSIONS)
        if invalid:
            raise ValueError(f"无效权限: {invalid}")
        return v


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    role: Optional[Literal["admin", "user"]] = None
    permissions: Optional[List[str]] = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v):
        if v is None:
            return v
        invalid = set(v) - set(VALID_PERMISSIONS)
        if invalid:
            raise ValueError(f"无效权限: {invalid}")
        return v
