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
          <button v-if="hasPermission('accounting_ar_edit')" @click="openCreate" class="btn btn-primary btn-sm">新增退款单</button>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-[13px]">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2">单号</th>
              <th class="px-3 py-2">日期</th>
              <th class="px-3 py-2">客户</th>
              <th class="px-3 py-2 text-right">退款金额</th>
              <th class="px-3 py-2">原收款单</th>
              <th class="px-3 py-2">退款原因</th>
              <th class="px-3 py-2">状态</th>
              <th class="px-3 py-2">凭证号</th>
              <th class="px-3 py-2">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!items.length">
              <td colspan="9">
                <div class="text-center py-12 text-muted">
                  <div class="text-3xl mb-3">📋</div>
                  <p class="text-sm font-medium mb-1">暂无收款退款数据</p>
                  <p class="text-xs text-muted">点击"手动新增"按钮创建第一条记录</p>
                </div>
              </td>
            </tr>
            <tr v-for="b in items" :key="b.id" class="hover:bg-elevated">
              <td class="px-3 py-2 font-mono text-[12px]"><span class="max-w-48 truncate inline-block align-bottom" :title="b.bill_no">{{ b.bill_no }}</span></td>
              <td class="px-3 py-2">{{ b.refund_date }}</td>
              <td class="px-3 py-2">{{ b.customer_name }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(b.amount) }}</td>
              <td class="px-3 py-2 font-mono text-[12px]"><span class="max-w-48 truncate inline-block align-bottom" :title="b.original_receipt_no">{{ b.original_receipt_no || '-' }}</span></td>
              <td class="px-3 py-2 max-w-[120px] truncate">{{ b.reason || '-' }}</td>
              <td class="px-3 py-2"><span :class="b.status === 'confirmed' ? 'badge badge-green' : 'badge badge-gray'">{{ b.status === 'confirmed' ? '已确认' : '草稿' }}</span></td>
              <td class="px-3 py-2 font-mono text-[12px]"><span class="max-w-48 truncate inline-block align-bottom" :title="b.voucher_no">{{ b.voucher_no || '-' }}</span></td>
              <td class="px-3 py-2" @click.stop>
                <button v-if="b.status === 'draft' && hasPermission('accounting_ar_confirm')" @click="confirmBill(b)" class="text-xs px-2.5 py-1 rounded-md bg-purple-subtle text-purple-emphasis font-medium">确认</button>
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
            <h3>新增收款退款单</h3>
            <button @click="showCreate = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="label" for="ar-refund-customer">客户</label>
                <select id="ar-refund-customer" v-model="form.customer_id" class="input text-sm">
                  <option value="">请选择</option>
                  <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </div>
              <div>
                <label class="label" for="ar-refund-date">退款日期</label>
                <input id="ar-refund-date" v-model="form.refund_date" type="date" class="input text-sm" />
              </div>
              <div>
                <label class="label" for="ar-refund-original-receipt-id">原收款单ID</label>
                <input id="ar-refund-original-receipt-id" v-model="form.original_receipt_id" type="number" class="input text-sm" />
              </div>
              <div>
                <label class="label" for="ar-refund-amount">退款金额</label>
                <input id="ar-refund-amount" v-model="form.amount" type="number" step="0.01" class="input text-sm" />
              </div>
              <div class="col-span-2">
                <label class="label" for="ar-refund-reason">退款原因</label>
                <input id="ar-refund-reason" v-model="form.reason" class="input text-sm" />
              </div>
              <div class="col-span-2">
                <label class="label" for="ar-refund-remark">备注</label>
                <input id="ar-refund-remark" v-model="form.remark" class="input text-sm" />
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showCreate = false" class="btn btn-secondary btn-sm">取消</button>
            <button @click="handleCreate" :disabled="submitting" class="btn btn-primary btn-sm">{{ submitting ? '提交中...' : '确定' }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'

const emit = defineEmits(['data-changed'])
import PageToolbar from '../common/PageToolbar.vue'
import { getReceiptRefundBills, createReceiptRefundBill, confirmReceiptRefundBill } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { usePermission } from '../../composables/usePermission'
import { useFormat } from '../../composables/useFormat'
import api from '../../api/index'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()
const { fmtMoney } = useFormat()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const filters = ref({ status: '' })
const showCreate = ref(false)
const submitting = ref(false)
const customers = ref([])
const form = ref({ customer_id: '', refund_date: new Date().toISOString().slice(0, 10), original_receipt_id: '', amount: '', reason: '', remark: '' })

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const params = { account_set_id: accountingStore.currentAccountSetId, page: page.value, page_size: pageSize }
  if (filters.value.status) params.status = filters.value.status
  const res = await getReceiptRefundBills(params)
  items.value = res.data.items
  total.value = res.data.total
}

async function loadCustomers() {
  const res = await api.get('/customers', { params: { limit: 1000 } })
  customers.value = res.data.items || res.data || []
}

function openCreate() {
  form.value = { customer_id: '', refund_date: new Date().toISOString().slice(0, 10), original_receipt_id: '', amount: '', reason: '', remark: '' }
  showCreate.value = true
}

async function handleCreate() {
  if (submitting.value) return
  if (!form.value.customer_id || !form.value.original_receipt_id || !form.value.amount) {
    appStore.showToast('请填写客户、原收款单和退款金额', 'error')
    return
  }
  submitting.value = true
  try {
    await createReceiptRefundBill(accountingStore.currentAccountSetId, form.value)
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
  if (!await appStore.customConfirm('确认操作', `确认退款单 ${b.bill_no}？`)) return
  try {
    await confirmReceiptRefundBill(b.id)
    appStore.showToast('确认成功', 'success')
    loadList()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => { loadList(); loadCustomers() })
</script>
