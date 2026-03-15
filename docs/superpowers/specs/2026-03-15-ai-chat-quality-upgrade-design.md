# AI Chat 质量升级设计文档

> 日期: 2026-03-15
> 状态: 设计已确认，待实施

## 背景

AI Chat 当前存在多个影响用户体验的问题：预设查询匹配过于激进导致"答非所问"、R1 超时导致复杂查询频繁失败、对话上下文丢失导致追问无效、小数据集分析质量差、前端交互细节粗糙。用户反馈"总感觉有各种问题，一直在修"。

## 方案选择

**方案 C（预设仅限精确点击 + 增强 LLM 路径）** — 预设查询只在用户点击欢迎页/建议按钮时触发，手动输入的文字全部走 LLM 生成 SQL。同时全面优化 LLM 路径的超时、上下文、分析质量和前端体验。

## 设计详情

### 1. 预设查询 — 仅限精确点击触发

**问题根因**：`intent_classifier.py` 对所有用户输入做模糊匹配，单关键词预设（如 `["毛利"]`、`["缺货"]`、`["应收"]`）导致任何包含该词的问题都被短路到固定 SQL 模板，绕过了 LLM。

**改动**：

#### 前端 — `useAiChat.js`
- `sendMessage(text, options)` 新增第二参数 `options`，支持 `{ preset: true }`
- 请求体 `body` 新增 `is_preset` 布尔字段
- 欢迎页按钮（AiWelcome.vue）和建议标签（AiMessage.vue）的点击事件传 `{ preset: true }`

#### 前端 — `AiChatbot.vue`
- `handleSend(text)` 改为 `handleSend(text, options)`
- 将 options 透传给 `sendMessage`

#### 前端 — `AiWelcome.vue`
- `@send` emit 时附带 `{ preset: true }` 标记

#### 前端 — `AiMessage.vue`
- 建议标签和澄清选项的 `@select-option` emit 时附带 `{ preset: true }` 标记

#### 后端 — `schemas/ai.py`
- `ChatRequest` 新增 `is_preset: bool = Field(default=False)`

#### 后端 — `ai_chat_service.py`
- `process_chat` 和 `_process_chat_inner` 新增 `is_preset` 参数
- 只有 `is_preset=True` 时才执行 `classify_intent()`
- `is_preset=False`（用户手动输入）直接跳过意图分类，走 LLM 路径

#### 后端 — `routers/ai_chat.py`
- `ai_chat` 将 `body.is_preset` 传给 `process_chat`

**不改的**：
- `intent_classifier.py` 逻辑保持不变
- `preset_queries.py` 数据保持不变
- 预设查询的 SQL 模板保持不变

---

### 2. DeepSeek R1 超时 + 错误恢复

**问题根因**：httpx 统一 30s 超时，R1 推理模型经常需要 30-60s；V3 分析失败时返回"查询完成。"无信息量。

**改动**：

#### `deepseek_client.py`
- `call_deepseek` 新增 `timeout: float = 30.0` 参数
- 用传入的 timeout 创建单次请求超时，而非依赖全局 client 超时
- 全局 client 超时改为 `httpx.Timeout(120.0, connect=10.0)` 作为上限兜底

#### `ai_chat_service.py`
- R1 SQL 生成调用：传 `timeout=90.0`
- V3 数据分析调用：传 `timeout=30.0`（不变）
- **删除 text 回退重试逻辑**（第 312-331 行的 `_BIZ_DATA_KEYWORDS` + 二次调用），通过优化 prompt 从根源解决
- V3 分析返回 None 时，调用 `_build_local_summary` 作为降级兜底，不再返回"查询完成。"

---

### 3. 对话上下文增强

**问题根因**：`buildAssistantContext` 丢弃所有数据行，只保留列名和行数，追问时 LLM 不知道具体内容。

**改动**：

#### `useAiChat.js` — `buildAssistantContext`
- 现有逻辑保留（analysis + 列名 + 行数）
- 新增：从 `msg.table_data` 中取前 5 行，拼成文本摘要
- 格式：`前5行数据: {col1}={val1}, {col2}={val2}; ...`
- 每行摘要最多 100 字符，总摘要最多 500 字符
- 只在 `table_data` 存在且未过期时生成

**不改的**：
- 后端 history 处理逻辑不变
- sessionStorage 持久化逻辑不变（仍然剥离 table_data）

---

### 4. 分析质量提升

**问题根因**：≤10 行数据跳过 V3 分析，本地摘要只做金额求和；system prompt 对复合问题的引导不够强。

