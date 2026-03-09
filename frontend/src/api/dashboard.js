import api from './index'

export const getDashboard = () => api.get('/dashboard')
export const getTodoCounts = () => api.get('/todo-counts')
export const getSalesTrend = (days = 30) => api.get('/dashboard/sales-trend', { params: { days } })
export const getRecentOrders = (limit = 10) => api.get('/dashboard/recent-orders', { params: { limit } })
