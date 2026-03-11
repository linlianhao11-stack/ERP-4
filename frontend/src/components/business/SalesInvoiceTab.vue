<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="filters.status" class="toolbar-select" @change="loadList">
            <option value="">全部状态</option>
            <option value="draft">草稿</option>
            <option value="confirmed">已确认</option>
            <option value="cancelled">已作废</option>
          </select>
          <select v-model="filters.customer_id" class="toolbar-select" @change="loadList">
            <option value="">全部客户</option>
            <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <input v-model="filters.date_from" type="date" class="toolbar-select" @change="loadList" placeholder="开始日期" />
          <input v-model="filters.date_to" type="date" class="toolbar-select" @change="loadList" placeholder="结束日期" />
        </template>
        <template #actions>
          <button @click="openPushModal" class="btn btn-primary btn-sm">从应收单推送</button>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-[13px]">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2">发票号</th>
              <th class="px-3 py-2">日期</th>
              <th class="px-3 py-2">客户</th>
              <th class="px-3 py-2">类型</th>
              <th class="px-3 py-2 text-right">不含税金额</th>
              <th class="px-3 py-2 text-right">税额</th>
              <th class="px-3 py-2 text-right">价税合计</th>
              <th class="px-3 py-2">状态</th>
              <th class="px-3 py-2">凭证号</th>
              <th class="px-3 py-2 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!items.length">
              <td colspan="10" class="px-3 py-2">
                <div class="text-center py-12 text-muted">
                  <div class="text-3xl mb-3">📋</div>
                  <p class="text-sm font-medium mb-1">暂无销项发票</p>
                  <p class="text-xs text-muted">点击「从应收单推送」按钮创建发票</p>
                </div>
              </td>
            </tr>
            <tr v-for="inv in items" :key="inv.id" class="hover:bg-elevated">
              <td class="px-3 py-2 font-mono text-[12px] max-w-48 truncate" :title="inv.invoice_no">{{ inv.invoice_no }}</td>
              <td class="px-3 py-2">{{ inv.invoice_date }}</td>
              <td class="px-3 py-2">{{ inv.customer_name || inv.counterparty_name }}</td>
              <td class="px-3 py-2"><span :class="inv.invoice_type === 'special' ? 'badge badge-blue' : 'badge badge-gray'">{{ inv.invoice_type === 'special' ? '专票' : '普票' }}</span></td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(inv.amount_without_tax) }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(inv.tax_amount) }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(inv.total_amount) }}</td>
              <td class="px-3 py-2"><span :class="statusBadge(inv.status)">{{ statusName(inv.status) }}</span></td>
              <td class="px-3 py-2 font-mono text-[12px] max-w-48 truncate" :title="inv.voucher_no || ''">{{ inv.voucher_no || '-' }}</td>
              <td class="px-3 py-2" @click.stop>
                <div class="flex items-center gap-1.5 justify-center">
                  <!-- 主操作按钮（外露） -->
                  <button v-if="inv.status === 'draft'" @click="handleConfirm(inv)" class="btn btn-sm si-action-btn" style="background:var(--success-subtle);color:var(--success-emphasis);border:none">确认</button>
                  <button v-else-if="inv.status === 'confirmed' && inv.pdf_count > 0" @click="downloadFirstPdf(inv)" class="btn btn-sm si-action-btn">下载</button>
                  <button v-else-if="inv.status === 'confirmed' && !inv.pdf_count" @click="triggerUpload(inv)" class="btn btn-primary btn-sm si-action-btn">上传</button>
                  <button v-else @click="viewDetail(inv)" class="btn btn-sm si-action-btn">查看</button>
                  <!-- 更多操作下拉 -->
                  <div class="si-action-menu">
                    <button @click.stop="toggleActionMenu(inv, $event)" class="si-action-trigger">
                      ··· <span class="text-[10px]">▾</span>
                    </button>
                  </div>
                </div>
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

    <!-- 发票详情弹窗 -->
    <Transition name="fade">
      <div v-if="showDetail" class="modal-backdrop" @click.self="showDetail = false">
        <div class="modal max-w-2xl">
          <div class="modal-header">
            <h3>销项发票详情</h3>
            <button @click="showDetail = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div v-if="detailLoading" class="text-center py-8 text-muted">加载中...</div>
            <template v-else-if="detail">
              <!-- 查看模式 -->
              <template v-if="!editing">
                <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] mb-4">
                  <div><span class="text-muted">发票号：</span><span class="font-mono">{{ detail.invoice_no }}</span></div>
                  <div><span class="text-muted">日期：</span>{{ detail.invoice_date }}</div>
                  <div><span class="text-muted">客户：</span>{{ detail.customer_name }}</div>
                  <div><span class="text-muted">类型：</span>{{ detail.invoice_type === 'special' ? '专票' : '普票' }}</div>
                  <div><span class="text-muted">状态：</span><span :class="statusBadge(detail.status)">{{ statusName(detail.status) }}</span></div>
                  <div><span class="text-muted">凭证号：</span>{{ detail.voucher_no || '-' }}</div>
                  <div><span class="text-muted">关联应收单：</span>{{ detail.receivable_bill_no || '-' }}</div>
                  <div><span class="text-muted">备注：</span>{{ detail.remark || '-' }}</div>
                </div>
                <!-- 购方开票信息 -->
                <div v-if="detail.customer_name" class="border border-line rounded-xl p-3 mb-3">
                  <div class="text-xs font-semibold text-secondary mb-2">购方开票信息</div>
                  <div class="grid grid-cols-2 gap-x-6 gap-y-1.5 text-[13px]">
                    <div class="col-span-2"><span class="text-muted">名称：</span>{{ detail.customer_name }}</div>
                    <div class="col-span-2"><span class="text-muted">纳税人识别号：</span><span class="font-mono">{{ detail.customer_tax_id || '未填写' }}</span></div>
                    <div class="col-span-2"><span class="text-muted">地址电话：</span>{{ [detail.customer_address, detail.customer_phone].filter(Boolean).join(' ') || '未填写' }}</div>
                    <div class="col-span-2"><span class="text-muted">开户行及账号：</span>{{ [detail.customer_bank_name, detail.customer_bank_account].filter(Boolean).join(' ') || '未填写' }}</div>
                  </div>
                </div>
                <!-- 电子发票 -->
                <div class="border border-line rounded-xl p-3 mb-3">
                  <div class="flex items-center justify-between mb-2">
                    <div class="text-xs font-semibold text-secondary">电子发票</div>
                    <button v-if="detail.status !== 'cancelled'" @click="triggerUploadForDetail" class="btn btn-primary btn-sm" style="padding:4px 12px;min-height:24px;font-size:12px">上传 PDF</button>
                  </div>
                  <div v-if="detail.pdf_files && detail.pdf_files.length">
                    <div v-for="(pdf, idx) in detail.pdf_files" :key="idx" class="flex items-center justify-between py-1.5 text-[13px]" :class="idx > 0 ? 'border-t border-line' : ''">
                      <div class="flex items-center gap-2 min-w-0">
                        <span class="text-muted shrink-0">📄</span>
                        <span class="truncate max-w-48" :title="pdf.name">{{ pdf.name }}</span>
                        <span class="text-muted text-[11px] shrink-0">{{ (pdf.size / 1024).toFixed(0) }}KB</span>
                      </div>
                      <div class="flex gap-1.5 shrink-0">
                        <button @click="previewPdf(detail.id, idx)" class="btn btn-sm" style="padding:3px 10px;min-height:24px;font-size:12px">预览</button>
                        <button v-if="detail.status !== 'cancelled'" @click="handleDeletePdf(detail.id, idx)" class="btn btn-sm" style="padding:3px 10px;min-height:24px;font-size:12px;background:var(--error-subtle);color:var(--error-emphasis);border:none">删除</button>
                      </div>
                    </div>
                  </div>
                  <div v-else class="text-[13px] text-muted py-2">暂未上传电子发票</div>
                </div>
                <div class="bg-elevated rounded-xl p-3 mb-3">
                  <div class="grid grid-cols-3 gap-2 text-[13px]">
                    <div>不含税：<span class="font-medium">{{ fmtMoney(detail.amount_without_tax) }}</span></div>
                    <div>税额：<span class="font-medium">{{ fmtMoney(detail.tax_amount) }}</span></div>
                    <div>价税合计：<span class="font-medium">{{ fmtMoney(detail.total_amount) }}</span></div>
                  </div>
                </div>
                <div v-if="detail.items && detail.items.length" class="table-container">
                  <table class="w-full text-[13px]">
                    <thead>
                      <tr><th>品名</th><th class="text-right">数量</th><th class="text-right">单价</th><th class="text-right">税率(%)</th><th class="text-right">不含税金额</th><th class="text-right">税额</th><th class="text-right">金额</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="it in detail.items" :key="it.id">
                        <td>{{ it.product_name }}</td>
                        <td class="text-right">{{ it.quantity }}</td>
                        <td class="text-right">{{ fmtMoney(it.unit_price) }}</td>
                        <td class="text-right">{{ it.tax_rate }}</td>
                        <td class="text-right">{{ fmtMoney(it.amount_without_tax) }}</td>
                        <td class="text-right">{{ fmtMoney(it.tax_amount) }}</td>
                        <td class="text-right">{{ fmtMoney(it.amount) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
              <!-- 编辑模式 -->
              <template v-else>
                <div class="grid grid-cols-2 gap-3 mb-4">
                  <div><label for="si-edit-invoice-type" class="label">发票类型</label><select id="si-edit-invoice-type" v-model="editForm.invoice_type" class="input text-sm"><option value="special">专票</option><option value="normal">普票</option></select></div>
                  <div><label for="si-edit-invoice-date" class="label">日期</label><input id="si-edit-invoice-date" v-model="editForm.invoice_date" type="date" class="input text-sm" /></div>
                  <div class="col-span-2"><label for="si-edit-remark" class="label">备注</label><input id="si-edit-remark" v-model="editForm.remark" class="input text-sm" /></div>
                </div>
                <div class="table-container mb-3">
                  <table class="w-full text-[13px]">
                    <thead><tr><th>品名</th><th>数量</th><th>单价</th><th>税率(%)</th><th class="text-right">金额</th><th class="text-right">税额</th><th></th></tr></thead>
                    <tbody>
                      <tr v-for="(row, idx) in editForm.items" :key="idx">
                        <td><input v-model="row.product_name" class="input w-full text-[12px]" /></td>
                        <td><input v-model.number="row.quantity" type="number" step="1" min="1" class="input w-20 text-[12px]" /></td>
                        <td><input v-model.number="row.unit_price" type="number" step="0.01" class="input w-24 text-[12px]" /></td>
                        <td><input v-model.number="row.tax_rate" type="number" step="0.01" class="input w-20 text-[12px]" /></td>
                        <td class="text-right text-[12px]">{{ editRowAmount(row) }}</td>
                        <td class="text-right text-[12px]">{{ editRowTax(row) }}</td>
                        <td><button @click="editForm.items.length > 1 && editForm.items.splice(idx, 1)" class="text-[12px] px-1.5 py-0.5 rounded-md bg-error-subtle text-error-emphasis font-medium">&times;</button></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <button @click="editForm.items.push({ product_name: '', quantity: 1, unit_price: 0, tax_rate: 13 })" class="text-[12px] text-primary font-medium">+ 添加行</button>
              </template>
            </template>
          </div>
          <div class="modal-footer">
            <template v-if="detail && !editing">
              <button v-if="detail.status === 'draft'" @click="startEdit" class="btn btn-primary btn-sm">编辑</button>
            </template>
            <template v-if="editing">
              <button @click="editing = false" class="btn btn-secondary btn-sm">取消编辑</button>
              <button @click="handleEditSave" :disabled="editSubmitting" class="btn btn-primary btn-sm">{{ editSubmitting ? '保存中...' : '保存' }}</button>
            </template>
            <button v-if="!editing" @click="showDetail = false" class="btn btn-secondary btn-sm">关闭</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 从应收单推送弹窗 -->
    <Transition name="fade">
      <div v-if="showPush" class="modal-backdrop" @click.self="showPush = false">
        <div class="modal max-w-2xl">
          <div class="modal-header">
            <h3>从应收单推送销项发票</h3>
            <button @click="showPush = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <!-- 选择应收单 -->
            <div class="mb-4">
              <label for="si-receivable-bill" class="label mb-1">选择已完成的应收单</label>
              <select id="si-receivable-bill" v-model="pushForm.receivable_bill_id" class="input text-sm w-full" @change="onReceivableBillSelect">
                <option value="">请选择</option>
                <option v-for="rb in receivableBills" :key="rb.id" :value="rb.id">
                  {{ rb.bill_no }} - {{ rb.customer_name }} - {{ rb.total_amount }}
                </option>
              </select>
            </div>

            <template v-if="pushForm.receivable_bill_id">
              <div class="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <label for="si-push-invoice-type" class="label">发票类型</label>
                  <select id="si-push-invoice-type" v-model="pushForm.invoice_type" class="input text-sm">
                    <option value="special">增值税专用发票</option>
                    <option value="normal">增值税普通发票</option>
                  </select>
                </div>
                <div>
                  <label for="si-push-invoice-date" class="label">发票日期</label>
                  <input id="si-push-invoice-date" v-model="pushForm.invoice_date" type="date" class="input text-sm" />
                </div>
                <div>
                  <label for="si-push-tax-rate" class="label">税率 (%)</label>
                  <input id="si-push-tax-rate" v-model.number="pushForm.tax_rate" type="number" step="0.01" min="0" max="100" class="input text-sm" />
                </div>
                <div>
                  <label for="si-push-remark" class="label">备注</label>
                  <input id="si-push-remark" v-model="pushForm.remark" class="input text-sm" />
                </div>
              </div>

              <!-- 明细预览 -->
              <div v-if="selectedReceivable" class="bg-elevated rounded-xl p-3 mb-3">
                <div class="text-[12px] font-semibold text-muted mb-2">发票金额预览</div>
                <div class="grid grid-cols-3 gap-2 text-[13px]">
                  <div>不含税金额: <span class="font-medium">{{ fmtMoney(previewAmountWithoutTax) }}</span></div>
                  <div>税额: <span class="font-medium">{{ fmtMoney(previewTaxAmount) }}</span></div>
                  <div>价税合计: <span class="font-medium">{{ fmtMoney(selectedReceivable.total_amount) }}</span></div>
                </div>
              </div>
            </template>
          </div>
          <div class="modal-footer">
            <button @click="showPush = false" class="btn btn-secondary btn-sm">取消</button>
            <button @click="handlePush" :disabled="submitting || !pushForm.receivable_bill_id" class="btn btn-primary btn-sm">{{ submitting ? '推送中...' : '确认推送' }}</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 操作下拉菜单 -->
    <Teleport to="body">
      <div v-if="openMenuId" class="si-action-dropdown" :style="menuStyle" @click.stop>
        <button @click="viewDetailById(openMenuId); closeMenu()" class="si-action-item">查看</button>
        <button v-if="menuInv?.status === 'draft'" @click="startEditById(openMenuId); closeMenu()" class="si-action-item">编辑</button>
        <button v-if="menuInv?.status !== 'cancelled'" @click="triggerUpload(menuInv); closeMenu()" class="si-action-item">上传发票</button>
        <button v-if="menuInv?.pdf_count > 0" @click="downloadFirstPdf(menuInv); closeMenu()" class="si-action-item">下载发票</button>
        <button v-if="menuInv?.status === 'draft' || menuInv?.status === 'confirmed'" @click="handleCancel(menuInv); closeMenu()" class="si-action-item text-error">作废</button>
      </div>
    </Teleport>

    <!-- PDF 预览弹窗 -->
    <Transition name="fade">
      <div v-if="showPdfPreview" class="modal-backdrop" @click.self="showPdfPreview = false">
        <div class="modal max-w-4xl" style="height: 80vh; display: flex; flex-direction: column;">
          <div class="modal-header">
            <h3>预览电子发票</h3>
            <button @click="showPdfPreview = false" class="modal-close">&times;</button>
          </div>
          <iframe :src="pdfPreviewUrl" class="w-full flex-1 border-0"></iframe>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import PageToolbar from '../common/PageToolbar.vue'
import { getInvoices, getInvoice, updateInvoice, pushInvoiceFromReceivable, confirmInvoice, cancelInvoice, getReceivableBills, uploadInvoicePdf, getInvoicePdfUrl, deleteInvoicePdf } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { useFormat } from '../../composables/useFormat'
import api from '../../api/index'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { fmtMoney } = useFormat()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const filters = ref({ status: '', customer_id: '', date_from: '', date_to: '' })
const customers = ref([])
const showPush = ref(false)
const submitting = ref(false)
const showDetail = ref(false)
const detail = ref(null)
const detailLoading = ref(false)
const editing = ref(false)
const editForm = ref({ invoice_type: '', invoice_date: '', remark: '', items: [] })
const editSubmitting = ref(false)
const openMenuId = ref(null)
const menuStyle = ref({})
const menuInv = ref(null)
const showPdfPreview = ref(false)
const pdfPreviewUrl = ref('')

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
const receivableBills = ref([])
const selectedReceivable = ref(null)

const pushForm = ref({
  receivable_bill_id: '',
  invoice_type: 'special',
  invoice_date: new Date().toISOString().slice(0, 10),
  tax_rate: 13,
  remark: '',
})

const statusName = (s) => ({ draft: '草稿', confirmed: '已确认', cancelled: '已作废' }[s] || s)
const statusBadge = (s) => ({ draft: 'badge badge-yellow', confirmed: 'badge badge-green', cancelled: 'badge badge-gray' }[s] || 'badge')

const previewAmountWithoutTax = computed(() => {
  if (!selectedReceivable.value) return '0.00'
  const total = parseFloat(selectedReceivable.value.total_amount) || 0
  const rate = pushForm.value.tax_rate / 100
  return (total / (1 + rate)).toFixed(2)
})

const previewTaxAmount = computed(() => {
  if (!selectedReceivable.value) return '0.00'
  const total = parseFloat(selectedReceivable.value.total_amount) || 0
  return (total - parseFloat(previewAmountWithoutTax.value)).toFixed(2)
})

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const params = {
    account_set_id: accountingStore.currentAccountSetId,
    direction: 'output',
    page: page.value,
    page_size: pageSize,
  }
  if (filters.value.status) params.status = filters.value.status
  if (filters.value.customer_id) params.customer_id = filters.value.customer_id
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

async function loadCustomers() {
  const res = await api.get('/customers', { params: { limit: 1000 } })
  customers.value = res.data.items || res.data || []
}

async function loadReceivableBills() {
  if (!accountingStore.currentAccountSetId) return
  try {
    const res = await getReceivableBills({
      account_set_id: accountingStore.currentAccountSetId,
      status: 'completed',
      page_size: 200,
    })
    receivableBills.value = res.data.items || []
  } catch {
    receivableBills.value = []
  }
}

function openPushModal() {
  pushForm.value = {
    receivable_bill_id: '',
    invoice_type: 'special',
    invoice_date: new Date().toISOString().slice(0, 10),
    tax_rate: 13,
    remark: '',
  }
  selectedReceivable.value = null
  loadReceivableBills()
  showPush.value = true
}

function onReceivableBillSelect() {
  const id = pushForm.value.receivable_bill_id
  selectedReceivable.value = receivableBills.value.find((rb) => rb.id === id) || null
}

async function handlePush() {
  if (!pushForm.value.receivable_bill_id) {
    appStore.showToast('请选择应收单', 'error')
    return
  }
  submitting.value = true
  try {
    await pushInvoiceFromReceivable({
      account_set_id: accountingStore.currentAccountSetId,
      receivable_bill_id: pushForm.value.receivable_bill_id,
      invoice_type: pushForm.value.invoice_type,
      invoice_date: pushForm.value.invoice_date,
      tax_rate: pushForm.value.tax_rate,
      remark: pushForm.value.remark,
    })
    appStore.showToast('发票推送成功', 'success')
    showPush.value = false
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '推送失败', 'error')
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
    const doUpload = await appStore.customConfirm('上传电子发票', '发票已确认，是否立即上传电子发票 PDF？')
    if (doUpload) {
      triggerUpload(inv)
    }
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

// ---- 操作菜单 ----
function toggleActionMenu(inv, event) {
  if (openMenuId.value === inv.id) {
    closeMenu()
    return
  }
  const btn = event.currentTarget
  const rect = btn.getBoundingClientRect()
  menuStyle.value = {
    position: 'fixed',
    top: `${rect.bottom + 4}px`,
    right: `${window.innerWidth - rect.right}px`,
    zIndex: 9999,
  }
  openMenuId.value = inv.id
  menuInv.value = inv
}

function closeMenu() {
  openMenuId.value = null
  menuInv.value = null
}

function viewDetailById(id) {
  const inv = items.value.find(i => i.id === id)
  if (inv) viewDetail(inv)
}

async function startEditById(id) {
  const inv = items.value.find(i => i.id === id)
  if (inv) {
    await viewDetail(inv)
    startEdit()
  }
}

// ---- PDF 操作 ----
function triggerUpload(inv) {
  if (!inv) return
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      await uploadInvoicePdf(inv.id, file)
      appStore.showToast('上传成功', 'success')
      loadList()
    } catch (err) {
      appStore.showToast(err.response?.data?.detail || '上传失败', 'error')
    }
  }
  input.click()
}

function triggerUploadForDetail() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      await uploadInvoicePdf(detail.value.id, file)
      appStore.showToast('上传成功', 'success')
      const res = await getInvoice(detail.value.id)
      detail.value = res.data
      loadList()
    } catch (err) {
      appStore.showToast(err.response?.data?.detail || '上传失败', 'error')
    }
  }
  input.click()
}

