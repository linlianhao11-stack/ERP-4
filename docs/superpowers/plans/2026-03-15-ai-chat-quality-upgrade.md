# AI Chat 质量升级实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全面提升 AI Chat 的回答质量、响应稳定性和前端交互体验

**Architecture:** 预设查询仅限前端精确点击触发（is_preset 标记），手动输入全走 LLM；DeepSeek R1 超时增至 90s；对话上下文保留前 5 行数据摘要；所有有数据的查询统一走 V3 分析；前端增加打字机效果和菜单外部关闭。

**Tech Stack:** FastAPI + Tortoise ORM + PostgreSQL（后端），Vue 3 + Tailwind CSS（前端），DeepSeek R1/V3 API

**Spec:** `docs/superpowers/specs/2026-03-15-ai-chat-quality-upgrade-design.md`

---

## Task 1: 后端 — Schema + Router is_preset 字段

**Files:**
- Modify: `backend/app/schemas/ai.py:7-9`
- Modify: `backend/app/routers/ai_chat.py:90-96`

**可并行**: 是（与 Task 2、3、4 独立）

- [ ] **Step 1: ChatRequest 新增 is_preset 字段**

`backend/app/schemas/ai.py` — 在 `ChatRequest` 类中新增字段：

```python
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)
    is_preset: bool = Field(default=False)
```

- [ ] **Step 2: Router 透传 is_preset**

`backend/app/routers/ai_chat.py` — 在 `ai_chat` 函数的 `process_chat` 调用中新增 `is_preset` 参数：

```python
async for event in process_chat(
    message=clean_msg,
    history=body.history,
    user_id=user.id,
    db_dsn=dsn,
    user_permissions=None if user.role == "admin" else (user.permissions or []),
    is_preset=body.is_preset,
):
```

- [ ] **Step 3: Commit**

```
feat(ai): ChatRequest 新增 is_preset 字段 + router 透传
```

---

## Task 2: 后端 — DeepSeek Client 超时分级

**Files:**
- Modify: `backend/app/ai/deepseek_client.py:17-23,34-42,69-95`

**可并行**: 是（与 Task 1、3、4 独立）

- [ ] **Step 1: 全局 client 超时改为 120s 兜底**

`backend/app/ai/deepseek_client.py` — `_get_client` 函数：

```python
def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    return _client
```

- [ ] **Step 2: call_deepseek 新增 timeout 参数，用于单次请求超时**

`backend/app/ai/deepseek_client.py` — `call_deepseek` 函数签名新增 `timeout` 参数，在 `client.post` 调用时传入：

```python
async def call_deepseek(
    messages: list[dict],
    *,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL_SQL,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    timeout: float = 30.0,
) -> dict | None:
```

在 `client.post` 调用处添加 `timeout` 参数：

```python
resp = await client.post(url, json=payload, headers=headers, timeout=timeout)
```

- [ ] **Step 3: Commit**

```
feat(ai): DeepSeek client 支持单次请求超时分级
```

---

## Task 3: 后端 — Prompt 优化

**Files:**
- Modify: `backend/app/ai/prompt_builder.py:8-78,81-105`

**可并行**: 是（与 Task 1、2、4 独立）

- [ ] **Step 1: 优化 SQL 生成 prompt**

`backend/app/ai/prompt_builder.py` — `DEFAULT_SQL_SYSTEM_PROMPT`，强化判断规则部分：

把现有的 `**判断规则：以下情况用 text 直接回答，不要生成 SQL：**` 部分（含后面的"复合问题处理"段落）整块替换为以下更精确的版本：

