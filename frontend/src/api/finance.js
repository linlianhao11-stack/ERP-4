import api from './index'

export const getAllOrders = (params) => api.get('/finance/all-orders', { params })
export const exportOrders = (params) => api.get('/finance/all-orders/export', { params, responseType: 'blob' })
export const getUnpaidOrders = (params) => api.get('/finance/unpaid-orders', { params })
export const getStockLogs = (params) => api.get('/finance/stock-logs', { params })
export const createPayment = (data) => api.post('/finance/payment', data)
export const getPayments = () => api.get('/finance/payments')
export const confirmPayment = (id) => api.post('/finance/payment/' + id + '/confirm')
