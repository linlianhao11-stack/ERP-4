<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="filters.customer_id" class="toolbar-select" @change="loadList">
            <option value="">全部客户</option>
            <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <input v-model="filters.date_from" type="date" class="toolbar-select" @change="loadList" placeholder="开始日期" />
          <input v-model="filters.date_to" type="date" class="toolbar-select" @change="loadList" placeholder="结束日期" />
          <div class="toolbar-search-wrapper">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="searchQuery" @input="debouncedSearch" class="toolbar-search" placeholder="搜索单号/客户...">
          </div>
        </template>
        <template #actions>
          <button v-if="selectedIds.length" @click="handleBatchPdf" class="btn btn-secondary btn-sm">批量下载PDF ({{ selectedIds.length }})</button>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-[13px]">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2 w-8"><input type="checkbox" @change="toggleAll" :checked="allSelected" aria-label="全选" /></th>
              <th class="px-3 py-2">单号</th>
              <th class="px-3 py-2">日期</th>
              <th class="px-3 py-2">客户</th>
              <th class="px-3 py-2">仓库</th>
              <th class="px-3 py-2 text-right">成本合计</th>
              <th class="px-3 py-2 text-right">销售合计</th>
              <th class="px-3 py-2">凭证号</th>
              <th class="px-3 py-2">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!items.length">
              <td colspan="9" class="px-3 py-2">
                <div class="text-center py-12 text-muted">
                  <div class="text-3xl mb-3">📋</div>
                  <p class="text-sm font-medium mb-1">暂无出库单数据</p>
                  <p class="text-xs text-muted">出库单数据由销售订单发货时自动生成</p>
                </div>
              </td>
            </tr>
            <tr v-for="d in items" :key="d.id" class="hover:bg-elevated">
              <td class="px-3 py-2"><input type="checkbox" :value="d.id" v-model="selectedIds" aria-label="选择此行" /></td>
              <td class="px-3 py-2 font-mono text-[12px]"><span class="max-w-48 truncate inline-block align-bottom" :title="d.delivery_no || d.bill_no">{{ d.delivery_no || d.bill_no }}</span></td>
              <td class="px-3 py-2">{{ d.delivery_date || d.bill_date }}</td>
              <td class="px-3 py-2">{{ d.customer_name }}</td>
              <td class="px-3 py-2">{{ d.warehouse_name }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(d.cost_total) }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(d.sales_total) }}</td>
              <td class="px-3 py-2 font-mono text-[12px]"><span class="max-w-48 truncate inline-block align-bottom" :title="d.voucher_no">{{ d.voucher_no || '-' }}</span></td>
              <td class="px-3 py-2" @click.stop>
                <div class="flex gap-1">
                  <button @click="viewDetail(d)" class="text-xs px-2.5 py-1 rounded-md bg-info-subtle text-info-emphasis font-medium">查看</button>
                  <button @click="handleDownloadPdf(d)" class="text-xs px-2.5 py-1 rounded-md bg-purple-subtle text-purple-emphasis font-medium">PDF</button>
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

    <!-- 详情弹窗 -->
    <Transition name="fade">
      <div v-if="showDetail" class="modal-backdrop" @click.self="showDetail = false">
        <div class="modal max-w-2xl">
          <div class="modal-header">
            <h3>出库单详情</h3>
            <button @click="showDetail = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div v-if="detailLoading" class="text-center py-8 text-muted">加载中...</div>
            <template v-else-if="detail">
              <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] mb-4">
                <div><span class="text-muted">单号：</span><span class="font-mono">{{ detail.bill_no }}</span></div>
                <div><span class="text-muted">日期：</span>{{ detail.bill_date }}</div>
                <div><span class="text-muted">客户：</span>{{ detail.customer_name }}</div>
                <div><span class="text-muted">仓库：</span>{{ detail.warehouse_name || '-' }}</div>
                <div><span class="text-muted">成本合计：</span><span class="font-medium">{{ fmtMoney(detail.total_cost) }}</span></div>
                <div><span class="text-muted">销售合计：</span><span class="font-medium">{{ fmtMoney(detail.total_amount) }}</span></div>
                <div><span class="text-muted">凭证号：</span>{{ detail.voucher_no || '-' }}</div>
                <div><span class="text-muted">创建时间：</span>{{ detail.created_at?.slice(0, 19).replace('T', ' ') }}</div>
              </div>
              <div v-if="detail.items && detail.items.length">
                <div class="text-[12px] font-semibold text-muted uppercase tracking-wider mb-2">商品明细</div>
                <div class="table-container">
                  <table class="w-full text-[13px]">
                    <thead>
                      <tr><th>商品</th><th class="text-right">数量</th><th class="text-right">成本价</th><th class="text-right">销售价</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="it in detail.items" :key="it.id">
                        <td>{{ it.product_name }}</td>
                        <td class="text-right">{{ it.quantity }}</td>
                        <td class="text-right">{{ fmtMoney(it.cost_price) }}</td>
                        <td class="text-right">{{ fmtMoney(it.sale_price) }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </template>
          </div>
          <div class="modal-footer">
            <button @click="showDetail = false" class="btn btn-secondary btn-sm">关闭</button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Search } from 'lucide-vue-next'
