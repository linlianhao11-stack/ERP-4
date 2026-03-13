import api from './index'

export const getProducts = (params) => api.get('/products', { params })
export const getNextSku = () => api.get('/products/next-sku')
export const createProduct = (data) => api.post('/products', data)
export const updateProduct = (id, data) => api.put('/products/' + id, data)
export const getTemplate = () => api.get('/products/template', { responseType: 'blob' })
export const previewImport = (formData) => api.post('/products/import/preview', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
export const importProducts = (formData) => api.post('/products/import', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
