/**
 * 快递公司列表（与快递100 carrier_code 对应）
 */
export const CARRIERS = [
  { code: 'shunfeng', name: '顺丰速运' },
  { code: 'zhongtong', name: '中通快递' },
  { code: 'yuantong', name: '圆通速递' },
  { code: 'shentong', name: '申通快递' },
  { code: 'yunda', name: '韵达快递' },
  { code: 'jd', name: '京东物流' },
  { code: 'debangkuaidi', name: '德邦快递' },
  { code: 'ems', name: 'EMS' },
]

/** 需要手机号后四位才能查询物流的快递公司 */
export const PHONE_REQUIRED_CARRIERS = new Set(['shunfeng', 'shunfengkuaiyun', 'zhongtong'])

/** 无需物流跟踪的配送方式（自提/自配送） */
export const NO_LOGISTICS_CODES = new Set(['self_pickup', 'self_delivery'])
