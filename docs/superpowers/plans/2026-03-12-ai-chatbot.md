# ERP-4 AI Chatbot 实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 ERP-4 中集成 AI 数据助手，用户通过自然语言查询业务数据，系统自动生成 SQL、执行查询、分析结果并可视化展示。

**Architecture:** NL2SQL 双模型架构 — DeepSeek R1 生成 SQL（temp=0.0），sqlglot AST 校验安全性，PostgreSQL 只读用户执行，DeepSeek V3 分析结果（temp=0.7）。四层安全纵深防御确保绝对只读。AI 模块完全隔离，故障不影响 ERP 主业务。

**Tech Stack:** FastAPI + asyncpg（独立连接池） + sqlglot + cryptography（Fernet） + httpx | Vue 3 + Chart.js

**Spec:** `docs/superpowers/specs/2026-03-12-ai-chatbot-design.md`

---

## File Structure

### Backend — 新建文件

| 文件 | 职责 |
|------|------|
| `backend/app/ai/__init__.py` | AI 模块入口，配置缓存 + 连接池管理 |
| `backend/app/ai/encryption.py` | Fernet AES 加密/解密 API Key |
| `backend/app/ai/sql_validator.py` | sqlglot AST 安全校验 |
| `backend/app/ai/rate_limiter.py` | 内存滑动窗口限流器 |
| `backend/app/ai/schema_registry.py` | 视图+表 schema 文本生成 |
| `backend/app/ai/business_dict.py` | 默认业务词典 |
| `backend/app/ai/few_shots.py` | 默认 few-shot 示例 |
| `backend/app/ai/intent_classifier.py` | 意图预分类 + 预置 SQL 模板 |
| `backend/app/ai/deepseek_client.py` | DeepSeek R1/V3 API 客户端 |
| `backend/app/ai/prompt_builder.py` | System prompt 组装器 |
| `backend/app/ai/views.sql` | 7 个语义视图 DDL |
| `backend/app/ai/health_check.py` | 维护健康检查脚本 |
| `backend/app/routers/ai_chat.py` | AI 聊天 + 导出 + 反馈 + 状态路由 |
| `backend/app/routers/api_keys.py` | API 密钥 + AI 配置管理路由 |
| `backend/app/services/ai_chat_service.py` | NL2SQL 主流程编排 |
| `backend/app/schemas/ai.py` | AI 相关 Pydantic schemas |
| `backend/tests/__init__.py` | 测试包初始化 |
| `backend/tests/test_sql_validator.py` | SQL 校验器测试（安全核心） |
| `backend/tests/test_encryption.py` | 加密工具测试 |
| `backend/tests/test_rate_limiter.py` | 限流器测试 |

### Backend — 修改文件

| 文件 | 改动 |
|------|------|
| `backend/requirements.txt` | 添加 sqlglot, cryptography, pytest |
| `backend/app/migrations.py` | 添加 AI 只读用户 + 语义视图迁移 |
| `backend/main.py` | 注册 AI 路由 + lifespan 管理 AI 连接池 |
| `backend/app/config.py` | 添加 AI_DB_PASSWORD 配置 |
| `backend/app/services/logistics_service.py` | KD100 配置迁移到 SystemSetting |
| `docker-compose.yml`（项目根目录） | 添加 API_KEYS_ENCRYPTION_SECRET + AI_DB_PASSWORD |

### Frontend — 新建文件

| 文件 | 职责 |
|------|------|
| `frontend/src/api/ai.js` | AI 聊天 + 配置管理 API |
| `frontend/src/components/business/settings/ApiKeysPanel.vue` | AI 配置管理面板（5 折叠区） |
| `frontend/src/components/business/AiChatbot.vue` | 聊天浮窗主组件 |
| `frontend/src/components/business/AiMessage.vue` | 单条消息渲染 |
| `frontend/src/components/business/AiChartRenderer.vue` | Chart.js 图表渲染 |

### Frontend — 修改文件

| 文件 | 改动 |
|------|------|
| `frontend/src/views/SettingsView.vue` | 添加 AI 助手配置 Tab（仅 admin） |
| `frontend/src/App.vue` | 挂载 AiChatbot 浮窗 + 登录后检查 AI 可用性 |

---

## Chunk 1: Backend Foundation

### Task 1: Dependencies + Encryption Utility

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/ai/__init__.py`
- Create: `backend/app/ai/encryption.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_encryption.py`

- [ ] **Step 1: Update requirements.txt**

在 `backend/requirements.txt` 末尾添加：

```
sqlglot>=26.0.0
cryptography>=44.0.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 2: Create AI module init**

Create `backend/app/ai/__init__.py`:

```python
"""AI 数据助手模块 — 与 ERP 主业务完全隔离"""
from __future__ import annotations
```

- [ ] **Step 3: Write encryption tests**

Create `backend/tests/__init__.py` (empty file).

Create `backend/tests/test_encryption.py`:

```python
"""加密工具测试"""
from __future__ import annotations
import os
import pytest

os.environ.setdefault("API_KEYS_ENCRYPTION_SECRET", "test-secret-key-for-unit-tests-only")

from app.ai.encryption import encrypt_value, decrypt_value, mask_key


class TestEncryption:
    def test_roundtrip(self):
        original = "sk-abc123xyz"
        encrypted = encrypt_value(original)
        assert encrypted != original
        assert decrypt_value(encrypted) == original

    def test_empty_string(self):
        assert encrypt_value("") == ""
        assert decrypt_value("") == ""

    def test_none_value(self):
        assert encrypt_value(None) == ""
        assert decrypt_value(None) == ""

    def test_different_encryptions_same_input(self):
        """Fernet 每次加密结果不同（包含时间戳和 IV）"""
        a = encrypt_value("same")
        b = encrypt_value("same")
        assert a != b
        assert decrypt_value(a) == decrypt_value(b) == "same"

    def test_invalid_ciphertext(self):
        assert decrypt_value("not-valid-base64!") is None

    def test_mask_key_short(self):
        assert mask_key("sk-ab") == "sk-a***"

    def test_mask_key_long(self):
        assert mask_key("sk-abcdefghijklmnop") == "sk-abc***"

    def test_mask_key_empty(self):
        assert mask_key("") == ""
        assert mask_key(None) == ""
```

- [ ] **Step 4: Run tests — expect FAIL**

```bash
cd /Users/lin/Desktop/ERP-4-main/backend && python -m pytest tests/test_encryption.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.ai.encryption'`

- [ ] **Step 5: Implement encryption.py**

Create `backend/app/ai/encryption.py`:

```python
"""API Key 加密/解密工具 — Fernet 对称加密"""
from __future__ import annotations
import base64
import hashlib
import os
from cryptography.fernet import Fernet, InvalidToken
from app.logger import get_logger

logger = get_logger("ai.encryption")


def _get_fernet() -> Fernet:
    """从环境变量派生 Fernet 密钥（32 字节 base64），惰性读取"""
    secret = os.environ.get("API_KEYS_ENCRYPTION_SECRET", "")
    if not secret:
        raise RuntimeError("API_KEYS_ENCRYPTION_SECRET 环境变量未设置")
    # 用 SHA-256 将任意长度 secret 转为 32 字节密钥
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_value(plaintext: str | None) -> str:
    """加密明文，返回 base64 密文字符串"""
    if not plaintext:
        return ""
    try:
        return _get_fernet().encrypt(plaintext.encode()).decode()
    except Exception:
        logger.error("加密失败")
        return ""


def decrypt_value(ciphertext: str | None) -> str | None:
    """解密密文，返回明文。解密失败返回 None"""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        logger.warning("解密失败，可能密钥已变更")
        return None


def mask_key(key: str | None) -> str:
    """脱敏显示 API Key: sk-abc***"""
    if not key:
        return ""
    visible = min(max(len(key) // 3, 3), 6)
    return key[:visible] + "***"
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
cd /Users/lin/Desktop/ERP-4-main/backend && python -m pytest tests/test_encryption.py -v
```

Expected: 8 passed

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/ai/__init__.py backend/app/ai/encryption.py backend/tests/__init__.py backend/tests/test_encryption.py
git commit -m "feat(ai): 添加加密工具 + 测试基础设施"
```

---

### Task 2: SQL Validator（安全核心）

**Files:**
- Create: `backend/app/ai/sql_validator.py`
- Create: `backend/tests/test_sql_validator.py`

- [ ] **Step 1: Write comprehensive SQL validator tests**

Create `backend/tests/test_sql_validator.py`:

```python
"""SQL 校验器测试 — 覆盖正常 SQL 和各类攻击向量"""
from __future__ import annotations
import pytest
from app.ai.sql_validator import validate_sql

# ===== 合法 SQL =====

class TestValidSQL:
    def test_simple_select(self):
        ok, sql, reason = validate_sql("SELECT * FROM vw_sales_detail")
        assert ok
        assert "LIMIT" in sql.upper()

    def test_select_with_where(self):
        ok, sql, _ = validate_sql(
            "SELECT customer_name, SUM(amount) FROM vw_sales_detail "
            "WHERE order_date >= '2024-01-01' GROUP BY customer_name"
        )
        assert ok

    def test_select_with_join(self):
        ok, sql, _ = validate_sql(
            "SELECT a.name, b.quantity FROM products a "
            "JOIN warehouse_stocks b ON a.id = b.product_id"
        )
        assert ok

    def test_select_with_subquery(self):
        ok, sql, _ = validate_sql(
            "SELECT * FROM vw_sales_detail WHERE customer_name IN "
            "(SELECT name FROM customers WHERE id > 5)"
        )
        assert ok

    def test_limit_preserved(self):
        ok, sql, _ = validate_sql("SELECT * FROM products LIMIT 50")
        assert ok
        assert "LIMIT 50" in sql.upper() or "LIMIT 50" in sql

    def test_limit_capped_at_1000(self):
        ok, sql, _ = validate_sql("SELECT * FROM products LIMIT 5000")
        assert ok
        assert "1000" in sql

    def test_auto_limit_added(self):
        ok, sql, _ = validate_sql("SELECT * FROM products")
        assert ok
        assert "LIMIT" in sql.upper()

    def test_count_query(self):
        ok, sql, _ = validate_sql("SELECT COUNT(*) FROM vw_sales_summary")
        assert ok

    def test_case_when(self):
        ok, sql, _ = validate_sql(
            "SELECT CASE WHEN amount > 1000 THEN 'high' ELSE 'low' END FROM vw_sales_detail"
        )
        assert ok

    def test_cte_query(self):
        ok, sql, _ = validate_sql(
            "WITH top_customers AS (SELECT customer_name, SUM(amount) AS total "
            "FROM vw_sales_detail GROUP BY customer_name ORDER BY total DESC LIMIT 10) "
            "SELECT * FROM top_customers"
        )
        assert ok

# ===== DML/DDL 攻击 =====

class TestDMLDDLAttacks:
    def test_insert(self):
        ok, _, reason = validate_sql("INSERT INTO users (username) VALUES ('hacker')")
        assert not ok
        assert reason

    def test_update(self):
        ok, _, reason = validate_sql("UPDATE users SET role = 'admin' WHERE id = 1")
        assert not ok

    def test_delete(self):
        ok, _, reason = validate_sql("DELETE FROM orders WHERE id > 0")
        assert not ok

    def test_drop_table(self):
        ok, _, reason = validate_sql("DROP TABLE users")
        assert not ok

    def test_alter_table(self):
        ok, _, reason = validate_sql("ALTER TABLE users ADD COLUMN hack TEXT")
        assert not ok

    def test_truncate(self):
        ok, _, reason = validate_sql("TRUNCATE TABLE orders")
        assert not ok

    def test_create_table(self):
        ok, _, reason = validate_sql("CREATE TABLE evil (id INT)")
        assert not ok

# ===== 注入攻击 =====

