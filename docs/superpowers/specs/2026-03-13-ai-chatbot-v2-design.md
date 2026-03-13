# AI 聊天助手 V2 — 全面优化设计文档

## 概述

对现有 AI 数据助手进行 14 项系统性优化，涵盖核心体验、智能增强、交互展示、平台能力四大模块。优化后的助手将具备流式响应、细粒度权限控制、会话管理、增强图表等能力。

## 当前架构

- **后端**: FastAPI + asyncpg + sqlglot + httpx + DeepSeek API (R1 SQL生成 + V3 数据分析)
- **前端**: Vue 3 + Chart.js + Tailwind CSS，浮窗式聊天界面
- **安全**: 四层防护（输入清洗 → LLM约束 → AST验证 → DB只读用户）
- **文件**: 后端 `backend/app/ai/` + `backend/app/services/ai_chat_service.py`，前端 `frontend/src/components/business/AiChatbot.vue` 等

---

## 模块一：核心体验提升

### 1. 流式响应 / 分步进度（SSE）

**问题**: 用户发问后等待 5-20s 只看到"思考中..."动画，不知道进展到哪一步。

**方案**: 后端改用 SSE（Server-Sent Events），分阶段推送进度。

**SSE 事件流**:
```
event: progress
data: {"stage": "thinking", "message": "正在理解问题..."}

event: progress
data: {"stage": "generating", "message": "正在生成查询..."}

event: progress
data: {"stage": "executing", "message": "正在查询数据库..."}

event: progress
data: {"stage": "analyzing", "message": "正在分析数据 (32行)..."}

event: done
data: { ...完整 ChatResponse... }

event: error
data: {"message": "错误描述", "retryable": true}
```

**后端改动**:
- `POST /api/ai/chat` 返回 `StreamingResponse`（`text/event-stream`）
- `process_chat` 改为 `async generator`，在每个关键节点 yield 进度事件
- 保留原有限流、输入清洗逻辑不变
- **缓存命中**时仍需以 SSE 格式返回：直接 yield `event: done` 事件（跳过 progress 阶段）
- **断连检测**：async generator 内用 `try/finally` 包裹，捕获 `asyncio.CancelledError`，确保断连时释放 `_ai_semaphore` 和数据库连接

**前端改动**:
- 用 `fetch` + `ReadableStream` 接收 SSE（不用 EventSource，因为需要 POST + headers）
- 消息气泡内显示当前阶段文字 + 线性进度指示器（4 段高亮），替换三圆点动画
- 预设查询和本地回复仍走原有同步路径
- **AbortController**：每次发送新请求前 abort 上一个未完成的请求；组件 unmount 时 abort；聊天窗口关闭时 abort
- **重叠请求处理**：同一时间只允许一个 SSE 请求，新请求会取消前一个

### 2. 重试按钮 + 错误优化

**问题**: 所有失败只显示一行文字，无法重试。

**方案**:
- 错误消息气泡加"重试"按钮，点击后重新发送该轮用户消息
- 在 message 对象上存 `_retryable` 标记和 `_originalQuestion` 引用
- 按错误类型分级提示:

| 错误类型 | 提示文案 | 重试 |
|---------|---------|------|
| 超时 | "AI 思考超时了，可以简化问题后重试" | 有 |
| 429 限流 | "请求太频繁了，稍等一会再试" | 有（倒计时后启用） |
| API 余额不足 (402) | "AI 服务额度不足，请联系管理员" | 无 |
| 网络错误 | "网络连接异常，请检查网络" | 有 |
| SQL 执行失败 | "查询执行失败，请换个说法试试" | 有 |

**后端改动**: SSE error 事件中包含 `retryable` 字段和 `error_type` 字段。

### 3. 对话持久化（登录重置）

**问题**: 刷新页面聊天记录全丢。

**方案**:
- 使用 `sessionStorage` 存储消息列表
- key 格式: `ai_chat_messages_{userId}`
- 每次 `checkStatus` 时对比 `userId`，不同用户自动清空
- 序列化时**不存**完整 `table_data` 和 `chart_config`（避免超出 sessionStorage 5MB 限制），仅存 `analysis`、`sql`、`type`、`row_count` 等元数据
- 刷新后历史消息的表格/图表区域显示提示："数据已过期，点击重新查询"，点击后自动重发原始问题
- 新开标签页 / 重新登录 / 关闭浏览器 → 自动重置

**实现要点**:
- 使用 debounce 后的手动 `saveToStorage()` 在关键变更点调用（消息新增、反馈变更），避免 `watch deep: true` 导致的高频序列化
- `onMounted` 时从 storage 恢复
- 单条消息序列化最大 2KB，总体最大 100KB

