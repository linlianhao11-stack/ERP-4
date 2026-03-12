"""意图预分类器 — 高频查询直接匹配预置 SQL 模板"""
from __future__ import annotations
from app.logger import get_logger

logger = get_logger("ai.intent")


def classify_intent(
    message: str,
    preset_queries: list[dict] | None = None,
) -> dict | None:
    """
    尝试匹配预置查询模板。

    preset_queries 格式: [{"display": "...", "keywords": ["..."], "sql": "..."}]
    返回匹配的模板 dict 或 None（未命中走 NL2SQL）。
    """
    if not preset_queries or not message:
        return None

    msg_lower = message.lower().strip()

    for preset in preset_queries:
        keywords = preset.get("keywords", [])
        if not keywords:
            continue
        # 所有关键词都出现在消息中才算命中
        if all(kw.lower() in msg_lower for kw in keywords):
            logger.info(f"命中预置模板: {preset.get('display', '')}")
            return preset

    return None