```
**判断规则（非常重要！严格遵守）：**
以下情况用 text 直接回答，不要生成 SQL：
- 概念解释："什么是毛利率"、"交易和订单有什么区别"
- 闲聊问候："你好"、"你能做什么"、"谢谢"
- 纯观点预测（不涉及数据查询）："你觉得这个客户还会下单吗"
- 操作指引："怎么导出数据"、"怎么添加客户"
- 讨论上轮结果（不需要新数据时）："为什么会这样"、"这正常吗"

**除上述情况外，只要问题中出现以下任何一项，就必须生成 SQL：**
- 提到了具体的时间（今天、本月、上周、3月、Q1……）
- 提到了具体的实体名（客户名、供应商名、产品名、品牌名……）
- 提到了数量、金额、排名、对比、趋势、汇总
- 使用了"多少"、"几个"、"哪些"、"排名"、"最多"、"最少"等量化词
- 包含任何业务数据关键词（销售、采购、库存、应收、应付、毛利、订单……）
不要因为问题同时包含"建议"、"优化"、"分析"等词就跳过数据查询。先查数据，建议在分析阶段给。
```

- [ ] **Step 2: 优化分析 prompt**

`backend/app/ai/prompt_builder.py` — `DEFAULT_ANALYSIS_SYSTEM_PROMPT`，在"内容要求"部分新增指令：

```
## 内容要求
1. **先直接回答用户的问题**——一句话给结论。比如用户问"哪个客户买得最多"，先说"客户A 买得最多，本月销售额 5.2 万"
2. 如果是排名类问题，明确指出 Top 1-3 是谁
3. 有异常或值得注意的地方就提一句（比如某个数据波动大、某个客户突然增长/下降）
4. 金额大数字用万/亿（如 12.5 万），小数字直接写
5. 可以用加粗和列表，但别用 Markdown 表格（数据表格已经单独展示了）
6. **严禁出现任何英文**：不要出现字段名、表名、SQL 语法、代码。说"销售额"不说"amount"，说"毛利率"不说"profit_rate"
```

- [ ] **Step 3: Commit**

```
feat(ai): 优化 SQL 生成 + 数据分析 system prompt
```

---

## Task 4: 后端 — Service 核心逻辑重构

**Files:**
- Modify: `backend/app/services/ai_chat_service.py:172-228,282-399,406-503`

**依赖**: Task 1（is_preset 参数）、Task 2（timeout 参数）

- [ ] **Step 1: process_chat 和 _process_chat_inner 新增 is_preset 参数**

`backend/app/services/ai_chat_service.py` — 两个函数签名都新增 `is_preset: bool = False`：

```python
async def process_chat(
    message: str,
    history: list[dict],
    user_id: int,
    db_dsn: str,
    user_permissions: list[str] | None = None,
    is_preset: bool = False,
):
```

在 `process_chat` 调用 `_process_chat_inner` 时透传：

```python
async for event in _process_chat_inner(message, history, user_id, db_dsn, message_id, user_permissions=user_permissions, is_preset=is_preset):
```

- [ ] **Step 2: is_preset=True 跳过查询缓存**

`process_chat` 函数中，缓存逻辑前加条件判断：

```python
# is_preset 跳过缓存（预设本身极快，且避免 preset/非 preset 同文本缓存冲突）
if not is_preset:
    cached = _query_cache.get(cache_key)
    if cached:
        cached_time, cached_result = cached
        if now - cached_time < QUERY_CACHE_TTL:
            logger.info(f"命中查询缓存: {message[:30]}")
            yield {"event": "done", "data": {**cached_result, "message_id": str(uuid.uuid4())}}
            return
        else:
            del _query_cache[cache_key]
```

- [ ] **Step 3: 意图分类仅在 is_preset=True 时执行**

`_process_chat_inner` 中，用 `if is_preset:` 包裹 intent_classifier 调用块（约第 246-260 行）：