### 4. 聊天窗口尺寸优化

**问题**: 固定 400x600px 窗口太小，表格频繁水平滚动。

**方案**:
- 标题栏加一个"展开/收起"切换按钮（Maximize2 / Minimize2 图标）
- 两档尺寸:
  - **紧凑模式**（默认）: 400x600px
  - **扩展模式**: 680x720px
- 移动端保持全屏不变
- 用户选择的模式存入 `localStorage` 记住偏好
- CSS transition 动画过渡尺寸变化

### 5. 缓存 key 修复

**问题**: 缓存 key 只按消息文本，不区分用户和日期。"今天的销售额"今天和明天返回相同缓存。

**方案**:
- 缓存 key 改为: `f"{user_id}:{date.today().isoformat()}:{message.strip().lower()}"`
- 同一用户同一天相同问题命中缓存
- 不同用户 / 不同日期 → 不同缓存条目
- 其他缓存逻辑（TTL 5 分钟、LRU 50 条）不变

---

## 模块二：智能增强

### 6. Markdown 渲染升级

**问题**: 自写 renderMarkdown 只支持加粗、列表、换行，格式能力弱。

**方案**:
- 引入 `marked`（~7KB gzip）+ `DOMPurify`（~5KB gzip）替换自写函数
- 支持: 标题 (h1-h4)、加粗/斜体、有序/无序列表、行内代码、代码块、换行
- 不启用 HTML 标签透传，全部经 DOMPurify 过滤
- 添加 `.ai-markdown` 样式类统一排版（行距、列表缩进、代码块背景色），与 ERP 设计语言一致
- marked 配置 `{ breaks: true, gfm: true }`

**安装依赖**: `npm install marked dompurify`

### 7. 意图分类增强

**问题**: 精确关键词全匹配，稍微换个说法就匹配不上。

**方案**: 同义词映射 + 分词模糊匹配（不引入 embedding，避免额外 API 调用）。

**同义词表**（内置默认，管理员可编辑）:
```json
{
  "销售": ["卖", "营收", "出货", "卖了", "销量", "营业额"],
  "本月": ["这个月", "当月", "这月"],
  "上月": ["上个月", "前一个月"],
  "库存": ["存货", "仓库", "还有多少", "剩余"],
  "客户": ["买家", "客户群", "下单人"],
  "采购": ["进货", "进了多少", "采购单"],
  "利润": ["毛利", "赚了多少", "利润率"],
  "欠款": ["未收", "应收", "没付", "还欠"]
}
```

**匹配算法改进**:
1. 同义词展开方向：扫描用户输入，将输入中出现的同义词替换为对应的标准词（展开发生在用户消息上，不改变模板关键词）
2. 匹配逻辑从 `all(kw in msg)` 改为：关键词数 >= 2 时命中率 >= 80%；关键词数 = 1 时仍要求精确匹配
3. 多个模板同时命中时，取命中率最高的；命中率相同取关键词更多的（更具体的模板优先）

**配置**: 同义词表存入 `SystemSetting` key `ai.synonyms`，管理面板可编辑。

### 8. 反馈增强

**问题**: 踩了没有引导原因，反馈数据无法利用。

**方案**:
- 点赞后气泡上方短暂显示"感谢反馈"文字（1.5s 后淡出，CSS animation）
- 踩的时候在按钮下方弹出一个小浮层（非模态弹窗），提供 4 个选项:
  - 「数据不准确」「答非所问」「回复太慢」「其他」
- 选择后自动提交，`negative_reason` 传入后端
- 后端 `FeedbackRequest` schema 已有 `negative_reason` 字段，无需改动

### 9. 查询建议（相关问题推荐）

**问题**: 查完一个问题后没有引导，用户不知道还能问什么。

**方案**:
- 每次 AI 回答成功后，在操作栏下方显示 2-3 个"相关问题"小按钮
- 来源:
  1. **V3 分析时**: 在 analysis prompt 中增加 `"suggestions"` 字段，让 AI 推荐 2-3 个相关问题
  2. **本地小数据集回退**: 预设关联映射（如查了销售 → 推荐"毛利分析"、"客户排名"）
- 用户点击建议按钮 → 等同于发送该文字
- `ChatResponse` 新增 `suggestions: list[str] | None` 字段
- V3 返回中 `suggestions` 缺失时回退为 `None`（向后兼容）
- 本地摘要路径（`_build_local_summary`）使用硬编码关联映射表生成建议

