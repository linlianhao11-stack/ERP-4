import api from './index'

export const getSummary = () => api.get('/consignment/summary')
export const getConsignCustomers = () => api.get('/consignment/customers')
export const getCustomerDetail = (id) => api.get('/consignment/customer/' + id)
export const returnConsignment = (data) => api.post('/consignment/return', data)
