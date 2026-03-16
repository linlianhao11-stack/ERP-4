<template>
  <div class="card">
    <div class="p-3 border-b flex flex-wrap items-center gap-2">
      <select v-model="logFilter.type" @change="resetPage(); loadLogs()" class="input input-sm w-auto">
        <option value="">全部类型</option>
        <option value="RESTOCK">入库</option>
        <option value="SALE">销售出库</option>
        <option value="RETURN">退货入库</option>
        <option value="CONSIGN_OUT">寄售调拨</option>
        <option value="CONSIGN_SETTLE">寄售结算</option>
        <option value="CONSIGN_RETURN">寄售退货</option>
        <option value="ADJUST">库存调整</option>
        <option value="PURCHASE_IN">采购入库</option>
        <option value="PURCHASE_RETURN">采购退货</option>
        <option value="TRANSFER_OUT">调拨出库</option>
        <option value="TRANSFER_IN">调拨入库</option>
        <option value="RESERVE">库存预留</option>
        <option value="RESERVE_CANCEL">取消预留</option>
      </select>
      <input v-model="logFilter.start" @change="resetPage(); loadLogs()" type="date" class="input input-sm w-auto hidden md:block">
      <input v-model="logFilter.end" @change="resetPage(); loadLogs()" type="date" class="input input-sm w-auto hidden md:block">
      <input v-model="logFilter.search" @input="debouncedLoadLogs" class="input input-sm flex-1 min-w-[120px]" placeholder="搜索商品名/SKU/仓库名">
      <button @click="resetLogFilters" class="btn btn-secondary btn-sm flex-shrink-0" title="重置筛选"><RotateCcw :size="14" /></button>
    </div>
    <div class="overflow-x-auto table-container">
      <table class="w-full text-sm">
        <thead class="bg-elevated">
          <tr>
            <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleLogSort('product')">商品 <span v-if="logSort.key === 'product'" class="text-primary">{{ logSort.order === 'asc' ? '↑' : '↓' }}</span></th>
            <th class="px-2 py-2 text-left md-hide cursor-pointer select-none hover:text-primary" @click="toggleLogSort('warehouse')">仓库 <span v-if="logSort.key === 'warehouse'" class="text-primary">{{ logSort.order === 'asc' ? '↑' : '↓' }}</span></th>
            <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleLogSort('type')">类型 <span v-if="logSort.key === 'type'" class="text-primary">{{ logSort.order === 'asc' ? '↑' : '↓' }}</span></th>
            <th class="px-2 py-2 text-right cursor-pointer select-none hover:text-primary" @click="toggleLogSort('quantity')">数量 <span v-if="logSort.key === 'quantity'" class="text-primary">{{ logSort.order === 'asc' ? '↑' : '↓' }}</span></th>
            <th class="px-2 py-2 text-center md-hide">库存变化</th>
            <th class="px-2 py-2 text-left md-hide">备注</th>
            <th class="px-2 py-2 text-left md-hide">操作人</th>
            <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleLogSort('time')">时间 <span v-if="logSort.key === 'time'" class="text-primary">{{ logSort.order === 'asc' ? '↑' : '↓' }}</span></th>
          </tr>
        </thead>
        <tbody class="divide-y">
          <tr v-for="l in sortedLogs" :key="l.id">
            <td class="px-2 py-2"><div>{{ l.product_name }}</div><div class="text-xs text-muted">{{ l.product_sku }}</div></td>
            <td class="px-2 py-2 md-hide">{{ l.warehouse_name }}</td>
            <td class="px-2 py-2"><StatusBadge type="logType" :status="l.change_type" :label="l.change_type_name" /></td>
            <td class="px-2 py-2 text-right font-semibold" :class="l.quantity > 0 ? 'text-success' : 'text-error'">{{ l.quantity > 0 ? '+' : '' }}{{ l.quantity }}</td>
            <td class="px-2 py-2 text-center text-muted md-hide">{{ l.before_qty }}→{{ l.after_qty }}</td>
            <td class="px-2 py-2 text-muted text-xs max-w-24 truncate md-hide">{{ l.remark }}</td>
            <td class="px-2 py-2 text-muted md-hide">{{ l.creator_name }}</td>
            <td class="px-2 py-2 text-muted text-xs">{{ fmtDate(l.created_at) }}</td>
          </tr>
        </tbody>
        <tfoot v-if="hasPagination" class="bg-elevated">
          <tr>
            <td :colspan="100" class="px-3.5 py-2.5">
              <div class="flex items-center justify-between">
                <span class="text-xs text-muted">共 {{ pageItemCount }} 条</span>
                <div class="flex items-center gap-1">
                  <button @click="prevPage(); loadLogs()" :disabled="page <= 1" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">‹</button>
                  <template v-for="(p, i) in visiblePages" :key="i">
                    <span v-if="p === '…'" class="w-7 h-7 flex items-center justify-center text-xs text-muted cursor-default">…</span>
                    <button v-else @click="goToPage(p); loadLogs()" :class="p === page ? 'bg-primary text-white font-medium' : 'text-muted hover:bg-surface-hover hover:text-text'" class="w-7 h-7 flex items-center justify-center rounded-md text-xs">{{ p }}</button>
                  </template>
                  <button @click="nextPage(); loadLogs()" :disabled="page >= totalPages" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">›</button>
                </div>
                <span class="text-xs text-muted w-16"></span>
              </div>
            </td>
          </tr>
        </tfoot>
      </table>
      <div v-if="!stockLogs.length" class="p-6 text-center text-muted text-sm">暂无日志</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { RotateCcw } from 'lucide-vue-next'
import { useFormat } from '../../composables/useFormat'
import { useSort } from '../../composables/useSort'
import { usePagination } from '../../composables/usePagination'
import { getStockLogs } from '../../api/finance'
import StatusBadge from '../common/StatusBadge.vue'

const { fmtDate } = useFormat()
const { sortState: logSort, toggleSort: toggleLogSort, genericSort: genericSortLog } = useSort()
const { page, pageSize, total, totalPages, hasPagination, paginationParams, visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage } = usePagination(20)

const stockLogs = ref([])
const logFilter = reactive({ type: '', start: '', end: '', search: '' })

const sortedLogs = computed(() => {
  return genericSortLog(stockLogs.value, {
    product: l => (l.product_name || '').toLowerCase(),
    warehouse: l => (l.warehouse_name || '').toLowerCase(),
    type: l => l.change_type || '',
    quantity: l => l.quantity || 0,
    time: l => l.created_at || ''
  })
})

const loadLogs = async () => {
  try {
    const params = { ...paginationParams.value }
    if (logFilter.type) params.change_type = logFilter.type
    if (logFilter.start) params.start_date = logFilter.start
    if (logFilter.end) params.end_date = logFilter.end
    if (logFilter.search) params.search = logFilter.search
    const { data } = await getStockLogs(params)
    stockLogs.value = data.items || data
    total.value = data.total ?? 0
  } catch (e) {
    console.error(e)
  }
}

let _logSearchTimer = null
const debouncedLoadLogs = () => {
  clearTimeout(_logSearchTimer)
  resetPage()
  _logSearchTimer = setTimeout(loadLogs, 300)
}

const resetLogFilters = () => {
  logFilter.type = ''
  logFilter.start = ''
  logFilter.end = ''
  logFilter.search = ''
  resetPage()
  loadLogs()
}

defineExpose({ refresh: loadLogs })

onMounted(() => { loadLogs() })
onUnmounted(() => clearTimeout(_logSearchTimer))
</script>
