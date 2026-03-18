<template>
  <div>
    <!-- 移动端卡片列表 -->
    <div class="md:hidden space-y-2">
      <!-- 移动端筛选 -->
      <div class="flex flex-wrap items-center gap-2 mb-2">
        <select v-model="filters.supplier_id" @change="onFilterChange" class="toolbar-select flex-1">
          <option value="">全部供应商</option>
          <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <div class="toolbar-search-wrapper flex-1" style="max-width:none">
          <Search :size="14" class="toolbar-search-icon" />
          <input v-model="searchQuery" @input="debouncedSearch" class="toolbar-search" placeholder="搜索单号/供应商...">
        </div>
      </div>
      <div v-for="r in filteredItems" :key="r.id" class="card p-3" @click="viewDetail(r)">
        <div class="flex justify-between items-start mb-1">
          <div class="font-medium text-sm font-mono">{{ r.return_no }}</div>
          <div class="text-lg font-bold text-warning">{{ fmtMoney(r.total_amount) }}</div>
        </div>
        <div class="flex justify-between items-center text-xs">
          <div class="text-muted">{{ r.supplier_name }}</div>
          <span :class="refundStatusClass(r.refund_status)">{{ refundStatusLabel(r.refund_status) }}</span>
        </div>
        <div class="text-xs text-muted mt-1">{{ fmtDate(r.created_at) }}</div>
      </div>
      <div v-if="!filteredItems.length" class="p-8 text-center text-muted text-sm">暂无退货单数据</div>
    </div>

    <!-- 桌面端表格 -->
    <div class="card hidden md:block" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="filters.supplier_id" @change="onFilterChange" class="toolbar-select">
            <option value="">全部供应商</option>
            <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
          <div class="toolbar-search-wrapper">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="searchQuery" @input="debouncedSearch" class="toolbar-search" placeholder="搜索单号/供应商...">
          </div>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-2 py-2 text-left">退货单号</th>
              <th class="px-2 py-2 text-left">关联采购单</th>
              <th class="px-2 py-2 text-left">供应商</th>
              <th class="px-2 py-2 text-right">退货金额</th>
              <th class="px-2 py-2 text-left">退款方式</th>
              <th class="px-2 py-2 text-center">退款状态</th>
              <th class="px-2 py-2 text-left">退货时间</th>
              <th class="px-2 py-2 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!filteredItems.length">
              <td colspan="8">
                <div class="text-center py-12 text-muted">
                  <p class="text-sm font-medium mb-1">暂无退货单数据</p>
                  <p class="text-xs text-muted">退货单由采购订单退货时自动生成</p>
                </div>
              </td>
            </tr>
            <tr v-for="r in filteredItems" :key="r.id" class="hover:bg-elevated cursor-pointer" @click="viewDetail(r)">
              <td class="px-2 py-2 font-mono text-sm max-w-48 truncate" :title="r.return_no">{{ r.return_no }}</td>
              <td class="px-2 py-2 font-mono text-sm text-primary max-w-48 truncate" :title="r.po_no">{{ r.po_no }}</td>
              <td class="px-2 py-2">{{ r.supplier_name }}</td>
              <td class="px-2 py-2 text-right font-semibold text-warning">{{ fmtMoney(r.total_amount) }}</td>
              <td class="px-2 py-2">{{ r.is_refunded ? (r.refund_status === 'confirmed' ? '已退款' : '需要退款') : '转为在账资金' }}</td>
              <td class="px-2 py-2 text-center">
                <span :class="refundStatusClass(r.refund_status)">{{ refundStatusLabel(r.refund_status) }}</span>
              </td>
              <td class="px-2 py-2 text-muted text-xs">{{ fmtDate(r.created_at) }}</td>
              <td class="px-2 py-2 text-center" @click.stop>
                <button @click="viewDetail(r)" class="text-xs px-2.5 py-1 rounded-md bg-info-subtle text-info-emphasis font-medium">查看</button>
              </td>
            </tr>
          </tbody>
          <tfoot v-if="hasPagination" class="bg-elevated text-sm">
            <tr>
              <td :colspan="100" class="px-3.5 py-2.5">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-muted">共 {{ pageItemCount }} 条</span>
                  <div class="flex items-center gap-1">
                    <button @click="prevPage(); loadList()" :disabled="page <= 1" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">‹</button>
                    <template v-for="(p, i) in visiblePages" :key="i">
                      <span v-if="p === '…'" class="w-7 h-7 flex items-center justify-center text-xs text-muted cursor-default">…</span>
                      <button v-else @click="goToPage(p); loadList()" :class="p === page ? 'bg-primary text-white font-medium' : 'text-muted hover:bg-surface-hover hover:text-text'" class="w-7 h-7 flex items-center justify-center rounded-md text-xs">{{ p }}</button>
                    </template>
                    <button @click="nextPage(); loadList()" :disabled="page >= totalPages" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">›</button>
                  </div>
                  <span class="text-xs text-muted w-16"></span>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <Transition name="fade">
      <div v-if="showDetail" class="modal-backdrop" @click.self="showDetail = false">
        <div class="modal max-w-2xl">
          <div class="modal-header">
            <h3>退货单详情</h3>
            <button @click="showDetail = false" class="modal-close">&times;</button>
          </div>
          <div class="modal-body">
            <div v-if="detailLoading" class="text-center py-8 text-muted">加载中...</div>
            <template v-else-if="detail">
              <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] mb-4">
                <div><span class="text-muted">退货单号：</span><span class="font-mono">{{ detail.return_no }}</span></div>
                <div><span class="text-muted">关联采购单：</span><span class="font-mono text-primary">{{ detail.po_no }}</span></div>
                <div><span class="text-muted">供应商：</span>{{ detail.supplier_name }}</div>
                <div><span class="text-muted">退货金额：</span><span class="font-semibold text-warning">{{ fmtMoney(detail.total_amount) }}</span></div>
                <div><span class="text-muted">退款方式：</span>{{ detail.is_refunded ? (detail.refund_status === 'confirmed' ? '已退款' : '需要退款') : '转为在账资金' }}</div>
                <div>
                  <span class="text-muted">退款状态：</span>
                  <span :class="refundStatusClass(detail.refund_status)">{{ refundStatusLabel(detail.refund_status) }}</span>
                </div>
                <div v-if="detail.tracking_no"><span class="text-muted">退货物流：</span>{{ detail.tracking_no }}</div>
                <div v-if="detail.reason"><span class="text-muted">退货原因：</span>{{ detail.reason }}</div>
                <div><span class="text-muted">处理人：</span>{{ detail.created_by_name || '-' }}</div>
                <div><span class="text-muted">退货时间：</span>{{ fmtDate(detail.created_at) }}</div>
              </div>
              <div v-if="detail.items && detail.items.length">
                <div class="text-[12px] font-semibold text-muted uppercase tracking-wider mb-2">退货商品明细</div>
                <div class="table-container">
                  <table class="w-full text-sm">
                    <thead>
                      <tr>
                        <th>SKU</th>
                        <th>商品名</th>
                        <th class="text-right">数量</th>
                        <th class="text-right">单价</th>
                        <th class="text-right">小计</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="it in detail.items" :key="it.id">
                        <td class="font-mono text-[12px]">{{ it.product_sku }}</td>
                        <td>{{ it.product_name }}</td>
                        <td class="text-right">{{ it.quantity }}</td>
                        <td class="text-right">{{ fmtMoney(it.unit_price) }}</td>
                        <td class="text-right font-semibold">{{ fmtMoney(it.amount) }}</td>
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
import { ref, computed, onMounted } from 'vue'
import { Search } from 'lucide-vue-next'
import { getPurchaseReturns, getPurchaseReturn } from '../../../api/purchase'
import { useAppStore } from '../../../stores/app'
import { useFormat } from '../../../composables/useFormat'
import { usePagination } from '../../../composables/usePagination'
import PageToolbar from '../../common/PageToolbar.vue'
import api from '../../../api/index'

