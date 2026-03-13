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
    // clarification 或 text 回复的内容
    if (m.message) parts.push(m.message)
    // 过期消息（sessionStorage 恢复后 table_data 丢失）也保留已有上下文
    if (m._expired && m._hasTableData) parts.push('[之前有表格数据，已过期]')
    return parts.join('\n') || ''
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

  // sessionStorage 持久化
  const STORAGE_KEY_PREFIX = 'ai_chat_messages_'
  let currentUserId = null

  // 防抖保存
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
      if (json.length <= 102400) { // 100KB 限制
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
        messages.value = restored.map(m => {
          if (m._hasTableData || m._hasChartConfig) {
            return { ...m, _expired: true }
          }
          return m
        })
      } catch { /* 忽略损坏数据 */ }
    }
  }

  const clearStorage = () => {
    if (currentUserId) {
      sessionStorage.removeItem(`${STORAGE_KEY_PREFIX}${currentUserId}`)
    }
  }

  const sendMessage = async (text) => {
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
        body: JSON.stringify({ message: msg, history }),
        signal: abortController.signal,
      })

      if (response.status === 401) {
        messages.value[aiMsgIndex] = {
          loading: false, role: 'assistant', type: 'error',
          message: '登录已过期，请刷新页面重新登录',
          _retryable: false, _originalQuestion: msg, _errorType: 'auth',
        }
        return
      }

      if (response.status === 403) {
        messages.value[aiMsgIndex] = {
          loading: false, role: 'assistant', type: 'error',
          message: '你没有使用 AI 助手的权限，请联系管理员开通',
          _retryable: false, _originalQuestion: msg, _errorType: 'forbidden',
        }
        return
      }

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
      saveToStorage()
    }
  }

  const retryMessage = (msg) => {
    if (msg._originalQuestion) {
      const idx = messages.value.indexOf(msg)
      if (idx >= 0) messages.value.splice(idx, 1)
      if (idx > 0 && messages.value[idx - 1]?.role === 'user') {
        messages.value.splice(idx - 1, 1)
      }
      sendMessage(msg._originalQuestion)
    }
  }

  const clearChat = () => {
    messages.value = []
    if (abortController) abortController.abort()
    saveToStorage()
  }

  onUnmounted(() => {
    if (abortController) abortController.abort()
  })

  return {
    messages, loading, sendMessage, retryMessage, clearChat, buildHistory,
    restoreFromStorage, clearStorage, saveToStorage,
  }
}
