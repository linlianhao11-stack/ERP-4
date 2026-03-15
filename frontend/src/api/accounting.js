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

export const getSalesReturns = (params) => api.get('/receivables/sales-returns', { params })

export const generateArVouchers = (accountSetId, periodNames) =>
  api.post('/receivables/generate-ar-vouchers', { period_names: periodNames }, { params: { account_set_id: accountSetId } })

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

export const getPurchaseReturnsForAP = (params) => api.get('/payables/purchase-returns', { params })

export const generateApVouchers = (accountSetId, periodNames) =>
  api.post('/payables/generate-ap-vouchers', { period_names: periodNames }, { params: { account_set_id: accountSetId } })

// ========== 出入库单 ==========
export const getSalesDeliveries = (params) => api.get('/sales-delivery', { params })
export const getSalesDelivery = (id) => api.get(`/sales-delivery/${id}`)
export const getSalesDeliveryPdf = (id) => api.get(`/sales-delivery/${id}/pdf`, { responseType: 'blob' })
export const batchSalesDeliveryPdf = (ids) => api.post('/sales-delivery/batch-pdf', { ids }, { responseType: 'blob' })

export const getPurchaseReceipts = (params) => api.get('/purchase-receipt', { params })
export const getPurchaseReceipt = (id) => api.get(`/purchase-receipt/${id}`)
export const getPurchaseReceiptPdf = (id) => api.get(`/purchase-receipt/${id}/pdf`, { responseType: 'blob' })
export const batchPurchaseReceiptPdf = (ids) => api.post('/purchase-receipt/batch-pdf', { ids }, { responseType: 'blob' })

// ========== 发票管理 ==========
export const getInvoices = (params) => api.get('/invoices', { params })
export const getInvoice = (id) => api.get(`/invoices/${id}`)
export const pushInvoiceFromReceivable = (data) => {
  const { account_set_id, ...body } = data
  return api.post('/invoices/from-receivable', body, { params: { account_set_id } })
}
export const createInputInvoice = (data) => api.post('/invoices', data)
export const updateInvoice = (id, data) => api.put(`/invoices/${id}`, data)
export const confirmInvoice = (id) => api.post(`/invoices/${id}/confirm`)
export const cancelInvoice = (id) => api.post(`/invoices/${id}/cancel`)

// ========== 凭证 PDF ==========
export const getVoucherPdf = (id) => api.get(`/vouchers/${id}/pdf`, { responseType: 'blob' })
export const batchVoucherPdf = (ids) => api.post('/vouchers/batch-pdf', { ids }, { responseType: 'blob' })

// ========== 期末处理 ==========
export const previewCarryForward = (accountSetId, periodName) =>
  api.post('/period-end/carry-forward/preview', null, { params: { account_set_id: accountSetId, period_name: periodName } })
export const executeCarryForward = (accountSetId, periodName) =>
  api.post('/period-end/carry-forward', null, { params: { account_set_id: accountSetId, period_name: periodName } })
export const closeCheck = (accountSetId, periodName) =>
  api.post('/period-end/close-check', null, { params: { account_set_id: accountSetId, period_name: periodName } })
export const closePeriod = (accountSetId, periodName) =>
  api.post('/period-end/close', null, { params: { account_set_id: accountSetId, period_name: periodName } })
export const reopenPeriod = (accountSetId, periodName) =>
  api.post('/period-end/reopen', null, { params: { account_set_id: accountSetId, period_name: periodName } })
export const yearClose = (accountSetId, year) =>
  api.post('/period-end/year-close', null, { params: { account_set_id: accountSetId, year } })

// ========== 财务报表 ==========
export const getBalanceSheet = (params) => api.get('/financial-reports/balance-sheet', { params })
export const getIncomeStatement = (params) => api.get('/financial-reports/income-statement', { params })
export const getCashFlow = (params) => api.get('/financial-reports/cash-flow', { params })
export const exportBalanceSheet = (params) =>
  api.get('/financial-reports/balance-sheet/export', { params, responseType: 'blob' })
export const exportIncomeStatement = (params) =>
  api.get('/financial-reports/income-statement/export', { params, responseType: 'blob' })
export const exportCashFlow = (params) =>
  api.get('/financial-reports/cash-flow/export', { params, responseType: 'blob' })

// ========== 发票 PDF 管理 ==========
export const uploadInvoicePdf = (invoiceId, file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post(`/invoices/${invoiceId}/upload-pdf`, formData)
}

export const getInvoicePdfUrl = (invoiceId, index) =>
  `/api/invoices/${invoiceId}/pdf/${index}`

export const deleteInvoicePdf = (invoiceId, index) =>
  api.delete(`/invoices/${invoiceId}/pdf/${index}`)

export const getNextVoucherNumber = (params) => api.get('/vouchers/next-number', { params })

// ========== 批量操作 ==========
export const batchSubmitVouchers = (ids) => api.post('/vouchers/batch-submit', { voucher_ids: ids })
export const batchApproveVouchers = (ids) => api.post('/vouchers/batch-approve', { voucher_ids: ids })
export const batchPostVouchers = (ids) => api.post('/vouchers/batch-post', { voucher_ids: ids })

// ========== 凭证分录 ==========
export const getVoucherEntries = (params) => api.get('/vouchers/entries', { params })
export const exportVoucherEntries = (params) => api.get('/vouchers/entries/export', { params, responseType: 'blob' })
