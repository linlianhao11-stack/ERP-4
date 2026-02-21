export const fuzzyMatch = (text, kw) => {
  if (!kw) return true
  const words = kw.toLowerCase().split(/\s+/).filter(Boolean)
  const t = (text || '').toLowerCase()
  const ts = t.replace(/\s/g, '')
  return words.every(w => t.includes(w) || ts.includes(w))
}

export const fuzzyMatchAny = (fields, kw) => {
  if (!kw) return true
  const words = kw.toLowerCase().split(/\s+/).filter(Boolean)
  return words.every(w =>
    fields.some(f => {
      const fl = (f || '').toLowerCase()
      return fl.includes(w) || fl.replace(/\s/g, '').includes(w)
    })
  )
}

export const parseSnCodes = (input) => {
  if (!input || !input.trim()) return []
  return input.split(/[\s,，\n\r]+/).map(s => s.trim()).filter(s => s.length > 0)
}

export const amountToChinese = (n) => {
  if (!n || n === 0) return '零元整'
  n = Math.abs(parseFloat(n))
  n = Math.round(n * 100) / 100  // Round to cents first
  const digit = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
  const unit = [['元', '万', '亿', '兆'], ['', '拾', '佰', '仟']]
  const intPart_raw = Math.floor(n)
  const decPart = Math.round((n - intPart_raw) * 100)
  const jiao = Math.floor(decPart / 10)
  const fen = decPart % 10
  let s = ''
  if (jiao > 0) s += digit[jiao] + '角'
  if (fen > 0) s += digit[fen] + '分'
  if (!s) s = '整'
  let intPart = intPart_raw
  if (intPart === 0) return '零元' + s
  for (let i = 0; i < unit[0].length && intPart > 0; i++) {
    let p = ''
    for (let j = 0; j < unit[1].length && intPart > 0; j++) {
      p = digit[intPart % 10] + unit[1][j] + p
      intPart = Math.floor(intPart / 10)
    }
    s = p.replace(/(零.)*零$/, '').replace(/^$/, '零') + unit[0][i] + s
  }
  return s.replace(/(零.)*零元/, '元').replace(/(零.)+/g, '零').replace(/^整$/, '零元整')
}
