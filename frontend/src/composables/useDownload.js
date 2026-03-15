/**
 * 下载 Blob 数据为文件
 */
export function downloadBlob(data, filename) {
  const url = URL.createObjectURL(new Blob([data]))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
