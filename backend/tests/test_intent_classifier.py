"""意图分类器测试"""
import pytest
from app.ai.intent_classifier import classify_intent, _expand_synonyms

PRESETS = [
    {"display": "本月销售概况", "keywords": ["本月", "销售"], "sql": "SELECT 1"},
    {"display": "库存状态", "keywords": ["库存"], "sql": "SELECT 2"},
    {"display": "客户欠款排名", "keywords": ["客户", "欠款", "排名"], "sql": "SELECT 3"},
]

def test_exact_match():
    result = classify_intent("本月销售概况", PRESETS)
    assert result is not None
    assert result["display"] == "本月销售概况"

def test_synonym_expansion():
    result = classify_intent("这个月卖了多少", PRESETS)
    assert result is not None
    assert result["display"] == "本月销售概况"

def test_single_keyword_exact():
    result = classify_intent("库存", PRESETS)
    assert result is not None
    assert result["display"] == "库存状态"

def test_single_keyword_synonym():
    result = classify_intent("还有多少存货", PRESETS)
    assert result is not None
    assert result["display"] == "库存状态"

def test_no_match():
    result = classify_intent("天气怎么样", PRESETS)
    assert result is None

def test_expand_synonyms():
    expanded = _expand_synonyms("这个月卖了多少")
    assert "本月" in expanded
    assert "销售" in expanded
