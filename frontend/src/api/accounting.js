import api from './index'

// === 账套 ===
export const getAccountSets = () => api.get('/account-sets')
export const getAccountSet = (id) => api.get(`/account-sets/${id}`)
export const createAccountSet = (data) => api.post('/account-sets', data)
export const updateAccountSet = (id, data) => api.put(`/account-sets/${id}`, data)

// === 科目 ===
export const getChartOfAccounts = (accountSetId) =>
  api.get('/chart-of-accounts', { params: { account_set_id: accountSetId } })
export const createChartOfAccount = (accountSetId, data) =>
  api.post('/chart-of-accounts', data, { params: { account_set_id: accountSetId } })
export const updateChartOfAccount = (id, data) =>
  api.put(`/chart-of-accounts/${id}`, data)
export const deleteChartOfAccount = (id) =>
  api.delete(`/chart-of-accounts/${id}`)

// === 会计期间 ===
export const getAccountingPeriods = (accountSetId, year) =>
  api.get('/accounting-periods', { params: { account_set_id: accountSetId, year } })
export const initYearPeriods = (accountSetId, year) =>
  api.post('/accounting-periods/init-year', null, { params: { account_set_id: accountSetId, year } })

// === 凭证 ===
export const getVouchers = (params) => api.get('/vouchers', { params })
export const getVoucher = (id) => api.get(`/vouchers/${id}`)
export const createVoucher = (accountSetId, data) =>
  api.post('/vouchers', data, { params: { account_set_id: accountSetId } })
export const updateVoucher = (id, data) => api.put(`/vouchers/${id}`, data)
export const deleteVoucher = (id) => api.delete(`/vouchers/${id}`)
export const submitVoucher = (id) => api.post(`/vouchers/${id}/submit`)
export const approveVoucher = (id) => api.post(`/vouchers/${id}/approve`)
export const rejectVoucher = (id) => api.post(`/vouchers/${id}/reject`)
export const postVoucher = (id) => api.post(`/vouchers/${id}/post`)
export const unpostVoucher = (id) => api.post(`/vouchers/${id}/unpost`)
