# ERP-4 AI Chatbot 设计规格文档

> 日期：2026-03-12
> 状态：待审核

## 1. 概述

### 1.1 目标

在现有 ERP-4 系统中集成 AI 数据助手，用户通过自然语言（大白话）查询业务数据，系统自动检索、整理并分析。

### 1.2 核心用例

- "帮我查一下客户 A 在 1-3 月的手机壳销售情况，整理个数据表并分析"
- "这个月启领的毛利怎么样"
- "SKU ABC123 的库存管理做得怎么样"
- "各品牌的应收账款汇总"

### 1.3 技术路线

NL2SQL（自然语言转 SQL）+ 双模型分工 + 语义视图层 + 四层安全纵深防御。

### 1.4 关键约束

- AI **绝对只读**，不能修改任何数据
- AI 模块的任何故障**不影响 ERP 主业务**
- 接入 DeepSeek API（R1 生成 SQL，V3 分析数据）
- API 密钥等配置通过前端 UI 管理，不硬编码在代码中
- 多账套感知：查询涉及账套数据时，AI 主动澄清范围

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Vue.js 前端                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │  AiChatbot.vue（右下浮窗 / 移动端全屏）            │  │
│  │  消息流：Markdown + 数据表格 + Chart.js + 导出     │  │
│  └────────────────────┬──────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  设置 > AI 助手配置 Tab（仅 admin）                │  │
│  │  API 密钥 / 提示词 / 业务词典 / 示例库 / 快捷问题  │  │
│  └────────────────────┬──────────────────────────────┘  │
└───────────────────────┼──────────────────────────────────┘
                        │ POST /api/ai/chat
