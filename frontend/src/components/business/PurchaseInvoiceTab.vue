<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="filters.status" class="form-input w-28" @change="loadList">
        <option value="">全部状态</option>
        <option value="draft">草稿</option>
        <option value="confirmed">已确认</option>
        <option value="cancelled">已作废</option>
      </select>
      <select v-model="filters.supplier_id" class="form-input w-36" @change="loadList">
        <option value="">全部供应商</option>
        <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <input v-model="filters.date_from" type="date" class="form-input w-36" @change="loadList" placeholder="开始日期" />
      <input v-model="filters.date_to" type="date" class="form-input w-36" @change="loadList" placeholder="结束日期" />
      <button @click="openCreateModal" class="btn btn-primary btn-sm ml-auto">新增进项发票</button>
    </div>

    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>发票号</th>
            <th>日期</th>
            <th>供应商</th>
            <th>类型</th>
            <th class="text-right">不含税金额</th>
            <th class="text-right">税额</th>
            <th class="text-right">价税合计</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td colspan="9" class="text-center text-[#86868b] py-8">暂无数据</td>
          </tr>
          <tr v-for="inv in items" :key="inv.id">
            <td class="font-mono text-[12px]">{{ inv.invoice_no }}</td>
            <td>{{ inv.invoice_date }}</td>
            <td>{{ inv.supplier_name || inv.counterparty_name }}</td>
            <td><span :class="inv.invoice_type === 'special' ? 'badge badge-blue' : 'badge badge-gray'">{{ inv.invoice_type === 'special' ? '专票' : '普票' }}</span></td>
            <td class="text-right">{{ inv.amount_without_tax }}</td>
            <td class="text-right">{{ inv.tax_amount }}</td>
            <td class="text-right">{{ inv.total_amount }}</td>
            <td><span :class="statusBadge(inv.status)">{{ statusName(inv.status) }}</span></td>
            <td @click.stop>
              <div class="flex gap-1">
                <button @click="viewDetail(inv)" class="text-[12px] px-2 py-0.5 rounded-full bg-[#e8eaf8] text-[#3634a3]">查看</button>
                <button v-if="inv.status === 'draft'" @click="handleConfirm(inv)" class="text-[12px] px-2 py-0.5 rounded-full bg-[#e8f8ee] text-[#248a3d]">确认</button>
                <button v-if="inv.status === 'draft' || inv.status === 'confirmed'" @click="handleCancel(inv)" class="text-[12px] px-2 py-0.5 rounded-full bg-[#ffeaee] text-[#ff3b30]">作废</button>
              </div>
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

    <!-- 发票详情弹窗 -->
    <Transition name="fade">
      <div v-if="showDetail" class="modal-backdrop" @click.self="showDetail = false">
        <div class="modal" style="max-width: 700px">
          <div class="modal-header">
            <h3>进项发票详情</h3>
            <button @click="showDetail = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div v-if="detailLoading" class="text-center py-8 text-[#86868b]">加载中...</div>
            <template v-else-if="detail">
              <template v-if="!editing">
                <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] mb-4">
                  <div><span class="text-[#86868b]">发票号：</span><span class="font-mono">{{ detail.invoice_no }}</span></div>
                  <div><span class="text-[#86868b]">日期：</span>{{ detail.invoice_date }}</div>
                  <div><span class="text-[#86868b]">供应商：</span>{{ detail.supplier_name }}</div>
                  <div><span class="text-[#86868b]">类型：</span>{{ detail.invoice_type === 'special' ? '专票' : '普票' }}</div>
                  <div><span class="text-[#86868b]">状态：</span><span :class="statusBadge(detail.status)">{{ statusName(detail.status) }}</span></div>
                  <div><span class="text-[#86868b]">关联应付单：</span>{{ detail.payable_bill_no || '-' }}</div>
                  <div class="col-span-2"><span class="text-[#86868b]">备注：</span>{{ detail.remark || '-' }}</div>
                </div>
                <div class="bg-[#f5f5f7] rounded-xl p-3 mb-3">
                  <div class="grid grid-cols-3 gap-2 text-[13px]">
                    <div>不含税：<span class="font-medium">{{ detail.amount_without_tax }}</span></div>
                    <div>税额：<span class="font-medium">{{ detail.tax_amount }}</span></div>
                    <div>价税合计：<span class="font-medium">{{ detail.total_amount }}</span></div>
                  </div>
                </div>
                <div v-if="detail.items && detail.items.length" class="table-wrapper">
                  <table class="data-table">
                    <thead>
                      <tr><th>品名</th><th class="text-right">数量</th><th class="text-right">单价</th><th class="text-right">税率(%)</th><th class="text-right">不含税金额</th><th class="text-right">税额</th><th class="text-right">金额</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="it in detail.items" :key="it.id">
                        <td>{{ it.product_name }}</td>
                        <td class="text-right">{{ it.quantity }}</td>
                        <td class="text-right">{{ it.unit_price }}</td>
                        <td class="text-right">{{ it.tax_rate }}</td>
                        <td class="text-right">{{ it.amount_without_tax }}</td>
                        <td class="text-right">{{ it.tax_amount }}</td>
                        <td class="text-right">{{ it.amount }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
              <template v-else>
                <div class="grid grid-cols-2 gap-3 mb-4">
                  <div><label class="label">发票类型</label><select v-model="editForm.invoice_type" class="form-input"><option value="special">专票</option><option value="normal">普票</option></select></div>
                  <div><label class="label">日期</label><input v-model="editForm.invoice_date" type="date" class="form-input" /></div>
                  <div class="col-span-2"><label class="label">备注</label><input v-model="editForm.remark" class="form-input" /></div>
                </div>
                <div class="table-wrapper mb-3">
                  <table class="data-table">
                    <thead><tr><th>品名</th><th>数量</th><th>单价</th><th>税率(%)</th><th class="text-right">金额</th><th class="text-right">税额</th><th></th></tr></thead>
                    <tbody>
                      <tr v-for="(row, idx) in editForm.items" :key="idx">
                        <td><input v-model="row.product_name" class="form-input w-full text-[12px]" /></td>
                        <td><input v-model.number="row.quantity" type="number" step="1" min="1" class="form-input w-20 text-[12px]" /></td>
                        <td><input v-model.number="row.unit_price" type="number" step="0.01" class="form-input w-24 text-[12px]" /></td>
                        <td><input v-model.number="row.tax_rate" type="number" step="0.01" class="form-input w-20 text-[12px]" /></td>
                        <td class="text-right text-[12px]">{{ editRowAmount(row) }}</td>
                        <td class="text-right text-[12px]">{{ editRowTax(row) }}</td>
                        <td><button @click="editRemoveRow(idx)" class="text-[12px] px-1.5 py-0.5 rounded-full bg-[#ffeaee] text-[#ff3b30]">&times;</button></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <button @click="editAddRow" class="text-[12px] text-[#0071e3] font-medium">+ 添加行</button>
              </template>
            </template>
          </div>
          <div class="modal-footer">
            <template v-if="detail && !editing">
              <button v-if="detail.status === 'draft'" @click="startEdit" class="btn btn-primary btn-sm">编辑</button>
            </template>
            <template v-if="editing">
              <button @click="editing = false" class="btn btn-secondary btn-sm">取消编辑</button>
              <button @click="handleEditSave" :disabled="editSubmitting" class="btn btn-primary btn-sm">保存</button>
            </template>
            <button v-if="!editing" @click="showDetail = false" class="btn btn-secondary btn-sm">关闭</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 新增进项发票弹窗 -->
    <Transition name="fade">
      <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
        <div class="modal" style="max-width: 700px">
          <div class="modal-header">
            <h3>新增进项发票</h3>
            <button @click="showCreate = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div class="grid grid-cols-2 gap-3 mb-4">
              <div>
                <label class="label">供应商 <span class="text-[#ff3b30]">*</span></label>
                <select v-model="form.supplier_id" class="form-input">
                  <option value="">请选择</option>
                  <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
                </select>
              </div>
              <div>
                <label class="label">发票日期</label>
                <input v-model="form.invoice_date" type="date" class="form-input" />
              </div>
              <div>
                <label class="label">发票类型</label>
                <select v-model="form.invoice_type" class="form-input">
                  <option value="special">增值税专用发票</option>
                  <option value="normal">增值税普通发票</option>
                </select>
              </div>
              <div>
                <label class="label">关联应付单ID</label>
                <input v-model="form.payable_bill_id" type="number" class="form-input" placeholder="可选" />
              </div>
              <div class="col-span-2">
                <label class="label">备注</label>
                <input v-model="form.remark" class="form-input" />
              </div>
            </div>

            <!-- 明细行 -->
            <div class="text-[12px] font-semibold text-[#86868b] uppercase tracking-wider mb-2">发票明细</div>
            <div class="table-wrapper mb-3">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>品名</th>
                    <th>数量</th>
                    <th>单价(不含税)</th>
                    <th>税率(%)</th>
                    <th class="text-right">金额</th>
                    <th class="text-right">税额</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, idx) in form.items" :key="idx">
                    <td><input v-model="row.product_name" class="form-input w-full text-[12px]" placeholder="商品名称" /></td>
                    <td><input v-model.number="row.quantity" type="number" step="1" min="1" class="form-input w-20 text-[12px]" /></td>
                    <td><input v-model.number="row.unit_price" type="number" step="0.01" min="0" class="form-input w-24 text-[12px]" /></td>
                    <td><input v-model.number="row.tax_rate" type="number" step="0.01" min="0" max="100" class="form-input w-20 text-[12px]" /></td>
                    <td class="text-right text-[12px]">{{ rowAmount(row) }}</td>
                    <td class="text-right text-[12px]">{{ rowTax(row) }}</td>
                    <td>
                      <button @click="removeRow(idx)" class="text-[12px] px-1.5 py-0.5 rounded-full bg-[#ffeaee] text-[#ff3b30]">&times;</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <button @click="addRow" class="text-[12px] text-[#0071e3] hover:text-[#0077ED] font-medium">+ 添加明细行</button>

            <!-- 合计 -->
            <div class="bg-[#f5f5f7] rounded-xl p-3 mt-3">
              <div class="grid grid-cols-3 gap-2 text-[13px]">
                <div>不含税合计: <span class="font-medium">{{ totalWithoutTax }}</span></div>
                <div>税额合计: <span class="font-medium">{{ totalTax }}</span></div>
                <div>价税合计: <span class="font-medium">{{ totalWithTax }}</span></div>
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
import { ref, computed, onMounted, watch } from 'vue'
import { getInvoices, getInvoice, updateInvoice, createInputInvoice, confirmInvoice, cancelInvoice } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import api from '../../api/index'

