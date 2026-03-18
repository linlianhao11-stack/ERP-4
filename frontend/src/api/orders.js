import api from './index'

export const getOrders = (params) => api.get('/orders', { params })
export const getOrder = (id) => api.get('/orders/' + id)
export const createOrder = (data) => api.post('/orders', data)
export const cancelOrder = (id, data) => api.post('/orders/' + id + '/cancel', data)
export const cancelPreview = (id) => api.get('/orders/' + id + '/cancel-preview')
export const updateOrderRemark = (id, remark) => api.patch('/orders/' + id + '/remark', { remark })
