import api from './index'

export const restock = (data) => api.post('/stock/restock', data)
export const transfer = (data) => api.post('/stock/transfer', data)
export const exportStock = (params) => api.get('/stock/export', { params, responseType: 'blob' })
