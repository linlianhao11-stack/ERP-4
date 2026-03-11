/**
 * useColumnConfig — 可复用的列可见性 + 视图模式管理
 * 从 useShipment.js 列配置模式提取，供所有表格面板共享
 *
 * @param {string} storageKey — localStorage 键名（如 'purchase_columns'）
 * @param {Object} columnDefs — 列定义 { key: { label, defaultVisible, align, width } }
 * @param {Object} options — 可选配置 { supportViewMode: false }
 */
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'

export function useColumnConfig(storageKey, columnDefs, options = {}) {
  const { supportViewMode = false } = options

  // 从定义生成默认可见性映射
  const defaultVisibility = {}
  for (const [key, def] of Object.entries(columnDefs)) {
    defaultVisibility[key] = def.defaultVisible !== false
  }

  // 列标签映射（供模板遍历）
  const columnLabels = {}
  for (const [key, def] of Object.entries(columnDefs)) {
    columnLabels[key] = def.label
  }

  // 从 localStorage 恢复（兼容旧格式）
  let saved = null
  try {
    const raw = localStorage.getItem(storageKey)
    if (raw) {
      const parsed = JSON.parse(raw)
      // 兼容旧格式：如果没有 columns 子键，整个对象就是列配置
      if (parsed && typeof parsed === 'object' && !parsed.columns) {
        saved = { columns: parsed }
      } else {
        saved = parsed
      }
    }
  } catch { /* 忽略损坏数据 */ }

  const visibleColumns = reactive({ ...defaultVisibility, ...(saved?.columns || {}) })
  const viewMode = ref(saved?.viewMode || 'summary')

  // 持久化到 localStorage
  const persist = () => {
    const data = { columns: { ...visibleColumns } }
    if (supportViewMode) data.viewMode = viewMode.value
    localStorage.setItem(storageKey, JSON.stringify(data))
  }

  // 可见列定义（计算属性）
  const activeColumns = computed(() => {
    return Object.entries(columnDefs)
      .filter(([key]) => visibleColumns[key])
      .map(([key, def]) => ({ key, ...def }))
  })

  const toggleColumn = (key) => {
    visibleColumns[key] = !visibleColumns[key]
    persist()
  }

  const isColumnVisible = (key) => visibleColumns[key]

  const setViewMode = (mode) => {
    viewMode.value = mode
    persist()
  }

  const resetColumns = () => {
    Object.assign(visibleColumns, defaultVisibility)
    if (supportViewMode) viewMode.value = 'summary'
    persist()
  }

  // 列菜单展开状态 + 点击外部关闭（用 storageKey 区分不同面板的菜单）
  const menuAttr = `data-column-menu-${storageKey}`
  const showColumnMenu = ref(false)
  const handleDocClick = (e) => {
    if (showColumnMenu.value && !e.target.closest(`[${menuAttr}]`)) {
      showColumnMenu.value = false
    }
  }

  onMounted(() => document.addEventListener('click', handleDocClick))
  onUnmounted(() => document.removeEventListener('click', handleDocClick))

  return {
    columnDefs,
    columnLabels,
    visibleColumns,
    activeColumns,
    showColumnMenu,
    toggleColumn,
    isColumnVisible,
    resetColumns,
    // 视图模式（仅 supportViewMode 时有意义）
    viewMode,
    setViewMode,
    // 菜单属性名（用于模板 data-attribute）
    menuAttr
  }
}
