"""AI 模块 Pydantic Schemas"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)
    is_preset: bool = Field(default=False)


class ChatResponse(BaseModel):
    type: str  # "answer" | "clarification" | "error"
    message_id: Optional[str] = None
    analysis: Optional[str] = None
    table_data: Optional[dict] = None
    chart_config: Optional[dict] = None
    sql: Optional[str] = None
    row_count: Optional[int] = None
    message: Optional[str] = None
    options: Optional[list[str]] = None


class ExportRequest(BaseModel):
    table_data: dict
    title: str = "AI查询结果"


class FeedbackRequest(BaseModel):
    message_id: str
    feedback: str = Field(..., pattern="^(positive|negative)$")
    save_as_example: bool = False
    original_question: Optional[str] = None
    sql: Optional[str] = None
    negative_reason: Optional[str] = None


class ApiKeysUpdate(BaseModel):
    """API 密钥更新 — 字段全部可选，只更新传入的"""
    class Config:
        extra = "allow"


class AiConfigUpdate(BaseModel):
    prompt_system: Optional[str] = None
    prompt_analysis: Optional[str] = None
    business_dict: Optional[list] = None
    few_shots: Optional[list] = None
    preset_queries: Optional[list] = None