```python
# 意图预分类（仅预设点击时触发，手动输入直接走 LLM）
if is_preset:
    all_presets = config.get("ai.preset_queries") or DEFAULT_PRESET_QUERIES
    if user_permissions is not None:
        filtered_presets = [p for p in all_presets if p.get("permission", "ai_chat") in user_permissions]
    else:
        filtered_presets = all_presets
    preset = classify_intent(message, filtered_presets)
    if preset and preset.get("sql"):
        ok, _, reason = validate_sql(preset["sql"], allowed_tables=allowed)
        if not ok:
            yield {"event": "error", "data": {"message": "你没有查询该数据的权限", "retryable": False, "error_type": "forbidden"}}
            return
        yield {"event": "progress", "data": {"stage": "executing", "message": "正在查询数据库..."}}
        result = await _execute_and_analyze(sql=preset["sql"], message=message, config=config, db_dsn=db_dsn, message_id=message_id)
        yield {"event": "done", "data": result}
        return
```

- [ ] **Step 4: 删除 text 回退重试逻辑**

删除 `_process_chat_inner` 中第 311-331 行的 `_BIZ_DATA_KEYWORDS` 定义和 text 回退重试块。保留 `if resp_type == "text":` 的正常处理（第 333-339 行）。

- [ ] **Step 5: R1 调用传 timeout=90**

`_process_chat_inner` 中所有 `call_deepseek` 调用 R1 的地方（SQL 生成 + 自动纠错循环），添加 `timeout=90.0`：

```python
r1_result = await call_deepseek(
    messages=messages,
    api_key=api_key,
    base_url=config.get("base_url", DEFAULT_BASE_URL),
    model=config.get("model_sql", DEFAULT_MODEL_SQL),
    temperature=0.0,
    timeout=90.0,
)
```

同样在自动纠错循环（约第 356-362 行、第 388-394 行）的两处 `call_deepseek` 调用中添加 `timeout=90.0`。

V3 分析调用（`_execute_and_analyze` 中约第 472 行）显式传 `timeout=30.0`：

```python
v3_result = await call_deepseek(
    messages=[...],
    api_key=config["api_key"],
    base_url=config.get("base_url", DEFAULT_BASE_URL),
    model=config.get("model_analysis", DEFAULT_MODEL_ANALYSIS),
    temperature=0.7,
    max_tokens=1024,
    timeout=30.0,
)
```

- [ ] **Step 6: 删除 ≤10 行跳过 V3 的分支**

`_execute_and_analyze` 中删除第 449-462 行的 `if len(rows) <= 10:` 分支。所有有数据的结果统一走 V3 分析。

同时更新注释：将 `# 大数据集：调用分析模型（限制 max_tokens 加速）` 改为 `# 调用分析模型生成自然语言摘要`。

- [ ] **Step 7: V3 分析失败时降级到本地摘要**

`_execute_and_analyze` 中，V3 返回 None 时用 `_build_local_summary` 兜底：

```python
if v3_result:
    analysis_text = v3_result.get("analysis", analysis_text)
    chart_config = v3_result.get("chart_config")
    suggestions = v3_result.get("suggestions")
else:
    # V3 失败降级：用本地摘要代替"查询完成。"
    analysis_text = _build_local_summary(columns, row_data, message)
    suggestions = _get_local_suggestions(sql)
```

- [ ] **Step 8: Commit**

```
feat(ai): 预设逻辑条件化 + 删除 text 重试 + R1 超时 90s + V3 失败降级
```

---

## Task 5: 前端 — useAiChat 增强 + useTypewriter 新建

**Files:**
- Modify: `frontend/src/composables/useAiChat.js:34-57,87-102,110-111`
- Create: `frontend/src/composables/useTypewriter.js`

**可并行**: 是（与 Task 6、7 独立，但 Task 7 依赖此 Task 的 sendMessage 签名变更）

- [ ] **Step 1: sendMessage 新增 options 参数**

`frontend/src/composables/useAiChat.js` — `sendMessage` 函数：

