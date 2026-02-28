<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="filters.status" class="form-input w-28" @change="loadList">
        <option value="">全部状态</option>
        <option value="draft">草稿</option>
        <option value="confirmed">已确认</option>
      </select>
      <button v-if="hasPermission('accounting_ar_edit')" @click="openCreate" class="btn btn-primary btn-sm ml-auto">新增退款单</button>
    </div>

    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>单号</th>
            <th>日期</th>
            <th>客户</th>
            <th class="text-right">退款金额</th>
            <th>原收款单</th>
            <th>退款原因</th>
            <th>状态</th>
            <th>凭证号</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td colspan="9" class="text-center text-[#86868b] py-8">暂无数据</td>
          </tr>
          <tr v-for="b in items" :key="b.id">
            <td class="font-mono text-[12px]">{{ b.bill_no }}</td>
            <td>{{ b.refund_date }}</td>
            <td>{{ b.customer_name }}</td>
            <td class="text-right">{{ b.amount }}</td>
            <td class="font-mono text-[12px]">{{ b.original_receipt_no || '-' }}</td>
            <td class="max-w-[120px] truncate">{{ b.reason || '-' }}</td>
            <td><span :class="b.status === 'confirmed' ? 'badge badge-green' : 'badge badge-gray'">{{ b.status === 'confirmed' ? '已确认' : '草稿' }}</span></td>
            <td class="font-mono text-[12px]">{{ b.voucher_no || '-' }}</td>
            <td @click.stop>
              <button v-if="b.status === 'draft' && hasPermission('accounting_ar_confirm')" @click="confirmBill(b)" class="text-[12px] px-2 py-0.5 rounded-full bg-[#e8f8ee] text-[#248a3d]">确认</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-[#86868b] leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>

    <!-- 新增弹窗 -->
    <Transition name="fade">
      <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
        <div class="modal" style="max-width: 500px">
          <div class="modal-header">
            <h3>新增收款退款单</h3>
            <button @click="showCreate = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="form-label">客户</label>
                <select v-model="form.customer_id" class="form-input">
                  <option value="">请选择</option>
                  <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </div>
              <div>
                <label class="form-label">退款日期</label>
                <input v-model="form.refund_date" type="date" class="form-input" />
              </div>
              <div>
                <label class="form-label">原收款单ID</label>
                <input v-model="form.original_receipt_id" type="number" class="form-input" />
              </div>
              <div>
                <label class="form-label">退款金额</label>
                <input v-model="form.amount" type="number" step="0.01" class="form-input" />
              </div>
              <div class="col-span-2">
                <label class="form-label">退款原因</label>
                <input v-model="form.reason" class="form-input" />
              </div>
              <div class="col-span-2">
                <label class="form-label">备注</label>
                <input v-model="form.remark" class="form-input" />
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button @click="showCreate = false" class="btn btn-secondary btn-sm">取消</button>
            <button @click="handleCreate" :disabled="submitting" class="btn btn-primary btn-sm">保存</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { getReceiptRefundBills, createReceiptRefundBill, confirmReceiptRefundBill } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { usePermission } from '../../composables/usePermission'
import api from '../../api/index'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { hasPermission } = usePermission()

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
  if (!confirm(`确认退款单 ${b.bill_no}？`)) return
  try {
    await confirmReceiptRefundBill(b.id)
    appStore.showToast('确认成功', 'success')
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => { loadList(); loadCustomers() })
</script>
