"""NL2SQL 主流程编排 — AI 聊天核心服务"""
from __future__ import annotations
import asyncio
import json
import uuid
import asyncpg
from app.logger import get_logger
from app.models import SystemSetting, AccountSet
from app.ai.encryption import decrypt_value
from app.ai.sql_validator import validate_sql
from app.ai.intent_classifier import classify_intent
from app.ai.prompt_builder import build_sql_prompt, build_analysis_prompt
from app.ai.deepseek_client import (
    call_deepseek, DEFAULT_BASE_URL, DEFAULT_MODEL_SQL, DEFAULT_MODEL_ANALYSIS,
)

logger = get_logger("ai.chat_service")

# AI 专用连接池（与 Tortoise ORM 完全分离）
_ai_pool: asyncpg.Pool | None = None
_pool_dsn: str | None = None

# 并发限制 — 防止同时向 DeepSeek API 发送过多请求
_ai_semaphore = asyncio.Semaphore(3)  # spec 要求 DeepSeek 最大并发 3

# 配置缓存
_config_cache: dict | None = None
_config_cache_time: float = 0
CONFIG_CACHE_TTL = 300  # 5 分钟


async def get_ai_pool(dsn: str) -> asyncpg.Pool:
    """获取或创建 AI 专用连接池"""
    global _ai_pool, _pool_dsn
    # asyncpg.Pool 无公共 is_closed 属性，_closed 是唯一可检查方式
    if _ai_pool is not None and not _ai_pool._closed and _pool_dsn == dsn:
        return _ai_pool
    if _ai_pool is not None and not _ai_pool._closed:
        await _ai_pool.close()
    _ai_pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=5,
        command_timeout=30,
        statement_cache_size=0,
    )
    _pool_dsn = dsn
    return _ai_pool


async def close_ai_pool() -> None:
    """关闭 AI 连接池"""
    global _ai_pool, _pool_dsn
    if _ai_pool is not None and not _ai_pool._closed:
        await _ai_pool.close()
    _ai_pool = None
    _pool_dsn = None


async def _get_config() -> dict:
    """获取 AI 配置（带缓存）"""
    import time
    global _config_cache, _config_cache_time
    now = time.time()
    if _config_cache and (now - _config_cache_time) < CONFIG_CACHE_TTL:
        return _config_cache

    config = {}
    # 一次性批量查询所有 ai.* 配置
    settings = await SystemSetting.filter(key__startswith="ai.").all()
    settings_map = {s.key: s.value for s in settings}

    # DeepSeek 配置（从批量结果中提取）
    raw_key = settings_map.get("ai.deepseek.api_key", "")
    config["api_key"] = decrypt_value(raw_key) if raw_key else None
    config["base_url"] = settings_map.get("ai.deepseek.base_url") or DEFAULT_BASE_URL
    config["model_sql"] = settings_map.get("ai.deepseek.model_sql") or DEFAULT_MODEL_SQL
    config["model_analysis"] = settings_map.get("ai.deepseek.model_analysis") or DEFAULT_MODEL_ANALYSIS

    # JSON 配置
    for json_key in ["ai.business_dict", "ai.few_shots", "ai.preset_queries"]:
        raw = settings_map.get(json_key)
        if raw:
            try:
                config[json_key] = json.loads(raw)
            except json.JSONDecodeError:
                config[json_key] = None
        else:
            config[json_key] = None

    # 自定义提示词
    for prompt_key in ["ai.prompt.system", "ai.prompt.analysis"]:
        config[prompt_key] = settings_map.get(prompt_key)

    _config_cache = config
    _config_cache_time = now
    return config


def invalidate_config_cache() -> None:
    """清除配置缓存（admin 修改配置后调用）"""
    global _config_cache, _config_cache_time
    _config_cache = None
    _config_cache_time = 0


async def check_ai_available() -> tuple[bool, str | None]:
    """检查 AI 是否可用"""
    from app.config import AI_DB_PASSWORD
    if not AI_DB_PASSWORD:
        return False, "AI 数据库密码未配置"
    config = await _get_config()
    if not config.get("api_key"):
        return False, "DeepSeek API Key 未配置"
    return True, None


