/** 需要手机号后四位才能查询物流的快递公司 */
export const PHONE_REQUIRED_CARRIERS = new Set(['shunfeng', 'shunfengkuaiyun', 'zhongtong'])

/** 无需物流跟踪的配送方式（自提/自配送） */
export const NO_LOGISTICS_CODES = new Set(['self_pickup', 'self_delivery'])

/** 判断是否为无物流配送方式 */
export const isNoLogisticsCode = (code) => NO_LOGISTICS_CODES.has(code)

/** 无物流配送的提示文案 */
export const noLogisticsHint = (code) =>
  code === 'self_delivery' ? '自配送（无需快递单号）' : '客户上门自提'

/** 发货/操作按钮文案 */
export const shipActionText = (code) => {
  if (code === 'self_pickup') return '确认自提'
  if (code === 'self_delivery') return '确认送达'
  return '确认发货'
}