class TestInjectionAttacks:
    def test_semicolon_multi_statement(self):
        ok, _, reason = validate_sql(
            "SELECT 1; DROP TABLE users"
        )
        assert not ok

    def test_select_into(self):
        ok, _, reason = validate_sql(
            "SELECT * INTO new_table FROM products"
        )
        assert not ok

    def test_union_select_users(self):
        """UNION 访问敏感表"""
        ok, _, reason = validate_sql(
            "SELECT name FROM products UNION SELECT password_hash FROM users"
        )
        assert not ok

    def test_subquery_access_users(self):
        """子查询访问敏感表"""
        ok, _, reason = validate_sql(
            "SELECT * FROM products WHERE name IN (SELECT username FROM users)"
        )
        assert not ok

    def test_access_system_settings(self):
        ok, _, reason = validate_sql("SELECT * FROM system_settings")
        assert not ok

# ===== 边界情况 =====

class TestEdgeCases:
    def test_empty_string(self):
        ok, _, reason = validate_sql("")
        assert not ok

    def test_nonsense(self):
        ok, _, reason = validate_sql("this is not sql at all")
        assert not ok

    def test_comment_only(self):
        ok, _, reason = validate_sql("-- just a comment")
        assert not ok

    def test_whitespace_only(self):
        ok, _, reason = validate_sql("   \n\t  ")
        assert not ok
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd /Users/lin/Desktop/ERP-4-main/backend && python -m pytest tests/test_sql_validator.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement SQL validator**

Create `backend/app/ai/sql_validator.py`:

```python
"""SQL 安全校验器 — 基于 sqlglot AST 解析"""
from __future__ import annotations
import sqlglot
from sqlglot import exp
from app.logger import get_logger

logger = get_logger("ai.sql_validator")

# 禁止访问的表（大小写不敏感匹配）
BLOCKED_TABLES = frozenset({"users", "system_settings"})

# 禁止的语句类型
BLOCKED_STATEMENT_TYPES = (
    exp.Insert, exp.Update, exp.Delete,
    exp.Drop, exp.AlterTable, exp.Create,
)

# 额外的关键词级别拦截（处理 sqlglot 解析差异）
BLOCKED_KEYWORDS = frozenset({"truncate", "grant", "revoke", "copy", "execute", "call"})

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

    # 根节点必须是 SELECT（含 CTE）
    if not isinstance(statement, exp.Select):
        # 检查是否是 DML/DDL
        for blocked in BLOCKED_STATEMENT_TYPES:
            if isinstance(statement, blocked):
                return False, "", f"禁止 {type(statement).__name__} 语句"
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

    # LIMIT 处理
    sanitized = _enforce_limit(statement)

    return True, sanitized, ""


def _enforce_limit(statement: exp.Select) -> str:
    """确保 SELECT 有 LIMIT 且不超过 MAX_LIMIT"""
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
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd /Users/lin/Desktop/ERP-4-main/backend && python -m pytest tests/test_sql_validator.py -v
```

Expected: 全部通过。如有失败，根据具体错误调整实现。

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/sql_validator.py backend/tests/test_sql_validator.py
git commit -m "feat(ai): SQL 安全校验器 + 全面攻击测试覆盖"
```

---

### Task 3: Rate Limiter

**Files:**
- Create: `backend/app/ai/rate_limiter.py`
- Create: `backend/tests/test_rate_limiter.py`

- [ ] **Step 1: Write rate limiter tests**

Create `backend/tests/test_rate_limiter.py`:

```python
"""限流器测试"""
from __future__ import annotations
import time
import pytest
from app.ai.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_allows_under_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.allow("user1")

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.allow("user1")
        assert limiter.allow("user1")
        assert not limiter.allow("user1")

    def test_independent_keys(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.allow("user1")
        assert limiter.allow("user2")
        assert not limiter.allow("user1")

    def test_window_expiry(self):
        limiter = RateLimiter(max_requests=1, window_seconds=0.1)
        assert limiter.allow("user1")
        assert not limiter.allow("user1")
        time.sleep(0.15)
        assert limiter.allow("user1")

    def test_cleanup_old_entries(self):
        limiter = RateLimiter(max_requests=100, window_seconds=0.05)
        for i in range(50):
            limiter.allow(f"user{i}")
        time.sleep(0.1)
        # 新请求应触发清理
        limiter.allow("cleanup_trigger")
        # 旧条目应被清理（内部实现细节，不直接测试）
        assert limiter.allow("user0")
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd /Users/lin/Desktop/ERP-4-main/backend && python -m pytest tests/test_rate_limiter.py -v
```

- [ ] **Step 3: Implement rate limiter**

Create `backend/app/ai/rate_limiter.py`:

```python
"""内存滑动窗口限流器 — 单容器部署，无需 Redis"""
from __future__ import annotations
import time
from collections import defaultdict


class RateLimiter:
    """基于滑动窗口的限流器"""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.monotonic()

    def allow(self, key: str) -> bool:
        """检查是否允许请求。返回 True=放行，False=限流"""
        now = time.monotonic()

        # 定期清理（每 60 秒）
        if now - self._last_cleanup > 60:
            self._cleanup(now)

        # 移除窗口外的旧记录
        timestamps = self._requests[key]
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)

        if len(timestamps) >= self.max_requests:
            return False

        timestamps.append(now)
        return True

    def _cleanup(self, now: float) -> None:
        """清理过期的 key"""
        self._last_cleanup = now
        cutoff = now - self.window_seconds
        expired_keys = [
            k for k, v in self._requests.items()
            if not v or v[-1] < cutoff
        ]
        for k in expired_keys:
            del self._requests[k]


# 全局实例（按 spec 配置）
user_limiter = RateLimiter(max_requests=10, window_seconds=60)
global_limiter = RateLimiter(max_requests=60, window_seconds=60)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd /Users/lin/Desktop/ERP-4-main/backend && python -m pytest tests/test_rate_limiter.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/rate_limiter.py backend/tests/test_rate_limiter.py
git commit -m "feat(ai): 内存滑动窗口限流器"
```

---

### Task 4: Pydantic Schemas + Config Helpers

**Files:**
- Create: `backend/app/schemas/ai.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Create AI schemas**

Create `backend/app/schemas/ai.py`:

```python
"""AI 模块 Pydantic Schemas"""
from __future__ import annotations
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)


class ChatResponse(BaseModel):
    type: str  # "answer" | "clarification" | "error"
    message_id: str | None = None
    analysis: str | None = None
    table_data: dict | None = None
    chart_config: dict | None = None
    sql: str | None = None
    row_count: int | None = None
    message: str | None = None
    options: list[str] | None = None


class ExportRequest(BaseModel):
    table_data: dict
    title: str = "AI查询结果"


class FeedbackRequest(BaseModel):
    message_id: str
    feedback: str = Field(..., pattern="^(positive|negative)$")
    save_as_example: bool = False
    original_question: str | None = None
    sql: str | None = None
    negative_reason: str | None = None


class ApiKeysUpdate(BaseModel):
    """API 密钥更新 — 字段全部可选，只更新传入的"""
    class Config:
        extra = "allow"


class AiConfigUpdate(BaseModel):
    prompt_system: str | None = None
    prompt_analysis: str | None = None
    business_dict: list | None = None
    few_shots: list | None = None
    preset_queries: list | None = None
```

- [ ] **Step 2: Update config.py**

在 `backend/app/config.py` 末尾添加：

```python
# AI 数据库只读用户密码
AI_DB_PASSWORD = os.environ.get("AI_DB_PASSWORD", "")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/ai.py backend/app/config.py
git commit -m "feat(ai): Pydantic schemas + AI 数据库配置"
```

---

## Chunk 2: AI Core Engine

### Task 5: Schema Registry + Business Dict + Few-shots

**Files:**
- Create: `backend/app/ai/schema_registry.py`
- Create: `backend/app/ai/business_dict.py`
- Create: `backend/app/ai/few_shots.py`

- [ ] **Step 1: Create schema registry**

Create `backend/app/ai/schema_registry.py`:

```python
"""Schema 注册器 — 从 ORM models 和视图定义生成 LLM 可读的 schema 描述"""
from __future__ import annotations
from tortoise import Tortoise
from app.logger import get_logger

logger = get_logger("ai.schema_registry")

# 排除的表和列
EXCLUDED_TABLES = frozenset({"users", "system_settings", "aerich"})
SENSITIVE_COLUMNS = frozenset({
    "password_hash", "tax_id", "bank_account", "bank_name",
    "token_version", "must_change_password",
})

# 语义视图 schema（手动维护，与 views.sql 同步）
VIEW_SCHEMAS = {
    "vw_sales_detail": {
        "description": "销售明细宽表 — 每行一个订单商品",
        "columns": [
            ("order_no", "VARCHAR", "销售单号"),
            ("order_date", "DATE", "订单日期"),
            ("order_type", "VARCHAR", "订单类型: normal/account_period"),
            ("customer_name", "VARCHAR", "客户名称"),
            ("salesperson_name", "VARCHAR", "业务员"),
            ("sku", "VARCHAR", "产品SKU"),
            ("product_name", "VARCHAR", "产品名称"),
            ("brand", "VARCHAR", "品牌"),
            ("category", "VARCHAR", "分类"),
            ("quantity", "INT", "数量"),
            ("unit_price", "DECIMAL", "单价"),
            ("amount", "DECIMAL", "金额"),
            ("cost", "DECIMAL", "成本"),
            ("profit", "DECIMAL", "毛利"),
            ("profit_rate", "DECIMAL", "毛利率(%)"),
            ("account_set_name", "VARCHAR", "账套名称"),
        ],
    },
    "vw_sales_summary": {
        "description": "销售按月汇总",
        "columns": [
            ("year_month", "VARCHAR", "年月 如 2024-03"),
            ("order_count", "INT", "订单数"),
            ("total_amount", "DECIMAL", "总销售额"),
            ("total_cost", "DECIMAL", "总成本"),
            ("total_profit", "DECIMAL", "总毛利"),
            ("profit_rate", "DECIMAL", "毛利率(%)"),
            ("customer_count", "INT", "客户数"),
            ("account_set_name", "VARCHAR", "账套名称"),
        ],
    },
    "vw_purchase_detail": {
        "description": "采购明细宽表 — 每行一个采购商品",
        "columns": [
            ("po_no", "VARCHAR", "采购单号"),
            ("purchase_date", "DATE", "采购日期"),
            ("supplier_name", "VARCHAR", "供应商名称"),
            ("sku", "VARCHAR", "产品SKU"),
            ("product_name", "VARCHAR", "产品名称"),
            ("brand", "VARCHAR", "品牌"),
            ("quantity", "INT", "数量"),
            ("tax_inclusive_price", "DECIMAL", "含税单价"),
            ("tax_exclusive_price", "DECIMAL", "去税单价"),
            ("amount", "DECIMAL", "金额"),
            ("status", "VARCHAR", "采购单状态"),
            ("account_set_name", "VARCHAR", "账套名称"),
        ],
    },
    "vw_inventory_status": {
        "description": "当前库存状态快照",
        "columns": [
            ("sku", "VARCHAR", "产品SKU"),
            ("product_name", "VARCHAR", "产品名称"),
            ("brand", "VARCHAR", "品牌"),
            ("warehouse_name", "VARCHAR", "仓库名称"),
            ("location_name", "VARCHAR", "库位名称"),
            ("quantity", "INT", "库存数量"),
            ("reserved_qty", "INT", "预留数量"),
            ("available_qty", "INT", "可用数量"),
            ("avg_cost", "DECIMAL", "加权平均成本"),
            ("stock_value", "DECIMAL", "库存金额"),
        ],
    },
    "vw_inventory_turnover": {
        "description": "库存周转分析",
        "columns": [
            ("sku", "VARCHAR", "产品SKU"),
            ("product_name", "VARCHAR", "产品名称"),
            ("brand", "VARCHAR", "品牌"),
            ("current_stock", "INT", "当前库存"),
            ("sold_30d", "INT", "近30天出库量"),
            ("sold_90d", "INT", "近90天出库量"),
            ("turnover_rate", "DECIMAL", "月周转率"),
        ],
    },
    "vw_receivables": {
        "description": "应收账款明细",
        "columns": [
            ("bill_no", "VARCHAR", "应收单号"),
            ("customer_name", "VARCHAR", "客户名称"),
            ("bill_date", "DATE", "开单日期"),
            ("total_amount", "DECIMAL", "应收金额"),
            ("received_amount", "DECIMAL", "已收金额"),
            ("unreceived_amount", "DECIMAL", "未收金额"),
            ("status", "VARCHAR", "状态: pending/partial/completed"),
            ("age_days", "INT", "账龄天数"),
            ("account_set_name", "VARCHAR", "账套名称"),
        ],
    },
    "vw_payables": {
        "description": "应付账款明细",
        "columns": [
            ("bill_no", "VARCHAR", "应付单号"),
            ("supplier_name", "VARCHAR", "供应商名称"),
            ("bill_date", "DATE", "开单日期"),
            ("total_amount", "DECIMAL", "应付金额"),
            ("paid_amount", "DECIMAL", "已付金额"),
            ("unpaid_amount", "DECIMAL", "未付金额"),
            ("status", "VARCHAR", "状态: pending/partial/completed"),
            ("age_days", "INT", "账龄天数"),
            ("account_set_name", "VARCHAR", "账套名称"),
        ],
    },
}

_cached_schema: str | None = None


def get_view_schema_text() -> str:
    """生成视图 schema 文本（供 system prompt 使用）"""
    lines = ["## 数据视图（优先使用这些视图查询）\n"]
    for view_name, info in VIEW_SCHEMAS.items():
        lines.append(f"### {view_name} — {info['description']}")
        for col_name, col_type, comment in info["columns"]:
            lines.append(f"  - {col_name} ({col_type}): {comment}")
        lines.append("")
    return "\n".join(lines)


async def get_table_schema_text() -> str:
    """从 Tortoise ORM models 生成原始表 schema 文本（作为 fallback）"""
    global _cached_schema
    if _cached_schema is not None:
        return _cached_schema

    lines = ["## 原始数据表（视图无法满足时使用）\n"]
    try:
        models_map = Tortoise.apps.get("models", {})
        for model_name, model_cls in sorted(models_map.items()):
            table_name = model_cls.Meta.table if hasattr(model_cls.Meta, "table") else model_name.lower() + "s"
            if table_name.lower() in EXCLUDED_TABLES:
                continue

            lines.append(f"### {table_name}")
            for field_name, field_obj in model_cls._meta.fields_map.items():
                if field_name in SENSITIVE_COLUMNS:
                    continue
                field_type = type(field_obj).__name__.replace("Field", "")
                desc = getattr(field_obj, "description", "") or ""
                lines.append(f"  - {field_name} ({field_type}){': ' + desc if desc else ''}")
            lines.append("")
    except Exception as e:
        logger.warning(f"生成表 schema 失败: {e}")
        lines.append("（表 schema 生成失败，请仅使用视图查询）\n")

    _cached_schema = "\n".join(lines)
    return _cached_schema


def get_full_schema_text() -> str:
    """返回 AI 可用的 schema 文本。

    当前仅包含语义视图 — 原始表 schema 不暴露给 AI，
    因为视图已涵盖所有业务查询需求，且避免泄露敏感表结构。
    如需支持更复杂查询，可在此合并 get_table_schema_text()。
    """
    return get_view_schema_text()


def invalidate_cache() -> None:
    """清除 schema 缓存（表结构变更时调用）"""
    global _cached_schema
    _cached_schema = None
```