const appStore = useAppStore()
const { fmtMoney, fmtDate } = useFormat()
const { page, pageSize, total, totalPages, hasPagination, paginationParams, visiblePages, pageItemCount, setTotal, resetPage, prevPage, nextPage, goToPage } = usePagination(20)

const items = ref([])
const filters = ref({ supplier_id: '' })
const suppliers = ref([])
const showDetail = ref(false)
const detail = ref(null)
const detailLoading = ref(false)
const searchQuery = ref('')

let _searchTimer = null
function debouncedSearch() {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(() => {
    resetPage()
    loadList()
  }, 300)
}

const filteredItems = computed(() => {
  if (!searchQuery.value) return items.value
  const q = searchQuery.value.toLowerCase()
  return items.value.filter(r =>
    (r.return_no && r.return_no.toLowerCase().includes(q)) ||
    (r.po_no && r.po_no.toLowerCase().includes(q)) ||
    (r.supplier_name && r.supplier_name.toLowerCase().includes(q))
  )
})

function refundStatusLabel(status) {
  if (status === 'pending') return '待退款'
  if (status === 'confirmed') return '已到账'
  return '转为在账资金'
}

function refundStatusClass(status) {
  if (status === 'pending') return 'text-warning'
  if (status === 'confirmed') return 'text-success'
  return 'text-muted'
}

async function loadList() {
  const params = { ...paginationParams.value }
  if (filters.value.supplier_id) params.supplier_id = filters.value.supplier_id
  if (searchQuery.value) params.search = searchQuery.value
  try {
    const res = await getPurchaseReturns(params)
    items.value = res.data.items || []
    setTotal(res.data.total || 0)
  } catch (e) {
    items.value = []
    setTotal(0)
  }
}

function onFilterChange() {
  resetPage()
  loadList()
}

async function viewDetail(r) {
  showDetail.value = true
  detailLoading.value = true
  try {
    const res = await getPurchaseReturn(r.id)
    detail.value = res.data
  } catch (e) {
    appStore.showToast('加载详情失败', 'error')
    showDetail.value = false
  } finally {
    detailLoading.value = false
  }
}

async function loadSuppliers() {
  try {
    const res = await api.get('/suppliers', { params: { limit: 1000 } })
    suppliers.value = res.data.items || res.data || []
  } catch (e) {
    suppliers.value = []
  }
}

onMounted(() => { loadList(); loadSuppliers() })
</script>
