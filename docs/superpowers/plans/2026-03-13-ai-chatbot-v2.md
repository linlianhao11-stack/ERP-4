# AI 聊天助手 V2 全面优化 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 AI 聊天助手进行 14 项系统性优化，涵盖 SSE 流式响应、细粒度权限控制、会话管理、增强图表等能力。

**Architecture:** 后端 SSE async generator 替代同步响应，权限双层拦截（prompt 裁剪 + SQL AST 白名单），前端组件拆分为 5 个 Vue 组件 + 2 个 composable。所有改动基于现有 FastAPI + Vue 3 + Tailwind 架构，不引入新框架。

**Tech Stack:** FastAPI StreamingResponse (SSE), Vue 3 Composition API, marked + DOMPurify, Chart.js + chartjs-plugin-datalabels, asyncpg, sqlglot

**Spec:** `docs/superpowers/specs/2026-03-13-ai-chatbot-v2-design.md`

**验证策略（遵循 CLAUDE.md）：**
- 首选 `npm run build` 验证前端编译
- 用 `preview_snapshot` 代替截图验证结构
- 后端有测试的模块运行 `pytest`
- `docker compose up -d --build` 验证部署

---

## File Structure Overview

### New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/composables/useAiChat.js` | SSE 通信、消息管理、会话缓存 |
| `frontend/src/composables/useAiFavorites.js` | 收藏管理 localStorage |
| `frontend/src/components/business/AiChatInput.vue` | 输入区组件 |
| `frontend/src/components/business/AiWelcome.vue` | 欢迎页（收藏+预设） |
| `frontend/src/components/business/AiProgressIndicator.vue` | SSE 进度指示器 |
| `backend/app/ai/synonym_map.py` | 同义词映射表 |
| `backend/app/ai/view_permissions.py` | 视图-权限映射常量 |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/services/ai_chat_service.py` | async generator 改造、缓存 key 修复、权限过滤、suggestions |
| `backend/app/routers/ai_chat.py` | SSE StreamingResponse、权限检查、错误分类 |
| `backend/app/ai/sql_validator.py` | 新增 allowed_tables 白名单参数 |
| `backend/app/ai/schema_registry.py` | 新增 allowed_views 过滤参数 |
| `backend/app/ai/intent_classifier.py` | 同义词展开 + 模糊匹配 |
| `backend/app/ai/prompt_builder.py` | analysis prompt 增加 suggestions 字段 |
| `backend/app/ai/preset_queries.py` | 每条预设增加 permission 字段 |
| `backend/app/ai/views.sql` | 新增 2 个会计视图 |
| `backend/app/schemas/ai.py` | ChatResponse 增加 suggestions 字段 |
| `frontend/src/components/business/AiChatbot.vue` | 瘦身为容器 + 尺寸切换 |
| `frontend/src/components/business/AiMessage.vue` | marked 渲染、重试、反馈浮层、建议 |
| `frontend/src/components/business/AiChartRenderer.vue` | 12 色、datalabels、全屏、保存 |
| `frontend/src/components/business/settings/ApiKeysPanel.vue` | 导入导出、同义词编辑、行号 |
| `frontend/src/api/ai.js` | SSE fetch 改造、CSV 导出 |
| `frontend/src/utils/constants.js` | AI 权限组 |

---

## Chunk 1: 独立快赢 — 缓存修复 + Markdown 升级

### Task 1: 缓存 key 修复（#5）

**Files:**
- Modify: `backend/app/services/ai_chat_service.py`
- Test: `backend/tests/test_ai_cache.py`（新建）

- [ ] **Step 1: 修改缓存 key 生成逻辑**

在 `ai_chat_service.py` 的 `process_chat` 函数中，将:
```python
cache_key = message.strip().lower()
```
改为:
```python
from datetime import date
cache_key = f"{user_id}:{date.today().isoformat()}:{message.strip().lower()}"
```

- [ ] **Step 2: 验证后端启动正常**

Run: `docker compose up -d --build && sleep 3 && docker compose logs erp --tail 5`
Expected: `Application startup complete`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/ai_chat_service.py
git commit -m "fix(ai): 缓存 key 加入 user_id + 日期，避免跨用户/跨天缓存串漏"
```

### Task 2: Markdown 渲染升级（#6）

**Files:**
- Modify: `frontend/src/components/business/AiMessage.vue`
- Install: `marked`, `dompurify`

- [ ] **Step 1: 安装依赖**

Run: `cd frontend && npm install marked dompurify`

- [ ] **Step 2: 替换 renderMarkdown 函数**

在 `AiMessage.vue` 的 `<script setup>` 中:
- 移除原有 `renderMarkdown` 函数（约 L116-L131）
- 替换为:
```javascript
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (text) => {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text), {
    ALLOWED_TAGS: ['strong', 'em', 'ul', 'ol', 'li', 'br', 'p', 'h3', 'h4', 'code', 'pre'],
    ALLOWED_ATTR: ['class'],
  })
}
```

- [ ] **Step 3: 添加 Markdown 样式**

在 `AiMessage.vue` 的 `<style scoped>` 中追加:
```css
.ai-analysis :deep(p) { margin-bottom: 0.5em; }
.ai-analysis :deep(ul), .ai-analysis :deep(ol) { padding-left: 1.2em; margin: 0.5em 0; }
.ai-analysis :deep(li) { margin-bottom: 0.25em; }
.ai-analysis :deep(code) { background: var(--elevated); padding: 1px 4px; border-radius: 3px; font-size: 0.85em; }
.ai-analysis :deep(pre) { background: var(--elevated); padding: 8px 12px; border-radius: 6px; overflow-x: auto; margin: 0.5em 0; }
.ai-analysis :deep(pre code) { background: none; padding: 0; }
.ai-analysis :deep(h3), .ai-analysis :deep(h4) { font-weight: 600; margin: 0.75em 0 0.25em; }
```

- [ ] **Step 4: Build 验证**

Run: `cd frontend && npm run build`
Expected: 编译成功无错误

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/business/AiMessage.vue
git commit -m "feat(ai): 升级 Markdown 渲染为 marked + DOMPurify，支持标题/代码块/列表"
```

---

## Chunk 2: SSE 基础 — 流式响应

### Task 3: 后端 SSE 改造 — ai_chat_service.py

**Files:**
- Modify: `backend/app/services/ai_chat_service.py`

- [ ] **Step 1: 将 process_chat 改为 async generator**

重写 `process_chat` 函数签名和核心逻辑：

```python
import asyncio