┌───────────────────────┼──────────────────────────────────┐
│              FastAPI 后端 (ai 模块)                       │
│                       ▼                                   │
│  ┌────────────────────────────────────────────────────┐  │
│  │  1. 意图预分类器                                    │  │
│  │     ├─ 高频查询 → 预置 SQL 模板（100% 准确）        │  │
│  │     └─ 自由查询 → 2                                 │  │
│  │  2. Prompt 组装（视图 schema + 词典 + few-shot）     │  │
│  │  3. DeepSeek R1 → 生成 SQL 或澄清问题 (temp=0.0)   │  │
│  │  4. sqlglot AST 安全校验                            │  │
│  │  5. 只读用户执行 SQL (READ ONLY 事务)               │  │
│  │     ├─ 成功 → 6                                     │  │
│  │     └─ 报错 → 反馈 R1 重试（最多 2 次）             │  │
│  │  6. DeepSeek V3 → 分析 + 图表参数 (temp=0.7)       │  │
│  │  7. 返回 JSON                                       │  │
│  └────────────────────────────────────────────────────┘  │
│                       │                                   │
│  独立 asyncpg 连接池（max=5, timeout=30s）               │
└───────────────────────┼───────────────────────────────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼                             ▼
┌──────────────────┐         ┌──────────────────┐
│ PostgreSQL       │         │ DeepSeek API     │
│ 同一实例         │         │ R1 + V3          │
│ erp_ai_readonly  │         └──────────────────┘
│ + 语义视图层     │
└──────────────────┘
```

---

## 3. 语义视图层

在 PostgreSQL 中创建 7 个只读语义视图，预聚合常见查询模式，降低 SQL 生成难度。

### 3.1 视图清单

| 视图名 | 用途 | 核心字段 | 含账套 |
|--------|------|---------|--------|
| `vw_sales_detail` | 销售明细宽表 | 订单号、客户名、产品 SKU/名称/品牌/分类、数量、单价、金额、成本、毛利、毛利率、业务员、账套名、订单日期 | 是 |
| `vw_sales_summary` | 销售按月汇总 | 年月、订单数、总销售额、总成本、总毛利、毛利率、客户数、账套名 | 是 |
| `vw_purchase_detail` | 采购明细宽表 | 采购单号、供应商名、产品、数量、含税价、去税价、金额、状态、账套名、日期 | 是 |
| `vw_inventory_status` | 当前库存状态 | SKU、产品名、品牌、仓库名、库位、数量、预留数、可用数、加权成本、库存金额、是否低库存 | 否 |
| `vw_inventory_turnover` | 库存周转分析 | SKU、产品名、品牌、当前库存、近 30 天出库量、近 90 天出库量、周转率、库龄 | 否 |
| `vw_receivables` | 应收账款 | 客户名、应收单号、应收金额、已收金额、未收金额、状态、账龄天数、账套名 | 是 |
| `vw_payables` | 应付账款 | 供应商名、应付单号、应付金额、已付金额、未付金额、状态、账龄天数、账套名 | 是 |

### 3.2 设计原则

- 视图内部完成多表 JOIN，LLM 只需 `SELECT ... FROM vw_xxx WHERE ... GROUP BY ...`
- 金额字段已 `ROUND(..., 2)`
- 毛利率已预算 `profit / NULLIF(amount, 0) * 100`
- 日期字段统一命名（`order_date`、`bill_date`）
- 销售视图内部已排除退货单（`order_type != 'return'`）
- 视图定义存放在 `backend/app/ai/views.sql`，由初始化脚本自动执行
- 视图由主数据库用户（`erp`）创建和拥有，`erp_ai_readonly` 用户通过 `GRANT SELECT` 获得只读访问权限
- 视图使用默认的 `SECURITY INVOKER` 模式（以查询者权限执行），确保 readonly 用户的权限约束不被绕过
- LLM 仍可访问原始表（作为 fallback），但 system prompt 引导优先使用视图

---

## 4. 多账套澄清机制

### 4.1 账套上下文注入

每次请求时从数据库查询可用账套列表，注入 system prompt，告知 LLM：

- 当前可用账套名称和 ID
- 当查询涉及财务/销售/采购数据且未指定账套时，必须反问用户
- 当用户指定了账套 → 加 `WHERE account_set_name = 'xxx'`
- 当用户说"全部" → 按账套分组 `GROUP BY account_set_name`
- 与账套无关的查询（纯库存）→ 不问

### 4.2 LLM 响应分类

LLM 返回 JSON 必须包含 `type` 字段：

- `"type": "clarification"` — 需要澄清，附带 `message` 和 `options`
- `"type": "sql"` — 生成了 SQL，附带 `sql` 和 `explanation`

后端根据 type 走不同分支。

---

## 5. 后端模块设计

### 5.1 新增文件结构

```
backend/app/
├── ai/
│   ├── __init__.py
│   ├── schema_registry.py       # 视图+表 schema 注册（启动时缓存）
│   ├── business_dict.py         # 默认业务词典（代码中的初始值）
│   ├── few_shots.py             # 默认 few-shot 示例（代码中的初始值）
│   ├── intent_classifier.py     # 意图预分类 + 预置 SQL 模板
│   ├── sql_validator.py         # sqlglot AST 安全校验
│   ├── deepseek_client.py       # DeepSeek API 客户端（R1/V3）
│   ├── prompt_builder.py        # System prompt 组装器
│   ├── views.sql                # 语义视图 DDL 定义
│   └── health_check.py          # 维护健康检查脚本
├── routers/
│   ├── ai_chat.py               # AI 聊天 + 导出 + 反馈 + 状态路由
│   └── api_keys.py              # API 密钥 + AI 配置管理路由
├── services/
│   └── ai_chat_service.py       # NL2SQL 主流程编排
```

### 5.2 配置存储

所有 AI 相关配置存储在 `SystemSetting` 表中，通过 admin UI 管理：

| Key | 内容 | 加密 |
|-----|------|------|
| `ai.deepseek.api_key` | DeepSeek API Key | AES 加密 |
| `ai.deepseek.base_url` | API 地址 | 否 |
| `ai.deepseek.model_sql` | SQL 生成模型 | 否 |
| `ai.deepseek.model_analysis` | 分析模型 | 否 |
| `api.kd100.key` | 快递 100 Key | AES 加密 |
| `api.kd100.customer` | 快递 100 Customer | 否 |
| `api.kd100.secret` | 快递 100 Secret | AES 加密 |
| `ai.prompt.system` | SQL 生成系统提示词 | 否 |
| `ai.prompt.analysis` | 数据分析提示词 | 否 |
| `ai.business_dict` | 业务词典 JSON | 否 |
| `ai.few_shots` | Few-shot 示例 JSON | 否 |
| `ai.preset_queries` | 预设快捷问题 JSON | 否 |

配置读取带 **5 分钟内存缓存**，变更后自动刷新，无需重启服务。

新增环境变量：

| 变量名 | 用途 | 必需 |
|--------|------|------|
| `API_KEYS_ENCRYPTION_SECRET` | AES 加密 API Key | 是，未设置容器拒绝启动 |
| `AI_DB_PASSWORD` | AI 只读数据库用户密码 | 否，未设置时自动生成并记录到日志 |

在 `docker-compose.yml` 中使用 `${API_KEYS_ENCRYPTION_SECRET:?请设置 API 密钥加密密钥}` 语法。

### 5.2.1 KD100 配置迁移

现有快递 100 配置从环境变量（`KD100_KEY`、`KD100_CUSTOMER`）读取。迁移策略：

1. `logistics_service.py` 重构为优先从 `SystemSetting` 读取，fallback 到环境变量
2. 首次启动时检测：如果 `SystemSetting` 中无 KD100 配置但环境变量有值，自动迁移写入
3. 迁移完成后环境变量仍可保留，但 `SystemSetting` 优先级更高
4. 前端 API 密钥管理页面统一管理所有第三方 API 密钥

### 5.3 Schema 注册器

启动时自动从 Tortoise ORM models 和语义视图定义生成 schema 文本描述：

- 遍历所有 Model 子类，提取表名、字段名、类型、外键
- 附加中文注释
- 排除 `users` 和 `system_settings` 表
- 排除敏感列（银行账号、税号等）
- 语义视图 schema 单独生成，在 prompt 中优先展示
- 结果缓存在内存中，应用生命周期内不变

### 5.4 意图预分类器

关键词匹配 + 编辑距离模糊匹配，命中预置模板时直接返回 SQL，跳过 LLM：

- 预置模板存储在 `SystemSetting`（`ai.preset_queries`）
- 用户可通过 UI 增删改
- 未命中则走 NL2SQL 流程

### 5.5 SQL 校验器（sqlglot AST）

```python
def validate_sql(sql: str) -> tuple[bool, str, str]:
    """
    返回 (is_safe, sanitized_sql, rejection_reason)

    校验规则：
    1. sqlglot.parse() 解析为 AST，解析失败 → 拒绝
    2. 根节点必须是 SELECT → 否则拒绝
    3. 遍历 AST 节点，禁止 DML/DDL（INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE）
    4. 禁止分号（多语句注入）
    5. 禁止 INTO 关键词（SELECT INTO）
    6. 禁止引用 BLOCKED_TABLES（users, system_settings）
    7. 禁止 UNION 嵌套超过 2 层
    8. 如果没有 LIMIT → 追加 LIMIT 1000
    9. 如果 LIMIT > 1000 → 修改为 1000
    """