async def get_preset_queries() -> list[dict]:
    """获取预设快捷问题列表（仅 display 字段，不暴露 sql/keywords）"""
    try:
        config = await _get_config()
        raw = config.get("ai.preset_queries") or []
        return [{"display": q["display"]} for q in raw if q.get("display")]
    except Exception:
        return []


async def process_chat(
    message: str,
    history: list[dict],
    user_id: int,
    db_dsn: str,
) -> dict:
    """
    处理用户聊天消息。

    返回 ChatResponse 格式的 dict。
    """
    message_id = str(uuid.uuid4())

    # 并发限制：防止同时过多 AI 请求耗尽 API 配额
    async with _ai_semaphore:
        return await _process_chat_inner(message, history, user_id, db_dsn, message_id)


async def _process_chat_inner(
    message: str,
    history: list[dict],
    user_id: int,
    db_dsn: str,
    message_id: str,
) -> dict:
    try:
        config = await _get_config()
        api_key = config.get("api_key")
        if not api_key:
            return {"type": "error", "message": "AI 助手未配置，请联系管理员设置 DeepSeek API Key"}

        # 1. 意图预分类 — 命中预置模板则校验后执行
        preset = classify_intent(message, config.get("ai.preset_queries"))
        if preset and preset.get("sql"):
            from app.ai.sql_validator import validate_sql
            ok, _, reason = validate_sql(preset["sql"])
            if not ok:
                logger.warning(f"预设 SQL 校验失败: {reason} — {preset['sql'][:100]}")
                return {"type": "error", "message": f"预设查询模板异常，请联系管理员检查: {reason}"}
            return await _execute_and_analyze(
                sql=preset["sql"],
                message=message,
                config=config,
                db_dsn=db_dsn,
                message_id=message_id,
            )

        # 2. 获取账套列表
        account_sets = await AccountSet.filter(is_active=True).values("id", "name")

        # 3. 组装 system prompt
        system_prompt = build_sql_prompt(
            account_sets=list(account_sets),
            custom_system_prompt=config.get("ai.prompt.system"),
            custom_dict=config.get("ai.business_dict"),
            custom_shots=config.get("ai.few_shots"),
        )

        # 4. 调用 R1 生成 SQL
        messages = [{"role": "system", "content": system_prompt}]
        # 添加历史对话（最多 10 轮）
        for h in history[-20:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": message})

        r1_result = await call_deepseek(
            messages=messages,
            api_key=api_key,
            base_url=config.get("base_url", DEFAULT_BASE_URL),
            model=config.get("model_sql", DEFAULT_MODEL_SQL),
            temperature=0.0,
        )

        if r1_result is None:
            return {"type": "error", "message": "AI 服务暂时不可用，请稍后再试"}

        # 5. 处理 R1 响应
        resp_type = r1_result.get("type", "")

        if resp_type == "clarification":
            return {
                "type": "clarification",
                "message_id": message_id,
                "message": r1_result.get("message", "请补充更多信息"),
                "options": r1_result.get("options", []),
            }

        if resp_type != "sql" or not r1_result.get("sql"):
            return {"type": "error", "message": "AI 无法理解这个查询，请换个说法试试"}

        sql = r1_result["sql"]

        # 6. 自动纠错循环（最多 2 次重试）
        for attempt in range(3):
            # AST 安全校验
            is_safe, sanitized_sql, reason = validate_sql(sql)
            if not is_safe:
                logger.warning(f"SQL 校验失败: {reason}，SQL: {sql[:200]}")
                if attempt < 2:
                    # 反馈给 R1 重新生成
                    messages.append({"role": "assistant", "content": json.dumps(r1_result, ensure_ascii=False)})
                    messages.append({"role": "user", "content": f"你生成的 SQL 不安全被拒绝了，原因: {reason}。请重新生成一个合法的 SELECT 查询。"})
                    r1_result = await call_deepseek(
                        messages=messages,
                        api_key=api_key,
                        base_url=config.get("base_url", DEFAULT_BASE_URL),
                        model=config.get("model_sql", DEFAULT_MODEL_SQL),
                        temperature=0.0,
                    )
                    if r1_result and r1_result.get("sql"):
                        sql = r1_result["sql"]
                        continue
                return {"type": "error", "message": "查询无法执行，请换个说法试试"}

            # 执行 SQL
            try:
                result = await _execute_and_analyze(
                    sql=sanitized_sql,
                    message=message,
                    config=config,
                    db_dsn=db_dsn,
                    message_id=message_id,
                )
                return result
            except Exception as exec_err:
                err_msg = str(exec_err)[:200]
                logger.warning(f"SQL 执行失败（第{attempt+1}次）: {err_msg}")
                if attempt < 2:
                    messages.append({"role": "assistant", "content": json.dumps({"type": "sql", "sql": sql}, ensure_ascii=False)})
                    messages.append({"role": "user", "content": f"SQL 执行报错: {err_msg}。请修正 SQL。"})
                    r1_result = await call_deepseek(
                        messages=messages,
                        api_key=api_key,
                        base_url=config.get("base_url", DEFAULT_BASE_URL),
                        model=config.get("model_sql", DEFAULT_MODEL_SQL),
                        temperature=0.0,
                    )
                    if r1_result and r1_result.get("sql"):
                        sql = r1_result["sql"]
                        continue

        return {"type": "error", "message": "查询执行失败，请换个说法试试"}

    except Exception as e:
        logger.error(f"AI 聊天处理异常: {type(e).__name__}: {e}")
        return {"type": "error", "message": "AI 服务出现异常，请稍后再试"}


async def _execute_and_analyze(
    sql: str,
    message: str,
    config: dict,
    db_dsn: str,
    message_id: str,
) -> dict:
    """执行 SQL 并调用 V3 分析"""
    pool = await get_ai_pool(db_dsn)

    async with pool.acquire() as conn:
        # READ ONLY 事务
        async with conn.transaction(readonly=True):
            rows = await conn.fetch(sql)

    if not rows:
        return {
            "type": "answer",
            "message_id": message_id,
            "analysis": "查询没有返回数据。可能是条件范围内没有匹配的记录。",
            "table_data": None,
            "chart_config": None,
            "sql": sql,
            "row_count": 0,
        }

    # 转为列表格式
    columns = list(rows[0].keys())
    row_data = []
    for r in rows:
        row_data.append([_serialize_value(r[c]) for c in columns])

    # 限制传给 V3 的数据量（最多 100 行）
    analysis_rows = row_data[:100]

    # 调用 V3 分析
    analysis_prompt = build_analysis_prompt(config.get("ai.prompt.analysis"))
    data_summary = f"用户问题: {message}\n\nSQL: {sql}\n\n查询结果 ({len(rows)} 行):\n列: {columns}\n数据（前 {len(analysis_rows)} 行）:\n"
    for row in analysis_rows[:20]:  # prompt 中只放 20 行
        data_summary += str(row) + "\n"

    v3_result = await call_deepseek(
        messages=[
            {"role": "system", "content": analysis_prompt},
            {"role": "user", "content": data_summary},
        ],
        api_key=config["api_key"],
        base_url=config.get("base_url", DEFAULT_BASE_URL),
        model=config.get("model_analysis", DEFAULT_MODEL_ANALYSIS),
        temperature=0.7,
    )

    analysis_text = "查询完成。"
    chart_config = None
    if v3_result:
        analysis_text = v3_result.get("analysis", analysis_text)
        chart_config = v3_result.get("chart_config")

    return {
        "type": "answer",
        "message_id": message_id,
        "analysis": analysis_text,
        "table_data": {"columns": columns, "rows": row_data},
        "chart_config": chart_config,
        "sql": sql,
        "row_count": len(rows),
    }


def _serialize_value(val) -> str | int | float | None:
    """将数据库值序列化为 JSON 兼容格式"""
    if val is None:
        return None
    from decimal import Decimal
    from datetime import date, datetime
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    return val