**改动**：

#### `ai_chat_service.py` — `_execute_and_analyze`
- 删除 ≤10 行跳过 V3 的分支（第 450-462 行）
- 所有有数据的结果统一走 V3 分析
- `_build_local_summary` 仅作为 V3 失败时的降级使用

#### `prompt_builder.py` — SQL 生成 prompt
- 强化"判断规则"：只要问题提到具体数据（客户名、时间范围、产品、金额等），必须生成 SQL
- 减少 text 类型误判，不再依赖 text 回退重试

#### `prompt_builder.py` — 分析 prompt
- 新增指令："先直接回答用户的问题（一句话结论），再做补充分析"
- 新增指令："如果是排名类问题，明确指出排名第一的是谁"
- 新增指令："如果数据有异常或值得注意的点，必须主动提出"

---

### 5. 前端体验修复

#### 5a. 下拉菜单点击外部关闭 — `AiMessage.vue`
- 导出菜单（`showExportMenu`）和负面反馈菜单（`showNegativeMenu`）加点击外部关闭
- 用原生 `document.addEventListener('pointerdown', handler)` 实现
- 在 `onMounted` 时注册，`onUnmounted` 时移除
- 通过 `ref` 标记菜单容器 DOM，判断点击是否在容器外

#### 5b. 分析文本打字机效果 — 新增 `useTypewriter.js` composable
- 输入：完整 markdown 文本
- 输出：`displayText` ref，逐字符递增
- 速度：每字符 20ms，总长度 > 200 字时降至 8ms
- 在 AiMessage.vue 中，新消息（非历史恢复）的 analysis 使用打字机效果
- 历史消息直接全量显示（通过判断 `msg._expired` 或消息是否在初始化时已存在）

#### 5c. 表格高度优化 — `AiMessage.vue` + `AiChatbot.vue`
- AiChatbot 通过 `provide('aiExpanded', expanded)` 传递窗口状态
- AiMessage 通过 `inject('aiExpanded')` 接收
- 表格 max-height：普通窗口 `200px`，展开窗口 `350px`

---

## 涉及文件清单

### 后端（4 文件）
| 文件 | 改动类型 |
|------|---------|
| `backend/app/schemas/ai.py` | ChatRequest 新增 is_preset 字段 |
| `backend/app/routers/ai_chat.py` | 传递 is_preset 参数 |
| `backend/app/services/ai_chat_service.py` | 预设逻辑条件化、删除 text 重试、删除 ≤10 行跳过、V3 失败降级 |
| `backend/app/ai/deepseek_client.py` | call_deepseek 新增 timeout 参数 |
| `backend/app/ai/prompt_builder.py` | 优化 SQL prompt 和 analysis prompt |

### 前端（5 文件）
| 文件 | 改动类型 |
|------|---------|
| `frontend/src/composables/useAiChat.js` | sendMessage 增加 options 参数、buildAssistantContext 增加数据摘要 |
| `frontend/src/composables/useTypewriter.js` | **新建** — 打字机效果 composable |
| `frontend/src/components/business/AiChatbot.vue` | handleSend 透传 options、provide expanded |
| `frontend/src/components/business/AiMessage.vue` | 打字机效果、菜单外部关闭、表格高度动态化、emit preset 标记 |
| `frontend/src/components/business/AiWelcome.vue` | emit 时附带 preset 标记 |

### 不涉及的文件
- `intent_classifier.py` — 逻辑不变，只是调用时机变了
- `preset_queries.py` — 数据不变
- `sql_validator.py` — 不变
- `schema_registry.py` — 不变
- `few_shots.py` — 不变
- `AiProgressIndicator.vue` — 不变
- `AiChartRenderer.vue` — 不变

## 风险与注意事项

1. **所有手动输入走 LLM 后，简单问题响应会变慢**：从预设秒回变成等 R1 的 15-30s。但这是正确的权衡——宁可慢一点但准确，也不要秒回但答错。用户仍可通过点击预设按钮获得秒回体验。
2. **R1 timeout 增加到 90s**：极端情况下用户可能等 90s。但 R1 超过 60s 的情况罕见，且超时总比频繁报错好。
3. **≤10 行也走 V3**：API 成本略增，但 V3 很便宜（约 ¥0.001/次），且这些查询的 prompt 很短，响应也快（1-3s）。
4. **打字机效果**：需要确保历史消息恢复时不触发打字机，否则刷新页面后所有消息都在"打字"。