- [ ] **Step 2: Create business dictionary defaults**

Create `backend/app/ai/business_dict.py`:

```python
"""默认业务词典 — 帮助 LLM 理解业务术语"""
from __future__ import annotations

DEFAULT_BUSINESS_DICT = [
    {"term": "毛利", "meaning": "销售额 - 成本，在视图中为 profit 字段"},
    {"term": "毛利率", "meaning": "毛利 / 销售额 * 100，在视图中为 profit_rate 字段"},
    {"term": "账期", "meaning": "赊销，order_type = 'account_period'"},
    {"term": "现结", "meaning": "现款结算，order_type = 'normal'"},
    {"term": "启领", "meaning": "账套名称，account_set_name = '启领'"},
    {"term": "链雾", "meaning": "账套名称，account_set_name = '链雾'"},
    {"term": "应收", "meaning": "客户欠我们的钱，查 vw_receivables"},
    {"term": "应付", "meaning": "我们欠供应商的钱，查 vw_payables"},
    {"term": "周转率", "meaning": "近30天出库量 / 当前库存，在 vw_inventory_turnover 中"},
    {"term": "手机壳", "meaning": "产品分类 category 或品牌 brand，需模糊匹配"},
    {"term": "SKU", "meaning": "产品唯一编码，products.sku 字段"},
]


def format_business_dict(custom_dict: list | None = None) -> str:
    """格式化业务词典为 prompt 文本"""
    items = custom_dict if custom_dict else DEFAULT_BUSINESS_DICT
    if not items:
        return ""
    lines = ["## 业务词典\n"]
    for item in items:
        lines.append(f"- {item['term']}：{item['meaning']}")
    return "\n".join(lines)
```

- [ ] **Step 3: Create few-shot defaults**

Create `backend/app/ai/few_shots.py`:

```python
"""默认 Few-shot 示例 — 引导 LLM 生成正确的 SQL"""
from __future__ import annotations

DEFAULT_FEW_SHOTS = [
    {
        "question": "这个月启领的毛利怎么样",
        "sql": "SELECT year_month, total_amount, total_cost, total_profit, profit_rate FROM vw_sales_summary WHERE account_set_name = '启领' AND year_month = TO_CHAR(CURRENT_DATE, 'YYYY-MM')",
        "source": "manual",
    },
    {
        "question": "客户A在1-3月的手机壳销售",
        "sql": "SELECT customer_name, product_name, brand, SUM(quantity) AS total_qty, SUM(amount) AS total_amount, SUM(profit) AS total_profit, ROUND(SUM(profit)/NULLIF(SUM(amount),0)*100, 2) AS profit_rate FROM vw_sales_detail WHERE customer_name LIKE '%A%' AND order_date BETWEEN '2024-01-01' AND '2024-03-31' AND (product_name LIKE '%手机壳%' OR category LIKE '%手机壳%') GROUP BY customer_name, product_name, brand ORDER BY total_amount DESC",
        "source": "manual",
    },
    {
        "question": "各品牌的应收账款汇总",
        "sql": "SELECT customer_name, COUNT(*) AS bill_count, SUM(total_amount) AS total_receivable, SUM(received_amount) AS total_received, SUM(unreceived_amount) AS total_unreceived FROM vw_receivables WHERE status != 'completed' GROUP BY customer_name ORDER BY total_unreceived DESC",
        "source": "manual",
    },
    {
        "question": "SKU ABC123 的库存管理做得怎么样",
        "sql": "SELECT s.sku, s.product_name, s.brand, s.warehouse_name, s.quantity, s.available_qty, s.stock_value, t.sold_30d, t.sold_90d, t.turnover_rate FROM vw_inventory_status s LEFT JOIN vw_inventory_turnover t ON s.sku = t.sku WHERE s.sku = 'ABC123'",
        "source": "manual",
    },
]


def format_few_shots(custom_shots: list | None = None) -> str:
    """格式化 few-shot 示例为 prompt 文本"""
    items = custom_shots if custom_shots else DEFAULT_FEW_SHOTS
    if not items:
        return ""
    lines = ["## 查询示例\n"]
    for i, item in enumerate(items, 1):
        lines.append(f"### 示例 {i}")
        lines.append(f"用户: {item['question']}")
        lines.append(f"SQL: {item['sql']}")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/ai/schema_registry.py backend/app/ai/business_dict.py backend/app/ai/few_shots.py
git commit -m "feat(ai): Schema 注册器 + 业务词典 + Few-shot 示例"
```

---

### Task 6: DeepSeek Client

**Files:**
- Create: `backend/app/ai/deepseek_client.py`

- [ ] **Step 1: Implement DeepSeek client**

Create `backend/app/ai/deepseek_client.py`:

```python
"""DeepSeek API 客户端 — R1 生成 SQL，V3 分析数据"""
from __future__ import annotations
import json
import httpx
from app.logger import get_logger

logger = get_logger("ai.deepseek")

# DeepSeek API 默认配置
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL_SQL = "deepseek-reasoner"
DEFAULT_MODEL_ANALYSIS = "deepseek-chat"

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """获取或创建 httpx 客户端（懒初始化）"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    return _client


async def close_client() -> None:
    """关闭 HTTP 客户端"""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def call_deepseek(
    messages: list[dict],
    *,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL_SQL,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> dict | None:
    """
    调用 DeepSeek API。

    返回解析后的 JSON 响应内容，失败返回 None。
    不向上抛出异常。
    """
    if not api_key:
        logger.error("DeepSeek API Key 未配置")
        return None

    client = _get_client()
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # response_format 仅 deepseek-chat (V3) 支持，deepseek-reasoner (R1) 不支持
    if "reasoner" not in model:
        payload["response_format"] = {"type": "json_object"}

    for attempt in range(2):  # 最多重试 1 次
        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # 尝试解析为 JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # 提取 JSON 块（处理 markdown 包裹的情况）
                    return _extract_json(content)
            else:
                logger.warning(
                    f"DeepSeek API 返回 {resp.status_code}（第{attempt+1}次）"
                )
                if attempt == 0 and resp.status_code >= 500:
                    continue  # 服务端错误重试
                return None
        except httpx.TimeoutException:
            logger.warning(f"DeepSeek API 超时（第{attempt+1}次）")
            if attempt == 0:
                continue
            return None
        except Exception as e:
            logger.error(f"DeepSeek API 调用异常: {type(e).__name__}")
            return None

    return None


async def test_connection(api_key: str, base_url: str = DEFAULT_BASE_URL) -> tuple[bool, str]:
    """测试 DeepSeek 连接。返回 (success, message)"""
    try:
        result = await call_deepseek(
            messages=[{"role": "user", "content": "回复 ok"}],
            api_key=api_key,
            base_url=base_url,
            model=DEFAULT_MODEL_ANALYSIS,
            temperature=0.0,
            max_tokens=10,
        )
        if result is not None:
            return True, "连接成功"
        return False, "API 返回异常"
    except Exception as e:
        return False, f"连接失败: {type(e).__name__}"


def _extract_json(text: str) -> dict | None:
    """从可能包含 markdown 的文本中提取 JSON"""
    # 尝试找 ```json ... ``` 块
    import re
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试找第一个 { ... } 块
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/ai/deepseek_client.py
git commit -m "feat(ai): DeepSeek API 客户端（R1/V3 双模型）"
```

---

### Task 7: Intent Classifier + Prompt Builder

**Files:**
- Create: `backend/app/ai/intent_classifier.py`
- Create: `backend/app/ai/prompt_builder.py`

- [ ] **Step 1: Implement intent classifier**

Create `backend/app/ai/intent_classifier.py`:

```python
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
```

- [ ] **Step 2: Implement prompt builder**

Create `backend/app/ai/prompt_builder.py`:

```python
"""System Prompt 组装器"""
from __future__ import annotations
from app.ai.schema_registry import get_view_schema_text
from app.ai.business_dict import format_business_dict
from app.ai.few_shots import format_few_shots

# SQL 生成系统提示词模板
DEFAULT_SQL_SYSTEM_PROMPT = """你是一个专业的数据分析 SQL 生成助手。你的任务是根据用户的自然语言问题，生成正确的 PostgreSQL SQL 查询。

## 重要规则
1. **只生成 SELECT 查询**，绝对禁止 INSERT/UPDATE/DELETE/DROP/ALTER 等任何修改操作
2. **优先使用视图**（vw_ 开头的表），它们已经预处理好了常用查询
3. 金额字段用 ROUND(..., 2) 保留两位小数
4. 日期过滤使用标准格式 'YYYY-MM-DD'
5. 模糊匹配使用 LIKE '%关键词%'
6. 需要时使用 GROUP BY 和聚合函数
7. 结果默认按相关性排序（如金额从大到小）
8. 不要使用 LIMIT 超过 1000

## 账套规则
{account_set_instruction}

## 响应格式
必须返回 JSON，格式为以下之一：

1. 生成了 SQL:
{{"type": "sql", "sql": "SELECT ...", "explanation": "这个查询..."}}

2. 需要用户澄清:
{{"type": "clarification", "message": "请问...", "options": ["选项1", "选项2"]}}

{schema}

{business_dict}

{few_shots}
"""

# 数据分析系统提示词模板
DEFAULT_ANALYSIS_SYSTEM_PROMPT = """你是一个专业的业务数据分析师。用户提出了一个业务问题，系统已经通过 SQL 查询获取了数据。
请分析这些数据并给出专业的业务洞察。

## 要求
1. 用简洁的中文回答
2. 先给出核心结论，再展开分析
3. 如果数据中有异常值或趋势，主动指出
4. 金额数字保留两位小数，大数字用万/亿为单位
5. 适当使用 Markdown 格式（加粗、列表），但不要使用 Markdown 表格（数据表格已在结构化字段中返回）

## 图表建议
如果数据适合可视化，在响应 JSON 中包含 chart_config：
{{"chart_type": "bar|line|pie|doughnut", "title": "图表标题", "labels": [...], "datasets": [{{"label": "...", "data": [...]}}]}}
如果数据不适合图表（如只有一行或纯文本），chart_config 设为 null。

响应 JSON 格式：
{{"analysis": "Markdown格式的分析文本", "chart_config": {{...}} 或 null}}
"""


def build_sql_prompt(
    account_sets: list[dict],
    custom_system_prompt: str | None = None,
    custom_dict: list | None = None,
    custom_shots: list | None = None,
) -> str:
    """组装 SQL 生成的 system prompt"""
    # 账套指令
    if account_sets:
        names = "、".join([s["name"] for s in account_sets])
        account_instruction = (
            f"当前系统有以下账套: {names}。\n"
            "当用户查询涉及销售/采购/应收/应付等与账套关联的数据时：\n"
            "- 如果用户指定了账套名称 → 加 WHERE account_set_name = '指定名称'\n"
            "- 如果用户说\"全部\"或\"所有\" → 按 account_set_name 分组\n"
            "- 如果用户未指定且有多个账套 → 返回 clarification 类型，让用户选择\n"
            "- 库存类查询（vw_inventory_*）不涉及账套，无需询问"
        )
    else:
        account_instruction = "系统当前未配置账套，忽略账套相关逻辑。"

    template = custom_system_prompt or DEFAULT_SQL_SYSTEM_PROMPT
    return template.format(
        account_set_instruction=account_instruction,
        schema=get_view_schema_text(),
        business_dict=format_business_dict(custom_dict),
        few_shots=format_few_shots(custom_shots),
    )


def build_analysis_prompt(
    custom_analysis_prompt: str | None = None,
) -> str:
    """组装数据分析的 system prompt"""
    return custom_analysis_prompt or DEFAULT_ANALYSIS_SYSTEM_PROMPT
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/ai/intent_classifier.py backend/app/ai/prompt_builder.py
git commit -m "feat(ai): 意图分类器 + Prompt 组装器"
```

---

## Chunk 3: Backend Service, Routes & Integration

### Task 8: AI Chat Service（NL2SQL 主流程）

**Files:**
- Create: `backend/app/services/ai_chat_service.py`

- [ ] **Step 1: Implement AI chat service**

Create `backend/app/services/ai_chat_service.py`:

```python
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

        # 1. 意图预分类 — 命中预置模板则直接执行
        preset = classify_intent(message, config.get("ai.preset_queries"))
        if preset and preset.get("sql"):
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/ai_chat_service.py
git commit -m "feat(ai): NL2SQL 主流程编排服务"
```

---

### Task 9: API Keys + AI Config Router

**Files:**
- Create: `backend/app/routers/api_keys.py`

- [ ] **Step 1: Implement API keys router**

Create `backend/app/routers/api_keys.py`:

```python
"""API 密钥 + AI 配置管理路由（仅 admin 角色）"""
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import require_permission
from app.models import User, SystemSetting
from app.ai.encryption import encrypt_value, decrypt_value, mask_key
from app.ai.deepseek_client import test_connection
from app.services.ai_chat_service import invalidate_config_cache
from app.logger import get_logger

logger = get_logger("api_keys")
router = APIRouter(prefix="/api/api-keys", tags=["API密钥管理"])

# 允许通过此接口管理的 key 白名单
MANAGED_KEYS = {
    "ai.deepseek.api_key",
    "ai.deepseek.base_url",
    "ai.deepseek.model_sql",
    "ai.deepseek.model_analysis",
    "api.kd100.key",
    "api.kd100.customer",
}

# 需要加密存储的 key
ENCRYPTED_KEYS = {"ai.deepseek.api_key", "api.kd100.key"}


@router.get("")
async def get_api_keys(user: User = Depends(require_permission("admin"))):
    """获取所有 API 配置（密钥脱敏）"""
    result = {}
    for key in MANAGED_KEYS:
        setting = await SystemSetting.filter(key=key).first()
        if setting and setting.value:
            if key in ENCRYPTED_KEYS:
                decrypted = decrypt_value(setting.value)
                result[key] = mask_key(decrypted) if decrypted else ""
            else:
                result[key] = setting.value
        else:
            result[key] = ""
    return result


@router.put("")
async def update_api_keys(body: dict, user: User = Depends(require_permission("admin"))):
    """更新 API 密钥配置"""
    updated = []
    for key, value in body.items():
        if key not in MANAGED_KEYS:
            continue
        if value is None or value == "":
            # 清空配置
            await SystemSetting.filter(key=key).delete()
            updated.append(key)
            continue
        # 如果值是脱敏的（含 ***），跳过不更新
        if "***" in str(value):
            continue
        # 加密敏感值
        store_value = encrypt_value(value) if key in ENCRYPTED_KEYS else value
        setting = await SystemSetting.filter(key=key).first()
        if setting:
            setting.value = store_value
            await setting.save()
        else:
            await SystemSetting.create(key=key, value=store_value)
        updated.append(key)

    invalidate_config_cache()
    logger.info(f"API 密钥已更新: {updated}（操作人: {user.username}）")
    return {"ok": True, "updated": updated}


@router.post("/test-deepseek")
async def test_deepseek_connection(user: User = Depends(require_permission("admin"))):
    """测试 DeepSeek API 连接"""
    api_key_setting = await SystemSetting.filter(key="ai.deepseek.api_key").first()
    if not api_key_setting or not api_key_setting.value:
        raise HTTPException(status_code=400, detail="请先配置 DeepSeek API Key")

    api_key = decrypt_value(api_key_setting.value)
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 解密失败，请重新设置")

    base_url_setting = await SystemSetting.filter(key="ai.deepseek.base_url").first()
    base_url = base_url_setting.value if base_url_setting and base_url_setting.value else "https://api.deepseek.com"

    success, msg = await test_connection(api_key, base_url)
    return {"success": success, "message": msg}


# ===== AI 配置管理 =====

@router.get("/ai-config")
async def get_ai_config(user: User = Depends(require_permission("admin"))):
    """获取 AI 配置（提示词、词典、示例、快捷问题）"""
    result = {}
    for key in ["ai.prompt.system", "ai.prompt.analysis", "ai.business_dict", "ai.few_shots", "ai.preset_queries"]:
        setting = await SystemSetting.filter(key=key).first()
        if setting and setting.value:
            if key in ("ai.business_dict", "ai.few_shots", "ai.preset_queries"):
                try:
                    result[key] = json.loads(setting.value)
                except json.JSONDecodeError:
                    result[key] = None
            else:
                result[key] = setting.value
        else:
            result[key] = None
    return result


@router.put("/ai-config")
async def update_ai_config(body: dict, user: User = Depends(require_permission("admin"))):
    """更新 AI 配置"""
    allowed_keys = {"ai.prompt.system", "ai.prompt.analysis", "ai.business_dict", "ai.few_shots", "ai.preset_queries"}
    updated = []
    for key, value in body.items():
        if key not in allowed_keys:
            continue
        # JSON 类型的配置序列化存储
        if key in ("ai.business_dict", "ai.few_shots", "ai.preset_queries"):
            store_value = json.dumps(value, ensure_ascii=False) if value else None
        else:
            store_value = value

        if store_value is None:
            await SystemSetting.filter(key=key).delete()
        else:
            setting = await SystemSetting.filter(key=key).first()
            if setting:
                setting.value = store_value
                await setting.save()
            else:
                await SystemSetting.create(key=key, value=store_value)
        updated.append(key)

    invalidate_config_cache()
    logger.info(f"AI 配置已更新: {updated}（操作人: {user.username}）")
    return {"ok": True, "updated": updated}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/api_keys.py
git commit -m "feat(ai): API 密钥 + AI 配置管理路由"
```

---

### Task 10: AI Chat Router

**Files:**
- Create: `backend/app/routers/ai_chat.py`

- [ ] **Step 1: Implement AI chat router**

Create `backend/app/routers/ai_chat.py`:

```python
"""AI 聊天路由 — 聊天 / 导出 / 反馈 / 状态"""
from __future__ import annotations
import io
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.auth.dependencies import get_current_user
from app.models import User, SystemSetting
from app.schemas.ai import ChatRequest, FeedbackRequest, ExportRequest
from app.services.ai_chat_service import process_chat, check_ai_available, get_preset_queries
from app.ai.rate_limiter import user_limiter, global_limiter
from app.config import DATABASE_URL, AI_DB_PASSWORD
from app.logger import get_logger

logger = get_logger("ai.chat")
router = APIRouter(prefix="/api/ai", tags=["AI助手"])


def _build_ai_dsn() -> str:
    """构建 AI 只读用户的数据库连接字符串"""
    # 从主 DSN 解析 host/port/dbname
    # DATABASE_URL 格式: postgres://user:pass@host:port/dbname
    import re
    from urllib.parse import quote_plus
    match = re.match(r'postgres(?:ql)?://[^@]+@([^/]+)/([\w-]+)', DATABASE_URL)
    if not match:
        raise RuntimeError("无法解析 DATABASE_URL")
    host_port = match.group(1)
    dbname = match.group(2)
    if not AI_DB_PASSWORD:
        raise RuntimeError("AI_DB_PASSWORD 环境变量未设置，无法连接 AI 只读数据库")
    return f"postgresql://erp_ai_readonly:{quote_plus(AI_DB_PASSWORD)}@{host_port}/{dbname}"


@router.get("/status")
async def ai_status(user: User = Depends(get_current_user)):
    """检查 AI 助手可用性（含预设快捷问题，所有登录用户可访问）"""
    available, reason = await check_ai_available()
    preset = await get_preset_queries() if available else []
    return {"available": available, "reason": reason, "preset_queries": preset}


@router.post("/chat")
async def ai_chat(body: ChatRequest, user: User = Depends(get_current_user)):
    """AI 聊天接口"""
    # 输入验证
    if len(body.history) > 20:
        body.history = body.history[-20:]
    for h in body.history:
        if len(h.get("content", "")) > 5000:
            h["content"] = h["content"][:5000]

    # 限流检查（spec 要求返回 HTTP 429）
    user_key = f"user:{user.id}"
    if not user_limiter.allow(user_key):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    if not global_limiter.allow("global"):
        raise HTTPException(status_code=429, detail="系统繁忙，请稍后再试")

    # 清洗输入
    clean_msg = body.message.strip()
    # 移除控制字符（保留换行）
    clean_msg = "".join(c for c in clean_msg if c == "\n" or (ord(c) >= 32))

    if not clean_msg:
        return {"type": "error", "message": "请输入查询内容"}

    dsn = _build_ai_dsn()
    result = await process_chat(
        message=clean_msg,
        history=body.history,
        user_id=user.id,
        db_dsn=dsn,
    )

    logger.info(
        f"AI 查询: user={user.username}, question={clean_msg[:50]}, "
        f"type={result.get('type')}, rows={result.get('row_count', 0)}"
    )
    return result


@router.post("/chat/export")
async def ai_export(body: ExportRequest, user: User = Depends(get_current_user)):
    """导出查询结果为 Excel"""
    import openpyxl

    table_data = body.table_data
    if not table_data or "columns" not in table_data or "rows" not in table_data:
        raise HTTPException(status_code=400, detail="无效的表格数据")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = body.title[:31]  # Excel sheet 名最多 31 字符

    # 写表头
    for col, name in enumerate(table_data["columns"], 1):
        ws.cell(row=1, column=col, value=name)

    # 写数据行
    for row_idx, row in enumerate(table_data["rows"], 2):
        for col_idx, val in enumerate(row, 1):
            ws.cell(row=row_idx, column=col_idx, value=val)

    # 输出为字节流
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"{body.title}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/chat/feedback")
async def ai_feedback(body: FeedbackRequest, user: User = Depends(get_current_user)):
    """接收用户反馈"""
    logger.info(
        f"AI 反馈: user={user.username}, message_id={body.message_id}, "
        f"feedback={body.feedback}, reason={body.negative_reason}"
    )

    # 正面反馈 + 保存为示例
    if body.feedback == "positive" and body.save_as_example and body.original_question and body.sql:
        try:
            setting = await SystemSetting.filter(key="ai.few_shots").first()
            shots = []
            if setting and setting.value:
                shots = json.loads(setting.value)

            new_shot = {
                "question": body.original_question,
                "sql": body.sql,
                "source": "feedback",
            }
            shots.append(new_shot)

            store_value = json.dumps(shots, ensure_ascii=False)
            if setting:
                setting.value = store_value
                await setting.save()
            else:
                await SystemSetting.create(key="ai.few_shots", value=store_value)

            logger.info(f"新增 few-shot 示例: {body.original_question[:50]}")
        except Exception as e:
            logger.error(f"保存 few-shot 失败: {e}")

    return {"ok": True}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/ai_chat.py
git commit -m "feat(ai): AI 聊天 + 导出 + 反馈 + 状态路由"
```

