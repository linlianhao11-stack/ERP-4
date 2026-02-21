from pydantic import BaseModel, Field


class SettingUpdate(BaseModel):
    value: str = Field(default="", max_length=1000)