```javascript
const sendMessage = async (text, options = {}) => {
    if (!text || !text.trim() || loading.value) return
    const msg = text.trim()

    messages.value.push({ role: 'user', content: msg })

    // 本地回复
    const localReply = tryLocalReply(msg)
    if (localReply) {
      messages.value.push({ role: 'assistant', type: 'clarification', message: localReply, options: [] })
      saveToStorage()
      return
    }

    // 添加 loading 占位
    const aiMsgIndex = messages.value.length
    messages.value.push({ role: 'assistant', loading: true, stage: 'thinking', stageMessage: '正在理解问题...' })
    loading.value = true

    // 取消前一个请求
    if (abortController) abortController.abort()
    abortController = new AbortController()

    try {
      const token = localStorage.getItem('erp_token')
      const history = buildHistory().slice(0, -2)

      const response = await fetch(`${API_BASE}/api/ai/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: msg,
          history,
          is_preset: !!options.preset,
        }),
        signal: abortController.signal,
      })
```

唯一改动：函数签名 `async (text)` → `async (text, options = {})`，body 新增 `is_preset: !!options.preset`。其余不变。

- [ ] **Step 2: buildAssistantContext 增加数据摘要**

`frontend/src/composables/useAiChat.js` — 替换 `buildAssistantContext` 函数：

```javascript
const buildAssistantContext = (m) => {
    const parts = []
    if (m.analysis) parts.push(m.analysis)
    if (m.table_data?.columns && m.table_data?.rows?.length) {
      const cols = m.table_data.columns
      const rows = m.table_data.rows
      parts.push(`[查询结果: ${rows.length} 行, 列: ${cols.join(', ')}]`)
      // 保留前 5 行数据摘要，便于追问时 LLM 知道具体内容
      const preview = rows.slice(0, 5).map(row =>
        cols.map((c, i) => `${c}=${row[i] ?? '-'}`).join(', ')
      )
      const summary = '前' + Math.min(5, rows.length) + '行: ' + preview.join('; ')
      // 限制摘要长度
      parts.push(summary.length > 500 ? summary.slice(0, 500) + '...' : summary)
    }
    if (m.message) parts.push(m.message)
    if (m._expired && m._hasTableData) parts.push('[之前有表格数据，已过期]')
    return parts.join('\n') || ''
  }
```

- [ ] **Step 3: restoreFromStorage 设置 _isRestored 标记**

`frontend/src/composables/useAiChat.js` — `restoreFromStorage` 函数：

```javascript
const restoreFromStorage = (userId) => {
    currentUserId = userId
    const key = `${STORAGE_KEY_PREFIX}${userId}`
    const raw = sessionStorage.getItem(key)
    if (raw) {
      try {
        const restored = JSON.parse(raw)
        messages.value = restored.map(m => ({
          ...m,
          _isRestored: true,
          ...(m._hasTableData || m._hasChartConfig ? { _expired: true } : {}),
        }))
      } catch { /* 忽略损坏数据 */ }
    }
  }
```

- [ ] **Step 4: 创建 useTypewriter composable**

新建 `frontend/src/composables/useTypewriter.js`：

```javascript
import { ref, watch, isRef, onUnmounted } from 'vue'

/**
 * 打字机效果 composable
 * @param {import('vue').Ref<string>} source - 完整文本 ref
 * @param {Object} options
 * @param {import('vue').Ref<boolean>|boolean} options.enabled - 是否启用（支持 ref 以便响应式判断）
 * @param {number} options.speed - 每字符间隔（ms），默认 20
 * @param {number} options.fastSpeed - 长文本加速间隔（ms），默认 8
 * @param {number} options.fastThreshold - 触发加速的字符数阈值，默认 200
 */
