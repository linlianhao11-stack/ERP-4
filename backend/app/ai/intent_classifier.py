"""意图预分类器 — 同义词展开 + 模糊匹配"""
from __future__ import annotations
from app.logger import get_logger
from app.ai.synonym_map import DEFAULT_SYNONYMS

logger = get_logger("ai.intent")


def _expand_synonyms(text: str, synonyms: dict[str, list[str]] | None = None) -> str:
    """将用户输入中的同义词替换为标准词"""
    syn = synonyms or DEFAULT_SYNONYMS
    result = text.lower()
    for standard, alts in syn.items():
        for alt in alts:
            if alt in result:
                result = result.replace(alt, standard)
    return result


def classify_intent(
    message: str,
    preset_queries: list[dict] | None = None,
    synonyms: dict[str, list[str]] | None = None,
) -> dict | None:
    if not preset_queries or not message:
        return None

    expanded = _expand_synonyms(message, synonyms)

    best_match = None
    best_rate = 0.0
    best_kw_count = 0

    for preset in preset_queries:
        keywords = preset.get("keywords", [])
        if not keywords:
            continue

        hits = sum(1 for kw in keywords if kw.lower() in expanded)
        rate = hits / len(keywords)

        # 单关键词精确匹配，多关键词 >= 80%
        if len(keywords) == 1:
            if rate < 1.0:
                continue
        else:
            if rate < 0.8:
                continue

        # 取命中率最高、关键词更多的
        if rate > best_rate or (rate == best_rate and len(keywords) > best_kw_count):
            best_match = preset
            best_rate = rate
            best_kw_count = len(keywords)

    if best_match:
        logger.info(f"命中预置模板: {best_match.get('display', '')} (命中率: {best_rate:.0%})")

    return best_match