const accountingStore = useAccountingStore()
const appStore = useAppStore()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const filters = ref({ status: '', supplier_id: '', date_from: '', date_to: '' })
const suppliers = ref([])
const showCreate = ref(false)
const submitting = ref(false)
const showDetail = ref(false)
const detail = ref(null)
const detailLoading = ref(false)
const editing = ref(false)
const editForm = ref({ invoice_type: '', invoice_date: '', remark: '', items: [] })
const editSubmitting = ref(false)

async function viewDetail(inv) {
  showDetail.value = true
  detailLoading.value = true
  editing.value = false
  try {
    const res = await getInvoice(inv.id)
    detail.value = res.data
  } catch (e) {
    appStore.showToast('加载详情失败', 'error')
    showDetail.value = false
  } finally {
    detailLoading.value = false
  }
}

function startEdit() {
  if (!detail.value) return
  editForm.value = {
    invoice_type: detail.value.invoice_type,
    invoice_date: detail.value.invoice_date,
    remark: detail.value.remark || '',
    items: (detail.value.items || []).map(it => ({
      product_name: it.product_name,
      quantity: it.quantity,
      unit_price: parseFloat(it.unit_price || it.amount_without_tax / it.quantity || 0),
      tax_rate: parseFloat(it.tax_rate || 13),
    })),
  }
  editing.value = true
}

