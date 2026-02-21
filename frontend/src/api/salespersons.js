import api from './index'

export const getSalespersons = () => api.get('/salespersons')
export const createSalesperson = (data) => api.post('/salespersons', data)
export const updateSalesperson = (id, data) => api.put('/salespersons/' + id, data)
export const deleteSalesperson = (id) => api.delete('/salespersons/' + id)
