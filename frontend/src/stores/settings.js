import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getUsers, getBackups, getOpLogs, getPaymentMethods, getDisbursementMethods, getCompanyName } from '../api/settings'
import { getEmployees } from '../api/employees'
import { getSnConfigs } from '../api/sn'
import { getProductBrands } from '../api/brands'
import { createLazyLoader } from '../utils/createLazyLoader'

export const useSettingsStore = defineStore('settings', () => {
  const users = ref([])
  const employees = ref([])
  const paymentMethods = ref([])
  const disbursementMethods = ref([])
  const backups = ref([])
  const opLogs = ref([])
  const snConfigs = ref([])
  const productBrands = ref([])
  const companyName = ref('')

  /**
   * 确保常用引用数据已加载（employees、companyName）。
   * 多次调用只会触发一次请求，适合在各页面入口调用。
   */
  const { ensureLoaded } = createLazyLoader(
    () => Promise.all([loadEmployees(), loadCompanyName()])
  )

  const loadUsers = async () => {
    try { const { data } = await getUsers(); users.value = data.items || data } catch (e) { console.error('加载用户列表失败:', e) }
  }
  const loadEmployees = async () => {
    try { const { data } = await getEmployees(); employees.value = data.items || data } catch (e) { console.error('加载员工列表失败:', e) }
  }
  const loadPaymentMethods = async (accountSetId) => {
    try {
      const params = accountSetId ? { account_set_id: accountSetId } : undefined
      const { data } = await getPaymentMethods(params)
      paymentMethods.value = data.items || data
    } catch (e) { console.error('加载收款方式失败:', e) }
  }
  const loadDisbursementMethods = async (accountSetId) => {
    try {
      const params = accountSetId ? { account_set_id: accountSetId } : undefined
      const { data } = await getDisbursementMethods(params)
      disbursementMethods.value = data.items || data
    } catch (e) { console.error('加载付款方式失败:', e) }
  }
  const loadBackups = async () => {
    try { const { data } = await getBackups(); backups.value = data.items || data } catch (e) { console.error('加载备份列表失败:', e) }
  }
  const loadOpLogs = async (params) => {
    try { const { data } = await getOpLogs(params); opLogs.value = data.items || data } catch (e) { console.error('加载操作日志失败:', e) }
  }
  const loadSnConfigs = async () => {
    try { const { data } = await getSnConfigs(); snConfigs.value = data.items || data } catch (e) { console.error('加载SN配置失败:', e) }
  }
  const loadProductBrands = async () => {
    try { const { data } = await getProductBrands(); productBrands.value = data.items || data } catch (e) { console.error('加载品牌列表失败:', e) }
  }
  const loadCompanyName = async () => {
    try { const { data } = await getCompanyName(); companyName.value = data.value || '' } catch (e) { console.error('加载公司名称失败:', e) }
  }

  return {
    users, employees, paymentMethods, disbursementMethods, backups, opLogs, snConfigs, productBrands, companyName,
    ensureLoaded, loadUsers, loadEmployees, loadPaymentMethods, loadDisbursementMethods, loadBackups, loadOpLogs,
    loadSnConfigs, loadProductBrands, loadCompanyName
  }
})
