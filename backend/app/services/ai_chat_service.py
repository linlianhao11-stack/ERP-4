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
from app.ai.preset_queries import DEFAULT_PRESET_QUERIES
from app.ai.business_dict import DEFAULT_BUSINESS_DICT
from app.ai.few_shots import DEFAULT_FEW_SHOTS
from app.ai.view_permissions import get_allowed_views
from app.ai.schema_registry import get_full_schema_text

logger = get_logger("ai.chat_service")

# 本地查询建议映射 — 小数据集回退用，按视图匹配
LOCAL_SUGGESTIONS = {
    "vw_sales": ["毛利分析", "客户销售排名", "产品销售排名"],
    "vw_purchase": ["供应商采购排名", "采购成本趋势"],
    "vw_inventory": ["缺货预警", "库存周转率"],
    "vw_receivable": ["客户欠款排名", "应收账龄分析"],
    "vw_payable": ["供应商应付汇总", "应付账龄分析"],
}


def _get_local_suggestions(sql: str) -> list[str]:
    """根据 SQL 内容匹配本地查询建议"""
    sql_lower = sql.lower()
    for prefix, suggestions in LOCAL_SUGGESTIONS.items():
        if prefix in sql_lower:
            return suggestions[:3]
    return []


# AI 专用连接池（与 Tortoise ORM 完全分离）
_ai_pool: asyncpg.Pool | None = None
_pool_dsn: str | None = None

# 并发限制 — 防止同时向 DeepSeek API 发送过多请求
_ai_semaphore = asyncio.Semaphore(3)  # spec 要求 DeepSeek 最大并发 3

# 配置缓存
_config_cache: dict | None = None
_config_cache_time: float = 0
CONFIG_CACHE_TTL = 300  # 5 分钟

# 查询结果缓存 — 相同问题短时间内不重复调用 API
_query_cache: dict[str, tuple[float, dict]] = {}
QUERY_CACHE_TTL = 300  # 5 分钟
QUERY_CACHE_MAX = 50   # 最多缓存 50 条


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

    # JSON 配置 — 数据库无值时使用代码默认值
    _json_defaults = {
        "ai.business_dict": DEFAULT_BUSINESS_DICT,
        "ai.few_shots": DEFAULT_FEW_SHOTS,
        "ai.preset_queries": DEFAULT_PRESET_QUERIES,
    }
    for json_key in _json_defaults:
        raw = settings_map.get(json_key)
        if raw:
            try:
                parsed = json.loads(raw)
                config[json_key] = parsed if parsed else _json_defaults[json_key]
            except json.JSONDecodeError:
                config[json_key] = _json_defaults[json_key]
        else:
            config[json_key] = _json_defaults[json_key]

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


async def get_preset_queries(user_permissions: list[str] | None = None) -> list[dict]:
    """获取预设快捷问题列表（仅 display 字段，不暴露 sql/keywords），按权限过滤"""
    try:
        config = await _get_config()
        raw = config.get("ai.preset_queries") or DEFAULT_PRESET_QUERIES
        result = []
        for q in raw:
            if not q.get("display"):
                continue
            perm = q.get("permission")
            if perm and user_permissions is not None and perm not in user_permissions:
                continue
            result.append({"display": q["display"]})
        return result
    except Exception:
        return [{"display": q["display"]} for q in DEFAULT_PRESET_QUERIES if q.get("display")]


async def process_chat(
    message: str,
    history: list[dict],
    user_id: int,
    db_dsn: str,
    user_permissions: list[str] | None = None,
):
    """处理用户聊天消息，yield SSE 事件 dict"""
    import time as _time
    from datetime import date

    # 查询缓存
    cache_key = f"{user_id}:{date.today().isoformat()}:{message.strip().lower()}"
    now = _time.time()
    cached = _query_cache.get(cache_key)
    if cached:
        cached_time, cached_result = cached
        if now - cached_time < QUERY_CACHE_TTL:
            logger.info(f"命中查询缓存: {message[:30]}")
            yield {"event": "done", "data": {**cached_result, "message_id": str(uuid.uuid4())}}
            return
        else:
            del _query_cache[cache_key]

    message_id = str(uuid.uuid4())

    async with _ai_semaphore:
        try:
            async for event in _process_chat_inner(message, history, user_id, db_dsn, message_id, user_permissions=user_permissions):
                yield event
                # 缓存最终结果
                if event.get("event") == "done":
                    result = event["data"]
                    if result.get("type") in ("answer", "clarification"):
                        if len(_query_cache) >= QUERY_CACHE_MAX:
                            expired = [k for k, (t, _) in _query_cache.items() if now - t >= QUERY_CACHE_TTL]
                            for k in expired:
                                del _query_cache[k]
                            if len(_query_cache) >= QUERY_CACHE_MAX:
                                oldest_key = min(_query_cache, key=lambda k: _query_cache[k][0])
                                del _query_cache[oldest_key]
                        _query_cache[cache_key] = (now, result)
        except asyncio.CancelledError:
            logger.info(f"客户端断开连接，取消查询: {message[:30]}")
            return