export function useTypewriter(source, options = {}) {
  const {
    enabled = true,
    speed = 20,
    fastSpeed = 8,
    fastThreshold = 200,
  } = options

  // enabled 支持 ref 或静态值
  const isEnabled = () => isRef(enabled) ? enabled.value : enabled

  const displayText = ref(isEnabled() ? '' : (source.value || ''))
  const isTyping = ref(false)
  let timer = null
  let index = 0

  const stop = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    isTyping.value = false
  }

  const start = (text) => {
    stop()
    if (!isEnabled() || !text) {
      displayText.value = text || ''
      return
    }
    index = 0
    isTyping.value = true
    const interval = text.length > fastThreshold ? fastSpeed : speed
    timer = setInterval(() => {
      index++
      displayText.value = text.slice(0, index)
      if (index >= text.length) {
        stop()
      }
    }, interval)
  }

  // 监听 source 变化（从 loading → 有内容时触发）
  watch(source, (newVal) => {
    if (newVal) {
      start(newVal)
    }
  }, { immediate: true })

  onUnmounted(stop)

  return { displayText, isTyping, stop }
}
```

- [ ] **Step 5: Commit**

```
feat(ai-frontend): useAiChat 增强(preset/上下文/恢复) + useTypewriter composable
```

---

## Task 6: 前端 — AiWelcome 预设标记

**Files:**
- Modify: `frontend/src/components/business/AiWelcome.vue:11,25,41`

**可并行**: 是（与 Task 5 独立，与 Task 7 独立）

- [ ] **Step 1: 拆分 emit — 预设按钮带 preset 标记，收藏按钮不带**

`frontend/src/components/business/AiWelcome.vue` — 修改 template：

收藏按钮（第 11 行）不变（不带 preset）：
```html
<button class="btn btn-secondary btn-sm text-xs" @click="$emit('send', fav.question)">
```

预设查询按钮（第 25 行）改为传 preset 标记：
```html
<button v-for="pq in presetQueries" :key="pq.display" class="btn btn-secondary btn-sm text-xs" @click="$emit('send', pq.display, { preset: true })">
```

修改 `defineEmits`（第 41 行）— 不需要改（emit 名称不变，只是参数多了一个）。

- [ ] **Step 2: Commit**

```
feat(AiWelcome): 预设查询按钮附带 preset 标记
```

---

## Task 7: 前端 — AiMessage 改造（preset + 菜单关闭 + 打字机 + 表格高度）

**Files:**
- Modify: `frontend/src/components/business/AiMessage.vue`

**依赖**: Task 5（useTypewriter）

- [ ] **Step 1: 建议标签附带 preset 标记，澄清选项和重查不带**

`frontend/src/components/business/AiMessage.vue` — template 修改：

建议标签（约第 114 行）改为：
```html
<button v-for="s in msg.suggestions" :key="s" class="text-xs px-2 py-1 rounded-full border text-muted hover:text-primary hover:border-primary transition-colors" @click="$emit('select-option', s, { preset: true })">
```

澄清选项（约第 17 行）保持不变（不带 preset）：
```html
<button v-for="opt in (msg.options || [])" :key="opt" class="btn btn-secondary btn-sm text-xs" @click="$emit('select-option', opt)">
```

重新查询按钮（约第 39 行）保持不变（不带 preset）：
```html
<button class="btn btn-secondary btn-sm text-xs" @click="$emit('select-option', msg._question)">重新查询</button>
```

- [ ] **Step 2: 下拉菜单点击外部关闭**

在 `<script setup>` 中新增：

```javascript
import { ref, onMounted, onUnmounted, computed, inject } from 'vue'

// 菜单外部点击关闭
const exportMenuRef = ref(null)
const negativeMenuRef = ref(null)

const handleOutsideClick = (e) => {
  if (showExportMenu.value && exportMenuRef.value && !exportMenuRef.value.contains(e.target)) {
    showExportMenu.value = false
  }
  if (showNegativeMenu.value && negativeMenuRef.value && !negativeMenuRef.value.contains(e.target)) {
    showNegativeMenu.value = false
  }
}

onMounted(() => document.addEventListener('pointerdown', handleOutsideClick))
onUnmounted(() => document.removeEventListener('pointerdown', handleOutsideClick))
```

在 template 中给导出菜单容器加 `ref="exportMenuRef"`（约第 80 行的 `<div class="relative">`），给负面反馈容器加 `ref="negativeMenuRef"`（约第 99 行的 `<div class="relative">`）。

- [ ] **Step 3: 打字机效果**

在 `<script setup>` 中新增：

```javascript
import { useTypewriter } from '../../composables/useTypewriter'

