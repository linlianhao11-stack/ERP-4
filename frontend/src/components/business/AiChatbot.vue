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
          aria-label="输入你的问题"
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

// 非数据问题本地快速回复，避免调用慢速 R1 模型
const LOCAL_REPLIES = [
  { patterns: ['你是谁', '你是什么', '介绍一下你', '你叫什么'], reply: '我是 AI 数据助手，专门帮你查询和分析业务数据（销售、采购、库存、应收应付等）。试试问我"本月销售概况"或"哪些产品快缺货了"吧！' },
  { patterns: ['你好', '嗨', 'hi', 'hello', '在吗'], reply: '你好！我是 AI 数据助手。你可以问我业务数据相关的问题，比如销售、采购、库存、应收应付等。' },
  { patterns: ['谢谢', '感谢', 'thanks'], reply: '不客气！有其他数据需要查询随时问我。' },
  { patterns: ['能做什么', '怎么用', '有什么功能', '帮助'], reply: '我可以帮你查询和分析：\n- **销售数据**：销售额、毛利、客户分析、产品排名\n- **采购数据**：采购金额、供应商分析\n- **库存数据**：库存状态、缺货预警、周转率\n- **应收应付**：欠款汇总、账龄分析\n\n直接用自然语言提问即可，比如"本月毛利多少"、"哪些客户欠款最多"。' },
  { patterns: ['聊天', '闲聊', '除了工作', '别的事', '聊点别的', '讲个笑话', '天气', '今天心情'], reply: '不好意思，我是专门的业务数据助手，只能帮你查询和分析 ERP 系统中的数据哦。试试问我一些业务问题吧，比如"本月毛利多少"、"哪些客户欠款最多"。' },
]

const tryLocalReply = (msg) => {
  const lower = msg.toLowerCase()
  for (const item of LOCAL_REPLIES) {
    if (item.patterns.some(p => lower.includes(p))) return item.reply
  }
  return null
}

const sendMessage = async (text) => {
  if (!text || !text.trim() || loading.value) return
  const msg = text.trim()
  input.value = ''
  autoResize()

  messages.value.push({ role: 'user', content: msg })

  // 非数据问题本地秒回
  const localReply = tryLocalReply(msg)
  if (localReply) {
    messages.value.push({ role: 'assistant', type: 'clarification', message: localReply, options: [] })
    scrollToBottom()
    return
  }

  messages.value.push({ role: 'assistant', loading: true })
  const aiMsgIndex = messages.value.length - 1
  scrollToBottom()

  loading.value = true
  try {
    const { data } = await aiChat({
      message: msg,
      history: buildHistory().slice(0, -2), // 排除当前这轮
    })
    messages.value[aiMsgIndex] = { ...data, loading: false, role: 'assistant', _question: msg }
  } catch (e) {
    const isTimeout = e.code === 'ECONNABORTED' || e.message?.includes('timeout')
    messages.value[aiMsgIndex] = {
      loading: false,
      role: 'assistant',
      type: 'error',
      message: isTimeout ? 'AI 思考超时了，请简化问题后重试' : (e.response?.data?.message || '请求失败，请检查网络连接'),
    }
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
  box-shadow: var(--shadow-lg);
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