**关联映射表**（用于本地摘要时）:
```json
{
  "sales": ["毛利分析", "客户销售排名", "产品销售排名"],
  "purchase": ["供应商采购排名", "采购成本趋势"],
  "inventory": ["缺货预警", "库存周转率"],
  "receivables": ["客户欠款排名", "应收账龄分析"],
  "payables": ["供应商应付汇总", "应付账龄分析"]
}
```

---

## 模块三：交互与展示优化

### 10. 图表体验增强

**问题**: 调色板太少、无交互、高度固定。

**方案**:
- 调色板从 6 色扩展到 12 色:
  ```javascript
  const PALETTE = [
    'oklch(0.55 0.20 250)',   // primary blue
    'oklch(0.65 0.20 145)',   // green
    'oklch(0.75 0.18 75)',    // amber
    'oklch(0.60 0.25 25)',    // red
    'oklch(0.60 0.18 300)',   // purple
    'oklch(0.70 0.15 200)',   // teal
    'oklch(0.58 0.22 220)',   // cyan
    'oklch(0.68 0.20 50)',    // orange
    'oklch(0.55 0.15 330)',   // magenta
    'oklch(0.72 0.12 110)',   // lime
    'oklch(0.50 0.20 280)',   // indigo
    'oklch(0.65 0.15 170)',   // emerald
  ]
  ```
- 启用 Chart.js tooltip（hover 显示精确数值）
- 饼图/环形图启用 `chartjs-plugin-datalabels` 显示百分比
- 图表高度动态: 饼图/环形图 220px，柱状/折线图 280px，数据集 >8 个时 360px
- 图表区域加"全屏查看"按钮（Maximize2 图标），点击后 modal 展示大图
- 图表区域加"保存图片"按钮，用 Chart.js `toBase64Image()` 生成 PNG 下载

**安装依赖**: `npm install chartjs-plugin-datalabels`

### 11. 收藏查询 / 快捷执行

**问题**: 无法保存常用查询，重复输入。

**方案**:
- 操作栏加"收藏"按钮（Star 图标），点击将 `{question, timestamp}` 存入 localStorage
- key: `ai_favorites_{userId}`，最多 20 条
- **去重**: 收藏相同 question 时更新 timestamp 而非创建重复项
- 聊天窗口欢迎页改为两区:
  - 上半区: **我的收藏**（用户收藏的查询）
  - 下半区: **常用查询**（系统预设模板）
- 收藏点击后一键重新执行（发送原始 question）
- 桌面端 hover 显示删除按钮，移动端长按删除
- 纯前端 localStorage 存储，不走后端

**代码影响**: 逻辑很轻量（~30 行存取 + ~20 行模板），不会导致文件膨胀。

### 12. 数据导出增强

**问题**: 只支持 Excel 导出。

**方案**:
- 导出按钮改为下拉菜单，提供:
  - **导出 Excel**（现有功能，走后端 openpyxl）
  - **导出 CSV**（纯前端生成，`Blob` + BOM 头确保中文编码）
- 图表"保存图片"按钮（已在第 10 项涵盖）

**CSV 生成**（前端纯本地）:
```javascript
const bom = '\uFEFF'
const csv = bom + [columns.join(','), ...rows.map(r => r.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(','))].join('\n')
const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
```

---

## 模块四：平台能力

### 13. 权限控制

**问题**: 所有登录用户都能查询所有数据，仓管员也能看销售利润。

**方案**: 在现有权限体系中新增 AI 权限组，按业务模块控制可查询数据范围。

**权限结构**:

| 权限 key | 名称 | 关联视图/表 |
|---------|------|------------|
| `ai_chat` | AI 助手（主开关） | — |
| `ai_sales` | 销售数据 | `vw_sales_detail`, `vw_sales_summary` |
| `ai_purchase` | 采购数据 | `vw_purchase_detail` |
| `ai_stock` | 库存数据 | `vw_inventory_status`, `vw_inventory_turnover` |
| `ai_customer` | 客户数据 | `customers` |
| `ai_finance` | 财务数据 | `vw_receivables`, `vw_payables` |
| `ai_accounting` | 会计数据 | `vw_accounting_ledger`, `vw_accounting_voucher_summary`（新建） |

**数据隔离机制（双层拦截）**:

1. **Prompt 层**: `schema_registry.py` 新增 `get_view_schema_text(allowed_views)` 参数，根据用户 AI 子权限动态裁剪注入 prompt 的 schema。无权限的视图不出现在 prompt 中，LLM 无法生成相关 SQL。

2. **SQL 验证层**: `sql_validator.py` 的 `validate_sql` 新增 `allowed_tables` 参数。AST 遍历时提取 LLM 生成 SQL 中直接引用的表名（视图作为不透明单元，不检查视图底层表），不在白名单内 → 拒绝执行，返回"你没有查询该模块数据的权限"。