import PageToolbar from '../common/PageToolbar.vue'
import { getSalesDeliveries, getSalesDelivery, getSalesDeliveryPdf, batchSalesDeliveryPdf } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useAppStore } from '../../stores/app'
import { useFormat } from '../../composables/useFormat'
import { useSearch } from '../../composables/useSearch'
import api from '../../api/index'

const accountingStore = useAccountingStore()
const appStore = useAppStore()
const { fmtMoney } = useFormat()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const filters = ref({ customer_id: '', date_from: '', date_to: '' })
const customers = ref([])
const selectedIds = ref([])
const showDetail = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

async function viewDetail(d) {
  showDetail.value = true
  detailLoading.value = true
  try {
    const res = await getSalesDelivery(d.id)
    detail.value = res.data
  } catch (e) {
    appStore.showToast('加载详情失败', 'error')
    showDetail.value = false
  } finally {
    detailLoading.value = false
  }
}

const allSelected = computed(() => items.value.length > 0 && selectedIds.value.length === items.value.length)

function toggleAll(e) {
  selectedIds.value = e.target.checked ? items.value.map((d) => d.id) : []
}

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const params = {
    account_set_id: accountingStore.currentAccountSetId,
    page: page.value,
    page_size: pageSize,
  }
  if (filters.value.customer_id) params.customer_id = filters.value.customer_id
  if (filters.value.date_from) params.start_date = filters.value.date_from
  if (filters.value.date_to) params.end_date = filters.value.date_to
  if (searchQuery.value) params.search = searchQuery.value
  try {
    const res = await getSalesDeliveries(params)
    items.value = res.data.items || res.data || []
    total.value = res.data.total || items.value.length
    selectedIds.value = []
  } catch (e) {
    items.value = []
    total.value = 0
  }
}

const { searchQuery, debouncedSearch } = useSearch(loadList, page)

async function loadCustomers() {
  const res = await api.get('/customers', { params: { limit: 1000 } })
  customers.value = res.data.items || res.data || []
}

const downloadPdf = async (apiCall, filename) => {
  try {
    const res = await apiCall
    const blob = new Blob([res.data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    appStore.showToast('下载失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

function handleDownloadPdf(d) {
  const no = d.delivery_no || d.bill_no || d.id
  downloadPdf(getSalesDeliveryPdf(d.id), `出库单_${no}.pdf`)
}

function handleBatchPdf() {
  if (!selectedIds.value.length) return
  downloadPdf(batchSalesDeliveryPdf(selectedIds.value), `出库单_批量_${new Date().toISOString().slice(0, 10)}.pdf`)
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => { loadList(); loadCustomers() })
</script>
