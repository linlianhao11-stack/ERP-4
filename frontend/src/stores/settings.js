import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getUsers, getBackups, getOpLogs, getPaymentMethods, getDisbursementMethods, getCompanyName } from '../api/settings'
import { getSalespersons } from '../api/salespersons'
import { getSnConfigs } from '../api/sn'
import { getProductBrands } from '../api/brands'

export const useSettingsStore = defineStore('settings', () => {
  const users = ref([])
  const salespersons = ref([])
  const paymentMethods = ref([])
  const disbursementMethods = ref([])
  const backups = ref([])
  const opLogs = ref([])
  const snConfigs = ref([])
  const productBrands = ref([])
  const companyName = ref('')

  const loadUsers = async () => {
    try { const { data } = await getUsers(); users.value = data } catch (e) { console.error('加载用户列表失败:', e) }
  }
  const loadSalespersons = async () => {
    try { const { data } = await getSalespersons(); salespersons.value = data } catch (e) { console.error('加载销售员列表失败:', e) }
  }
  const loadPaymentMethods = async () => {
    try { const { data } = await getPaymentMethods(); paymentMethods.value = data } catch (e) { console.error('加载收款方式失败:', e) }
  }
  const loadDisbursementMethods = async () => {
    try { const { data } = await getDisbursementMethods(); disbursementMethods.value = data } catch (e) { console.error('加载付款方式失败:', e) }
  }
  const loadBackups = async () => {
    try { const { data } = await getBackups(); backups.value = data } catch (e) { console.error('加载备份列表失败:', e) }
  }
  const loadOpLogs = async (params) => {
    try { const { data } = await getOpLogs(params); opLogs.value = data } catch (e) { console.error('加载操作日志失败:', e) }
  }
  const loadSnConfigs = async () => {
    try { const { data } = await getSnConfigs(); snConfigs.value = data } catch (e) { console.error('加载SN配置失败:', e) }
  }
  const loadProductBrands = async () => {
    try { const { data } = await getProductBrands(); productBrands.value = data } catch (e) { console.error('加载品牌列表失败:', e) }
  }
  const loadCompanyName = async () => {
    try { const { data } = await getCompanyName(); companyName.value = data.value || '' } catch (e) { console.error('加载公司名称失败:', e) }
  }

  return {
    users, salespersons, paymentMethods, disbursementMethods, backups, opLogs, snConfigs, productBrands, companyName,
    loadUsers, loadSalespersons, loadPaymentMethods, loadDisbursementMethods, loadBackups, loadOpLogs,
    loadSnConfigs, loadProductBrands, loadCompanyName
  }
})
