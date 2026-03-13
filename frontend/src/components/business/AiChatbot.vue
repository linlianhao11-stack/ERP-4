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
          <button class="ai-header-btn" @click="handleClear" title="清空对话">
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
            <button v-for="pq in presetQueries" :key="pq.display" class="btn btn-secondary btn-sm text-xs" @click="handleSend(pq.display)">
              {{ pq.display }}
            </button>
          </div>
        </div>

        <AiMessage
          v-for="(msg, i) in messages" :key="i"
          :msg="msg"
          @select-option="handleSend"
          @export="handleExport"
          @feedback="handleFeedback"
          @retry="retryMessage"
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
          @keydown.enter.exact.prevent="handleSend(input)"
          @input="autoResize"
        />
        <button class="ai-send-btn" @click="handleSend(input)" :disabled="!input.trim() || loading">
          <Send :size="16" />
        </button>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Sparkles, X, RotateCcw, Send } from 'lucide-vue-next'
import AiMessage from './AiMessage.vue'
import { aiExport, aiFeedback, getAiStatus } from '../../api/ai'
import { useAppStore } from '../../stores/app'
import { useAiChat } from '../../composables/useAiChat'

const appStore = useAppStore()
const { messages, loading, sendMessage, retryMessage, clearChat } = useAiChat()

const open = ref(false)
const available = ref(false)
const input = ref('')
const presetQueries = ref([])
const messagesRef = ref(null)
const inputRef = ref(null)
const isMobile = ref(false)
const mql = window.matchMedia('(max-width: 767px)')
const updateMobile = (e) => { isMobile.value = e.matches }
onMounted(() => {
  isMobile.value = mql.matches
  mql.addEventListener('change', updateMobile)
})
onUnmounted(() => mql.removeEventListener('change', updateMobile))

// 自动滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

// 监听消息变化自动滚动
watch(() => messages.value.length, scrollToBottom)
watch(loading, scrollToBottom)

const handleSend = async (text) => {
  if (!text || !text.trim()) return
  input.value = ''
  autoResize()
  await sendMessage(text)
  scrollToBottom()
}

const handleClear = () => {
  clearChat()
}

const checkStatus = async () => {
  try {
    const { data } = await getAiStatus()
    available.value = data.available
    if (data.available) {
      presetQueries.value = data.preset_queries || []
    }
  } catch {
    available.value = false
  }
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
  if (msg.feedback) return
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
  overscroll-behavior: contain;
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
