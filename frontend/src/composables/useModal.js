import { reactive, computed } from 'vue'

/**
 * 管理多个弹窗的显示状态和关联数据
 * @returns {Object} open, close, isVisible, getData
 *
 * 用法：
 *   const modal = useModal()
 *   modal.open('detail', { id: 1 })
 *   modal.isVisible('detail')  // true
 *   modal.getData('detail')    // { id: 1 }
 *   modal.close('detail')
 */
export function useModal() {
  const state = reactive({})
  const _computedCache = {}

  const open = (name, data = null) => {
    state[name] = { visible: true, data }
  }

  const close = (name) => {
    if (state[name]) {
      state[name].visible = false
      state[name].data = null
    }
  }

  const isVisible = (name) => {
    if (!_computedCache[name]) {
      _computedCache[name] = computed(() => !!state[name]?.visible)
    }
    return _computedCache[name]
  }

  const getData = (name) => {
    return state[name]?.data ?? null
  }

  return { open, close, isVisible, getData }
}