3. **预设问题过滤**: 每条预设问题新增 `permission` 字段（如 `"permission": "ai_sales"`），`get_preset_queries` 接收用户权限列表，过滤掉无权限模块的预设问题。

4. **权限检查时机**: `require_permission("ai_chat")` 作为 FastAPI 依赖项在请求级别检查（HTTP 403），子权限（`ai_sales` 等）在 SSE generator 内部检查并通过 SSE error 事件返回友好提示。

**视图-权限映射表**（后端常量）:
```python
AI_VIEW_PERMISSIONS = {
    # 业务视图 — 按模块隔离
    "vw_sales_detail": "ai_sales",
    "vw_sales_summary": "ai_sales",
    "vw_purchase_detail": "ai_purchase",
    "vw_inventory_status": "ai_stock",
    "vw_inventory_turnover": "ai_stock",
    "vw_receivables": "ai_finance",
    "vw_payables": "ai_finance",
    "vw_accounting_ledger": "ai_accounting",
    "vw_accounting_voucher_summary": "ai_accounting",
    # 基础参考表 — 主开关即可访问（非敏感数据）
    "customers": "ai_chat",
    "products": "ai_chat",
    "suppliers": "ai_chat",
    "warehouses": "ai_chat",
    "account_sets": "ai_chat",
}
```

**部署迁移策略**:
- admin 用户自动拥有所有权限（`has_permission` 逻辑已覆盖），无需额外处理
- 部署时自动为所有**现有活跃非 admin 用户**追加 `ai_chat` + 全部 AI 子权限，保持功能不中断
- 迁移脚本在后端启动时检查（一次性），已有 AI 权限的用户跳过

**新建会计语义视图**:

1. `vw_accounting_ledger`: 科目明细账
   - 来源: `vouchers` + `voucher_entries` + `chart_of_accounts` + `accounting_periods`
   - 字段: account_code, account_name, category, period_name, voucher_no, voucher_date, summary, debit_amount, credit_amount, direction, aux_customer_name, aux_supplier_name, account_set_name
   - 条件: 仅 status = 'posted' 的已过账凭证

2. `vw_accounting_voucher_summary`: 凭证汇总
   - 来源: `vouchers` + `account_sets`
   - 字段: account_set_name, period_name, voucher_type, total_count, total_debit, total_credit, draft_count, pending_count, approved_count, posted_count

**前端改动**:
- `constants.js` 的 `permissionGroups` 新增:
  ```javascript
  {
    label: 'AI 助手', icon: 'ai', main: 'ai_chat',
    children: [
      { key: 'ai_sales', name: '销售数据' },
      { key: 'ai_purchase', name: '采购数据' },
      { key: 'ai_stock', name: '库存数据' },
      { key: 'ai_customer', name: '客户数据' },
      { key: 'ai_finance', name: '财务数据' },
      { key: 'ai_accounting', name: '会计数据' },
    ]
  }
  ```
- `PermissionSettings.vue` 无需改动（已支持主权限+子权限结构）

### 14. 配置面板增强

**问题**: 无导入导出，编辑体验差。

**方案**:
- 业务词典、示例问答、快捷问题、同义词表（新增）四个区块各加:
  - **导出 JSON** 按钮: 当前配置序列化为 `.json` 文件下载
  - **导入 JSON** 按钮: 文件选择器 → 读取 → 校验格式 → 替换当前配置
- 提示词编辑区加行号显示（CSS counter 实现，不引入重型编辑器）
- 同义词表编辑界面: 类似业务词典，左侧标准词 + 右侧同义词（逗号分隔输入）
- **导入校验规则**:
  - 业务词典: 每项必须有 `term` (string) + `meaning` (string)
  - 示例问答: 每项必须有 `question` (string) + `sql` (string)，且 `sql` 通过 `validate_sql()` 校验
  - 快捷问题: 每项必须有 `display` (string) + `keywords` (string[]) + `sql` (string)，且 `sql` 通过 `validate_sql()` 校验
  - 同义词表: key 为标准词 (string)，value 为同义词数组 (string[])
  - 校验失败时提示具体哪一行有问题，不导入

---

## 组件拆分计划

14 项改进会让 AiChatbot.vue 从 360 行膨胀到 600+。拆分方案:

