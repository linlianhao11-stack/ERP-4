/**
 * 样机管理模块 API
 */
import api from './index'

// 统计
export const getDemoStats = (params) => api.get('/demo/stats', { params })

// 样机台账
export const getDemoUnits = (params) => api.get('/demo/units', { params })
export const getDemoUnit = (id) => api.get('/demo/units/' + id)
export const createDemoUnit = (data) => api.post('/demo/units', data)
export const updateDemoUnit = (id, data) => api.put('/demo/units/' + id, data)
export const deleteDemoUnit = (id) => api.delete('/demo/units/' + id)
export const exportDemoUnits = (params) => api.get('/demo/units/export', { params, responseType: 'blob' })

// 借还记录
export const getDemoLoans = (params) => api.get('/demo/loans', { params })
export const getDemoLoan = (id) => api.get('/demo/loans/' + id)
export const createDemoLoan = (data) => api.post('/demo/loans', data)
export const approveDemoLoan = (id) => api.post('/demo/loans/' + id + '/approve')
export const rejectDemoLoan = (id) => api.post('/demo/loans/' + id + '/reject')
export const lendDemoLoan = (id) => api.post('/demo/loans/' + id + '/lend')
export const returnDemoLoan = (id, data) => api.post('/demo/loans/' + id + '/return', data)

// 处置
export const sellDemoUnit = (id, data) => api.post('/demo/units/' + id + '/sell', data)
export const convertDemoUnit = (id, data) => api.post('/demo/units/' + id + '/convert', data)
export const scrapDemoUnit = (id, data) => api.post('/demo/units/' + id + '/scrap', data)
export const reportLossDemoUnit = (id, data) => api.post('/demo/units/' + id + '/report-loss', data)