---

### Task 11: Database Migration + Views SQL

**Files:**
- Create: `backend/app/ai/views.sql`
- Modify: `backend/app/migrations.py`

- [ ] **Step 1: Create semantic views SQL**

Create `backend/app/ai/views.sql`:

```sql
-- ERP AI 语义视图 — 由 erp 主用户创建，erp_ai_readonly 只读访问

-- 1. 销售明细宽表
CREATE OR REPLACE VIEW vw_sales_detail AS
SELECT
    o.order_no,
    o.created_at::date AS order_date,
    o.order_type,
    c.name AS customer_name,
    s.name AS salesperson_name,
    p.sku,
    p.name AS product_name,
    p.brand,
    p.category,
    oi.quantity,
    oi.unit_price,
    ROUND((oi.quantity * oi.unit_price)::numeric, 2) AS amount,
    ROUND((oi.quantity * COALESCE(oi.cost_price, 0))::numeric, 2) AS cost,
    ROUND((oi.quantity * (oi.unit_price - COALESCE(oi.cost_price, 0)))::numeric, 2) AS profit,
    ROUND(
        CASE WHEN oi.unit_price > 0
             THEN ((oi.unit_price - COALESCE(oi.cost_price, 0)) / oi.unit_price * 100)::numeric
             ELSE 0 END,
        2
    ) AS profit_rate,
    ast.name AS account_set_name
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN products p ON p.id = oi.product_id
LEFT JOIN customers c ON c.id = o.customer_id
LEFT JOIN salespersons s ON s.id = o.salesperson_id
LEFT JOIN account_sets ast ON ast.id = o.account_set_id
WHERE o.shipping_status != 'cancelled'
  AND o.order_type != 'return';

-- 2. 销售按月汇总
CREATE OR REPLACE VIEW vw_sales_summary AS
SELECT
    TO_CHAR(o.created_at, 'YYYY-MM') AS year_month,
    COUNT(DISTINCT o.id) AS order_count,
    ROUND(SUM(oi.quantity * oi.unit_price)::numeric, 2) AS total_amount,
    ROUND(SUM(oi.quantity * COALESCE(oi.cost_price, 0))::numeric, 2) AS total_cost,
    ROUND(SUM(oi.quantity * (oi.unit_price - COALESCE(oi.cost_price, 0)))::numeric, 2) AS total_profit,
    ROUND(
        CASE WHEN SUM(oi.quantity * oi.unit_price) > 0
             THEN (SUM(oi.quantity * (oi.unit_price - COALESCE(oi.cost_price, 0)))
                   / NULLIF(SUM(oi.quantity * oi.unit_price), 0) * 100)::numeric
             ELSE 0 END,
        2
    ) AS profit_rate,
    COUNT(DISTINCT o.customer_id) AS customer_count,
    ast.name AS account_set_name
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
LEFT JOIN account_sets ast ON ast.id = o.account_set_id
WHERE o.shipping_status != 'cancelled'
  AND o.order_type != 'return'
GROUP BY TO_CHAR(o.created_at, 'YYYY-MM'), ast.name;

-- 3. 采购明细宽表
CREATE OR REPLACE VIEW vw_purchase_detail AS
SELECT
    po.po_no,
    po.created_at::date AS purchase_date,
    sup.name AS supplier_name,
    p.sku,
    p.name AS product_name,
    p.brand,
    poi.quantity,
    poi.tax_inclusive_price,
    poi.tax_exclusive_price,
    ROUND((poi.quantity * poi.tax_inclusive_price)::numeric, 2) AS amount,
    po.status,
    ast.name AS account_set_name
FROM purchase_orders po
JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
JOIN products p ON p.id = poi.product_id
LEFT JOIN suppliers sup ON sup.id = po.supplier_id
LEFT JOIN account_sets ast ON ast.id = po.account_set_id
WHERE po.status != 'cancelled';

-- 4. 当前库存状态
CREATE OR REPLACE VIEW vw_inventory_status AS
SELECT
    p.sku,
    p.name AS product_name,
    p.brand,
    w.name AS warehouse_name,
    COALESCE(loc.name, loc.code, '') AS location_name,
    ws.quantity,
    COALESCE(ws.reserved_qty, 0) AS reserved_qty,
    ws.quantity - COALESCE(ws.reserved_qty, 0) AS available_qty,
    ROUND(COALESCE(p.cost_price, 0)::numeric, 2) AS avg_cost,
    ROUND((ws.quantity * COALESCE(p.cost_price, 0))::numeric, 2) AS stock_value
FROM warehouse_stocks ws
JOIN products p ON p.id = ws.product_id
JOIN warehouses w ON w.id = ws.warehouse_id
LEFT JOIN locations loc ON loc.id = ws.location_id
WHERE ws.quantity > 0
  AND w.is_virtual = false;

-- 5. 库存周转分析
CREATE OR REPLACE VIEW vw_inventory_turnover AS
SELECT
    p.sku,
    p.name AS product_name,
    p.brand,
    COALESCE(SUM(ws.quantity), 0) AS current_stock,
    COALESCE(sold_30.qty, 0) AS sold_30d,
    COALESCE(sold_90.qty, 0) AS sold_90d,
    CASE WHEN COALESCE(SUM(ws.quantity), 0) > 0
         THEN ROUND((COALESCE(sold_30.qty, 0)::numeric / NULLIF(SUM(ws.quantity), 0)), 2)
         ELSE 0 END AS turnover_rate
FROM products p
LEFT JOIN warehouse_stocks ws ON ws.product_id = p.id
LEFT JOIN (
    SELECT oi.product_id, SUM(oi.quantity) AS qty
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    WHERE o.created_at >= CURRENT_DATE - INTERVAL '30 days'
      AND o.shipping_status != 'cancelled' AND o.order_type != 'return'
    GROUP BY oi.product_id
) sold_30 ON sold_30.product_id = p.id
LEFT JOIN (
    SELECT oi.product_id, SUM(oi.quantity) AS qty
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    WHERE o.created_at >= CURRENT_DATE - INTERVAL '90 days'
      AND o.shipping_status != 'cancelled' AND o.order_type != 'return'
    GROUP BY oi.product_id
) sold_90 ON sold_90.product_id = p.id
GROUP BY p.id, p.sku, p.name, p.brand, sold_30.qty, sold_90.qty;

-- 6. 应收账款
CREATE OR REPLACE VIEW vw_receivables AS
SELECT
    rb.bill_no,
    c.name AS customer_name,
    rb.bill_date,
    rb.total_amount,
    rb.received_amount,
    rb.unreceived_amount,
    rb.status,
    (CURRENT_DATE - rb.bill_date) AS age_days,
    ast.name AS account_set_name
FROM receivable_bills rb
LEFT JOIN customers c ON c.id = rb.customer_id
LEFT JOIN account_sets ast ON ast.id = rb.account_set_id;

-- 7. 应付账款
CREATE OR REPLACE VIEW vw_payables AS
SELECT
    pb.bill_no,
    sup.name AS supplier_name,
    pb.bill_date,
    pb.total_amount,
    pb.paid_amount,
    pb.unpaid_amount,
    pb.status,
    (CURRENT_DATE - pb.bill_date) AS age_days,
    ast.name AS account_set_name
FROM payable_bills pb
LEFT JOIN suppliers sup ON sup.id = pb.supplier_id
LEFT JOIN account_sets ast ON ast.id = pb.account_set_id;

-- 授权只读用户
GRANT SELECT ON vw_sales_detail TO erp_ai_readonly;
GRANT SELECT ON vw_sales_summary TO erp_ai_readonly;
GRANT SELECT ON vw_purchase_detail TO erp_ai_readonly;
GRANT SELECT ON vw_inventory_status TO erp_ai_readonly;
GRANT SELECT ON vw_inventory_turnover TO erp_ai_readonly;
GRANT SELECT ON vw_receivables TO erp_ai_readonly;
GRANT SELECT ON vw_payables TO erp_ai_readonly;
```

- [ ] **Step 2: Add AI migration to migrations.py**

在 `backend/app/migrations.py` 的 `run_migrations()` 函数末尾（在现有迁移之后）添加调用：

```python
await migrate_ai_readonly_user()
```

然后在文件末尾添加迁移函数：

```python
async def migrate_ai_readonly_user():
    """创建 AI 只读数据库用户 + 语义视图"""
    conn = connections.get("default")

    # 检查用户是否已存在
    result = await conn.execute_query_dict(
        "SELECT 1 FROM pg_roles WHERE rolname = 'erp_ai_readonly'"
    )
    if not result:
        from app.config import AI_DB_PASSWORD
        if not AI_DB_PASSWORD:
            logger.warning("AI_DB_PASSWORD 未设置，跳过创建 AI 只读用户（AI 功能将不可用）")
            return
        try:
            # 使用单引号 + 转义防止密码中的特殊字符
            safe_password = AI_DB_PASSWORD.replace("'", "''")
            await conn.execute_query(f"CREATE USER erp_ai_readonly WITH PASSWORD '{safe_password}'")
            await conn.execute_query("GRANT CONNECT ON DATABASE erp TO erp_ai_readonly")
            await conn.execute_query("GRANT USAGE ON SCHEMA public TO erp_ai_readonly")
            await conn.execute_query("GRANT SELECT ON ALL TABLES IN SCHEMA public TO erp_ai_readonly")
            await conn.execute_query("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO erp_ai_readonly")
            await conn.execute_query("REVOKE SELECT ON users FROM erp_ai_readonly")
            await conn.execute_query("REVOKE SELECT ON system_settings FROM erp_ai_readonly")
            await conn.execute_query("ALTER USER erp_ai_readonly SET statement_timeout = '30s'")
            await conn.execute_query("ALTER USER erp_ai_readonly SET work_mem = '16MB'")
            await conn.execute_query("ALTER USER erp_ai_readonly SET temp_file_limit = '100MB'")
            await conn.execute_query("ALTER USER erp_ai_readonly CONNECTION LIMIT 5")
            logger.info(f"AI 只读用户 erp_ai_readonly 已创建（密码: {AI_DB_PASSWORD[:4]}...）")
        except Exception as e:
            logger.warning(f"创建 AI 只读用户失败（可能权限不足）: {e}")

    # 创建/更新语义视图
    try:
        import os
        views_path = os.path.join(os.path.dirname(__file__), "ai", "views.sql")
        if os.path.exists(views_path):
            with open(views_path, "r", encoding="utf-8") as f:
                views_sql = f.read()
            # 逐条执行（按分号分割，跳过纯注释段落）
            for stmt in views_sql.split(";"):
                stmt = stmt.strip()
                if not stmt:
                    continue
                # 跳过只有注释的段落
                non_comment_lines = [l for l in stmt.split("\n")
                                     if l.strip() and not l.strip().startswith("--")]
                if not non_comment_lines:
                    continue
                try:
                    await conn.execute_query(stmt)
                except Exception as ve:
                    logger.warning(f"视图语句执行失败: {ve}")
            logger.info("AI 语义视图已创建/更新")
    except Exception as e:
        logger.warning(f"语义视图创建失败: {e}")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/ai/views.sql backend/app/migrations.py
git commit -m "feat(ai): 语义视图 DDL + AI 只读用户迁移"
```

