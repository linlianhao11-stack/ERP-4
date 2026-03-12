"""SQL 安全校验器 — 基于 sqlglot AST 解析"""
from __future__ import annotations
import sqlglot
from sqlglot import exp
from app.logger import get_logger

logger = get_logger("ai.sql_validator")

# 禁止访问的表（大小写不敏感匹配）
BLOCKED_TABLES = frozenset({"users", "system_settings"})

# 禁止的语句类型（根节点级别）
BLOCKED_STATEMENT_TYPES = (
    exp.Insert, exp.Update, exp.Delete,
    exp.Drop, exp.Alter, exp.Create, exp.TruncateTable,
)

# 额外的关键词级别拦截（处理 sqlglot 可能不识别的语句）
BLOCKED_KEYWORDS = frozenset({"grant", "revoke", "copy", "execute", "call"})

MAX_LIMIT = 1000


def validate_sql(sql: str) -> tuple[bool, str, str]:
    """
    校验 SQL 安全性。

    返回 (is_safe, sanitized_sql, rejection_reason)
    - is_safe=True 时 sanitized_sql 是处理后可执行的 SQL
    - is_safe=False 时 rejection_reason 说明拒绝原因
    """
    if not sql or not sql.strip():
        return False, "", "空 SQL"

    # 关键词级拦截（在解析前处理 sqlglot 可能不识别的语句）
    first_word = sql.strip().split()[0].lower() if sql.strip() else ""
    if first_word in BLOCKED_KEYWORDS:
        return False, "", f"禁止 {first_word.upper()} 语句"

    # 分号检测（多语句注入）
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        return False, "", "禁止多语句（检测到分号）"

    # 解析 AST
    try:
        statements = sqlglot.parse(stripped, dialect="postgres")
    except sqlglot.errors.ParseError as e:
        return False, "", f"SQL 解析失败: {e}"

    if not statements or statements[0] is None:
        return False, "", "SQL 解析结果为空"

    if len(statements) > 1:
        return False, "", "禁止多语句"

    statement = statements[0]

    # 检查根节点是否为禁止的 DML/DDL 类型
    for blocked in BLOCKED_STATEMENT_TYPES:
        if isinstance(statement, blocked):
            return False, "", f"禁止 {type(statement).__name__} 语句"

    # 根节点必须是 SELECT 或 Union（UNION/INTERSECT/EXCEPT 也由 SELECT 组成）
    if not isinstance(statement, (exp.Select, exp.Union)):
        return False, "", f"仅允许 SELECT 语句，检测到 {type(statement).__name__}"

    # 遍历 AST 检查所有节点
    for node in statement.walk():
        # 检查 DML/DDL 节点（防止嵌套）
        for blocked in BLOCKED_STATEMENT_TYPES:
            if isinstance(node, blocked):
                return False, "", f"检测到嵌套的 {type(node).__name__} 语句"

        # 检查 INTO（SELECT INTO）
        if isinstance(node, exp.Into):
            return False, "", "禁止 SELECT INTO"

        # 检查表引用
        if isinstance(node, exp.Table):
            table_name = (node.name or "").lower()
            if table_name in BLOCKED_TABLES:
                return False, "", f"禁止访问敏感表: {table_name}"

    # LIMIT 处理（只对 SELECT 追加，Union 根节点不直接加 LIMIT）
    sanitized = _enforce_limit(statement)

    return True, sanitized, ""


def _enforce_limit(statement: exp.Expression) -> str:
    """确保顶层 SELECT 有 LIMIT 且不超过 MAX_LIMIT"""
    if isinstance(statement, exp.Select):
        limit_node = statement.find(exp.Limit)

        if limit_node is None:
            # 无 LIMIT → 追加
            statement = statement.limit(MAX_LIMIT)
        else:
            # 有 LIMIT → 检查是否超限
            limit_expr = limit_node.expression
            if isinstance(limit_expr, exp.Literal) and limit_expr.is_int:
                val = int(limit_expr.this)
                if val > MAX_LIMIT:
                    limit_node.set("expression", exp.Literal.number(MAX_LIMIT))

        return statement.sql(dialect="postgres")
    else:
        # Union 等：直接生成 SQL（含已有 LIMIT）
        return statement.sql(dialect="postgres")
