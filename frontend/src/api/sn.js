import api from './index'

export const getSnConfigs = () => api.get('/sn-configs')
export const createSnConfig = (data) => api.post('/sn-configs', data)
export const deleteSnConfig = (id) => api.delete('/sn-configs/' + id)
export const checkSnRequired = (params) => api.get('/sn-codes/check-required', { params })
