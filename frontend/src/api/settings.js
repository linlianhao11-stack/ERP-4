import api from './index'

export const getUsers = () => api.get('/users')
export const createUser = (data) => api.post('/users', data)
export const updateUser = (id, data) => api.put('/users/' + id, data)
export const toggleUser = (id) => api.post('/users/' + id + '/toggle')

export const getBackups = () => api.get('/backups')
export const createBackup = () => api.post('/backup')
export const downloadBackup = (filename) => api.get('/backups/' + encodeURIComponent(filename), { responseType: 'blob' })
export const deleteBackup = (filename) => api.delete('/backups/' + encodeURIComponent(filename))
export const restoreBackup = (filename) => api.post('/backups/' + encodeURIComponent(filename) + '/restore')
export const uploadRestoreBackup = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/backups/upload-restore', formData)
}

export const getOpLogs = (params) => api.get('/operation-logs', { params })

export const getCompanyName = () => api.get('/settings/company_name')
export const saveCompanyName = (data) => api.put('/settings/company_name', data)

export const getPaymentMethods = (params) => api.get('/payment-methods', { params })
export const createPaymentMethod = (data) => api.post('/payment-methods', data)
export const getPaymentMethodsByAccountSet = (accountSetId) => api.get('/payment-methods', { params: { account_set_id: accountSetId } })
export const updatePaymentMethod = (id, data) => api.put('/payment-methods/' + id, data)
export const deletePaymentMethod = (id) => api.delete('/payment-methods/' + id)

export const getDisbursementMethods = (params) => api.get('/disbursement-methods', { params })
export const createDisbursementMethod = (data) => api.post('/disbursement-methods', data)
export const getDisbursementMethodsByAccountSet = (accountSetId) => api.get('/disbursement-methods', { params: { account_set_id: accountSetId } })
export const updateDisbursementMethod = (id, data) => api.put('/disbursement-methods/' + id, data)
export const deleteDisbursementMethod = (id) => api.delete('/disbursement-methods/' + id)