```

### 5.6 自动纠错循环

SQL 执行报错时，将错误信息反馈给 R1 重新生成：

- 最多重试 2 次（共 3 次机会）
- 每次重试在 prompt 中附加前次的 SQL 和错误信息
- 第 3 次仍失败 → 返回友好提示

### 5.7 DeepSeek Client

- 从 `SystemSetting` 读取配置（API Key 解密后使用）
- 独立的 `httpx.AsyncClient`，与 ERP 业务 HTTP 客户端完全分离
- 请求超时 60 秒
- 失败重试 1 次
- 所有异常被捕获，不向上传播

### 5.8 数据库只读用户初始化

```sql
CREATE USER erp_ai_readonly WITH PASSWORD 'xxx';
GRANT CONNECT ON DATABASE erp TO erp_ai_readonly;
GRANT USAGE ON SCHEMA public TO erp_ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO erp_ai_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO erp_ai_readonly;

-- 排除敏感表
REVOKE SELECT ON users FROM erp_ai_readonly;
REVOKE SELECT ON system_settings FROM erp_ai_readonly;

-- 资源限制
ALTER USER erp_ai_readonly SET statement_timeout = '30s';
ALTER USER erp_ai_readonly SET work_mem = '16MB';
ALTER USER erp_ai_readonly SET temp_file_limit = '100MB';
ALTER USER erp_ai_readonly CONNECTION LIMIT 5;
```

通过 `backend/app/migrations.py` 中新增迁移步骤执行（与现有迁移模式一致）。迁移逻辑：
1. 检查 `erp_ai_readonly` 用户是否存在（`SELECT 1 FROM pg_roles WHERE rolname = 'erp_ai_readonly'`）
2. 不存在则创建用户、授权、设资源限制
3. 创建/更新语义视图（执行 `backend/app/ai/views.sql`）
4. 密码从 `AI_DB_PASSWORD` 环境变量读取，默认随机生成并记录到日志

---

## 6. 安全设计

### 6.1 四层数据保护

| 层 | 机制 | 独立拦截能力 |
|----|------|-------------|
| 1 | System Prompt 防注入指令 | LLM 拒绝生成恶意 SQL |
| 2 | sqlglot AST 解析校验 | 代码层拦截非 SELECT 语句 |
| 3 | PostgreSQL 只读用户权限 | 数据库拒绝执行写操作 |
| 4 | READ ONLY 事务模式 | 事务级写操作拦截 |

### 6.2 数据泄露防护

- Schema 注册时排除 `users`、`system_settings` 表
- 排除敏感列（`tax_id`、`bank_account`、`bank_name`、`password_hash`）
- AST 校验二次拦截对敏感表的访问
- 数据库权限三次拦截（REVOKE）

### 6.3 资源隔离（防止拖垮 ERP）

- AI 独立 asyncpg 连接池（max=5），与 Tortoise ORM 连接池完全分离
- 单条 SQL 超时 30 秒（数据库层面强制）
- 单查询内存限制 16MB
- 结果集强制 LIMIT 1000
- 传给 V3 分析的数据最多 100 行
- DeepSeek API 请求超时 60 秒
- AI 模块所有异常被 try/except 捕获，不向 ERP 主流程传播

**asyncpg 连接池生命周期：**
- 在 FastAPI `lifespan` 事件的 startup 阶段创建，与应用启动绑定
- 在 lifespan 的 shutdown 阶段调用 `pool.close()` 优雅关闭
- AI 未配置（无 API Key）时**不创建连接池**，避免无谓的数据库连接
- 配置变更（如 admin 修改了 AI 数据库密码）后，下次请求时惰性重建连接池

### 6.4 API Key 安全

- AES 加密存储，明文不落盘
- GET 接口只返回脱敏版（`sk-xxx...***`）
- 日志中自动替换为 `[REDACTED]`
- DeepSeek 原始错误信息不暴露给前端

### 6.5 滥用防护

- 每用户每分钟 10 次请求
- 全局每分钟 60 次请求
- DeepSeek API 最大并发 3
- 数据库连接上限 5
- 实现方式：内存字典 + 滑动窗口计数器（单容器部署，无需 Redis）
- 触发限流时返回 HTTP 429 + `{"type": "error", "message": "请求过于频繁，请稍后再试"}`

### 6.6 输入验证

- chat message 最大长度 2000 字符
- history 数组最大 10 轮（20 条消息）
- history 每条消息最大 5000 字符
- 清洗：strip 前后空白、移除控制字符（保留换行）
- 超出限制返回 HTTP 422 + 友好提示

---

## 7. API 接口设计

### 7.1 AI 聊天

**POST /api/ai/chat**（需 JWT 认证）

请求：
```json
{
  "message": "这个月启领的毛利怎么样",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

响应（成功）：
```json
{
  "type": "answer",
  "message_id": "uuid",
  "analysis": "Markdown 格式的分析文本",
  "table_data": {
    "columns": ["周", "销售额", "成本", "毛利", "毛利率"],
    "rows": [["第1周", 45200, 32100, 13100, "29.0%"]]
  },
  "chart_config": {
    "chart_type": "bar",
    "title": "...",
    "labels": ["..."],
    "datasets": [{"label": "...", "data": []}]
  },
  "sql": "SELECT ...",
  "row_count": 4
}
```

响应（澄清）：
```json
{
  "type": "clarification",
  "message_id": "uuid",
  "message": "请问你要查看哪个账套的毛利数据？",
  "options": ["启领", "链雾", "全部汇总"]
}
```

响应（错误，无 `message_id`）：
```json
{
  "type": "error",
  "message": "抱歉，我无法理解这个查询，能换个说法试试吗？"
}
```

history 最多保留最近 10 轮对话。

### 7.1.1 聊天会话管理

- 对话历史**仅存储在浏览器内存中**（组件 ref），不持久化到服务端或 localStorage
- 页面刷新后对话清空，每次打开 chatbot 是全新会话
- `message_id` 为后端生成的 UUID，用于反馈接口关联，不用于消息检索
- 前端 Axios 请求超时设为 **90 秒**（覆盖默认 30 秒，因为 R1 推理可能较慢）

### 7.1.2 AI 可用性检查

**GET /api/ai/status**（需 JWT 认证）

响应：`{ "available": true, "reason": null }`

前端在用户登录后调用，`available=false` 时隐藏 chatbot 按钮。不可用原因包括：DeepSeek API Key 未配置、只读用户未创建。

### 7.2 导出

**POST /api/ai/chat/export**（需 JWT 认证）

请求：`{ "table_data": {...}, "title": "..." }`

响应：`.xlsx` 文件流

### 7.3 反馈

**POST /api/ai/chat/feedback**（需 JWT 认证）

请求：
```json
{
  "message_id": "uuid",
  "feedback": "positive | negative",
  "save_as_example": true,
  "original_question": "...",
  "sql": "...",
  "negative_reason": "data_error | understanding_error | format_error"
}
```

### 7.4 API 密钥管理

**GET /api/api-keys**（仅 admin 角色）

响应：所有 API 配置，密钥脱敏显示。

**PUT /api/api-keys**（仅 admin 角色）

请求：`{ "ai.deepseek.api_key": "sk-new...", ... }`

**POST /api/api-keys/test-deepseek**（仅 admin 角色）

测试 DeepSeek 连接是否正常。

### 7.5 AI 配置管理

**GET /api/ai/config**（仅 admin 角色）

响应：提示词、业务词典、示例库、快捷问题。

**PUT /api/ai/config**（仅 admin 角色）

请求：`{ "prompt_system": "...", "business_dict": [...], ... }`

---

## 8. 前端设计

### 8.1 Chatbot 浮窗组件

- 入口：右下角固定圆形按钮（Sparkles 图标）
- 桌面端：400x600px 浮窗，右下角弹出
- 移动端（< 768px）：全屏展示
- 顶部：标题 "AI 数据助手" + 最小化/关闭按钮
- 消息区域：可滚动，自动滚底
- 底部：输入框（Enter 发送，Shift+Enter 换行）+ 发送按钮
- 首次打开显示欢迎语 + 预设快捷问题标签

### 8.2 消息组件

每条 AI 回复包含以下可选区块：

1. **文字分析区** — Markdown 渲染（轻量实现，支持加粗、表格、列表、换行）
2. **数据表格区** — 可横向滚动，金额用 Geist Mono + tabular-nums
3. **图表区** — Chart.js 渲染，根据 chart_config 自动选型（柱/折线/饼），跟随主题色
4. **SQL 折叠区** — 默认收起，点击展开，monospace 字体
5. **操作栏** — 复制表格（TSV）/ 导出 Excel / 👍 / 👎
6. **澄清选项** — 当 type=clarification 时显示可点击标签

### 8.3 图表生成逻辑

V3 分析时同时输出 `chart_config` JSON，前端直接喂给 Chart.js：

- `chart_type` 可选：`bar`、`line`、`pie`、`doughnut`
- 配色自动跟随亮/暗主题，从 CSS 变量读取
- 图表可选不渲染（V3 判断数据不适合图表时返回 `chart_config: null`）

### 8.4 设置页 — AI 助手配置 Tab

仅 admin 角色可见，包含 5 个折叠面板：

1. **API 密钥** — DeepSeek（Key/URL/模型选择/测试连接）+ 快递 100（Key/Customer/Secret/测试连接）
2. **提示词模板** — 系统提示词 / 分析提示词，大 textarea，旁有"重置默认"按钮
3. **业务词典** — 两列可编辑表格（术语 / SQL 含义），支持增删改
4. **示例问答库** — 卡片列表（问题 + SQL），标记来源（手动 / 👍 收藏），支持增删改
5. **快捷问题管理** — 可拖拽排序列表（显示文字 + 预置 SQL），支持增删改

### 8.5 新增文件

```
frontend/src/
├── api/
│   └── ai.js                    # AI 聊天 + 配置管理 API
├── components/
│   └── business/
│       ├── AiChatbot.vue         # 聊天浮窗主组件
│       ├── AiMessage.vue         # 单条消息渲染组件
│       ├── AiChartRenderer.vue   # Chart.js 图表渲染
│       └── settings/
│           └── ApiKeysPanel.vue  # AI 配置管理面板
```

---

## 9. 维护策略

### 9.1 用户通过 UI 维护（日常）

| 内容 | 操作位置 | 频率 |
|------|---------|------|
| API 密钥 | 设置 > AI 助手配置 > API 密钥 | 密钥变动时 |
| 提示词调优 | 设置 > AI 助手配置 > 提示词模板 | 想优化时随时改 |
| 业务词典 | 设置 > AI 助手配置 > 业务词典 | 新增品牌/术语时 |
| Few-shot 示例 | 聊天 👍 收藏 + 设置页管理 | 日常使用中积累 |
| 快捷问题 | 设置 > AI 助手配置 > 快捷问题 | 想加就加 |

### 9.2 Claude Code 维护（低频）

- 在 `MEMORY.md` 中记录上次维护日期，每 30 天主动提醒用户
- 维护内容：检查视图定义是否与最新 models 同步、检查 few-shot SQL 是否仍可执行
- 提供 `python -m app.ai.health_check` 一键健康检查脚本

### 9.3 用户反馈闭环

- 👍 → 可一键将问答对存入 few-shot 示例库
- 👎 → 记录反馈类型（数据错误/理解错误/格式不好），存入日志用于后续改进

---

## 10. 代码质量要求

### 10.1 通用规范

- 全程中文注释
- 遵循项目现有代码风格（参见 CLAUDE.md）
- Python 3.9 兼容：`from __future__ import annotations`
- Vue 3 `<script setup>` 语法
- Tailwind CSS 工具类 + CSS 变量，禁止硬编码色值
- 图标只用 lucide-vue-next

### 10.2 后端质量

- 所有函数带类型注解
- 所有公开函数和类带 docstring
- 异步 async/await 风格
- AI 模块的所有异常必须被 try/except 捕获，禁止向 ERP 主流程传播
- 独立连接池和 HTTP 客户端，不复用 ERP 业务资源
- 日志记录每次 AI 查询（用户、问题、SQL、耗时、结果行数）
- 敏感信息（API Key）日志中自动脱敏
- SQL 校验器必须有完整的单元测试覆盖（正常 SQL + 各类攻击 SQL）

### 10.3 前端质量

- 组件单文件不超过 500 行，超过则拆分子组件
- Markdown 渲染必须防 XSS（对用户输入做 HTML 转义）
- 响应式设计（桌面浮窗 + 移动端全屏）
- 亮/暗主题完整适配
- 加载状态、错误状态、空状态都要有对应 UI
- 金额数字用 tabular-nums + Geist Mono
- 所有可交互元素必须使用 `<button>` 或 `<a>` 标签，禁止 `<div @click>` 或 `<span @click>` 反模式（CLAUDE.md 硬性要求）
- DeepSeek API 调用完全在后端代理，前端无需修改 CSP（Content Security Policy）配置

### 10.4 安全编码

- 永远不信任 LLM 输出——所有 SQL 必须经过 AST 校验
- 永远不在前端暴露 API Key
- 永远不在日志中打印完整 API Key
- 永远不把 DeepSeek 的原始错误信息返回给前端
- SQL 执行必须在 READ ONLY 事务中
- 用户输入（包括 chat message）必须做基本的长度限制和清洗

---

## 11. 依赖新增

### 后端

| 包 | 用途 | 备注 |
|----|------|------|
| `sqlglot` | SQL AST 解析校验 | 纯 Python，无外部依赖 |
| `asyncpg` | AI 专用只读连接池 | 已是 Tortoise ORM 的间接依赖 |
| `cryptography` | AES 加密 API Key | 用 Fernet 对称加密 |

httpx 和 pydantic 项目中已有，不需要额外安装。

不引入 LangChain、向量数据库等重型依赖。

### 前端

无新增 npm 依赖。Chart.js 项目中已有，Markdown 渲染自己轻量实现。

---

## 12. 成本估算

DeepSeek API 定价（2026 年 3 月）：

| 模型 | 输入 | 输出 |
|------|------|------|
| deepseek-reasoner (R1) | 约 ¥4/百万 token | 约 ¥16/百万 token |
| deepseek-chat (V3) | 约 ¥1/百万 token（缓存 ¥0.1） | 约 ¥2/百万 token |

单次对话估算：
- R1 输入（schema + 词典 + few-shot + 问题）：约 4000 token
- R1 输出（SQL）：约 500 token
- V3 输入（问题 + 数据）：约 2000 token
- V3 输出（分析 + 图表参数）：约 800 token
- **单次总计约 ¥0.03**

按每天 50 次查询：**每月约 ¥45**。
