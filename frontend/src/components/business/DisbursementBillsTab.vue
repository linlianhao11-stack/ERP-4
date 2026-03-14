<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="filters.status" class="toolbar-select" @change="loadList">
            <option value="">全部状态</option>
            <option value="draft">草稿</option>
            <option value="confirmed">已确认</option>
          </select>
        </template>
        <template #actions>
          <button v-if="hasPermission('accounting_ap_edit')" @click="openCreate" class="btn btn-primary btn-sm">新增付款单</button>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-[13px]">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2">单号</th>
              <th class="px-3 py-2">日期</th>
              <th class="px-3 py-2">供应商</th>
              <th class="px-3 py-2 text-right">金额</th>
              <th class="px-3 py-2">付款方式</th>
              <th class="px-3 py-2">状态</th>
              <th class="px-3 py-2">备注</th>
              <th class="px-3 py-2">凭证号</th>
              <th class="px-3 py-2">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!items.length">
              <td colspan="9">
                <div class="text-center py-12 text-muted">
                  <div class="text-3xl mb-3">📋</div>
                  <p class="text-sm font-medium mb-1">暂无付款单数据</p>
                  <p class="text-xs text-muted">点击"手动新增"按钮创建第一条记录</p>
                </div>
              </td>
            </tr>
            <tr v-for="b in items" :key="b.id" class="hover:bg-elevated">
              <td class="px-3 py-2 font-mono text-[12px]">
                <span class="max-w-48 truncate inline-block align-bottom" :title="b.bill_no">{{ b.bill_no }}</span>
                <span v-if="b.bill_type === 'return_refund'" class="ml-1 px-1.5 py-0.5 text-xs bg-error/10 text-error rounded">退款</span>
              </td>
              <td class="px-3 py-2">{{ b.disbursement_date }}</td>
              <td class="px-3 py-2">{{ b.supplier_name }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(b.amount) }}</td>
              <td class="px-3 py-2">{{ b.disbursement_method }}</td>
              <td class="px-3 py-2"><span :class="b.status === 'confirmed' ? 'badge badge-green' : 'badge badge-gray'">{{ b.status === 'confirmed' ? '已确认' : '草稿' }}</span></td>
              <td class="px-3 py-2 text-xs text-muted max-w-48 truncate" :title="b.remark">{{ b.remark || '-' }}</td>
              <td class="px-3 py-2 font-mono text-[12px] max-w-48 truncate" :title="b.voucher_no">{{ b.voucher_no || '-' }}</td>
              <td class="px-3 py-2" @click.stop>
                <button v-if="b.status === 'draft' && hasPermission('accounting_ap_confirm')" @click="confirmBill(b)" class="text-xs px-2.5 py-1 rounded-md bg-success-subtle text-success-emphasis font-medium">确认</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>

    <!-- 新增弹窗 -->
    <Transition name="fade">
      <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
        <div class="modal max-w-lg">
          <div class="modal-header">
            <h3>新增付款单</h3>
            <button @click="showCreate = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="label" for="ap-disb-supplier">供应商</label>
                <select id="ap-disb-supplier" v-model="form.supplier_id" class="input text-sm">
                  <option value="">请选择</option>
                  <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
                </select>
              </div>
              <div>
                <label class="label" for="ap-disb-date">付款日期</label>
                <input id="ap-disb-date" v-model="form.disbursement_date" type="date" class="input text-sm" />
              </div>
              <div>
                <label class="label" for="ap-disb-amount">金额</label>
                <input id="ap-disb-amount" v-model="form.amount" type="number" step="0.01" class="input text-sm" />
              </div>
              <div>
                <label class="label" for="ap-disb-method">付款方式</label>
                <select id="ap-disb-method" v-model="form.disbursement_method" class="input text-sm">
                  <option value="">请选择</option>
                  <option v-for="m in filteredDisbursementMethods" :key="m.id" :value="m.name">{{ m.name }}</option>
                </select>
              </div>
              <div>
                <label class="label" for="ap-disb-payable-id">关联应付单ID</label>
                <input id="ap-disb-payable-id" v-model="form.payable_bill_id" type="number" class="input text-sm" placeholder="可选" />
              </div>
              <div class="col-span-2">
                <label class="label" for="ap-disb-remark">备注</label>
                <input id="ap-disb-remark" v-model="form.remark" class="input text-sm" />
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showCreate = false" class="btn btn-secondary btn-sm">取消</button>
            <button @click="handleCreate" :disabled="submitting" class="btn btn-primary btn-sm">{{ submitting ? '保存中...' : '保存' }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import PageToolbar from '../common/PageToolbar.vue'
import { getDisbursementBills, createDisbursementBill, confirmDisbursementBill } from '../../api/accounting'
import { getDisbursementMethods as getDisbursementMethodsApi } from '../../api/settings'
import { useAccountingStore } from '../../stores/accounting'
import { useSettingsStore } from '../../stores/settings'
import { useAppStore } from '../../stores/app'
import { usePermission } from '../../composables/usePermission'
import { useFormat } from '../../composables/useFormat'
import api from '../../api/index'

const accountingStore = useAccountingStore()
const settingsStore = useSettingsStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()
const { fmtMoney } = useFormat()

// 按当前账套过滤的付款方式
const accountSetDisbursementMethods = ref([])
async function loadAccountSetDisbursementMethods() {
  if (!accountingStore.currentAccountSetId) {
    accountSetDisbursementMethods.value = settingsStore.disbursementMethods
    return
  }
  try {
    const { data } = await getDisbursementMethodsApi({ account_set_id: accountingStore.currentAccountSetId })
    accountSetDisbursementMethods.value = data
  } catch {
    accountSetDisbursementMethods.value = settingsStore.disbursementMethods
  }
}
const filteredDisbursementMethods = computed(() =>
  accountSetDisbursementMethods.value.length ? accountSetDisbursementMethods.value : settingsStore.disbursementMethods
)

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const filters = ref({ status: '' })
const showCreate = ref(false)
const submitting = ref(false)
const suppliers = ref([])
const form = ref({ supplier_id: '', disbursement_date: new Date().toISOString().slice(0, 10), amount: '', disbursement_method: '', payable_bill_id: null, remark: '' })

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const params = { account_set_id: accountingStore.currentAccountSetId, page: page.value, page_size: pageSize }
  if (filters.value.status) params.status = filters.value.status
  const res = await getDisbursementBills(params)
  items.value = res.data.items
  total.value = res.data.total
}