---

### Task 12: main.py Integration + Docker + KD100 Migration

**Files:**
- Modify: `backend/main.py`
- Modify: `docker-compose.yml`（项目根目录）
- Modify: `backend/app/services/logistics_service.py`

- [ ] **Step 1: Update main.py — register AI routes + lifespan**

在 `backend/main.py` 的 import 区域（第 31 行 `purchase_returns,` 之后）添加：

```python
from app.routers import ai_chat, api_keys
```

在 lifespan 函数的 yield 之前（启动阶段）添加：

```python
    # AI 连接池在首次请求时惰性创建，无需启动时初始化
```

在 lifespan 函数的关闭阶段（`await close_db()` 之前）添加：

```python
    # 关闭 AI 资源
    try:
        from app.services.ai_chat_service import close_ai_pool
        from app.ai.deepseek_client import close_client
        await close_ai_pool()
        await close_client()
    except Exception:
        pass
```

在路由注册区域（第 137 行 `purchase_returns.router` 之后）添加：

```python
app.include_router(ai_chat.router)
app.include_router(api_keys.router)
```

- [ ] **Step 2: Update docker-compose.yml（项目根目录）**

在 erp 服务的 environment 部分添加：

```yaml
    API_KEYS_ENCRYPTION_SECRET: ${API_KEYS_ENCRYPTION_SECRET:?请在 .env 文件中设置 API_KEYS_ENCRYPTION_SECRET}
    AI_DB_PASSWORD: ${AI_DB_PASSWORD:-}
```

- [ ] **Step 3: KD100 config migration**

修改 `backend/app/services/logistics_service.py`，在文件开头的 import 区域添加：

```python
from app.models import SystemSetting
from app.ai.encryption import decrypt_value
```

添加辅助函数（在 `subscribe_kd100` 之前）：

```python
async def _get_kd100_config() -> tuple[str, str]:
    """获取 KD100 配置（优先 SystemSetting，fallback 环境变量）"""
    key = ""
    customer = ""

    # 优先从数据库读取
    try:
        key_setting = await SystemSetting.filter(key="api.kd100.key").first()
        if key_setting and key_setting.value:
            key = decrypt_value(key_setting.value) or ""
        customer_setting = await SystemSetting.filter(key="api.kd100.customer").first()
        if customer_setting and customer_setting.value:
            customer = customer_setting.value or ""
    except Exception:
        pass

    # Fallback 到环境变量
    if not key:
        key = KD100_KEY
    if not customer:
        customer = KD100_CUSTOMER

    return key, customer
```

然后修改 `subscribe_kd100` 和 `query_kd100` 函数，将直接使用 `KD100_KEY` / `KD100_CUSTOMER` 的地方改为调用 `await _get_kd100_config()`。

- [ ] **Step 4: Commit**

```bash
git add backend/main.py docker-compose.yml backend/app/services/logistics_service.py
git commit -m "feat(ai): main.py 集成 + Docker 环境变量 + KD100 配置迁移"
```

---

## Chunk 4: Frontend

### Task 13: AI API Module

**Files:**
- Create: `frontend/src/api/ai.js`

- [ ] **Step 1: Create API module**

Create `frontend/src/api/ai.js`:

```javascript
import api from './index'

// AI 聊天
export const aiChat = (data) => api.post('/ai/chat', data, { timeout: 90000 })

// AI 状态检查
export const getAiStatus = () => api.get('/ai/status')

// 导出 Excel
export const aiExport = (data) => api.post('/ai/chat/export', data, { responseType: 'blob' })

// 反馈
export const aiFeedback = (data) => api.post('/ai/chat/feedback', data)

// API 密钥管理
export const getApiKeys = () => api.get('/api-keys')
export const updateApiKeys = (data) => api.put('/api-keys', data)
export const testDeepseek = () => api.post('/api-keys/test-deepseek')

// AI 配置管理
export const getAiConfig = () => api.get('/api-keys/ai-config')
export const updateAiConfig = (data) => api.put('/api-keys/ai-config', data)
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/ai.js
git commit -m "feat(ai): 前端 AI API 模块"
```

---

### Task 14: ApiKeysPanel Settings Component

**Files:**
- Create: `frontend/src/components/business/settings/ApiKeysPanel.vue`

- [ ] **Step 1: Create ApiKeysPanel**

Create `frontend/src/components/business/settings/ApiKeysPanel.vue`:

```vue
<template>
  <div class="space-y-4">
    <!-- 1. API 密钥 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.keys = !sections.keys">
        <h3 class="font-semibold flex items-center gap-2">
          <Key :size="16" />
          API 密钥
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.keys }" class="transition-transform" />
      </button>
      <div v-if="sections.keys" class="mt-4 space-y-4">
        <!-- DeepSeek -->
        <div class="space-y-3">
          <h4 class="text-sm font-medium text-secondary">DeepSeek</h4>
          <div class="grid md:grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-muted mb-1 block" for="ds-key">API Key</label>
              <input id="ds-key" v-model="keys['ai.deepseek.api_key']" type="password" class="input text-sm" placeholder="sk-..." />
            </div>
            <div>
              <label class="text-xs text-muted mb-1 block" for="ds-url">Base URL</label>
              <input id="ds-url" v-model="keys['ai.deepseek.base_url']" class="input text-sm" placeholder="https://api.deepseek.com" />
            </div>
            <div>
              <label class="text-xs text-muted mb-1 block" for="ds-model-sql">SQL 模型</label>
              <input id="ds-model-sql" v-model="keys['ai.deepseek.model_sql']" class="input text-sm" placeholder="deepseek-reasoner" />
            </div>
            <div>
              <label class="text-xs text-muted mb-1 block" for="ds-model-analysis">分析模型</label>
              <input id="ds-model-analysis" v-model="keys['ai.deepseek.model_analysis']" class="input text-sm" placeholder="deepseek-chat" />
            </div>
          </div>
          <button class="btn btn-secondary btn-sm" @click="handleTestDeepseek" :disabled="testing">
            {{ testing ? '测试中...' : '测试连接' }}
          </button>
        </div>
        <!-- KD100 -->
        <div class="border-t pt-4 space-y-3">
          <h4 class="text-sm font-medium text-secondary">快递100</h4>
          <div class="grid md:grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-muted mb-1 block" for="kd-key">Key</label>
              <input id="kd-key" v-model="keys['api.kd100.key']" type="password" class="input text-sm" />
            </div>
            <div>
              <label class="text-xs text-muted mb-1 block" for="kd-customer">Customer</label>
              <input id="kd-customer" v-model="keys['api.kd100.customer']" class="input text-sm" />
            </div>
          </div>
        </div>
        <div class="flex justify-end">
          <button class="btn btn-primary btn-sm" @click="handleSaveKeys" :disabled="saving">保存密钥</button>
        </div>
      </div>
    </div>

    <!-- 2. 提示词模板 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.prompts = !sections.prompts">
        <h3 class="font-semibold flex items-center gap-2">
          <FileText :size="16" />
          提示词模板
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.prompts }" class="transition-transform" />
      </button>
      <div v-if="sections.prompts" class="mt-4 space-y-4">
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-xs text-muted" for="prompt-sql">SQL 生成提示词</label>
            <button class="text-xs text-primary" @click="aiConfig['ai.prompt.system'] = null">重置默认</button>
          </div>
          <textarea id="prompt-sql" v-model="aiConfig['ai.prompt.system']" class="input text-sm font-mono" rows="8" placeholder="留空使用默认提示词..." />
        </div>
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-xs text-muted" for="prompt-analysis">数据分析提示词</label>
            <button class="text-xs text-primary" @click="aiConfig['ai.prompt.analysis'] = null">重置默认</button>
          </div>
          <textarea id="prompt-analysis" v-model="aiConfig['ai.prompt.analysis']" class="input text-sm font-mono" rows="6" placeholder="留空使用默认提示词..." />
        </div>
        <div class="flex justify-end">
          <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存提示词</button>
        </div>
      </div>
    </div>

    <!-- 3. 业务词典 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.dict = !sections.dict">
        <h3 class="font-semibold flex items-center gap-2">
          <BookOpen :size="16" />
          业务词典
          <span class="text-xs text-muted">({{ (aiConfig['ai.business_dict'] || []).length }})</span>
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.dict }" class="transition-transform" />
      </button>
      <div v-if="sections.dict" class="mt-4">
        <div class="space-y-2">
          <div v-for="(item, idx) in (aiConfig['ai.business_dict'] || [])" :key="idx" class="flex gap-2 items-start">
            <input v-model="item.term" class="input text-sm w-32" placeholder="术语" />
            <input v-model="item.meaning" class="input text-sm flex-1" placeholder="SQL 含义" />
            <button class="btn btn-danger btn-sm" @click="removeItem('ai.business_dict', idx)">
              <Trash2 :size="14" />
            </button>
          </div>
        </div>
        <div class="flex justify-between mt-3">
          <button class="btn btn-secondary btn-sm" @click="addDictItem">添加术语</button>
          <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存词典</button>
        </div>
      </div>
    </div>

    <!-- 4. 示例问答库 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.shots = !sections.shots">
        <h3 class="font-semibold flex items-center gap-2">
          <MessageSquare :size="16" />
          示例问答库
          <span class="text-xs text-muted">({{ (aiConfig['ai.few_shots'] || []).length }})</span>
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.shots }" class="transition-transform" />
      </button>
      <div v-if="sections.shots" class="mt-4">
        <div class="space-y-3">
          <div v-for="(item, idx) in (aiConfig['ai.few_shots'] || [])" :key="idx" class="bg-elevated p-3 rounded-lg">
            <div class="flex justify-between items-start mb-2">
              <span class="text-xs px-1.5 py-0.5 rounded" :class="item.source === 'feedback' ? 'bg-success-subtle text-success-emphasis' : 'bg-primary-muted text-primary'">
                {{ item.source === 'feedback' ? '👍 收藏' : '手动' }}
              </span>
              <button class="text-error text-xs" @click="removeItem('ai.few_shots', idx)">删除</button>
            </div>
            <input v-model="item.question" class="input text-sm mb-2" placeholder="用户问题" />
            <textarea v-model="item.sql" class="input text-sm font-mono" rows="2" placeholder="SQL" />
          </div>
        </div>
        <div class="flex justify-between mt-3">
          <button class="btn btn-secondary btn-sm" @click="addShotItem">添加示例</button>
          <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存示例</button>
        </div>
      </div>
    </div>

    <!-- 5. 快捷问题 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.presets = !sections.presets">
        <h3 class="font-semibold flex items-center gap-2">
          <Zap :size="16" />
          快捷问题
          <span class="text-xs text-muted">({{ (aiConfig['ai.preset_queries'] || []).length }})</span>
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.presets }" class="transition-transform" />
      </button>
      <div v-if="sections.presets" class="mt-4">
        <div class="space-y-2">
          <div v-for="(item, idx) in (aiConfig['ai.preset_queries'] || [])" :key="idx" class="flex gap-2 items-start">
            <input v-model="item.display" class="input text-sm w-40" placeholder="显示文字" />
            <input :value="(item.keywords || []).join(', ')" @change="item.keywords = $event.target.value.split(',').map(s => s.trim()).filter(Boolean)" class="input text-sm w-40" placeholder="关键词（逗号分隔）" />
            <input v-model="item.sql" class="input text-sm flex-1 font-mono" placeholder="预置 SQL" />
            <button class="btn btn-danger btn-sm" @click="removeItem('ai.preset_queries', idx)">
              <Trash2 :size="14" />
            </button>
          </div>
        </div>
        <div class="flex justify-between mt-3">
          <button class="btn btn-secondary btn-sm" @click="addPresetItem">添加问题</button>
          <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存问题</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Key, ChevronDown, FileText, BookOpen, MessageSquare, Zap, Trash2 } from 'lucide-vue-next'
import { getApiKeys, updateApiKeys, testDeepseek, getAiConfig, updateAiConfig } from '../../../api/ai'
import { useAppStore } from '../../../stores/app'

const appStore = useAppStore()

const sections = reactive({ keys: true, prompts: false, dict: false, shots: false, presets: false })
const keys = reactive({})
const aiConfig = reactive({})
const saving = ref(false)
const testing = ref(false)

const loadKeys = async () => {
  try {
    const { data } = await getApiKeys()
    Object.assign(keys, data)
  } catch (e) {
    appStore.showToast('加载 API 密钥失败', 'error')
  }
}

const loadConfig = async () => {
  try {
    const { data } = await getAiConfig()
    Object.assign(aiConfig, data)
  } catch (e) {
    appStore.showToast('加载 AI 配置失败', 'error')
  }
}

const handleSaveKeys = async () => {
  if (saving.value) return
  saving.value = true
  try {
    await updateApiKeys(keys)
    appStore.showToast('密钥已保存')
    await loadKeys()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

const handleTestDeepseek = async () => {
  testing.value = true
  try {
    const { data } = await testDeepseek()
    appStore.showToast(data.message, data.success ? 'success' : 'error')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '测试失败', 'error')
  } finally {
    testing.value = false
  }
}

const handleSaveConfig = async () => {
  if (saving.value) return
  saving.value = true
  try {
    await updateAiConfig(aiConfig)
    appStore.showToast('配置已保存')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

const addDictItem = () => {
  if (!aiConfig['ai.business_dict']) aiConfig['ai.business_dict'] = []
  aiConfig['ai.business_dict'].push({ term: '', meaning: '' })
}

const addShotItem = () => {
  if (!aiConfig['ai.few_shots']) aiConfig['ai.few_shots'] = []
  aiConfig['ai.few_shots'].push({ question: '', sql: '', source: 'manual' })
}

const addPresetItem = () => {
  if (!aiConfig['ai.preset_queries']) aiConfig['ai.preset_queries'] = []
  aiConfig['ai.preset_queries'].push({ display: '', keywords: [], sql: '' })
}

const removeItem = (key, idx) => {
  if (aiConfig[key]) aiConfig[key].splice(idx, 1)
}

onMounted(() => {
  loadKeys()
  loadConfig()
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/business/settings/ApiKeysPanel.vue
git commit -m "feat(ai): API 密钥 + AI 配置管理面板"
```