// 打字机效果（仅新消息的 answer 类型，历史恢复的直接全量显示）
// enabled 用 computed 因为 msg.type 在 loading 阶段还不是 'answer'，需要响应式等待
const analysisSource = computed(() => props.msg.analysis || '')
const typewriterEnabled = computed(() => !props.msg._isRestored && props.msg.type === 'answer')
const { displayText: typedAnalysis, isTyping } = useTypewriter(analysisSource, {
  enabled: typewriterEnabled,
})
```

在 template 中替换分析文本渲染（约第 34 行）：

```html
<div v-if="msg.analysis" class="ai-analysis text-sm" v-html="renderMarkdown(typedAnalysis)" />
```

- [ ] **Step 4: 表格高度动态化**

在 `<script setup>` 中新增：

```javascript
const aiExpanded = inject('aiExpanded', ref(false))
const tableMaxH = computed(() => aiExpanded.value ? 'max-h-[400px]' : 'max-h-[250px]')
```

在 template 中替换表格容器（约第 43 行），**必须移除**静态的 `max-h-[300px]` 类，改用动态绑定：

当前代码：
```html
<div class="overflow-x-auto max-h-[300px]">
```

改为：
```html
<div class="overflow-x-auto" :class="tableMaxH">
```

- [ ] **Step 5: Commit**

```
feat(AiMessage): preset标记 + 菜单外部关闭 + 打字机效果 + 表格高度动态化
```

---

## Task 8: 前端 — AiChatbot 透传 options + provide expanded

**Files:**
- Modify: `frontend/src/components/business/AiChatbot.vue:72,121-127`

**依赖**: Task 5（sendMessage 签名变更）

- [ ] **Step 1: provide expanded 状态**

`frontend/src/components/business/AiChatbot.vue` — `<script setup>` 中新增：

```javascript
import { ref, watch, onMounted, onUnmounted, nextTick, provide } from 'vue'
```

在 `expanded` 定义后添加：

```javascript
provide('aiExpanded', expanded)
```

- [ ] **Step 2: handleSend 透传 options**

```javascript
const handleSend = async (text, options) => {
  if (!text || !text.trim()) return
  input.value = ''
  autoResize()
  await sendMessage(text, options)
  scrollToBottom()
}
```

- [ ] **Step 3: template 中的事件处理**

输入框 enter 和发送按钮的 `handleSend(input)` 不需要改（不传 options 默认是 `{}`，即 `is_preset=false`）。

AiWelcome 的 `@send` 需要支持第二参数：
```html
<AiWelcome
  v-if="messages.length === 0"
  :favorites="favorites"
  :preset-queries="presetQueries"
  @send="handleSend"
  @remove-favorite="handleRemoveFavorite"
/>
```
这里 `@send="handleSend"` 已经会自动透传 emit 的所有参数，因为 AiWelcome emit `send` 时带了两个参数 `(text, options)`，Vue 会把它们都传给 `handleSend(text, options)`。不需要改 template。

AiMessage 的 `@select-option` 同理——emit 带两个参数时自动透传。不需要改 template。

- [ ] **Step 4: Commit**

```
feat(AiChatbot): provide expanded + handleSend 透传 options
```

---

## Task 9: Build 验证

**Files:** 无新改动

**依赖**: Task 1-8 全部完成

- [ ] **Step 1: 前端 build**

```bash
cd frontend && npm run build
```

期望：编译成功，无错误。

- [ ] **Step 2: 修复任何 build 错误**

如果有错误，定位并修复后重新 build。

- [ ] **Step 3: 最终 commit（如有修复）**

```
fix: 修复 AI Chat 升级 build 错误
```
