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

// === 账簿查询 ===
export const getGeneralLedger = (params) =>
  api.get('/ledgers/general-ledger', { params })
export const getDetailLedger = (params) =>
  api.get('/ledgers/detail-ledger', { params })
export const getTrialBalance = (params) =>
  api.get('/ledgers/trial-balance', { params })
export const exportGeneralLedger = (params) =>
  api.get('/ledgers/general-ledger/export', { params, responseType: 'blob' })
export const exportDetailLedger = (params) =>
  api.get('/ledgers/detail-ledger/export', { params, responseType: 'blob' })
export const exportTrialBalance = (params) =>
  api.get('/ledgers/trial-balance/export', { params, responseType: 'blob' })

// === 应收管理 ===
export const getReceivableBills = (params) => api.get('/receivables/receivable-bills', { params })
export const getReceivableBill = (id) => api.get(`/receivables/receivable-bills/${id}`)
export const createReceivableBill = (accountSetId, data) =>
  api.post('/receivables/receivable-bills', data, { params: { account_set_id: accountSetId } })
export const cancelReceivableBill = (id) => api.post(`/receivables/receivable-bills/${id}/cancel`)

export const getReceiptBills = (params) => api.get('/receivables/receipt-bills', { params })
export const createReceiptBill = (accountSetId, data) =>
  api.post('/receivables/receipt-bills', data, { params: { account_set_id: accountSetId } })
export const confirmReceiptBill = (id) => api.post(`/receivables/receipt-bills/${id}/confirm`)

export const getReceiptRefundBills = (params) => api.get('/receivables/receipt-refund-bills', { params })
export const createReceiptRefundBill = (accountSetId, data) =>
  api.post('/receivables/receipt-refund-bills', data, { params: { account_set_id: accountSetId } })
export const confirmReceiptRefundBill = (id) => api.post(`/receivables/receipt-refund-bills/${id}/confirm`)

export const getReceivableWriteOffs = (params) => api.get('/receivables/receivable-write-offs', { params })
export const createReceivableWriteOff = (accountSetId, data) =>
  api.post('/receivables/receivable-write-offs', data, { params: { account_set_id: accountSetId } })
export const confirmReceivableWriteOff = (id) => api.post(`/receivables/receivable-write-offs/${id}/confirm`)

export const generateArVouchers = (accountSetId, periodName) =>
  api.post('/receivables/generate-ar-vouchers', null, { params: { account_set_id: accountSetId, period_name: periodName } })

// === 应付管理 ===
export const getPayableBills = (params) => api.get('/payables/payable-bills', { params })
export const getPayableBill = (id) => api.get(`/payables/payable-bills/${id}`)
export const createPayableBill = (accountSetId, data) =>
  api.post('/payables/payable-bills', data, { params: { account_set_id: accountSetId } })
export const cancelPayableBill = (id) => api.post(`/payables/payable-bills/${id}/cancel`)

export const getDisbursementBills = (params) => api.get('/payables/disbursement-bills', { params })
export const createDisbursementBill = (accountSetId, data) =>
  api.post('/payables/disbursement-bills', data, { params: { account_set_id: accountSetId } })
export const confirmDisbursementBill = (id) => api.post(`/payables/disbursement-bills/${id}/confirm`)

export const getDisbursementRefundBills = (params) => api.get('/payables/disbursement-refund-bills', { params })
export const createDisbursementRefundBill = (accountSetId, data) =>
  api.post('/payables/disbursement-refund-bills', data, { params: { account_set_id: accountSetId } })
export const confirmDisbursementRefundBill = (id) => api.post(`/payables/disbursement-refund-bills/${id}/confirm`)

export const generateApVouchers = (accountSetId, periodName) =>
  api.post('/payables/generate-ap-vouchers', null, { params: { account_set_id: accountSetId, period_name: periodName } })
