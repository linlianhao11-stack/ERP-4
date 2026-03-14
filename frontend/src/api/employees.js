import api from './index'

export const getDepartments = () => api.get('/departments')
export const createDepartment = (data) => api.post('/departments', data)
export const updateDepartment = (id, data) => api.put('/departments/' + id, data)
export const deleteDepartment = (id) => api.delete('/departments/' + id)

export const getEmployees = (params) => api.get('/employees', { params })
export const createEmployee = (data) => api.post('/employees', data)
export const updateEmployee = (id, data) => api.put('/employees/' + id, data)
export const deleteEmployee = (id) => api.delete('/employees/' + id)
