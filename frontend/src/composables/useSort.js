import { reactive } from 'vue'

export function useSort(defaultKey = '', defaultOrder = '') {
  const sortState = reactive({ key: defaultKey, order: defaultOrder })

  const toggleSort = (key) => {
    if (sortState.key === key) {
      if (sortState.order === 'asc') sortState.order = 'desc'
      else { sortState.key = ''; sortState.order = '' }
    } else {
      sortState.key = key
      sortState.order = 'asc'
    }
  }

  const genericSort = (list, fieldMap) => {
    if (!sortState.key) return list
    const asc = sortState.order === 'asc'
    return [...list].sort((a, b) => {
      const fn = fieldMap[sortState.key]
      if (!fn) return 0
      const va = fn(a), vb = fn(b)
      if (va == null && vb == null) return 0
      if (va == null) return 1   // nulls last
      if (vb == null) return -1
      if (typeof va === 'string') {
        const r = va.localeCompare(vb, 'zh')
        return asc ? r : -r
      }
      if (va < vb) return asc ? -1 : 1
      if (va > vb) return asc ? 1 : -1
      return 0
    })
  }

  return { sortState, toggleSort, genericSort }
}
