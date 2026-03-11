import api from './index'

export const getSuppliers = (params) => api.get('/suppliers', { params })
export const createSupplier = (data) => api.post('/suppliers', data)
export const updateSupplier = (id, data) => api.put('/suppliers/' + id, data)
export const deleteSupplier = (id) => api.delete('/suppliers/' + id)

export const getPurchaseOrders = (params) => api.get('/purchase-orders', { params })
export const getPurchaseOrder = (id) => api.get('/purchase-orders/' + id)
export const createPurchaseOrder = (data) => api.post('/purchase-orders', data)
export const exportPurchaseOrders = (params) => api.get('/purchase-orders/export', { params, responseType: 'blob' })
export const getReceivablePOs = () => api.get('/purchase-orders/receivable')

export const approvePurchaseOrder = (id) => api.post('/purchase-orders/' + id + '/approve')
export const rejectPurchaseOrder = (id) => api.post('/purchase-orders/' + id + '/reject')
export const payPurchaseOrder = (id, data) => api.post('/purchase-orders/' + id + '/pay', data)
export const cancelPurchaseOrder = (id) => api.post('/purchase-orders/' + id + '/cancel')
export const receivePurchaseOrder = (id, data) => api.post('/purchase-orders/' + id + '/receive', data)
export const returnPurchaseOrder = (id, data) => api.post('/purchase-orders/' + id + '/return', data)
export const getSupplierTransactions = (id, params) => api.get('/suppliers/' + id + '/transactions', { params })
export const refundSupplierCredit = (id, data) => api.post('/suppliers/' + id + '/credit-refund', data)

export const getPurchaseOrderItems = (poId) => api.get(`/purchase-orders/${poId}/items`)

export const getPurchaseReturns = (params) => api.get('/purchase-returns', { params })
export const getPurchaseReturn = (id) => api.get('/purchase-returns/' + id)