const editRowAmount = (r) => ((r.quantity || 0) * (r.unit_price || 0)).toFixed(2)
const editRowTax = (r) => ((r.quantity || 0) * (r.unit_price || 0) * ((r.tax_rate || 0) / 100)).toFixed(2)

function editAddRow() { editForm.value.items.push({ product_name: '', quantity: 1, unit_price: 0, tax_rate: 13 }) }
function editRemoveRow(idx) { if (editForm.value.items.length > 1) editForm.value.items.splice(idx, 1) }

async function handleEditSave() {
  editSubmitting.value = true
  try {
    await updateInvoice(detail.value.id, editForm.value)
    appStore.showToast('更新成功', 'success')
    showDetail.value = false
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '更新失败', 'error')
  } finally {
    editSubmitting.value = false
  }
}

const emptyRow = () => ({ product_name: '', quantity: 1, unit_price: 0, tax_rate: 13 })
const form = ref({
  supplier_id: '',
  invoice_date: new Date().toISOString().slice(0, 10),
  invoice_type: 'special',
  payable_bill_id: null,
  remark: '',
  items: [emptyRow()],
})

const statusName = (s) => ({ draft: '草稿', confirmed: '已确认', cancelled: '已作废' }[s] || s)
const statusBadge = (s) => ({ draft: 'badge badge-yellow', confirmed: 'badge badge-green', cancelled: 'badge badge-gray' }[s] || 'badge')