async def _process_chat_inner(
    message: str,
    history: list[dict],
    user_id: int,
    db_dsn: str,
    message_id: str,
    user_permissions: list[str] | None = None,
):
    try:
        import time as _time
        _t0 = _time.monotonic()

        yield {"event": "progress", "data": {"stage": "thinking", "message": "正在理解问题..."}}

        config = await _get_config()
        api_key = config.get("api_key")
        if not api_key:
            yield {"event": "error", "data": {"message": "AI 助手未配置，请联系管理员设置 DeepSeek API Key", "retryable": False, "error_type": "config"}}
            return

        # 计算用户允许访问的视图/表（None=admin 不限制）
        allowed = get_allowed_views(user_permissions) if user_permissions is not None else None

        # 意图预分类（按权限过滤预设）
        all_presets = config.get("ai.preset_queries") or DEFAULT_PRESET_QUERIES
        if user_permissions is not None:
            filtered_presets = [p for p in all_presets if p.get("permission", "ai_chat") in user_permissions]
        else:
            filtered_presets = all_presets
        preset = classify_intent(message, filtered_presets)
        if preset and preset.get("sql"):
            ok, _, reason = validate_sql(preset["sql"], allowed_tables=allowed)
            if not ok:
                yield {"event": "error", "data": {"message": f"你没有查询该数据的权限", "retryable": False, "error_type": "forbidden"}}
                return
            yield {"event": "progress", "data": {"stage": "executing", "message": "正在查询数据库..."}}
            result = await _execute_and_analyze(sql=preset["sql"], message=message, config=config, db_dsn=db_dsn, message_id=message_id)
            yield {"event": "done", "data": result}
            return

        # 获取账套列表
        account_sets = await AccountSet.filter(is_active=True).values("id", "name")

        # 组装 system prompt（按权限过滤 schema）
        schema_text = get_full_schema_text(allowed_views=allowed)
        system_prompt = build_sql_prompt(
            account_sets=list(account_sets),
            custom_system_prompt=config.get("ai.prompt.system"),
            custom_dict=config.get("ai.business_dict"),
            custom_shots=config.get("ai.few_shots"),
            schema_text=schema_text,
        )

        # 调用 DeepSeek 生成 SQL
        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-50:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": message})

        yield {"event": "progress", "data": {"stage": "generating", "message": "正在生成查询..."}}

        _t1 = _time.monotonic()
        r1_result = await call_deepseek(
            messages=messages,
            api_key=api_key,
            base_url=config.get("base_url", DEFAULT_BASE_URL),
            model=config.get("model_sql", DEFAULT_MODEL_SQL),
            temperature=0.0,
        )
        _t2 = _time.monotonic()
        logger.info(f"SQL 生成耗时: {_t2 - _t1:.1f}s")

        if r1_result is None:
            yield {"event": "error", "data": {"message": "AI 服务暂时不可用，请稍后再试", "retryable": True, "error_type": "api"}}
            return

        resp_type = r1_result.get("type", "")

        if resp_type == "clarification":
            yield {"event": "done", "data": {
                "type": "clarification",
                "message_id": message_id,
                "message": r1_result.get("message", "请补充更多信息"),
                "options": r1_result.get("options", []),
            }}
            return

        if resp_type == "text":
            yield {"event": "done", "data": {
                "type": "answer",
                "message_id": message_id,
                "analysis": r1_result.get("message", ""),
            }}
            return

        if resp_type != "sql" or not r1_result.get("sql"):
            yield {"event": "done", "data": {"type": "clarification", "message_id": message_id, "message": "我是业务数据查询助手，只能帮你查询 ERP 系统中的销售、采购、库存、应收应付等数据。请试试问我具体的业务问题吧！", "options": ["本月销售概况", "库存状态", "应收账款汇总"]}}
            return

        sql = r1_result["sql"]

        # 自动纠错循环
        for attempt in range(3):
            is_safe, sanitized_sql, reason = validate_sql(sql, allowed_tables=allowed)
            if not is_safe:
                logger.warning(f"SQL 校验失败: {reason}，SQL: {sql[:200]}")
                if attempt < 2:
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
                yield {"event": "error", "data": {"message": "查询无法执行，请换个说法试试", "retryable": True, "error_type": "validation"}}
                return

            try:
                yield {"event": "progress", "data": {"stage": "executing", "message": "正在查询数据库..."}}
                result = await _execute_and_analyze(
                    sql=sanitized_sql,
                    message=message,
                    config=config,
                    db_dsn=db_dsn,
                    message_id=message_id,
                )
                yield {"event": "done", "data": result}
                return
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

        yield {"event": "error", "data": {"message": "查询执行失败，请换个说法试试", "retryable": True, "error_type": "execution"}}

    except Exception as e:
        logger.error(f"AI 聊天处理异常: {type(e).__name__}: {e}")
        yield {"event": "error", "data": {"message": "AI 服务出现异常，请稍后再试", "retryable": True, "error_type": "server"}}


