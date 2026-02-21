import api from './index'

export const getCustomers = () => api.get('/customers')
export const createCustomer = (data) => api.post('/customers', data)
export const updateCustomer = (id, data) => api.put('/customers/' + id, data)
export const getCustomerTransactions = (id, params) => api.get('/customers/' + id + '/transactions', { params })