---

### Task 15: SettingsView — Add AI Tab

**Files:**
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] **Step 1: Update SettingsView**

在 `SettingsView.vue` 中做以下修改：

1. 在 import 区域添加：
```javascript
import ApiKeysPanel from '../components/business/settings/ApiKeysPanel.vue'
```

2. 将现有的 `<span @click>` 标签**全部改为 `<button>`**（修复 CLAUDE.md 反模式），并在末尾添加新 AI tab：
```html
<button v-if="hasPermission('admin')" @click="settingsTab = 'ai'" :class="['tab', settingsTab === 'ai' ? 'active' : '']">AI 助手配置</button>
```
注意使用 `hasPermission('admin')` 而非 `authStore.user?.role`（与现有模式一致）。

3. 在 `<Transition>` 的内容区域添加新面板：
```html
<div v-else-if="settingsTab === 'ai'" key="ai">
  <ApiKeysPanel />
</div>
```

注意：新 tab 使用 `<button>` 而非 `<span>`（修复 CLAUDE.md 反模式）。同时建议将现有的 `<span @click>` 标签也改为 `<button>`。

- [ ] **Step 2: Build 验证**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
```

Expected: 构建成功

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/SettingsView.vue
git commit -m "feat(ai): 设置页添加 AI 助手配置 Tab"
```

---

### Task 16: AiMessage + AiChartRenderer Components

**Files:**
- Create: `frontend/src/components/business/AiChartRenderer.vue`
- Create: `frontend/src/components/business/AiMessage.vue`

- [ ] **Step 1: Create chart renderer**

Create `frontend/src/components/business/AiChartRenderer.vue`:

```vue
<template>
  <div class="ai-chart-container">
    <canvas ref="canvasRef" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

const props = defineProps({
  config: { type: Object, required: true },
})

const canvasRef = ref(null)
let chartInstance = null

const getThemeColors = () => {
  const style = getComputedStyle(document.documentElement)
  return {
    text: style.getPropertyValue('--text').trim() || '#0a0a0a',
    textMuted: style.getPropertyValue('--text-muted').trim() || '#555',
    border: style.getPropertyValue('--border').trim() || '#e5e5e5',
    primary: style.getPropertyValue('--primary').trim() || '#3b82f6',
  }
}

const PALETTE = [
  'oklch(0.55 0.20 250)',   // primary blue
  'oklch(0.65 0.20 145)',   // green
  'oklch(0.75 0.18 75)',    // amber
  'oklch(0.60 0.25 25)',    // red
  'oklch(0.60 0.18 300)',   // purple
  'oklch(0.70 0.15 200)',   // teal
]

const renderChart = () => {
  if (!canvasRef.value || !props.config) return
  if (chartInstance) chartInstance.destroy()

  const colors = getThemeColors()
  const cfg = props.config

  const datasets = (cfg.datasets || []).map((ds, i) => ({
    ...ds,
    backgroundColor: ds.backgroundColor || PALETTE[i % PALETTE.length],
    borderColor: ds.borderColor || PALETTE[i % PALETTE.length],
    borderWidth: cfg.chart_type === 'line' ? 2 : 0,
    tension: 0.3,
  }))

  chartInstance = new Chart(canvasRef.value, {
    type: cfg.chart_type || 'bar',
    data: { labels: cfg.labels || [], datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: !!cfg.title,
          text: cfg.title || '',
          color: colors.text,
          font: { size: 14, weight: 500 },
        },
        legend: {
          labels: { color: colors.textMuted, font: { size: 12 } },
        },
      },
      scales: cfg.chart_type === 'pie' || cfg.chart_type === 'doughnut' ? {} : {
        x: { ticks: { color: colors.textMuted }, grid: { color: colors.border } },
        y: { ticks: { color: colors.textMuted }, grid: { color: colors.border } },
      },
    },
  })
}

watch(() => props.config, renderChart, { deep: true })
onMounted(renderChart)
onBeforeUnmount(() => { if (chartInstance) chartInstance.destroy() })
</script>

<style scoped>
.ai-chart-container {
  height: 240px;
  position: relative;
}
</style>
```

- [ ] **Step 2: Create message component**

Create `frontend/src/components/business/AiMessage.vue`:

```vue
<template>
  <div class="ai-msg" :class="msg.role">
    <!-- 用户消息 -->
    <div v-if="msg.role === 'user'" class="ai-msg-user">
      {{ msg.content }}
    </div>

    <!-- AI 消息 -->
    <div v-else class="ai-msg-ai">
      <!-- 加载中 -->
      <div v-if="msg.loading" class="flex items-center gap-2 text-muted text-sm">
        <div class="ai-typing">
          <span /><span /><span />
        </div>
        思考中...
      </div>

      <!-- 澄清 -->
      <template v-else-if="msg.type === 'clarification'">
        <p class="text-sm mb-2">{{ msg.message }}</p>
        <div class="flex flex-wrap gap-2">
          <button v-for="opt in (msg.options || [])" :key="opt" class="btn btn-secondary btn-sm text-xs" @click="$emit('select-option', opt)">
            {{ opt }}
          </button>
        </div>
      </template>

      <!-- 错误 -->
      <template v-else-if="msg.type === 'error'">
        <p class="text-sm text-error">{{ msg.message }}</p>
      </template>

      <!-- 正常回答 -->
      <template v-else-if="msg.type === 'answer'">
        <!-- 文字分析 -->
        <div v-if="msg.analysis" class="ai-analysis text-sm" v-html="renderMarkdown(msg.analysis)" />

        <!-- 数据表格 -->
        <div v-if="msg.table_data" class="mt-3 border rounded-lg overflow-hidden">
          <div class="overflow-x-auto max-h-[300px]">
            <table class="w-full text-sm">
              <thead class="bg-elevated sticky top-0">
                <tr>
                  <th v-for="col in msg.table_data.columns" :key="col" class="px-3 py-2 text-left text-xs font-medium text-muted whitespace-nowrap">
                    {{ col }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in msg.table_data.rows" :key="ri" class="border-t">
                  <td v-for="(cell, ci) in row" :key="ci" class="px-3 py-1.5 whitespace-nowrap" :class="isNumber(cell) ? 'tabular-nums font-mono text-right' : ''">
                    {{ formatCell(cell) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="px-3 py-1.5 text-xs text-muted border-t bg-elevated">
            共 {{ msg.row_count }} 行
          </div>
        </div>

        <!-- 图表 -->
        <AiChartRenderer v-if="msg.chart_config" :config="msg.chart_config" class="mt-3" />

        <!-- SQL 折叠 -->
        <details v-if="msg.sql" class="mt-3">
          <summary class="text-xs text-muted cursor-pointer">查看 SQL</summary>
          <pre class="mt-1 p-2 bg-elevated rounded text-xs font-mono overflow-x-auto">{{ msg.sql }}</pre>
        </details>

        <!-- 操作栏 -->
        <div class="flex items-center gap-3 mt-3 pt-2 border-t">
          <button v-if="msg.table_data" class="text-xs text-muted hover:text-primary" @click="copyTable" title="复制表格">
            <Copy :size="14" />
          </button>
          <button v-if="msg.table_data" class="text-xs text-muted hover:text-primary" @click="$emit('export', msg)" title="导出 Excel">
            <Download :size="14" />
          </button>
          <div class="flex-1" />
          <button class="text-xs px-2 py-1 rounded" :class="msg.feedback === 'positive' ? 'bg-success-subtle text-success-emphasis' : 'text-muted hover:text-success'" @click="$emit('feedback', msg, 'positive')">
            <ThumbsUp :size="14" />
          </button>
          <button class="text-xs px-2 py-1 rounded" :class="msg.feedback === 'negative' ? 'bg-error-subtle text-error-emphasis' : 'text-muted hover:text-error'" @click="$emit('feedback', msg, 'negative')">
            <ThumbsDown :size="14" />
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { Copy, Download, ThumbsUp, ThumbsDown } from 'lucide-vue-next'
import AiChartRenderer from './AiChartRenderer.vue'
import { useAppStore } from '../../stores/app'

const appStore = useAppStore()

const props = defineProps({
  msg: { type: Object, required: true },
})

defineEmits(['select-option', 'export', 'feedback'])

const isNumber = (val) => typeof val === 'number'

const formatCell = (val) => {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'number') {
    return Number.isInteger(val) ? val.toLocaleString() : val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  return String(val)
}

const renderMarkdown = (text) => {
  if (!text) return ''
  // 轻量 Markdown：加粗、列表、换行（防 XSS）
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
  // 处理列表项：连续的 "- xxx<br>" 行合并为 <ul>
  html = html.replace(/(?:^|<br>)((?:- .+?(?:<br>|$))+)/g, (_, block) => {
    const items = block.replace(/<br>$/g, '').split('<br>').map(
      line => '<li>' + line.replace(/^- /, '') + '</li>'
    ).join('')
    return '<ul>' + items + '</ul>'
  })
  return html
}

const copyTable = async () => {
  if (!props.msg.table_data) return
  const { columns, rows } = props.msg.table_data
  const tsv = [columns.join('\t'), ...rows.map(r => r.map(c => c ?? '').join('\t'))].join('\n')
  try {
    await navigator.clipboard.writeText(tsv)
    appStore.showToast('已复制到剪贴板')
  } catch {
    appStore.showToast('复制失败', 'error')
  }
}
</script>

<style scoped>
.ai-msg-user {
  background: var(--primary-muted);
  color: var(--text);
  padding: 8px 12px;
  border-radius: 12px 12px 4px 12px;
  max-width: 85%;
  margin-left: auto;
  font-size: 14px;
}
.ai-msg-ai {
  background: var(--elevated);
  padding: 10px 14px;
  border-radius: 4px 12px 12px 12px;
  max-width: 95%;
  font-size: 14px;
}
.ai-typing span {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: typing 1.2s infinite;
  margin-right: 3px;
}
.ai-typing span:nth-child(2) { animation-delay: 0.2s; }
.ai-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/business/AiChartRenderer.vue frontend/src/components/business/AiMessage.vue
git commit -m "feat(ai): AI 消息 + 图表渲染组件"
```

