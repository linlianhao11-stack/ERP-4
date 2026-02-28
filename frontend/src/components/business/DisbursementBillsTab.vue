<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="filters.status" class="form-input w-28" @change="loadList">
        <option value="">全部状态</option>
        <option value="draft">草稿</option>
        <option value="confirmed">已确认</option>
      </select>
      <button v-if="hasPermission('accounting_ap_edit')" @click="openCreate" class="btn btn-primary btn-sm ml-auto">新增付款单</button>
    </div>

    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>单号</th>
            <th>日期</th>
            <th>供应商</th>
            <th class="text-right">金额</th>
            <th>付款方式</th>
            <th>状态</th>
            <th>凭证号</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td colspan="8" class="text-center text-[#86868b] py-8">暂无数据</td>
          </tr>
          <tr v-for="b in items" :key="b.id">
            <td class="font-mono text-[12px]">{{ b.bill_no }}</td>
            <td>{{ b.disbursement_date }}</td>
            <td>{{ b.supplier_name }}</td>
            <td class="text-right">{{ b.amount }}</td>
            <td>{{ b.disbursement_method }}</td>
            <td><span :class="b.status === 'confirmed' ? 'badge badge-green' : 'badge badge-gray'">{{ b.status === 'confirmed' ? '已确认' : '草稿' }}</span></td>
            <td class="font-mono text-[12px]">{{ b.voucher_no || '-' }}</td>
            <td @click.stop>
              <button v-if="b.status === 'draft' && hasPermission('accounting_ap_confirm')" @click="confirmBill(b)" class="text-[12px] px-2 py-0.5 rounded-full bg-[#e8f8ee] text-[#248a3d]">确认</button>
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
            <h3>新增付款单</h3>
            <button @click="showCreate = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="form-label">供应商</label>
                <select v-model="form.supplier_id" class="form-input">
                  <option value="">请选择</option>
                  <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
                </select>
              </div>
              <div>
                <label class="form-label">付款日期</label>
                <input v-model="form.disbursement_date" type="date" class="form-input" />
              </div>
              <div>
                <label class="form-label">金额</label>
                <input v-model="form.amount" type="number" step="0.01" class="form-input" />
              </div>
              <div>
                <label class="form-label">付款方式</label>
                <input v-model="form.disbursement_method" class="form-input" placeholder="如：银行转账" />
              </div>
              <div>
                <label class="form-label">关联应付单ID</label>
                <input v-model="form.payable_bill_id" type="number" class="form-input" placeholder="可选" />
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
import { getDisbursementBills, createDisbursementBill, confirmDisbursementBill } from '../../api/accounting'
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
  if (!confirm(`确认付款单 ${b.bill_no}？`)) return
  try {
    await confirmDisbursementBill(b.id)
    appStore.showToast('确认成功', 'success')
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => { loadList(); loadSuppliers() })
</script>
