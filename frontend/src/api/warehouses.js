import api from './index'

export const getWarehouses = (params) => api.get('/warehouses', { params })
export const createWarehouse = (data) => api.post('/warehouses', data)
export const updateWarehouse = (id, data) => api.put('/warehouses/' + id, data)
export const deleteWarehouse = (id) => api.delete('/warehouses/' + id)
export const getLocations = (params) => api.get('/locations', { params })
export const createLocation = (data) => api.post('/locations', data)
export const updateLocation = (id, data) => api.put('/locations/' + id, data)
export const deleteLocation = (id) => api.delete('/locations/' + id)
