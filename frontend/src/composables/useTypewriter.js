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