| 文件 | 职责 | 预估行数 |
|------|------|---------|
| `AiChatbot.vue` | 主容器: 窗口开关、尺寸切换、布局骨架 | ~120 |
| `AiChatInput.vue` | 输入区: textarea、发送、自动调高 | ~60 |
| `AiWelcome.vue` | 欢迎页: 收藏列表 + 预设查询 | ~80 |
| `AiMessage.vue` | 消息渲染（已有，增强 Markdown + 重试 + 反馈浮层 + 建议） | ~200 |
| `AiChartRenderer.vue` | 图表渲染（已有，增强调色板 + 全屏 + 保存） | ~120 |
| `AiProgressIndicator.vue` | SSE 进度指示器 | ~40 |
| `composables/useAiChat.js` | 核心逻辑: SSE 通信、消息管理、会话缓存 | ~180 |
| `composables/useAiFavorites.js` | 收藏管理: 读/写/删 localStorage | ~40 |

---

## 新增依赖

| 包 | 用途 | 大小 |
|----|------|------|
| `marked` | Markdown 渲染 | ~7KB gzip |
| `dompurify` | XSS 防护 | ~5KB gzip |
| `chartjs-plugin-datalabels` | 饼图百分比标签 | ~3KB gzip |

---

## 后端新增/修改文件清单

| 文件 | 改动 |
|------|------|
| `backend/app/ai/views.sql` | 新增 `vw_accounting_ledger`, `vw_accounting_voucher_summary` |
| `backend/app/ai/schema_registry.py` | `get_view_schema_text` 支持 `allowed_views` 过滤 |
| `backend/app/ai/sql_validator.py` | `validate_sql` 支持 `allowed_tables` 白名单检查 |
| `backend/app/ai/intent_classifier.py` | 同义词展开 + 模糊匹配 |
| `backend/app/ai/synonym_map.py` | 新建，默认同义词表 |
| `backend/app/ai/prompt_builder.py` | analysis prompt 增加 suggestions 字段 |
| `backend/app/routers/ai_chat.py` | SSE 响应 + 权限检查 + 错误分类 |
| `backend/app/services/ai_chat_service.py` | async generator 改造 + 缓存 key 修复 + 权限过滤 |
| `backend/app/schemas/ai.py` | ChatResponse 增加 suggestions 字段 |

## 前端新增/修改文件清单

| 文件 | 改动 |
|------|------|
| `frontend/src/components/business/AiChatbot.vue` | 拆分为容器 + 尺寸切换 + sessionStorage |
| `frontend/src/components/business/AiChatInput.vue` | 新建，输入区组件 |
| `frontend/src/components/business/AiWelcome.vue` | 新建，欢迎页（收藏+预设） |
| `frontend/src/components/business/AiMessage.vue` | marked 渲染 + 重试 + 反馈浮层 + 建议按钮 |
| `frontend/src/components/business/AiChartRenderer.vue` | 12 色 + datalabels + 全屏 + 保存图片 |
| `frontend/src/components/business/AiProgressIndicator.vue` | 新建，SSE 进度 |
| `frontend/src/composables/useAiChat.js` | 新建，SSE + 消息管理 + 缓存 |
| `frontend/src/composables/useAiFavorites.js` | 新建，收藏管理 |
| `frontend/src/api/ai.js` | SSE fetch 改造 + CSV 导出 |
| `frontend/src/utils/constants.js` | AI 权限组 |
| `frontend/src/components/business/settings/ApiKeysPanel.vue` | 导入导出 + 同义词编辑 + 行号 |

---

## 实施顺序

按依赖关系和风险排序的建议实施顺序:

| 批次 | 项目 | 理由 |
|------|------|------|
| **1 — 独立快赢** | #5 缓存 key 修复, #6 Markdown 渲染 | 无依赖，低风险，立即生效 |
| **2 — SSE 基础** | #1 流式响应 | 后续 #2 #3 依赖 SSE 消息格式 |
| **3 — SSE 配套** | #2 重试 + 错误, #3 对话持久化 | 依赖 SSE 格式定义 |
| **4 — 独立 UI** | #4 窗口尺寸, #11 收藏查询, #12 导出增强 | 互相独立，纯前端 |
| **5 — 智能增强** | #7 意图分类, #8 反馈增强 | #7 被 #13 权限和 #14 配置依赖 |
| **6 — 权限体系** | #13 权限控制 | 需要 #7 同义词表完成（共享配置面板） |
| **7 — 分析增强** | #9 查询建议, #10 图表增强 | 依赖 SSE 完成，增强分析输出 |
| **8 — 配置收尾** | #14 配置面板增强 | 需要 #7 同义词表完成 |

---

## 不在范围内

- 多语言支持（保持中文）
- 语音输入/输出
- 多会话标签页
- AI 写入操作（保持只读）