function downloadFirstPdf(inv) {
  if (!inv || !inv.pdf_count) return
  window.open(getInvoicePdfUrl(inv.id, 0), '_blank')
}

function previewPdf(invoiceId, index) {
  pdfPreviewUrl.value = getInvoicePdfUrl(invoiceId, index)
  showPdfPreview.value = true
}

async function handleDeletePdf(invoiceId, index) {
  if (!await appStore.customConfirm('删除确认', '确认删除此 PDF 文件？')) return
  try {
    await deleteInvoicePdf(invoiceId, index)
    appStore.showToast('删除成功', 'success')
    const res = await getInvoice(invoiceId)
    detail.value = res.data
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => {
  loadList()
  loadCustomers()
  document.addEventListener('click', closeMenu)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', closeMenu)
})
</script>

<style scoped>
.si-action-menu {
  position: relative;
  display: inline-block;
}
.si-action-trigger {
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  font-family: inherit;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s;
  min-height: 28px;
}
.si-action-trigger:hover {
  border-color: var(--border-strong);
  background: var(--elevated);
}
.si-action-btn {
  padding: 4px 12px;
  min-height: 28px;
  font-size: 12px;
}
</style>

<style>
/* Teleport 到 body 的下拉菜单，不能用 scoped */
.si-action-dropdown {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow-md);
  min-width: 120px;
  padding: 4px;
}
.si-action-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
  border-radius: 6px;
  font-family: inherit;
  text-align: left;
  transition: background 0.1s;
}
.si-action-item:hover {
  background: var(--elevated);
}
.si-action-item.text-error {
  color: var(--error-emphasis) !important;
}
.si-action-item.text-error:hover {
  background: var(--error-subtle) !important;
}
</style>