async def process_chat(
    message: str,
    history: list[dict],
    user_id: int,
    db_dsn: str,
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
            async for event in _process_chat_inner(message, history, user_id, db_dsn, message_id):
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
```

- [ ] **Step 2: 改造 _process_chat_inner 为 async generator**

在每个关键节点 yield progress 事件:
```python
async def _process_chat_inner(message, history, user_id, db_dsn, message_id):
    try:
        yield {"event": "progress", "data": {"stage": "thinking", "message": "正在理解问题..."}}

        config = await _get_config()
        api_key = config.get("api_key")
        if not api_key:
            yield {"event": "error", "data": {"message": "AI 助手未配置，请联系管理员设置 DeepSeek API Key", "retryable": False, "error_type": "config"}}
            return

        # 意图预分类
        preset = classify_intent(message, config.get("ai.preset_queries") or DEFAULT_PRESET_QUERIES)
        if preset and preset.get("sql"):
            ok, _, reason = validate_sql(preset["sql"])
            if not ok:
                yield {"event": "error", "data": {"message": f"预设查询模板异常: {reason}", "retryable": False, "error_type": "config"}}
                return
            yield {"event": "progress", "data": {"stage": "executing", "message": "正在查询数据库..."}}
            result = await _execute_and_analyze(sql=preset["sql"], message=message, config=config, db_dsn=db_dsn, message_id=message_id)
            yield {"event": "done", "data": result}
            return

        # LLM 生成 SQL
        yield {"event": "progress", "data": {"stage": "generating", "message": "正在生成查询..."}}
        # ... (保留原有 LLM 调用逻辑，在执行前 yield executing, 在分析前 yield analyzing)

        yield {"event": "progress", "data": {"stage": "executing", "message": "正在查询数据库..."}}
        # ... SQL 执行

        yield {"event": "progress", "data": {"stage": "analyzing", "message": f"正在分析数据 ({row_count}行)..."}}
        # ... 数据分析

        yield {"event": "done", "data": result}

    except Exception as e:
        logger.error(f"AI 聊天处理异常: {type(e).__name__}: {e}")
        yield {"event": "error", "data": {"message": "AI 服务出现异常，请稍后再试", "retryable": True, "error_type": "server"}}
```

注意：保留 `_execute_and_analyze` 为普通 async 函数不变（它不需要 yield progress）。

- [ ] **Step 3: Commit 后端 SSE 改造**

```bash
git add backend/app/services/ai_chat_service.py
git commit -m "refactor(ai): process_chat 改为 async generator，支持 SSE 分阶段推送"
```

### Task 4: 后端 SSE 路由改造 — ai_chat.py

**Files:**
- Modify: `backend/app/routers/ai_chat.py`

- [ ] **Step 1: 改写 ai_chat 端点为 SSE StreamingResponse**

```python
import json
import asyncio
from fastapi.responses import StreamingResponse

@router.post("/chat")
async def ai_chat(body: ChatRequest, user: User = Depends(get_current_user)):
    """AI 聊天接口 — SSE 流式响应"""
    # 输入验证 (保留原逻辑)
    if len(body.history) > 50:
        body.history = body.history[-50:]
    for h in body.history:
        if len(h.get("content", "")) > 5000:
            h["content"] = h["content"][:5000]

    # 限流检查
    user_key = f"user:{user.id}"
    if not user_limiter.allow(user_key):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    if not global_limiter.allow("global"):
        raise HTTPException(status_code=429, detail="系统繁忙，请稍后再试")

    # 清洗输入
    clean_msg = body.message.strip()
    clean_msg = "".join(c for c in clean_msg if c == "\n" or (ord(c) >= 32))
    if not clean_msg:
        raise HTTPException(status_code=400, detail="请输入查询内容")

    dsn = _build_ai_dsn()

    async def event_stream():
        try:
            async for event in process_chat(
                message=clean_msg,
                history=body.history,
                user_id=user.id,
                db_dsn=dsn,
            ):
                evt_type = event.get("event", "progress")
                evt_data = json.dumps(event.get("data", {}), ensure_ascii=False)
                yield f"event: {evt_type}\ndata: {evt_data}\n\n"
        except asyncio.CancelledError:
            pass

        logger.info(f"AI 查询: user={user.username}, question={clean_msg[:50]}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 2: Docker 重建验证**

Run: `docker compose up -d --build && sleep 3 && docker compose logs erp --tail 5`
Expected: `Application startup complete`

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/ai_chat.py
git commit -m "feat(ai): 聊天端点改为 SSE StreamingResponse，支持分阶段进度推送"
```

### Task 5: 前端 SSE 接收 — useAiChat.js composable

**Files:**
- Create: `frontend/src/composables/useAiChat.js`
- Modify: `frontend/src/api/ai.js`

- [ ] **Step 1: 创建 useAiChat.js composable**

```javascript
import { ref, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export function useAiChat() {
  const appStore = useAppStore()
  const messages = ref([])
  const loading = ref(false)
  let abortController = null

  // 非数据问题本地快速回复
  const LOCAL_REPLIES = [
    { patterns: ['你是谁', '你是什么', '介绍一下你', '你叫什么'], reply: '我是 AI 数据助手，专门帮你查询和分析业务数据（销售、采购、库存、应收应付等）。试试问我"本月销售概况"或"哪些产品快缺货了"吧！' },
    { patterns: ['你好', '嗨', 'hi', 'hello', '在吗'], reply: '你好！我是 AI 数据助手。你可以问我业务数据相关的问题，比如销售、采购、库存、应收应付等。' },
    { patterns: ['谢谢', '感谢', 'thanks'], reply: '不客气！有其他数据需要查询随时问我。' },
    { patterns: ['能做什么', '怎么用', '有什么功能', '帮助'], reply: '我可以帮你查询和分析：\n- **销售数据**：销售额、毛利、客户分析、产品排名\n- **采购数据**：采购金额、供应商分析\n- **库存数据**：库存状态、缺货预警、周转率\n- **应收应付**：欠款汇总、账龄分析\n\n直接用自然语言提问即可。' },
    { patterns: ['聊天', '闲聊', '除了工作', '别的事', '聊点别的', '讲个笑话', '天气', '今天心情'], reply: '不好意思，我是专门的业务数据助手，只能帮你查询和分析 ERP 系统中的数据哦。试试问我一些业务问题吧！' },
  ]

  const tryLocalReply = (msg) => {
    const lower = msg.toLowerCase()
    for (const item of LOCAL_REPLIES) {
      if (item.patterns.some(p => lower.includes(p))) return item.reply
    }
    return null
  }

  const buildAssistantContext = (m) => {
    const parts = []
    if (m.analysis) parts.push(m.analysis)
    if (m.sql) parts.push(`[SQL: ${m.sql}]`)
    if (m.table_data?.columns && m.table_data?.rows?.length) {
      const cols = m.table_data.columns.join(', ')
      const preview = m.table_data.rows.slice(0, 5).map(r => r.join(' | ')).join('\n')
      parts.push(`[数据 (${m.table_data.rows.length}行): ${cols}\n${preview}]`)
    }
    return parts.join('\n') || m.message || ''
  }

  const buildHistory = () => {
    return messages.value
      .filter(m => !m.loading && (m.role === 'user' || m.type === 'answer' || m.type === 'clarification'))
      .slice(-50)
      .map(m => ({
        role: m.role,
        content: m.role === 'user' ? m.content : buildAssistantContext(m),
      }))
  }

  const sendMessage = async (text) => {
    if (!text || !text.trim() || loading.value) return
    const msg = text.trim()

    messages.value.push({ role: 'user', content: msg })

    // 本地回复
    const localReply = tryLocalReply(msg)
    if (localReply) {
      messages.value.push({ role: 'assistant', type: 'clarification', message: localReply, options: [] })
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
      const token = localStorage.getItem('token')
      const history = buildHistory().slice(0, -2)

      const response = await fetch(`${API_BASE}/api/ai/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message: msg, history }),
        signal: abortController.signal,
      })

      if (response.status === 429) {
        messages.value[aiMsgIndex] = {
          loading: false, role: 'assistant', type: 'error',
          message: '请求太频繁了，稍等一会再试',
          _retryable: true, _originalQuestion: msg, _errorType: 'rate_limit',
        }
        return
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      // 解析 SSE 流
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let eventType = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))
            if (eventType === 'progress') {
              messages.value[aiMsgIndex] = {
                ...messages.value[aiMsgIndex],
                stage: data.stage,
                stageMessage: data.message,
              }
            } else if (eventType === 'done') {
              messages.value[aiMsgIndex] = {
                ...data, loading: false, role: 'assistant', _question: msg,
              }
            } else if (eventType === 'error') {
              messages.value[aiMsgIndex] = {
                loading: false, role: 'assistant', type: 'error',
                message: data.message,
                _retryable: data.retryable !== false,
                _originalQuestion: msg,
                _errorType: data.error_type || 'unknown',
              }
            }
          }
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') return
      const isTimeout = e.code === 'ECONNABORTED' || e.message?.includes('timeout')
      messages.value[aiMsgIndex] = {
        loading: false, role: 'assistant', type: 'error',
        message: isTimeout ? 'AI 思考超时了，请简化问题后重试' : '网络连接异常，请检查网络',
        _retryable: true, _originalQuestion: msg,
        _errorType: isTimeout ? 'timeout' : 'network',
      }
    } finally {
      loading.value = false
      abortController = null
    }
  }

  const retryMessage = (msg) => {
    if (msg._originalQuestion) {
      // 移除当前错误消息
      const idx = messages.value.indexOf(msg)
      if (idx >= 0) messages.value.splice(idx, 1)
      // 移除对应的用户消息（紧邻上方）
      if (idx > 0 && messages.value[idx - 1]?.role === 'user') {
        messages.value.splice(idx - 1, 1)
      }
      sendMessage(msg._originalQuestion)
    }
  }

  const clearChat = () => {
    messages.value = []
    if (abortController) abortController.abort()
  }

  onUnmounted(() => {
    if (abortController) abortController.abort()
  })

  return {
    messages, loading, sendMessage, retryMessage, clearChat, buildHistory,
  }
}
```

- [ ] **Step 2: Build 验证**

Run: `cd frontend && npm run build`
Expected: 编译成功

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useAiChat.js
git commit -m "feat(ai): 新建 useAiChat composable，实现 SSE 流式接收 + AbortController"
```

### Task 6: 前端主组件改造 — AiChatbot.vue 对接 composable

**Files:**
- Modify: `frontend/src/components/business/AiChatbot.vue`
- Create: `frontend/src/components/business/AiProgressIndicator.vue`

- [ ] **Step 1: 创建 AiProgressIndicator.vue**

```vue
<template>
  <div class="flex items-center gap-2 text-muted text-sm">
    <div class="ai-progress-bar">
      <div v-for="(s, i) in stages" :key="s" class="ai-progress-segment" :class="{ active: i <= currentIndex, pulse: i === currentIndex }" />
    </div>
    <span>{{ stageMessage }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stage: { type: String, default: 'thinking' },
  stageMessage: { type: String, default: '正在理解问题...' },
})

const stages = ['thinking', 'generating', 'executing', 'analyzing']
const currentIndex = computed(() => stages.indexOf(props.stage))
</script>

<style scoped>
.ai-progress-bar { display: flex; gap: 3px; }
.ai-progress-segment {
  width: 24px; height: 3px; border-radius: 1.5px;
  background: var(--border); transition: background 0.3s;
}
.ai-progress-segment.active { background: var(--primary); }
.ai-progress-segment.pulse { animation: pulse-bar 1.5s infinite; }
@keyframes pulse-bar {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
```

- [ ] **Step 2: 改造 AiChatbot.vue 使用 composable**

重写 `AiChatbot.vue`，移除内联逻辑，改用 `useAiChat`:
- 移除 `sendMessage`, `handleSelectOption`, `clearChat`, `buildHistory`, `LOCAL_REPLIES`, `tryLocalReply` 等函数
- 从 `useAiChat` 导入 `messages`, `loading`, `sendMessage`, `retryMessage`, `clearChat`
- 保留 `open`, `available`, `presetQueries`, `isMobile`, `checkStatus`, `handleExport`, `handleFeedback`
- `AiMessage` 新增 `@retry` 事件
- loading 消息改用 `AiProgressIndicator` 组件

模板中 loading 部分替换:
```vue
<!-- 在 AiMessage 组件上加 @retry -->
<AiMessage
  v-for="(msg, i) in messages" :key="i"
  :msg="msg"
  @select-option="sendMessage"
  @export="handleExport"
  @feedback="handleFeedback"
  @retry="retryMessage"
/>
```

- [ ] **Step 3: AiMessage.vue 中处理 loading 和 retry**

在 `AiMessage.vue` 的 loading 部分替换三圆点为进度指示器:
```vue
<!-- 替换原有 loading div -->
<AiProgressIndicator v-if="msg.loading" :stage="msg.stage" :stage-message="msg.stageMessage" />
```

在错误模板中加重试按钮:
```vue
<template v-else-if="msg.type === 'error'">
  <p class="text-sm text-error">{{ msg.message }}</p>
  <button v-if="msg._retryable" class="btn btn-secondary btn-sm text-xs mt-2" @click="$emit('retry', msg)">
    <RotateCcw :size="12" class="mr-1" /> 重试
  </button>
</template>
```

新增 import:
```javascript
import { RotateCcw } from 'lucide-vue-next'
import AiProgressIndicator from './AiProgressIndicator.vue'
```

新增 emit:
```javascript
defineEmits(['select-option', 'export', 'feedback', 'retry'])
```

- [ ] **Step 4: Build 验证**

Run: `cd frontend && npm run build`
Expected: 编译成功

- [ ] **Step 5: Docker 重建验证**

Run: `docker compose up -d --build && sleep 3 && docker compose logs erp --tail 5`
Expected: `Application startup complete`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/business/AiChatbot.vue frontend/src/components/business/AiMessage.vue frontend/src/components/business/AiProgressIndicator.vue
git commit -m "feat(ai): 前端 SSE 对接，进度指示器替换三圆点动画，支持重试"
```

---

## Chunk 3: SSE 配套 — 对话持久化 + 输入组件拆分

### Task 7: 对话持久化（#3）

**Files:**
- Modify: `frontend/src/composables/useAiChat.js`

- [ ] **Step 1: 在 useAiChat.js 中添加 sessionStorage 持久化**

在 composable 内部追加:
```javascript
const STORAGE_KEY_PREFIX = 'ai_chat_messages_'
let currentUserId = null

// debounced save
let saveTimer = null
const saveToStorage = () => {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    if (!currentUserId) return
    const key = `${STORAGE_KEY_PREFIX}${currentUserId}`
    // 序列化时剥离 table_data 和 chart_config
    const stripped = messages.value.map(m => {
      if (m.role === 'user') return m
      const { table_data, chart_config, ...rest } = m
      return {
        ...rest,
        _hasTableData: !!table_data,
        _hasChartConfig: !!chart_config,
      }
    })
    const json = JSON.stringify(stripped)
    if (json.length <= 102400) { // 100KB limit
      sessionStorage.setItem(key, json)
    }
  }, 500)
}

const restoreFromStorage = (userId) => {
  currentUserId = userId
  const key = `${STORAGE_KEY_PREFIX}${userId}`
  const raw = sessionStorage.getItem(key)
  if (raw) {
    try {
      const restored = JSON.parse(raw)
      // 标记需要重新查询的消息
      messages.value = restored.map(m => {
        if (m._hasTableData || m._hasChartConfig) {
          return { ...m, _expired: true }
        }
        return m
      })
    } catch { /* ignore corrupt data */ }
  }
}

const clearStorage = () => {
  if (currentUserId) {
    sessionStorage.removeItem(`${STORAGE_KEY_PREFIX}${currentUserId}`)
  }
}
```

修改 `sendMessage` 和 `clearChat` 在操作后调用 `saveToStorage()`。
在 return 中暴露 `restoreFromStorage`, `clearStorage`, `saveToStorage`。

- [ ] **Step 2: AiChatbot.vue 中调用恢复逻辑**

在 `checkStatus` 成功后调用 `restoreFromStorage(userId)`:
```javascript
// 在 checkStatus 中，available 为 true 时
const appStore = useAppStore()
restoreFromStorage(appStore.user?.id)
```

- [ ] **Step 3: AiMessage.vue 中处理过期消息**

在 answer 模板的表格区域加条件:
```vue
<!-- 数据表格 -->
<div v-if="msg._expired && (msg._hasTableData || msg._hasChartConfig)" class="mt-3 p-3 bg-elevated rounded-lg text-center">
  <p class="text-xs text-muted mb-2">数据已过期</p>
  <button class="btn btn-secondary btn-sm text-xs" @click="$emit('select-option', msg._question)">重新查询</button>
</div>
<div v-else-if="msg.table_data" class="mt-3 border rounded-lg overflow-hidden">
  <!-- 原有表格渲染 -->
</div>
```

- [ ] **Step 4: Build 验证**

Run: `cd frontend && npm run build`
Expected: 编译成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useAiChat.js frontend/src/components/business/AiChatbot.vue frontend/src/components/business/AiMessage.vue
git commit -m "feat(ai): 对话 sessionStorage 持久化，刷新不丢，登录重置"
```

### Task 8: 窗口尺寸优化（#4）

**Files:**
- Modify: `frontend/src/components/business/AiChatbot.vue`

- [ ] **Step 1: 添加尺寸切换逻辑和 UI**

在 AiChatbot.vue 中:
```javascript
import { Maximize2, Minimize2 } from 'lucide-vue-next'

const expanded = ref(localStorage.getItem('ai_window_expanded') === 'true')
const toggleExpand = () => {
  expanded.value = !expanded.value
  localStorage.setItem('ai_window_expanded', String(expanded.value))
}
```

标题栏按钮区域加入:
```vue
<button class="ai-header-btn" @click="toggleExpand" :title="expanded ? '缩小' : '展开'" v-if="!isMobile">
  <component :is="expanded ? Minimize2 : Maximize2" :size="14" />
</button>
```

窗口 class 绑定加入 expanded:
```vue
<div v-if="open" class="ai-window" :class="{ 'ai-window-mobile': isMobile, 'ai-window-expanded': expanded && !isMobile }">
```

CSS 新增:
```css
.ai-window-expanded {
  width: 680px;
  height: 720px;
}
.ai-window { transition: width 0.3s ease, height 0.3s ease; }
```

- [ ] **Step 2: Build 验证**

Run: `cd frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/business/AiChatbot.vue
git commit -m "feat(ai): 聊天窗口支持紧凑/扩展双模式切换"
```

---

## Chunk 4: 收藏查询 + 导出增强

### Task 9: 收藏功能（#11）

**Files:**
- Create: `frontend/src/composables/useAiFavorites.js`
- Create: `frontend/src/components/business/AiWelcome.vue`
- Modify: `frontend/src/components/business/AiChatbot.vue`
- Modify: `frontend/src/components/business/AiMessage.vue`

- [ ] **Step 1: 创建 useAiFavorites.js**

```javascript
import { ref } from 'vue'

const KEY_PREFIX = 'ai_favorites_'
const MAX_FAVORITES = 20

export function useAiFavorites(userId) {
  const favorites = ref([])

  const load = () => {
    try {
      const raw = localStorage.getItem(`${KEY_PREFIX}${userId}`)
      favorites.value = raw ? JSON.parse(raw) : []
    } catch { favorites.value = [] }
  }

  const save = () => {
    localStorage.setItem(`${KEY_PREFIX}${userId}`, JSON.stringify(favorites.value))
  }

  const addFavorite = (question) => {
    // 去重：相同 question 更新 timestamp
    const idx = favorites.value.findIndex(f => f.question === question)
    if (idx >= 0) {
      favorites.value[idx].timestamp = Date.now()
    } else {
      favorites.value.unshift({ question, timestamp: Date.now() })
      if (favorites.value.length > MAX_FAVORITES) favorites.value.pop()
    }
    save()
  }

  const removeFavorite = (index) => {
    favorites.value.splice(index, 1)
    save()
  }

  const isFavorited = (question) => favorites.value.some(f => f.question === question)

  load()

  return { favorites, addFavorite, removeFavorite, isFavorited }
}
```

- [ ] **Step 2: 创建 AiWelcome.vue**

```vue
<template>
  <div class="text-center py-6">
    <Sparkles :size="32" class="mx-auto mb-3 opacity-30" />
    <p class="text-sm text-muted mb-4">你好！我是 AI 数据助手，可以帮你查询和分析业务数据。</p>

    <!-- 我的收藏 -->
    <div v-if="favorites.length" class="mb-4 text-left">
      <p class="text-xs text-muted mb-2 px-1">我的收藏</p>
      <div class="flex flex-wrap gap-2">
        <div v-for="(fav, i) in favorites" :key="fav.question" class="group relative">
          <button class="btn btn-secondary btn-sm text-xs" @click="$emit('send', fav.question)">
            <Star :size="10" class="mr-1 text-warning" /> {{ fav.question }}
          </button>
          <button class="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-error text-on-primary text-xs hidden group-hover:flex items-center justify-center" @click.stop="$emit('remove-favorite', i)">
            <X :size="10" />
          </button>
        </div>
      </div>
    </div>

    <!-- 常用查询 -->
    <div v-if="presetQueries.length">
      <p class="text-xs text-muted mb-2 px-1 text-left">常用查询</p>
      <div class="flex flex-wrap gap-2">
        <button v-for="pq in presetQueries" :key="pq.display" class="btn btn-secondary btn-sm text-xs" @click="$emit('send', pq.display)">
          {{ pq.display }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Sparkles, Star, X } from 'lucide-vue-next'

defineProps({
  favorites: { type: Array, default: () => [] },
  presetQueries: { type: Array, default: () => [] },
})

defineEmits(['send', 'remove-favorite'])
</script>
```

- [ ] **Step 3: AiMessage.vue 操作栏加收藏按钮**

在操作栏中（Copy 和 Download 按钮区域）加入:
```vue
<button class="text-xs text-muted hover:text-warning" @click="$emit('favorite', msg)" :title="msg._favorited ? '已收藏' : '收藏查询'">
  <Star :size="14" :fill="msg._favorited ? 'currentColor' : 'none'" :class="msg._favorited ? 'text-warning' : ''" />
</button>
```

新增 `Star` import 和 `favorite` emit。

- [ ] **Step 4: AiChatbot.vue 集成**

在 AiChatbot.vue 中引入 `useAiFavorites` 和 `AiWelcome`，替换原有欢迎语模板，连接收藏和取消收藏逻辑。

- [ ] **Step 5: Build 验证**

Run: `cd frontend && npm run build`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/composables/useAiFavorites.js frontend/src/components/business/AiWelcome.vue frontend/src/components/business/AiChatbot.vue frontend/src/components/business/AiMessage.vue
git commit -m "feat(ai): 收藏查询功能，欢迎页展示收藏+预设，操作栏星标按钮"
```

### Task 10: 导出增强（#12）

**Files:**
- Modify: `frontend/src/components/business/AiMessage.vue`

- [ ] **Step 1: 导出按钮改为下拉菜单，加 CSV 导出**

将原有 Download 按钮替换为下拉:
```vue
<div class="relative" v-if="msg.table_data">
  <button class="text-xs text-muted hover:text-primary" @click="showExportMenu = !showExportMenu" title="导出">
    <Download :size="14" />
  </button>
  <div v-if="showExportMenu" class="absolute bottom-full left-0 mb-1 bg-surface border rounded-lg shadow-lg py-1 z-10 whitespace-nowrap">
    <button class="block w-full text-left px-3 py-1.5 text-xs hover:bg-elevated" @click="$emit('export', msg); showExportMenu = false">导出 Excel</button>
    <button class="block w-full text-left px-3 py-1.5 text-xs hover:bg-elevated" @click="exportCsv(); showExportMenu = false">导出 CSV</button>
  </div>
</div>
```

新增 CSV 生成函数:
```javascript
const showExportMenu = ref(false)

const exportCsv = () => {
  if (!props.msg.table_data) return
  const { columns, rows } = props.msg.table_data
  const bom = '\uFEFF'
  const csv = bom + [
    columns.join(','),
    ...rows.map(r => r.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(','))
  ].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'AI查询结果.csv'
  a.click()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 2: Build 验证**

Run: `cd frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/business/AiMessage.vue
git commit -m "feat(ai): 导出下拉菜单支持 Excel + CSV，CSV 纯前端生成"
```

---

## Chunk 5: 智能增强 — 意图分类 + 反馈

### Task 11: 同义词映射 + 意图分类增强（#7）

**Files:**
- Create: `backend/app/ai/synonym_map.py`
- Modify: `backend/app/ai/intent_classifier.py`
- Test: `backend/tests/test_intent_classifier.py`（新建）

- [ ] **Step 1: 创建 synonym_map.py**

```python
"""默认同义词映射表"""
from __future__ import annotations

DEFAULT_SYNONYMS: dict[str, list[str]] = {
    "销售": ["卖", "营收", "出货", "卖了", "销量", "营业额"],
    "本月": ["这个月", "当月", "这月"],
    "上月": ["上个月", "前一个月"],
    "库存": ["存货", "仓库", "还有多少", "剩余"],
    "客户": ["买家", "客户群", "下单人"],
    "采购": ["进货", "进了多少", "采购单"],
    "利润": ["毛利", "赚了多少", "利润率"],
    "欠款": ["未收", "应收", "没付", "还欠"],
    "缺货": ["不够", "快没了", "补货"],
    "热销": ["卖得好", "销量高", "畅销"],
}
```

- [ ] **Step 2: 改写 intent_classifier.py**

```python
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
```

- [ ] **Step 3: 创建测试 test_intent_classifier.py**

```python
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
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest tests/test_intent_classifier.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/synonym_map.py backend/app/ai/intent_classifier.py backend/tests/test_intent_classifier.py
git commit -m "feat(ai): 意图分类增强 — 同义词展开 + 模糊匹配 + 单关键词精确"
```

### Task 12: 反馈增强（#8）

**Files:**
- Modify: `frontend/src/components/business/AiMessage.vue`

- [ ] **Step 1: 添加反馈确认 Toast 和踩的原因浮层**

在 AiMessage.vue 中:
```javascript
const showNegativeMenu = ref(false)
const feedbackToast = ref(false)

const NEGATIVE_REASONS = ['数据不准确', '答非所问', '回复太慢', '其他']

const handlePositiveFeedback = () => {
  emit('feedback', props.msg, 'positive')
  feedbackToast.value = true
  setTimeout(() => { feedbackToast.value = false }, 1500)
}

const handleNegativeReason = (reason) => {
  props.msg.negative_reason = reason
  emit('feedback', props.msg, 'negative')
  showNegativeMenu.value = false
}
```

模板中替换反馈按钮:
```vue
<!-- 反馈区域 -->
<div class="relative flex items-center gap-1">
  <Transition name="fade"><span v-if="feedbackToast" class="absolute -top-6 left-0 text-xs text-success whitespace-nowrap">感谢反馈</span></Transition>
  <button class="text-xs px-2 py-1 rounded" :class="msg.feedback === 'positive' ? 'bg-success-subtle text-success-emphasis' : 'text-muted hover:text-success'" @click="handlePositiveFeedback">
    <ThumbsUp :size="14" />
  </button>
  <div class="relative">
    <button class="text-xs px-2 py-1 rounded" :class="msg.feedback === 'negative' ? 'bg-error-subtle text-error-emphasis' : 'text-muted hover:text-error'" @click="showNegativeMenu = !showNegativeMenu">
      <ThumbsDown :size="14" />
    </button>
    <div v-if="showNegativeMenu && !msg.feedback" class="absolute bottom-full right-0 mb-1 bg-surface border rounded-lg shadow-lg py-1 z-10 whitespace-nowrap">
      <button v-for="reason in NEGATIVE_REASONS" :key="reason" class="block w-full text-left px-3 py-1.5 text-xs hover:bg-elevated" @click="handleNegativeReason(reason)">
        {{ reason }}
      </button>
    </div>
  </div>
</div>
```

CSS:
```css
.fade-enter-active { transition: opacity 0.3s; }
.fade-leave-active { transition: opacity 0.5s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
```

- [ ] **Step 2: AiChatbot.vue 的 handleFeedback 传递 reason**

确保 `handleFeedback` 传递 `msg.negative_reason`:
```javascript
const handleFeedback = async (msg, type) => {
  if (msg.feedback) return
  msg.feedback = type
  try {
    await aiFeedback({
      message_id: msg.message_id,
      feedback: type,
      save_as_example: type === 'positive',
      original_question: msg._question,
      sql: msg.sql,
      negative_reason: msg.negative_reason || null,
    })
  } catch { /* silent */ }
  saveToStorage()
}
```

- [ ] **Step 3: Build 验证**

Run: `cd frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/business/AiMessage.vue frontend/src/components/business/AiChatbot.vue
git commit -m "feat(ai): 反馈增强 — 点赞 Toast 确认，踩弹出原因选择浮层"
```

---

## Chunk 6: 权限体系

### Task 13: 新建会计语义视图

**Files:**
- Modify: `backend/app/ai/views.sql`

- [ ] **Step 1: 在 views.sql 末尾新增两个会计视图**

```sql
-- ============================================================
-- 8. 科目明细账（仅已过账凭证）
-- ============================================================
CREATE OR REPLACE VIEW vw_accounting_ledger AS
SELECT
    coa.code       AS account_code,
    coa.name       AS account_name,
    coa.category   AS category,
    coa.direction  AS direction,
    v.period_name  AS period_name,
    v.voucher_no   AS voucher_no,
    v.voucher_date AS voucher_date,
    v.voucher_type AS voucher_type,
    ve.summary     AS summary,
    ve.debit_amount  AS debit_amount,
    ve.credit_amount AS credit_amount,
    c.name         AS aux_customer_name,
    s.name         AS aux_supplier_name,
    acts.name      AS account_set_name
FROM voucher_entries ve
JOIN vouchers v          ON v.id = ve.voucher_id
JOIN chart_of_accounts coa ON coa.id = ve.account_id
LEFT JOIN customers c    ON c.id = ve.aux_customer
LEFT JOIN suppliers s    ON s.id = ve.aux_supplier
JOIN account_sets acts   ON acts.id = v.account_set_id
WHERE v.status = 'posted';

-- ============================================================
-- 9. 凭证汇总（按期间、类型统计）
-- ============================================================
CREATE OR REPLACE VIEW vw_accounting_voucher_summary AS
SELECT
    acts.name        AS account_set_name,
    v.period_name    AS period_name,
    v.voucher_type   AS voucher_type,
    COUNT(*)         AS total_count,
    SUM(v.total_debit)  AS total_debit,
    SUM(v.total_credit) AS total_credit,
    COUNT(*) FILTER (WHERE v.status = 'draft')    AS draft_count,
    COUNT(*) FILTER (WHERE v.status = 'pending')  AS pending_count,
    COUNT(*) FILTER (WHERE v.status = 'approved') AS approved_count,
    COUNT(*) FILTER (WHERE v.status = 'posted')   AS posted_count
FROM vouchers v
JOIN account_sets acts ON acts.id = v.account_set_id
GROUP BY acts.name, v.period_name, v.voucher_type;
```

- [ ] **Step 2: 授权 AI 只读用户访问新视图**

在 views.sql 的 GRANT 部分追加:
```sql
GRANT SELECT ON vw_accounting_ledger TO erp_ai_readonly;
GRANT SELECT ON vw_accounting_voucher_summary TO erp_ai_readonly;
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/ai/views.sql
git commit -m "feat(ai): 新增会计语义视图 vw_accounting_ledger + vw_accounting_voucher_summary"
```

### Task 14: 视图权限映射 + schema_registry 改造

**Files:**
- Create: `backend/app/ai/view_permissions.py`
- Modify: `backend/app/ai/schema_registry.py`

- [ ] **Step 1: 创建 view_permissions.py**

```python
"""AI 视图-权限映射表"""
from __future__ import annotations

AI_VIEW_PERMISSIONS: dict[str, str] = {
    # 业务视图
    "vw_sales_detail": "ai_sales",
    "vw_sales_summary": "ai_sales",
    "vw_purchase_detail": "ai_purchase",
    "vw_inventory_status": "ai_stock",
    "vw_inventory_turnover": "ai_stock",
    "vw_receivables": "ai_finance",
    "vw_payables": "ai_finance",
    "vw_accounting_ledger": "ai_accounting",
    "vw_accounting_voucher_summary": "ai_accounting",
    # 基础参考表 — 主开关即可
    "customers": "ai_chat",
    "products": "ai_chat",
    "suppliers": "ai_chat",
    "warehouses": "ai_chat",
    "account_sets": "ai_chat",
}

AI_PERMISSION_KEYS = [
    "ai_chat", "ai_sales", "ai_purchase", "ai_stock",
    "ai_customer", "ai_finance", "ai_accounting",
]


def get_allowed_views(user_permissions: list[str]) -> set[str]:
    """根据用户权限列表返回允许访问的视图/表名集合"""
    allowed = set()
    for view_name, perm_key in AI_VIEW_PERMISSIONS.items():
        if perm_key in user_permissions or "admin" in str(user_permissions):
            allowed.add(view_name)
    return allowed
```

- [ ] **Step 2: 改造 schema_registry.py 支持过滤**

修改 `get_view_schema_text` 函数签名，增加 `allowed_views` 参数:

```python
def get_view_schema_text(allowed_views: set[str] | None = None) -> str:
    """返回视图和参考表的 schema 文本，支持按权限过滤"""
    parts = ["## 可用数据视图和表\n"]

    for view_name, schema in VIEW_SCHEMAS.items():
        if allowed_views is not None and view_name not in allowed_views:
            continue
        parts.append(f"### {view_name}\n{schema}\n")

    for table_name, schema in REFERENCE_TABLE_SCHEMAS.items():
        if allowed_views is not None and table_name not in allowed_views:
            continue
        parts.append(f"### {table_name}（参考表）\n{schema}\n")

    return "\n".join(parts)
```

同时在 `VIEW_SCHEMAS` 中添加两个新会计视图的 schema 描述。

- [ ] **Step 3: Commit**

```bash
git add backend/app/ai/view_permissions.py backend/app/ai/schema_registry.py
git commit -m "feat(ai): 视图权限映射表 + schema_registry 支持 allowed_views 过滤"
```

### Task 15: sql_validator 白名单检查

**Files:**
- Modify: `backend/app/ai/sql_validator.py`
- Modify: `backend/tests/test_sql_validator.py`

- [ ] **Step 1: validate_sql 增加 allowed_tables 参数**

```python
def validate_sql(sql: str, allowed_tables: set[str] | None = None) -> tuple[bool, str, str]:
    # ... 保留原有逻辑 ...

    # 在表引用检查区域追加白名单逻辑
    for node in statement.walk():
        # 原有 blocked tables 检查 ...

        # 新增：白名单检查
        if isinstance(node, exp.Table) and allowed_tables is not None:
            table_name = (node.name or "").lower()
            if table_name and table_name not in allowed_tables:
                return False, "", f"你没有查询 {table_name} 数据的权限"
```

- [ ] **Step 2: 添加白名单测试用例**

在 `test_sql_validator.py` 中追加:
```python
def test_allowed_tables_whitelist():
    ok, _, _ = validate_sql("SELECT * FROM vw_sales_detail", allowed_tables={"vw_sales_detail"})
    assert ok

def test_allowed_tables_blocked():
    ok, _, reason = validate_sql("SELECT * FROM vw_receivables", allowed_tables={"vw_sales_detail"})
    assert not ok
    assert "权限" in reason
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && python -m pytest tests/test_sql_validator.py -v`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/ai/sql_validator.py backend/tests/test_sql_validator.py
git commit -m "feat(ai): SQL 校验器增加 allowed_tables 白名单，按权限拦截越权查询"
```

### Task 16: 前端权限配置 + 后端集成

**Files:**
- Modify: `frontend/src/utils/constants.js`
- Modify: `backend/app/routers/ai_chat.py`
- Modify: `backend/app/services/ai_chat_service.py`
- Modify: `backend/app/ai/preset_queries.py`

- [ ] **Step 1: constants.js 新增 AI 权限组**

在 `permissionGroups` 数组末尾（settings 之前）插入:
```javascript
{
  label: 'AI 助手', icon: 'sparkles', main: 'ai_chat',
  children: [
    { key: 'ai_sales', name: '销售数据' },
    { key: 'ai_purchase', name: '采购数据' },
    { key: 'ai_stock', name: '库存数据' },
    { key: 'ai_customer', name: '客户数据' },
    { key: 'ai_finance', name: '财务数据' },
    { key: 'ai_accounting', name: '会计数据' },
  ]
},
```

- [ ] **Step 2: preset_queries.py 每条预设增加 permission 字段**

为每条预设添加 `"permission": "ai_xxx"` 字段，例如:
```python
{"display": "本月销售概况", "keywords": ["本月", "销售"], "sql": "...", "permission": "ai_sales"},
{"display": "库存状态", "keywords": ["库存"], "sql": "...", "permission": "ai_stock"},
{"display": "应收账款汇总", "keywords": ["应收"], "sql": "...", "permission": "ai_finance"},
```

- [ ] **Step 3: ai_chat.py 路由加权限检查**

`POST /api/ai/chat` 改用 `require_permission("ai_chat")`:
```python
@router.post("/chat")
async def ai_chat(body: ChatRequest, user: User = Depends(require_permission("ai_chat"))):
```

`GET /api/ai/status` 加权限判断:
```python
@router.get("/status")
async def ai_status(user: User = Depends(get_current_user)):
    available, reason = await check_ai_available()
    if available and not user.has_permission("ai_chat"):
        available = False
        reason = "你没有 AI 助手使用权限"
    preset = await get_preset_queries(user_permissions=user.permissions or []) if available else []
    return {"available": available, "reason": reason, "preset_queries": preset}
```

- [ ] **Step 4: ai_chat_service.py 传递权限到各层**

修改 `process_chat` 签名增加 `user_permissions`:
```python
async def process_chat(message, history, user_id, db_dsn, user_permissions=None):
```

在 `_process_chat_inner` 中:
- 调用 `get_allowed_views(user_permissions)` 获取白名单
- 传给 `get_view_schema_text(allowed_views=allowed)` 裁剪 prompt
- 传给 `validate_sql(sql, allowed_tables=allowed)` 做白名单校验

修改 `get_preset_queries` 接收权限过滤:
```python
async def get_preset_queries(user_permissions: list[str] | None = None) -> list[dict]:
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
```

- [ ] **Step 5: Build + Docker 验证**

Run: `cd frontend && npm run build && cd .. && docker compose up -d --build && sleep 3 && docker compose logs erp --tail 5`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/utils/constants.js backend/app/ai/preset_queries.py backend/app/routers/ai_chat.py backend/app/services/ai_chat_service.py
git commit -m "feat(ai): 细粒度 AI 权限控制 — 按用户配置可查询的数据模块"
```

### Task 17: 现有用户权限迁移

**Files:**
- Modify: `backend/app/main.py` 或适当的启动钩子

- [ ] **Step 1: 在应用启动时检查并迁移 AI 权限**

在 `main.py` 的 startup 事件中追加迁移逻辑:
```python
from app.ai.view_permissions import AI_PERMISSION_KEYS

async def _migrate_ai_permissions():
    """一次性：为所有活跃非 admin 用户追加 AI 权限"""
    from app.models import User
    users = await User.filter(is_active=True).exclude(role="admin").all()
    migrated = 0
    for user in users:
        perms = user.permissions or []
        if "ai_chat" not in perms:
            perms.extend(AI_PERMISSION_KEYS)
            user.permissions = list(set(perms))
            await user.save()
            migrated += 1
    if migrated:
        logger.info(f"AI 权限迁移完成，已为 {migrated} 个用户添加 AI 权限")
```

在 lifespan 或 startup 中调用:
```python
await _migrate_ai_permissions()
```

- [ ] **Step 2: Docker 重建验证**

Run: `docker compose up -d --build && sleep 3 && docker compose logs erp --tail 10`
Expected: 启动正常，可能看到迁移日志

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(ai): 启动时自动为现有用户追加 AI 权限（一次性迁移）"
```

---

## Chunk 7: 分析增强 — 查询建议 + 图表

### Task 18: 查询建议（#9）

**Files:**
- Modify: `backend/app/ai/prompt_builder.py`
- Modify: `backend/app/services/ai_chat_service.py`
- Modify: `frontend/src/components/business/AiMessage.vue`

- [ ] **Step 1: 修改 analysis prompt 加 suggestions**

在 `prompt_builder.py` 的 `DEFAULT_ANALYSIS_SYSTEM_PROMPT` 中，响应 JSON 格式改为:
```
响应 JSON 格式：
{{"analysis": "分析文本", "chart_config": {{...}} 或 null, "suggestions": ["相关问题1", "相关问题2", "相关问题3"]}}

suggestions 是 2-3 个用户可能接着问的相关问题，用简短自然语言。不需要时写空数组。
```

- [ ] **Step 2: _execute_and_analyze 提取 suggestions**

在 `ai_chat_service.py` 的 `_execute_and_analyze` 中:
```python
suggestions = None
if v3_result:
    analysis_text = v3_result.get("analysis", analysis_text)
    chart_config = v3_result.get("chart_config")
    suggestions = v3_result.get("suggestions")

return {
    # ... 原有字段 ...
    "suggestions": suggestions,
}
```

- [ ] **Step 3: 本地摘要路径加建议**

在 `_build_local_summary` 返回值改为返回 tuple 或单独处理。更简单的做法：在 `_execute_and_analyze` 的小数据集分支中生成建议:

```python
# 本地建议映射
LOCAL_SUGGESTIONS = {
    "vw_sales": ["毛利分析", "客户销售排名", "产品销售排名"],
    "vw_purchase": ["供应商采购排名", "采购成本趋势"],
    "vw_inventory": ["缺货预警", "库存周转率"],
    "vw_receivable": ["客户欠款排名", "应收账龄分析"],
    "vw_payable": ["供应商应付汇总", "应付账龄分析"],
}

def _get_local_suggestions(sql: str) -> list[str]:
    sql_lower = sql.lower()
    for prefix, suggestions in LOCAL_SUGGESTIONS.items():
        if prefix in sql_lower:
            return suggestions[:3]
    return []
```

在小数据集返回中:
```python
return {
    # ... 原有字段 ...
    "suggestions": _get_local_suggestions(sql),
}
```

- [ ] **Step 4: AiMessage.vue 显示建议按钮**

在 answer 模板的操作栏下方:
```vue
<!-- 相关问题建议 -->
<div v-if="msg.suggestions?.length" class="flex flex-wrap gap-1.5 mt-2">
  <button v-for="s in msg.suggestions" :key="s" class="text-xs px-2 py-1 rounded-full border text-muted hover:text-primary hover:border-primary transition-colors" @click="$emit('select-option', s)">
    {{ s }}
  </button>
</div>
```

- [ ] **Step 5: Build + Docker 验证**

Run: `cd frontend && npm run build && cd .. && docker compose up -d --build`

- [ ] **Step 6: Commit**

```bash
git add backend/app/ai/prompt_builder.py backend/app/services/ai_chat_service.py frontend/src/components/business/AiMessage.vue
git commit -m "feat(ai): 查询建议功能 — AI 推荐相关问题 + 本地回退映射"
```

### Task 19: 图表增强（#10）

**Files:**
- Modify: `frontend/src/components/business/AiChartRenderer.vue`
- Install: `chartjs-plugin-datalabels`

- [ ] **Step 1: 安装依赖**

Run: `cd frontend && npm install chartjs-plugin-datalabels`

- [ ] **Step 2: 重写 AiChartRenderer.vue**

关键改动:
- 调色板扩展到 12 色
- 注册 datalabels 插件
- 动态高度
- 全屏按钮 + 保存图片按钮

```vue
<template>
  <div class="relative">
    <div class="ai-chart-container" :style="{ height: chartHeight + 'px' }">
      <canvas ref="canvasRef" />
    </div>
    <div class="flex items-center gap-2 mt-1 justify-end">
      <button class="text-xs text-muted hover:text-primary" @click="saveAsImage" title="保存图片">
        <ImageDown :size="14" />
      </button>
      <button class="text-xs text-muted hover:text-primary" @click="showFullscreen = true" title="全屏查看">
        <Maximize2 :size="14" />
      </button>
    </div>

    <!-- 全屏 Modal -->
    <Teleport to="body">
      <div v-if="showFullscreen" class="modal-backdrop" @click.self="showFullscreen = false">
        <div class="modal" style="max-width: 90vw; max-height: 90vh;">
          <div class="flex items-center justify-between p-3 border-b">
            <span class="font-semibold text-sm">{{ config.title || '图表' }}</span>
            <button class="ai-header-btn" @click="showFullscreen = false"><X :size="16" /></button>
          </div>
          <div class="p-4" style="height: 60vh;">
            <canvas ref="fullscreenCanvasRef" />
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
```

Script 中:
```javascript
import ChartDataLabels from 'chartjs-plugin-datalabels'
Chart.register(...registerables, ChartDataLabels)

const PALETTE = [
  'oklch(0.55 0.20 250)', 'oklch(0.65 0.20 145)', 'oklch(0.75 0.18 75)',
  'oklch(0.60 0.25 25)', 'oklch(0.60 0.18 300)', 'oklch(0.70 0.15 200)',
  'oklch(0.58 0.22 220)', 'oklch(0.68 0.20 50)', 'oklch(0.55 0.15 330)',
  'oklch(0.72 0.12 110)', 'oklch(0.50 0.20 280)', 'oklch(0.65 0.15 170)',
]

const chartHeight = computed(() => {
  const type = props.config.chart_type
  if (type === 'pie' || type === 'doughnut') return 220
  const dataCount = props.config.labels?.length || 0
  return dataCount > 8 ? 360 : 280
})
```

datalabels 配置（仅饼图/环形图启用）:
```javascript
plugins: {
  datalabels: isPieType ? {
    color: colors.text,
    font: { size: 11 },
    formatter: (value, ctx) => {
      const total = ctx.dataset.data.reduce((a, b) => a + b, 0)
      const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0
      return pct > 5 ? `${pct}%` : ''
    },
  } : { display: false },
  tooltip: { enabled: true },
}
```

保存图片:
```javascript
const saveAsImage = () => {
  if (!chartInstance) return
  const link = document.createElement('a')
  link.download = `${props.config.title || '图表'}.png`
  link.href = chartInstance.toBase64Image()
  link.click()
}
```

- [ ] **Step 3: Build 验证**

Run: `cd frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/business/AiChartRenderer.vue
git commit -m "feat(ai): 图表增强 — 12色调色板、饼图百分比、全屏查看、保存图片"
```

---

## Chunk 8: 配置面板增强

### Task 20: 配置面板导入导出 + 同义词编辑（#14）

**Files:**
- Modify: `frontend/src/components/business/settings/ApiKeysPanel.vue`
- Modify: `backend/app/schemas/ai.py`
- Modify: `backend/app/routers/api_keys.py`

- [ ] **Step 1: AiConfigUpdate schema 增加 synonyms 字段**

在 `ai.py` 的 `AiConfigUpdate` 中追加:
```python
synonyms: Optional[dict] = Field(default=None, alias="ai.synonyms")
```

- [ ] **Step 2: api_keys.py 处理同义词配置的读写**

在 `get_ai_config` 和 `update_ai_config` 中加上 `ai.synonyms` 的处理，与其他 JSON 配置同模式。

- [ ] **Step 3: ApiKeysPanel.vue 加同义词编辑区**

新增一个 card 区块（在快捷问题之后）:
```vue
<!-- 6. 同义词映射 -->
<div class="card p-4">
  <button class="flex items-center justify-between w-full text-left" @click="sections.synonyms = !sections.synonyms">
    <h3 class="font-semibold flex items-center gap-2">
      <ArrowLeftRight :size="16" />
      同义词映射
    </h3>
    <ChevronDown :size="16" :class="{ 'rotate-180': sections.synonyms }" class="transition-transform" />
  </button>
  <div v-if="sections.synonyms" class="mt-4">
    <div class="space-y-2">
      <div v-for="(alts, term) in (aiConfig['ai.synonyms'] || {})" :key="term" class="flex gap-2 items-start">
        <input :value="term" @change="renameSynonymKey(term, $event.target.value)" class="input text-sm w-28" placeholder="标准词" />
        <input :value="alts.join(', ')" @change="updateSynonymAlts(term, $event.target.value)" class="input text-sm flex-1" placeholder="同义词（逗号分隔）" />
        <button class="btn btn-danger btn-sm" @click="deleteSynonym(term)"><Trash2 :size="14" /></button>
      </div>
    </div>
    <div class="flex justify-between mt-3">
      <button class="btn btn-secondary btn-sm" @click="addSynonym">添加映射</button>
      <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存映射</button>
    </div>
  </div>
</div>
```

- [ ] **Step 4: 每个配置区块加导入/导出按钮**

在每个区块的底部按钮栏中追加:
```vue
<div class="flex justify-between mt-3">
  <div class="flex gap-2">
    <button class="btn btn-secondary btn-sm" @click="addXxxItem">添加</button>
    <button class="btn btn-secondary btn-sm" @click="exportJson('ai.xxx')">
      <Download :size="12" class="mr-1" />导出
    </button>
    <label class="btn btn-secondary btn-sm cursor-pointer">
      <Upload :size="12" class="mr-1" />导入
      <input type="file" accept=".json" class="hidden" @change="importJson('ai.xxx', $event)" />
    </label>
  </div>
  <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存</button>
</div>
```

通用导出/导入函数:
```javascript
const exportJson = (configKey) => {
  const data = aiConfig[configKey]
  if (!data) return
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${configKey.replace(/\./g, '_')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

const importJson = async (configKey, event) => {
  const file = event.target.files?.[0]
  if (!file) return
  event.target.value = ''
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    // 基础校验
    if (!validateImport(configKey, data)) return
    aiConfig[configKey] = data
    appStore.showToast('导入成功，请检查后保存')
  } catch {
    appStore.showToast('JSON 格式无效', 'error')
  }
}

const validateImport = (key, data) => {
  if (key === 'ai.business_dict') {
    if (!Array.isArray(data) || !data.every(d => d.term && d.meaning)) {
      appStore.showToast('格式错误：每项需要 term 和 meaning', 'error')
      return false
    }
  } else if (key === 'ai.few_shots') {
    if (!Array.isArray(data) || !data.every(d => d.question && d.sql)) {
      appStore.showToast('格式错误：每项需要 question 和 sql', 'error')
      return false
    }
  } else if (key === 'ai.preset_queries') {
    if (!Array.isArray(data) || !data.every(d => d.display && Array.isArray(d.keywords) && d.sql)) {
      appStore.showToast('格式错误：每项需要 display, keywords, sql', 'error')
      return false
    }
  } else if (key === 'ai.synonyms') {
    if (typeof data !== 'object' || Array.isArray(data)) {
      appStore.showToast('格式错误：应为 {标准词: [同义词...]} 格式', 'error')
      return false
    }
  }
  return true
}
```

- [ ] **Step 5: Build 验证**

Run: `cd frontend && npm run build`

- [ ] **Step 6: Docker 重建验证**

Run: `docker compose up -d --build && sleep 3 && docker compose logs erp --tail 5`

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/business/settings/ApiKeysPanel.vue backend/app/schemas/ai.py backend/app/routers/api_keys.py
git commit -m "feat(ai): 配置面板增强 — 同义词编辑 + JSON 导入导出 + 格式校验"
```

### Task 21: 最终集成验证 + 收尾

- [ ] **Step 1: 全量 Build 验证**

Run: `cd frontend && npm run build`
Expected: 编译成功

- [ ] **Step 2: Docker 完整重建**

Run: `docker compose up -d --build && sleep 5 && docker compose logs erp --tail 20`
Expected: 启动正常

- [ ] **Step 3: 后端测试**

Run: `cd backend && python -m pytest tests/test_intent_classifier.py tests/test_sql_validator.py tests/test_rate_limiter.py -v`
Expected: 全部 PASS

- [ ] **Step 4: 最终 Commit**

如有遗漏修改:
```bash
git add -A && git commit -m "chore(ai): AI 聊天助手 V2 全面优化收尾"
```
