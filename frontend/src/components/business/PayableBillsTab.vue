<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="filters.status" class="form-input w-28" @change="loadList">
        <option value="">全部状态</option>
        <option value="pending">待付款</option>
        <option value="partial">部分付款</option>
        <option value="completed">已付清</option>
        <option value="cancelled">已取消</option>
      </select>
      <button v-if="hasPermission('accounting_ap_edit')" @click="showCreate = true" class="btn btn-primary btn-sm ml-auto">手动新增</button>
    </div>

    <div class="table-wrapper">
      <table class="data-table">
        <thead>
          <tr>
            <th>单号</th>
            <th>日期</th>
            <th>供应商</th>
            <th class="text-right">应付金额</th>
            <th class="text-right">已付金额</th>
            <th class="text-right">未付金额</th>
            <th>状态</th>
            <th>凭证号</th>
            <th>来源采购单</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td colspan="10" class="text-center text-[#86868b] py-8">暂无数据</td>
          </tr>
          <tr v-for="b in items" :key="b.id">
            <td class="font-mono text-[12px]">{{ b.bill_no }}</td>
            <td>{{ b.bill_date }}</td>
            <td>{{ b.supplier_name }}</td>
            <td class="text-right">{{ b.total_amount }}</td>
            <td class="text-right">{{ b.paid_amount }}</td>
            <td class="text-right">{{ b.unpaid_amount }}</td>
            <td><span :class="statusBadge(b.status)">{{ statusName(b.status) }}</span></td>
            <td class="font-mono text-[12px]">{{ b.voucher_no || '-' }}</td>
            <td class="font-mono text-[12px]">{{ b.purchase_order_no || '-' }}</td>
            <td @click.stop>
              <div class="flex gap-1">
                <button @click="viewDetail(b)" class="text-[12px] px-2 py-0.5 rounded-full bg-[#e8eaf8] text-[#3634a3]">查看</button>
                <button v-if="b.status === 'pending' || b.status === 'partial'" @click="cancelBill(b)" class="text-[12px] px-2 py-0.5 rounded-full bg-[#ffeaee] text-[#ff3b30]">取消</button>
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

    <!-- 详情弹窗 -->
    <Transition name="fade">
      <div v-if="showDetail" class="modal-backdrop" @click.self="showDetail = false">
        <div class="modal" style="max-width: 500px">
          <div class="modal-header">
            <h3>应付单详情</h3>
            <button @click="showDetail = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div v-if="detailLoading" class="text-center py-8 text-[#86868b]">加载中...</div>
            <template v-else-if="detail">
              <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px]">
                <div><span class="text-[#86868b]">单号：</span><span class="font-mono">{{ detail.bill_no }}</span></div>
                <div><span class="text-[#86868b]">日期：</span>{{ detail.bill_date }}</div>
                <div><span class="text-[#86868b]">供应商：</span>{{ detail.supplier_name }}</div>
                <div><span class="text-[#86868b]">状态：</span><span :class="statusBadge(detail.status)">{{ statusName(detail.status) }}</span></div>
                <div><span class="text-[#86868b]">应付金额：</span><span class="font-medium">{{ detail.total_amount }}</span></div>
                <div><span class="text-[#86868b]">已付金额：</span>{{ detail.paid_amount }}</div>
                <div><span class="text-[#86868b]">未付金额：</span>{{ detail.unpaid_amount }}</div>
                <div><span class="text-[#86868b]">凭证号：</span>{{ detail.voucher_no || '-' }}</div>
                <div><span class="text-[#86868b]">来源采购单：</span>{{ detail.purchase_order_no || '-' }}</div>
                <div><span class="text-[#86868b]">创建时间：</span>{{ detail.created_at?.slice(0, 19).replace('T', ' ') }}</div>
                <div class="col-span-2"><span class="text-[#86868b]">备注：</span>{{ detail.remark || '-' }}</div>
              </div>
            </template>
          </div>
          <div class="modal-footer">
            <button @click="showDetail = false" class="btn btn-secondary btn-sm">关闭</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 新增弹窗 -->
    <Transition name="fade">
      <div v-if="showCreate" class="modal-backdrop" @click.self="showCreate = false">
        <div class="modal" style="max-width: 500px">
          <div class="modal-header">
            <h3>手动新增应付单</h3>
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
                <label class="form-label">日期</label>
                <input v-model="form.bill_date" type="date" class="form-input" />
              </div>
              <div>
                <label class="form-label">金额</label>
                <input v-model="form.total_amount" type="number" step="0.01" class="form-input" />
              </div>
              <div>
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
import { getPayableBills, getPayableBill, createPayableBill, cancelPayableBill } from '../../api/accounting'
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
const form = ref({ supplier_id: '', bill_date: new Date().toISOString().slice(0, 10), total_amount: '', remark: '' })
const showDetail = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

async function viewDetail(b) {
  showDetail.value = true
  detailLoading.value = true
  try {
    const res = await getPayableBill(b.id)
    detail.value = res.data
  } catch (e) {
    appStore.showToast('加载详情失败', 'error')
    showDetail.value = false
  } finally {
    detailLoading.value = false
  }
}

const statusName = (s) => ({ pending: '待付款', partial: '部分付款', completed: '已付清', cancelled: '已取消' }[s] || s)
const statusBadge = (s) => ({ pending: 'badge badge-yellow', partial: 'badge badge-orange', completed: 'badge badge-green', cancelled: 'badge badge-gray' }[s] || 'badge')

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const params = { account_set_id: accountingStore.currentAccountSetId, page: page.value, page_size: pageSize }
  if (filters.value.status) params.status = filters.value.status
  const res = await getPayableBills(params)
  items.value = res.data.items
  total.value = res.data.total
}

async function loadSuppliers() {
  const res = await api.get('/suppliers', { params: { limit: 1000 } })
  suppliers.value = res.data.items || res.data || []
}

async function handleCreate() {
  if (!form.value.supplier_id || !form.value.total_amount) {
    appStore.showToast('请填写供应商和金额', 'error')
    return
  }
  submitting.value = true
  try {
    await createPayableBill(accountingStore.currentAccountSetId, form.value)
    appStore.showToast('创建成功', 'success')
    showCreate.value = false
    form.value = { supplier_id: '', bill_date: new Date().toISOString().slice(0, 10), total_amount: '', remark: '' }
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    submitting.value = false
  }
}

async function cancelBill(b) {
  if (!await appStore.customConfirm('作废确认', `确认取消应付单 ${b.bill_no}？`)) return
  try {
    await cancelPayableBill(b.id)
    appStore.showToast('已取消', 'success')
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '取消失败', 'error')
  }
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => { loadList(); loadSuppliers() })
</script>
