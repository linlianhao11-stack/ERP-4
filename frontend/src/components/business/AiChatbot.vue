<template>
  <!-- 入口按钮 -->
  <button v-if="available && !open" class="ai-fab" @click="open = true" title="AI 数据助手">
    <Sparkles :size="22" />
  </button>

  <!-- 聊天窗口 -->
  <Transition name="slide-up">
    <div v-if="open" class="ai-window" :class="{ 'ai-window-mobile': isMobile, 'ai-window-expanded': expanded && !isMobile }">
      <!-- 标题栏 -->
      <div class="ai-header">
        <div class="flex items-center gap-2">
          <Sparkles :size="16" />
          <span class="font-semibold text-sm">AI 数据助手</span>
        </div>
        <div class="flex items-center gap-1">
          <button class="ai-header-btn" @click="toggleExpand" :title="expanded ? '缩小' : '展开'" v-if="!isMobile">
            <component :is="expanded ? Minimize2 : Maximize2" :size="14" />
          </button>
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
        <!-- 欢迎页（含收藏和预设查询） -->
        <AiWelcome
          v-if="messages.length === 0"
          :favorites="favorites"
          :preset-queries="presetQueries"
          @send="handleSend"
          @remove-favorite="handleRemoveFavorite"
        />

        <AiMessage
          v-for="(msg, i) in messages" :key="i"
          :msg="msg"
          @select-option="handleSend"
          @export="handleExport"
          @feedback="handleFeedback"
          @retry="retryMessage"
          @favorite="handleFavorite"
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
import { Sparkles, X, RotateCcw, Send, Maximize2, Minimize2 } from 'lucide-vue-next'
import AiMessage from './AiMessage.vue'
import AiWelcome from './AiWelcome.vue'
import { aiExport, aiFeedback, getAiStatus } from '../../api/ai'
import { useAppStore } from '../../stores/app'
import { useAiChat } from '../../composables/useAiChat'
import { useAiFavorites } from '../../composables/useAiFavorites'

const appStore = useAppStore()
const { messages, loading, sendMessage, retryMessage, clearChat, restoreFromStorage, clearStorage, saveToStorage } = useAiChat()

const open = ref(false)
const available = ref(false)
const input = ref('')
const presetQueries = ref([])
const favorites = ref([])
let favFns = null
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

// 窗口尺寸切换
const expanded = ref(localStorage.getItem('ai_window_expanded') === 'true')
const toggleExpand = () => {
  expanded.value = !expanded.value
  localStorage.setItem('ai_window_expanded', String(expanded.value))
}

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
  clearStorage()
}

const checkStatus = async () => {
  try {
    const { data } = await getAiStatus()
    available.value = data.available
    if (data.available) {
      presetQueries.value = data.preset_queries || []
      restoreFromStorage(appStore.user?.id)
      // 初始化收藏功能
      const userId = appStore.user?.id
      if (userId) {
        favFns = useAiFavorites(userId)
        favorites.value = [...favFns.favorites.value]
      }
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
      negative_reason: msg.negative_reason || null,
    })
  } catch { /* silent */ }
  saveToStorage()
}

const handleFavorite = (msg) => {
  if (!favFns || !msg._question) return
  if (favFns.isFavorited(msg._question)) return
  favFns.addFavorite(msg._question)
  msg._favorited = true
  favorites.value = [...favFns.favorites.value]
}

const handleRemoveFavorite = (index) => {
  if (!favFns) return
  favFns.removeFavorite(index)
  favorites.value = [...favFns.favorites.value]
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
  transition: width 0.3s ease, height 0.3s ease;
}
.ai-window-expanded {
  width: 680px;
  height: 720px;
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
