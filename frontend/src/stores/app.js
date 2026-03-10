import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import { getTodoCounts } from '../api/dashboard'

export const useAppStore = defineStore('app', () => {
  // Theme — light/dark, persisted to localStorage
  const theme = ref(localStorage.getItem('erp-theme') || 'light')

  const setTheme = (newTheme) => {
    theme.value = newTheme
    localStorage.setItem('erp-theme', newTheme)
    document.documentElement.dataset.theme = newTheme
  }

  const toggleTheme = () => {
    setTheme(theme.value === 'light' ? 'dark' : 'light')
  }

  const initTheme = () => {
    document.documentElement.dataset.theme = theme.value
  }

  const toast = reactive({ show: false, msg: '', type: 'success' })
  const modal = reactive({ show: false, type: '', title: '' })
  const confirmDialog = reactive({ show: false, message: '', detail: '', resolve: null })
  const _submittingCount = ref(0)
  const submitting = computed({
    get: () => _submittingCount.value > 0,
    set: (val) => {
      if (val) _submittingCount.value++
      else _submittingCount.value = Math.max(0, _submittingCount.value - 1)
    }
  })
  const previousModal = ref(null)

  let _toastTimer = null
  const _toastQueue = []

  const _showNextToast = () => {
    if (_toastQueue.length === 0) {
      toast.show = false
      return
    }
    const next = _toastQueue.shift()
    toast.msg = next.msg
    toast.type = next.type
    toast.show = true
    if (_toastTimer) clearTimeout(_toastTimer)
    _toastTimer = setTimeout(() => {
      toast.show = false
      // 延迟一点再显示下一条，给过渡动画留时间
      setTimeout(_showNextToast, 150)
    }, 3000)
  }

  const showToast = (msg, type = 'success') => {
    // 相同消息去重
    if (toast.show && toast.msg === msg && toast.type === type) return
    if (_toastQueue.some(t => t.msg === msg && t.type === type)) return
    if (toast.show) {
      // 当前有 toast 显示中，排队（最多保留3条）
      if (_toastQueue.length < 3) _toastQueue.push({ msg, type })
    } else {
      toast.msg = msg
      toast.type = type
      toast.show = true
      if (_toastTimer) clearTimeout(_toastTimer)
      _toastTimer = setTimeout(() => {
        toast.show = false
        setTimeout(_showNextToast, 150)
      }, 3000)
    }
  }

  const openModal = (type, title) => {
    modal.type = type
    modal.title = title || type
    modal.show = true
  }

  const closeModal = () => {
    modal.show = false
    modal.type = ''
  }

  const customConfirm = (message, detail = '') => new Promise(resolve => {
    confirmDialog.message = message
    confirmDialog.detail = detail
    confirmDialog.show = true
    confirmDialog.resolve = resolve
  })

  const confirmDialogYes = () => {
    confirmDialog.show = false
    if (confirmDialog.resolve) {
      confirmDialog.resolve(true)
      confirmDialog.resolve = null
    }
  }

  const confirmDialogNo = () => {
    confirmDialog.show = false
    if (confirmDialog.resolve) {
      confirmDialog.resolve(false)
      confirmDialog.resolve = null
    }
  }

  const resetTransientState = () => {
    if (_toastTimer) clearTimeout(_toastTimer)
    _toastTimer = null
    _toastQueue.length = 0
    toast.show = false
    toast.msg = ''
    toast.type = 'success'
    modal.show = false
    modal.type = ''
    modal.title = ''
    if (confirmDialog.resolve) confirmDialog.resolve(false)
    confirmDialog.show = false
    confirmDialog.message = ''
    confirmDialog.detail = ''
    confirmDialog.resolve = null
    _submittingCount.value = 0
    previousModal.value = null
  }

  // Todo counts — sidebar badges
  const todoCounts = ref({})

  const loadTodoCounts = async () => {
    try {
      const { data } = await getTodoCounts()
      todoCounts.value = data
    } catch (e) {
      // silent fail
    }
  }

  return {
    theme, setTheme, toggleTheme, initTheme,
    toast, modal, confirmDialog, submitting, previousModal,
    showToast, openModal, closeModal,
    customConfirm, confirmDialogYes, confirmDialogNo,
    resetTransientState,
    todoCounts, loadTodoCounts
  }
})
