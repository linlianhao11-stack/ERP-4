import api from './index'

export const getRebateSummary = (params) => api.get('/rebates/summary', { params })
export const chargeRebate = (data) => api.post('/rebates/charge', data)
export const getRebateLogs = (params) => api.get('/rebates/logs', { params })