async def _execute_and_analyze(
    sql: str,
    message: str,
    config: dict,
    db_dsn: str,
    message_id: str,
) -> dict:
    """执行 SQL 并调用 V3 分析"""
    import time as _time
    _t0 = _time.monotonic()

    pool = await get_ai_pool(db_dsn)

    async with pool.acquire() as conn:
        # READ ONLY 事务
        async with conn.transaction(readonly=True):
            rows = await conn.fetch(sql)

    _t1 = _time.monotonic()
    logger.info(f"SQL 执行耗时: {_t1 - _t0:.2f}s, 行数: {len(rows)}")

    if not rows:
        return {
            "type": "answer",
            "message_id": message_id,
            "analysis": "没查到符合条件的数据，可能这个时间段或范围内确实没有相关记录。",
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

    # 小数据集（≤10 行）：本地生成摘要，跳过分析 API 调用（省 15-20s）
    if len(rows) <= 10:
        analysis_text = _build_local_summary(columns, row_data, message)
        logger.info(f"本地摘要（{len(rows)} 行），跳过分析 API，总耗时: {_time.monotonic() - _t0:.1f}s")
        return {
            "type": "answer",
            "message_id": message_id,
            "analysis": analysis_text,
            "table_data": {"columns": columns, "rows": row_data},
            "chart_config": None,
            "sql": sql,
            "row_count": len(rows),
            "suggestions": _get_local_suggestions(sql),
        }

    # 大数据集：调用分析模型（限制 max_tokens 加速）
    analysis_rows = row_data[:100]
    analysis_prompt = build_analysis_prompt(config.get("ai.prompt.analysis"))
    data_summary = f"用户问题: {message}\n\nSQL: {sql}\n\n查询结果 ({len(rows)} 行):\n列: {columns}\n数据（前 {len(analysis_rows)} 行）:\n"
    for row in analysis_rows[:20]:  # prompt 中只放 20 行
        data_summary += str(row) + "\n"

    _t2 = _time.monotonic()
    v3_result = await call_deepseek(
        messages=[
            {"role": "system", "content": analysis_prompt},
            {"role": "user", "content": data_summary},
        ],
        api_key=config["api_key"],
        base_url=config.get("base_url", DEFAULT_BASE_URL),
        model=config.get("model_analysis", DEFAULT_MODEL_ANALYSIS),
        temperature=0.7,
        max_tokens=1024,
    )
    _t3 = _time.monotonic()
    logger.info(f"数据分析耗时: {_t3 - _t2:.1f}s, 总耗时: {_t3 - _t0:.1f}s")

    analysis_text = "查询完成。"
    chart_config = None
    suggestions = None
    if v3_result:
        analysis_text = v3_result.get("analysis", analysis_text)
        chart_config = v3_result.get("chart_config")
        suggestions = v3_result.get("suggestions")

    return {
        "type": "answer",
        "message_id": message_id,
        "analysis": analysis_text,
        "table_data": {"columns": columns, "rows": row_data},
        "chart_config": chart_config,
        "sql": sql,
        "row_count": len(rows),
        "suggestions": suggestions,
    }


_COL_LABEL_MAP = {
    "amount": "金额", "total_amount": "总金额", "销售额": "销售额",
    "profit": "毛利", "total_profit": "总毛利", "毛利": "毛利",
    "cost": "成本", "total_cost": "总成本", "成本": "成本",
    "stock_value": "库存金额", "库存金额": "库存金额",
    "unreceived_amount": "未收金额", "未收": "未收",
    "unpaid_amount": "未付金额", "未付总额": "未付总额",
    "received_amount": "已收金额", "已收": "已收",
    "paid_amount": "已付金额",
    "profit_rate": "毛利率", "毛利率": "毛利率",
    "quantity": "数量", "数量": "数量",
    "order_count": "订单数", "订单数": "订单数",
    "bill_count": "笔数", "笔数": "笔数",
    "采购金额": "采购金额", "应收总额": "应收总额", "欠款总额": "欠款总额",
}

_AMOUNT_COLS = {
    "amount", "total_amount", "profit", "total_profit", "cost", "total_cost",
    "stock_value", "unreceived_amount", "unpaid_amount", "received_amount", "paid_amount",
    "销售额", "毛利", "成本", "库存金额", "未收", "已收", "未付总额", "欠款总额",
    "采购金额", "应收总额", "总金额", "总毛利", "总成本",
}


def _build_local_summary(columns: list[str], row_data: list[list], question: str) -> str:
    """为小数据集生成本地摘要，避免调用分析 API"""
    n = len(row_data)

    summaries = []
    for i, col in enumerate(columns):
        if col.lower() in _AMOUNT_COLS or col in _AMOUNT_COLS:
            vals = [r[i] for r in row_data if isinstance(r[i], (int, float))]
            if vals:
                total = sum(vals)
                label = _COL_LABEL_MAP.get(col.lower(), _COL_LABEL_MAP.get(col, col))
                if total >= 10000:
                    summaries.append(f"**{label}** 合计 {total / 10000:.2f} 万")
                else:
                    summaries.append(f"**{label}** 合计 {total:,.2f}")

    parts = [f"查到 **{n}** 条数据"]
    if summaries:
        parts.append("，" + "、".join(summaries))
    parts.append("，详细看下面表格。")
    return "".join(parts)


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