---

### Task 17: AiChatbot Main Component + App.vue Integration

**Files:**
- Create: `frontend/src/components/business/AiChatbot.vue`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Create AiChatbot**

Create `frontend/src/components/business/AiChatbot.vue`:

```vue
<template>
  <!-- 入口按钮 -->
  <button v-if="available && !open" class="ai-fab" @click="open = true" title="AI 数据助手">
    <Sparkles :size="22" />
  </button>

  <!-- 聊天窗口 -->
  <Transition name="slide-up">
    <div v-if="open" class="ai-window" :class="{ 'ai-window-mobile': isMobile }">
      <!-- 标题栏 -->
      <div class="ai-header">
        <div class="flex items-center gap-2">
          <Sparkles :size="16" />
          <span class="font-semibold text-sm">AI 数据助手</span>
        </div>
        <div class="flex items-center gap-1">
          <button class="ai-header-btn" @click="clearChat" title="清空对话">
            <RotateCcw :size="14" />
          </button>
          <button class="ai-header-btn" @click="open = false" title="关闭">
            <X :size="16" />
          </button>
        </div>
      </div>

      <!-- 消息区域 -->
      <div ref="messagesRef" class="ai-messages">
        <!-- 欢迎语 -->
        <div v-if="messages.length === 0" class="text-center py-8 text-muted">
          <Sparkles :size="32" class="mx-auto mb-3 opacity-30" />
          <p class="text-sm mb-4">你好！我是 AI 数据助手，可以帮你查询和分析业务数据。</p>
          <div v-if="presetQueries.length" class="flex flex-wrap gap-2 justify-center">
            <button v-for="pq in presetQueries" :key="pq.display" class="btn btn-secondary btn-sm text-xs" @click="sendMessage(pq.display)">
              {{ pq.display }}
            </button>
          </div>
        </div>

        <AiMessage
          v-for="(msg, i) in messages" :key="i"
          :msg="msg"
          @select-option="handleSelectOption"
          @export="handleExport"
          @feedback="handleFeedback"
        />
      </div>

      <!-- 输入区域 -->
      <div class="ai-input-area">
        <textarea
          ref="inputRef"
          v-model="input"
          class="ai-input"
          placeholder="输入你的问题..."
          rows="1"
          @keydown.enter.exact.prevent="sendMessage(input)"
          @input="autoResize"
        />
        <button class="ai-send-btn" @click="sendMessage(input)" :disabled="!input.trim() || loading">
          <Send :size="16" />
        </button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { Sparkles, X, RotateCcw, Send } from 'lucide-vue-next'
import AiMessage from './AiMessage.vue'
import { aiChat, aiExport, aiFeedback, getAiStatus } from '../../api/ai'
import { useAppStore } from '../../stores/app'

const appStore = useAppStore()

const open = ref(false)
const available = ref(false)
const loading = ref(false)
const input = ref('')
const messages = ref([])
const presetQueries = ref([])
const messagesRef = ref(null)
const inputRef = ref(null)
// 使用 matchMedia 实现真正的响应式
const isMobile = ref(false)
const mql = window.matchMedia('(max-width: 767px)')
const updateMobile = (e) => { isMobile.value = e.matches }
onMounted(() => {
  isMobile.value = mql.matches
  mql.addEventListener('change', updateMobile)
})
onUnmounted(() => mql.removeEventListener('change', updateMobile))

const checkStatus = async () => {
  try {
    const { data } = await getAiStatus()
    available.value = data.available
    if (data.available) {
      // 预设问题随 status 一起返回，所有用户可见
      presetQueries.value = data.preset_queries || []
    }
  } catch {
    available.value = false
  }
}

const buildHistory = () => {
  return messages.value
    .filter(m => !m.loading && (m.role === 'user' || m.type === 'answer'))
    .slice(-20)
    .map(m => ({
      role: m.role,
      content: m.role === 'user' ? m.content : (m.analysis || m.message || ''),
    }))
}

const sendMessage = async (text) => {
  if (!text || !text.trim() || loading.value) return
  const msg = text.trim()
  input.value = ''
  autoResize()

  messages.value.push({ role: 'user', content: msg })
  const aiMsg = { role: 'assistant', loading: true }
  messages.value.push(aiMsg)
  scrollToBottom()

  loading.value = true
  try {
    const { data } = await aiChat({
      message: msg,
      history: buildHistory().slice(0, -2), // 排除当前这轮
    })
    Object.assign(aiMsg, data, { loading: false, role: 'assistant', _question: msg })
  } catch (e) {
    Object.assign(aiMsg, {
      loading: false,
      type: 'error',
      message: e.response?.data?.message || '请求失败，请检查网络连接',
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

const handleSelectOption = (option) => {
  sendMessage(option)
}

const handleExport = async (msg) => {
  if (!msg.table_data) return
  try {
    const { data } = await aiExport({ table_data: msg.table_data, title: 'AI查询结果' })
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'AI查询结果.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    appStore.showToast('导出失败', 'error')
  }
}

const handleFeedback = async (msg, type) => {
  if (msg.feedback) return // 已反馈
  msg.feedback = type
  try {
    await aiFeedback({
      message_id: msg.message_id,
      feedback: type,
      save_as_example: type === 'positive',
      original_question: msg._question,
      sql: msg.sql,
    })
  } catch { /* silent */ }
}

const clearChat = () => {
  messages.value = []
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

const autoResize = () => {
  nextTick(() => {
    if (inputRef.value) {
      inputRef.value.style.height = 'auto'
      inputRef.value.style.height = Math.min(inputRef.value.scrollHeight, 100) + 'px'
    }
  })
}

onMounted(checkStatus)
</script>

<style scoped>
.ai-fab {
  position: fixed;
  right: 20px;
  bottom: 20px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--primary);
  color: var(--on-primary);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-lg);
  z-index: 1000;
  transition: transform 0.2s;
}
.ai-fab:hover { transform: scale(1.08); }

.ai-window {
  position: fixed;
  right: 20px;
  bottom: 20px;
  width: 400px;
  height: 600px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  z-index: 1001;
  box-shadow: var(--shadow-xl);
  overflow: hidden;
}
.ai-window-mobile {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  border-radius: 0;
  right: 0;
  bottom: 0;
}
.ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--elevated);
}
.ai-header-btn {
  padding: 4px;
  border-radius: 6px;
  color: var(--text-muted);
  background: none;
  border: none;
  cursor: pointer;
}
.ai-header-btn:hover { background: var(--surface-hover); }
.ai-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ai-input-area {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  background: var(--surface);
}
.ai-input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 14px;
  resize: none;
  background: var(--bg);
  color: var(--text);
  outline: none;
  min-height: 36px;
  max-height: 100px;
  line-height: 1.4;
}
.ai-input:focus { border-color: var(--primary); box-shadow: 0 0 0 2px var(--primary-ring); }
.ai-send-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--primary);
  color: var(--on-primary);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ai-send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.slide-up-enter-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.slide-up-leave-active { transition: all 0.2s ease-in; }
.slide-up-enter-from { transform: translateY(20px) scale(0.95); opacity: 0; }
.slide-up-leave-to { transform: translateY(10px); opacity: 0; }

@media (max-width: 768px) {
  .ai-fab { right: 16px; bottom: 72px; }
}
</style>
```

- [ ] **Step 2: Update App.vue — mount chatbot**

在 `frontend/src/App.vue` 中：

1. 在 import 区域添加：
```javascript
import AiChatbot from './components/business/AiChatbot.vue'
```

2. 在 `app-layout` div 内部的末尾（`<BottomNav>` 之后、`</div>` 之前）添加：
```html
<AiChatbot />
```
注意：`app-layout` 已被 `v-if="authStore.user"` 保护，所以 chatbot 只在登录后渲染，无需额外 `v-if`。

- [ ] **Step 3: Build 验证**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
```

Expected: 构建成功

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/business/AiChatbot.vue frontend/src/App.vue
git commit -m "feat(ai): AI 聊天浮窗 + App.vue 集成"
```

---

### Task 18: Health Check + Final Build Verification

**Files:**
- Create: `backend/app/ai/health_check.py`

- [ ] **Step 1: Create health check script**

Create `backend/app/ai/health_check.py`:

```python
"""AI 模块健康检查脚本 — python -m app.ai.health_check"""
from __future__ import annotations
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


async def main():
    from app.database import init_db, close_db
    from tortoise import connections

    print("=" * 50)
    print("ERP AI 模块健康检查")
    print("=" * 50)

    await init_db()
    conn = connections.get("default")
    errors = []

    # 1. 检查只读用户
    print("\n[1/4] 检查 AI 只读用户...")
    result = await conn.execute_query_dict("SELECT 1 FROM pg_roles WHERE rolname = 'erp_ai_readonly'")
    if result:
        print("  ✓ erp_ai_readonly 用户存在")
    else:
        errors.append("erp_ai_readonly 用户不存在")
        print("  ✗ erp_ai_readonly 用户不存在")

    # 2. 检查语义视图
    print("\n[2/4] 检查语义视图...")
    views = ["vw_sales_detail", "vw_sales_summary", "vw_purchase_detail",
             "vw_inventory_status", "vw_inventory_turnover", "vw_receivables", "vw_payables"]
    for v in views:
        try:
            await conn.execute_query(f"SELECT 1 FROM {v} LIMIT 0")
            print(f"  ✓ {v}")
        except Exception as e:
            errors.append(f"视图 {v} 异常: {e}")
            print(f"  ✗ {v}: {e}")

    # 3. 检查 API Key 配置
    print("\n[3/4] 检查 DeepSeek 配置...")
    from app.models import SystemSetting
    key_setting = await SystemSetting.filter(key="ai.deepseek.api_key").first()
    if key_setting and key_setting.value:
        print("  ✓ DeepSeek API Key 已配置")
    else:
        errors.append("DeepSeek API Key 未配置")
        print("  ✗ DeepSeek API Key 未配置")

    # 4. 检查 Few-shot 示例
    print("\n[4/4] 检查 Few-shot 示例...")
    shots_setting = await SystemSetting.filter(key="ai.few_shots").first()
    if shots_setting and shots_setting.value:
        import json
        shots = json.loads(shots_setting.value)
        print(f"  ✓ {len(shots)} 个示例")
        # 验证示例 SQL 是否可执行
        from app.ai.sql_validator import validate_sql
        for shot in shots:
            ok, _, reason = validate_sql(shot.get("sql", ""))
            if not ok:
                print(f"  ⚠ 示例 SQL 校验失败: {shot.get('question', '')[:30]}... — {reason}")
    else:
        print("  ○ 未配置自定义示例（使用默认）")

    await close_db()

    print("\n" + "=" * 50)
    if errors:
        print(f"发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("所有检查通过 ✓")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Final build verification**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
```

Expected: 构建成功，无错误

- [ ] **Step 3: Commit all**

```bash
git add backend/app/ai/health_check.py
git commit -m "feat(ai): 健康检查脚本 + 最终构建验证"
```

---