const rowAmount = (r) => ((r.quantity || 0) * (r.unit_price || 0)).toFixed(2)
const rowTax = (r) => ((r.quantity || 0) * (r.unit_price || 0) * ((r.tax_rate || 0) / 100)).toFixed(2)

const totalWithoutTax = computed(() => form.value.items.reduce((s, r) => s + (r.quantity || 0) * (r.unit_price || 0), 0).toFixed(2))
const totalTax = computed(() => form.value.items.reduce((s, r) => s + (r.quantity || 0) * (r.unit_price || 0) * ((r.tax_rate || 0) / 100), 0).toFixed(2))
const totalWithTax = computed(() => (parseFloat(totalWithoutTax.value) + parseFloat(totalTax.value)).toFixed(2))

function addRow() { form.value.items.push(emptyRow()) }
function removeRow(idx) { if (form.value.items.length > 1) form.value.items.splice(idx, 1) }

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const params = {
    account_set_id: accountingStore.currentAccountSetId,
    direction: 'input',
    page: page.value,
    page_size: pageSize,
  }
  if (filters.value.status) params.status = filters.value.status
  if (filters.value.supplier_id) params.supplier_id = filters.value.supplier_id
  if (filters.value.date_from) params.date_from = filters.value.date_from
  if (filters.value.date_to) params.date_to = filters.value.date_to
  try {
    const res = await getInvoices(params)
    items.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    items.value = []
    total.value = 0
  }
}

async function loadSuppliers() {
  const res = await api.get('/suppliers', { params: { limit: 1000 } })
  suppliers.value = res.data.items || res.data || []
}

function openCreateModal() {
  form.value = {
    supplier_id: '',
    invoice_date: new Date().toISOString().slice(0, 10),
    invoice_type: 'special',
    payable_bill_id: null,
    remark: '',
    items: [emptyRow()],
  }
  showCreate.value = true
}

async function handleCreate() {
  if (!form.value.supplier_id) {
    appStore.showToast('请选择供应商', 'error')
    return
  }
  if (!form.value.items.some((r) => r.product_name && r.quantity > 0)) {
    appStore.showToast('请至少填写一条有效明细', 'error')
    return
  }
  submitting.value = true
  try {
    const data = {
      account_set_id: accountingStore.currentAccountSetId,
      direction: 'input',
      supplier_id: form.value.supplier_id,
      invoice_date: form.value.invoice_date,
      invoice_type: form.value.invoice_type,
      remark: form.value.remark,
      items: form.value.items.filter((r) => r.product_name),
    }
    if (form.value.payable_bill_id) data.payable_bill_id = form.value.payable_bill_id
    await createInputInvoice(data)
    appStore.showToast('创建成功', 'success')
    showCreate.value = false
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    submitting.value = false
  }
}

async function handleConfirm(inv) {
  if (!await appStore.customConfirm('确认操作', `确认发票 ${inv.invoice_no}？`)) return
  try {
    await confirmInvoice(inv.id)
    appStore.showToast('确认成功', 'success')
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认失败', 'error')
  }
}

async function handleCancel(inv) {
  if (!await appStore.customConfirm('作废确认', `确认作废发票 ${inv.invoice_no}？此操作不可撤回。`)) return
  try {
    await cancelInvoice(inv.id)
    appStore.showToast('已作废', 'success')
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '作废失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => { loadList(); loadSuppliers() })
</script>
