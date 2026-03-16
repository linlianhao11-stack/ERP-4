/**
 * 代采代发模块 API
 */
import api from './index'

// 订单 CRUD
export const getDropshipOrders = (params) => api.get('/dropship', { params })
export const getDropshipOrder = (id) => api.get('/dropship/' + id)
export const createDropshipOrder = (data, submit = false) =>
  api.post('/dropship' + (submit ? '?submit=true' : ''), data)
export const updateDropshipOrder = (id, data) => api.put('/dropship/' + id, data)

// 订单操作
export const submitDropshipOrder = (id) => api.post('/dropship/' + id + '/submit')
export const urgeDropshipOrder = (id) => api.post('/dropship/' + id + '/urge')
export const shipDropshipOrder = (id, data) => api.post('/dropship/' + id + '/ship', data)
export const completeDropshipOrder = (id) => api.post('/dropship/' + id + '/complete')
export const cancelDropshipOrder = (id, data) => api.post('/dropship/' + id + '/cancel', data)
export const batchPayDropship = (data) => api.post('/dropship/batch-pay', data)

// 报表
export const getDropshipReportSummary = (params) => api.get('/dropship/reports/summary', { params })
export const getDropshipReportProfit = (params) => api.get('/dropship/reports/profit', { params })
export const getDropshipReportReceivable = (params) => api.get('/dropship/reports/receivable', { params })

// 付款工作台
export const getPaymentWorkbench = (params) => api.get('/dropship/payment-workbench', { params })

// 供应商导入
export const importSuppliers = (formData) =>
  api.post('/suppliers/import', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
export const downloadSupplierTemplate = () =>
  api.get('/suppliers/import-template', { responseType: 'blob' })

// 物流
export const refreshDropshipTracking = (id) => api.post('/dropship/' + id + '/refresh-tracking')