async function loadSuppliers() {
  const res = await api.get('/suppliers', { params: { limit: 1000 } })
  suppliers.value = res.data.items || res.data || []
}

function openCreate() {
  form.value = { supplier_id: '', disbursement_date: new Date().toISOString().slice(0, 10), amount: '', disbursement_method: '', payable_bill_id: null, remark: '' }
  loadAccountSetDisbursementMethods()
  showCreate.value = true
}

async function handleCreate() {
  if (!form.value.supplier_id || !form.value.amount || !form.value.disbursement_method) {
    appStore.showToast('请填写供应商、金额和付款方式', 'error')
    return
  }
  submitting.value = true
  try {
    const data = { ...form.value }
    if (!data.payable_bill_id) delete data.payable_bill_id
    await createDisbursementBill(accountingStore.currentAccountSetId, data)
    appStore.showToast('创建成功', 'success')
    showCreate.value = false
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    submitting.value = false
  }
}

async function confirmBill(b) {
  if (!await appStore.customConfirm('确认操作', `确认付款单 ${b.bill_no}？`)) return
  try {
    await confirmDisbursementBill(b.id)
    appStore.showToast('确认成功', 'success')
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => {
  page.value = 1
  loadList()
  loadAccountSetDisbursementMethods()
})
onMounted(() => {
  loadList()
  loadSuppliers()
  loadAccountSetDisbursementMethods()
})
</script>
