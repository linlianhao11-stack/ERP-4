<template>
  <div class="card">
    <div class="p-3 border-b flex flex-wrap gap-2">
      <select v-model="logFilter.type" @change="loadLogs" class="input w-auto text-sm">
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
    </div>
    <div class="overflow-x-auto table-container">
      <table class="w-full text-sm">
        <thead class="bg-[#f5f5f7]">
          <tr>
            <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleLogSort('product')">商品 <span v-if="logSort.key === 'product'" class="text-[#0071e3]">{{ logSort.order === 'asc' ? '↑' : '↓' }}</span></th>
            <th class="px-2 py-2 text-left md-hide cursor-pointer select-none hover:text-[#0071e3]" @click="toggleLogSort('warehouse')">仓库 <span v-if="logSort.key === 'warehouse'" class="text-[#0071e3]">{{ logSort.order === 'asc' ? '↑' : '↓' }}</span></th>
            <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleLogSort('type')">类型 <span v-if="logSort.key === 'type'" class="text-[#0071e3]">{{ logSort.order === 'asc' ? '↑' : '↓' }}</span></th>
            <th class="px-2 py-2 text-right cursor-pointer select-none hover:text-[#0071e3]" @click="toggleLogSort('quantity')">数量 <span v-if="logSort.key === 'quantity'" class="text-[#0071e3]">{{ logSort.order === 'asc' ? '↑' : '↓' }}</span></th>
            <th class="px-2 py-2 text-center md-hide">库存变化</th>
            <th class="px-2 py-2 text-left md-hide">备注</th>
            <th class="px-2 py-2 text-left md-hide">操作人</th>
            <th class="px-2 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleLogSort('time')">时间 <span v-if="logSort.key === 'time'" class="text-[#0071e3]">{{ logSort.order === 'asc' ? '↑' : '↓' }}</span></th>
          </tr>
        </thead>
        <tbody class="divide-y">
          <tr v-for="l in sortedLogs" :key="l.id">
            <td class="px-2 py-2"><div>{{ l.product_name }}</div><div class="text-xs text-[#86868b]">{{ l.product_sku }}</div></td>
            <td class="px-2 py-2 md-hide">{{ l.warehouse_name }}</td>
            <td class="px-2 py-2"><StatusBadge type="logType" :status="l.change_type" :label="l.change_type_name" /></td>
            <td class="px-2 py-2 text-right font-semibold" :class="l.quantity > 0 ? 'text-[#34c759]' : 'text-[#ff3b30]'">{{ l.quantity > 0 ? '+' : '' }}{{ l.quantity }}</td>
            <td class="px-2 py-2 text-center text-[#86868b] md-hide">{{ l.before_qty }}→{{ l.after_qty }}</td>
            <td class="px-2 py-2 text-[#86868b] text-xs max-w-24 truncate md-hide">{{ l.remark }}</td>
            <td class="px-2 py-2 text-[#86868b] md-hide">{{ l.creator_name }}</td>
            <td class="px-2 py-2 text-[#86868b] text-xs">{{ fmtDate(l.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!stockLogs.length" class="p-6 text-center text-[#86868b] text-sm">暂无日志</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useFormat } from '../../composables/useFormat'
import { useSort } from '../../composables/useSort'
import { getStockLogs } from '../../api/finance'
import StatusBadge from '../common/StatusBadge.vue'

const { fmtDate } = useFormat()
const { sortState: logSort, toggleSort: toggleLogSort, genericSort: genericSortLog } = useSort()

const stockLogs = ref([])
const logFilter = reactive({ type: '' })

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
    const params = {}
    if (logFilter.type) params.change_type = logFilter.type
    const { data } = await getStockLogs(params)
    stockLogs.value = data
  } catch (e) {
    console.error(e)
  }
}

defineExpose({ refresh: loadLogs })

onMounted(() => { loadLogs() })
</script>
