export function useFormat() {
  const fmt = (v) => (Number(v) || 0).toFixed(2)

  const fmtDate = (d) => {
    if (!d) return ''
    return new Date(d).toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
    })
  }

  /**
   * 格式化余额显示值（取反：正值余额显示为负数）
   * 注意：getBalanceLabel/getBalanceClass 使用原始值，不取反
   */
  const formatBalance = (v) => fmt(-(v || 0))

  const getBalanceLabel = (v) => v < 0 ? '在账资金' : (v > 0 ? '欠款' : '两清')
  const getBalanceClass = (v) => v < 0 ? 'text-primary' : (v > 0 ? 'text-error' : 'text-muted')

  const getAgeClass = (d) => d < 30 ? 'age-normal' : d < 90 ? 'age-slow' : 'age-dead'

  const fmtMoney = (v) => {
    if (!v && v !== 0) return ''
    return parseFloat(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  return { fmt, fmtDate, formatBalance, getBalanceLabel, getBalanceClass, getAgeClass, fmtMoney }
}
