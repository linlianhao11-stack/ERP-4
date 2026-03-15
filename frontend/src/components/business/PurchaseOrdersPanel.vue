<template>
  <div>
    <!-- 移动端卡片列表 -->
    <div class="md:hidden space-y-2">
      <!-- 移动端筛选 -->
      <div class="flex flex-wrap items-center gap-2 mb-2">
        <select v-model="purchaseStatusFilter" @change="resetPage(); loadPurchaseOrders()" class="toolbar-select flex-1">
          <option value="">全部状态</option>
          <option value="pending_review">待审核</option>
          <option value="pending">待付款</option>
          <option value="paid">在途</option>
          <option value="partial">部分到货</option>
          <option value="completed">已完成</option>
          <option value="returned">已退货</option>
          <option value="rejected">已拒绝</option>
        </select>
        <div class="toolbar-search-wrapper flex-1" style="max-width:none">
          <Search :size="14" class="toolbar-search-icon" />
          <input v-model="purchaseSearch" @input="debouncedLoad" class="toolbar-search" placeholder="搜索单号/供应商...">
        </div>
      </div>
      <div v-for="o in purchaseOrders" :key="o.id" class="card p-3" @click="detailRef?.viewPurchaseOrder(o.id)">
        <div class="flex justify-between items-start mb-1">
          <div class="font-medium text-sm font-mono">
            <span v-if="['pending_review','paid','partial'].includes(o.status)" class="todo-dot mr-1"></span>{{ o.po_no }}
          </div>
          <div class="text-lg font-bold text-primary">¥{{ fmt(o.total_amount) }}</div>
        </div>
        <div class="flex justify-between items-center text-xs">
          <div class="text-muted">{{ o.supplier_name }}</div>
          <StatusBadge type="purchaseStatus" :status="o.status" />
        </div>
        <div class="text-xs text-muted mt-1">{{ fmtDate(o.created_at) }} · {{ o.creator_name }}</div>
      </div>
      <div v-if="!purchaseOrders.length" class="p-8 text-center text-muted text-sm">暂无采购订单</div>
    </div>

    <!-- 桌面端表格 -->
    <div class="card hidden md:block" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="purchaseStatusFilter" @change="resetPage(); loadPurchaseOrders()" class="toolbar-select">
            <option value="">全部状态</option>
            <option value="pending_review">待审核</option>
            <option value="pending">待付款</option>
            <option value="paid">在途</option>
            <option value="partial">部分到货</option>
            <option value="completed">已完成</option>
            <option value="returned">已退货</option>
            <option value="rejected">已拒绝</option>
          </select>
          <select v-if="accountSets.length" v-model="purchaseAccountSetFilter" @change="resetPage(); loadPurchaseOrders()" class="toolbar-select">
            <option value="">全部账套</option>
            <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
          <DateRangePicker v-model:start="purchaseDateStart" v-model:end="purchaseDateEnd" @change="resetPage(); loadPurchaseOrders()" />
          <div class="toolbar-search-wrapper">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="purchaseSearch" @input="debouncedLoad" class="toolbar-search" placeholder="搜索单号/供应商...">
          </div>
        </template>
        <template #actions>
          <SegmentedControl v-model="viewMode" :options="viewModeOptions" @update:model-value="setViewMode($event)" />
          <button v-if="hasPermission('purchase')" @click="showPOCreateModal = true" class="btn btn-primary btn-sm">
            <Plus :size="14" /> 新建
          </button>
          <button v-if="hasPermission('purchase_receive')" @click="detailRef?.openReceive()" class="btn btn-success btn-sm">采购收货</button>
          <button @click="handleExport" class="btn btn-secondary btn-sm">导出</button>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th v-if="viewMode === 'summary'" class="px-3 py-2 w-6"></th>
              <th v-if="isColumnVisible('po_no')" class="px-3 py-2 text-left cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('po_no')">采购单号 <span v-if="purchaseSort.key === 'po_no'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('supplier')" class="px-3 py-2 text-left cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('supplier')">供应商 <span v-if="purchaseSort.key === 'supplier'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('date')" class="px-3 py-2 text-left cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('date')">采购日期 <span v-if="purchaseSort.key === 'date'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('total_amount')" class="px-3 py-2 text-right cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('total_amount')">总金额 <span v-if="purchaseSort.key === 'total_amount'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('tax_amount')" class="px-3 py-2 text-right">含税金额</th>
              <th v-if="isColumnVisible('item_count')" class="px-3 py-2 text-center">品项数</th>
              <th v-if="isColumnVisible('status')" class="px-3 py-2 text-center cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('status')">状态 <span v-if="purchaseSort.key === 'status'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('remark')" class="px-3 py-2 text-left">备注</th>
              <th v-if="isColumnVisible('creator')" class="px-3 py-2 text-left cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('creator')">创建人 <span v-if="purchaseSort.key === 'creator'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('account_set')" class="px-3 py-2 text-left">账套</th>
              <th v-if="isColumnVisible('return_amount')" class="px-3 py-2 text-right">退货金额</th>
              <th v-if="isColumnVisible('target_warehouse')" class="px-3 py-2 text-left">目标仓库</th>
              <th v-if="isColumnVisible('target_location')" class="px-3 py-2 text-left">目标仓位</th>
              <th v-if="isColumnVisible('rebate_used')" class="px-3 py-2 text-right">返利已用</th>
              <th v-if="isColumnVisible('credit_used')" class="px-3 py-2 text-right">在账资金</th>
              <th v-if="isColumnVisible('reviewer')" class="px-3 py-2 text-left">审核人</th>
              <th v-if="isColumnVisible('reviewed_at')" class="px-3 py-2 text-left">审核时间</th>
              <th v-if="isColumnVisible('payment_method')" class="px-3 py-2 text-left">付款方式</th>
              <!-- 列选择器 -->
              <th class="col-selector-th">
                <ColumnMenu :labels="columnLabels" :visible="visibleColumns" pinned="po_no"
                  @toggle="toggleColumn" @reset="resetColumns" />
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <template v-for="o in sortedPurchaseOrders" :key="o.id">
              <tr class="hover:bg-elevated cursor-pointer" @click="detailRef?.viewPurchaseOrder(o.id)">
                <td v-if="viewMode === 'summary'" class="px-1 py-2 text-center text-muted" @click="toggleExpand(o.id, $event)">
                  <span class="cursor-pointer">{{ expandedRows[o.id] ? '▼' : '▶' }}</span>
                </td>
                <td v-if="isColumnVisible('po_no')" class="px-3 py-2 font-mono text-sm">
                  <span v-if="['pending_review','paid','partial'].includes(o.status)" class="todo-dot mr-1.5"></span>{{ o.po_no }}
                </td>
                <td v-if="isColumnVisible('supplier')" class="px-3 py-2">{{ o.supplier_name }}</td>
                <td v-if="isColumnVisible('date')" class="px-3 py-2 text-muted text-xs">{{ fmtDate(o.created_at) }}</td>
                <td v-if="isColumnVisible('total_amount')" class="px-3 py-2 text-right font-semibold">¥{{ fmt(o.total_amount) }}</td>
                <td v-if="isColumnVisible('tax_amount')" class="px-3 py-2 text-right">¥{{ fmt(o.tax_amount) }}</td>
                <td v-if="isColumnVisible('item_count')" class="px-3 py-2 text-center">{{ o.item_count }}</td>
                <td v-if="isColumnVisible('status')" class="px-3 py-2 text-center"><StatusBadge type="purchaseStatus" :status="o.status" /></td>
                <td v-if="isColumnVisible('remark')" class="px-3 py-2 text-muted text-xs max-w-[150px] truncate">{{ o.remark || '-' }}</td>
                <td v-if="isColumnVisible('creator')" class="px-3 py-2 text-secondary">{{ o.creator_name }}</td>
                <td v-if="isColumnVisible('account_set')" class="px-3 py-2">{{ o.account_set_name || '-' }}</td>
                <td v-if="isColumnVisible('return_amount')" class="px-3 py-2 text-right">{{ o.return_amount ? '¥' + fmt(o.return_amount) : '-' }}</td>
                <td v-if="isColumnVisible('target_warehouse')" class="px-3 py-2">{{ o.target_warehouse_name || '-' }}</td>
                <td v-if="isColumnVisible('target_location')" class="px-3 py-2">{{ o.target_location_code || '-' }}</td>
                <td v-if="isColumnVisible('rebate_used')" class="px-3 py-2 text-right">{{ o.rebate_used ? '¥' + fmt(o.rebate_used) : '-' }}</td>
                <td v-if="isColumnVisible('credit_used')" class="px-3 py-2 text-right">{{ o.credit_used ? '¥' + fmt(o.credit_used) : '-' }}</td>
                <td v-if="isColumnVisible('reviewer')" class="px-3 py-2">{{ o.reviewed_by_name || '-' }}</td>
                <td v-if="isColumnVisible('reviewed_at')" class="px-3 py-2 text-xs text-muted">{{ o.reviewed_at ? fmtDate(o.reviewed_at) : '-' }}</td>
                <td v-if="isColumnVisible('payment_method')" class="px-3 py-2">{{ o.payment_method || '-' }}</td>
                <td></td>
              </tr>
              <!-- 展开行：物料明细子表 -->
              <tr v-if="(viewMode === 'summary' && expandedRows[o.id]) || viewMode === 'detail'">
                <td :colspan="100" class="bg-elevated/50 px-6 py-3">
                  <div v-if="loadingItems[o.id]" class="text-center text-muted text-sm py-2">加载中...</div>
                  <table v-else-if="expandedItems[o.id]?.length" class="w-full text-xs">
                    <thead>
                      <tr class="text-muted border-b">
                        <th class="px-2 py-1.5 text-left font-medium">物料编码</th>
                        <th class="px-2 py-1.5 text-left font-medium">物料名称</th>
                        <th class="px-2 py-1.5 text-left font-medium">规格型号</th>
                        <th class="px-2 py-1.5 text-center font-medium">数量</th>
                        <th class="px-2 py-1.5 text-right font-medium">单价</th>
                        <th class="px-2 py-1.5 text-right font-medium">含税单价</th>
                        <th class="px-2 py-1.5 text-right font-medium">价税合计</th>
                        <th class="px-2 py-1.5 text-center font-medium">已收货</th>
                        <th class="px-2 py-1.5 text-center font-medium">已退货</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-border-light">
                      <tr v-for="item in expandedItems[o.id]" :key="item.id">
                        <td class="px-2 py-1.5 text-primary font-mono">{{ item.product_sku }}</td>
                        <td class="px-2 py-1.5">{{ item.product_name }}</td>
                        <td class="px-2 py-1.5 text-muted">{{ item.spec || '-' }}</td>
                        <td class="px-2 py-1.5 text-center">{{ item.quantity }}</td>
                        <td class="px-2 py-1.5 text-right">¥{{ fmt(item.tax_exclusive_price) }}</td>
                        <td class="px-2 py-1.5 text-right">¥{{ fmt(item.tax_inclusive_price) }}</td>
                        <td class="px-2 py-1.5 text-right font-medium">¥{{ fmt(item.amount) }}</td>
                        <td class="px-2 py-1.5 text-center">{{ item.received_quantity }}</td>
                        <td class="px-2 py-1.5 text-center">{{ item.returned_quantity || '-' }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-else class="text-muted text-sm text-center py-2">暂无明细</div>
                </td>
              </tr>
            </template>
          </tbody>
          <tfoot v-if="sortedPurchaseOrders.length > 0" class="bg-elevated font-semibold text-sm border-t">
            <tr>
              <td v-if="viewMode === 'summary'" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('po_no')" class="px-3 py-2 text-left">本页合计</td>
              <td v-if="isColumnVisible('supplier')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('date')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('total_amount')" class="px-3 py-2 text-right">¥{{ fmt(pageSummary.total_amount) }}</td>
              <td v-if="isColumnVisible('tax_amount')" class="px-3 py-2 text-right">¥{{ fmt(pageSummary.tax_amount) }}</td>
              <td v-if="isColumnVisible('item_count')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('status')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('remark')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('creator')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('account_set')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('return_amount')" class="px-3 py-2 text-right">¥{{ fmt(pageSummary.return_amount) }}</td>
              <td v-if="isColumnVisible('target_warehouse')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('target_location')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('rebate_used')" class="px-3 py-2 text-right">¥{{ fmt(pageSummary.rebate_used) }}</td>
              <td v-if="isColumnVisible('credit_used')" class="px-3 py-2 text-right">¥{{ fmt(pageSummary.credit_used) }}</td>
              <td v-if="isColumnVisible('reviewer')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('reviewed_at')" class="px-3 py-2"></td>
              <td v-if="isColumnVisible('payment_method')" class="px-3 py-2"></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div v-if="!purchaseOrders.length" class="p-8 text-center text-muted text-sm">暂无采购订单</div>
    </div>
    <!-- 分页 -->
    <div v-if="hasPagination" class="flex items-center justify-center gap-2 py-3">
      <button @click="prevPage(); loadPurchaseOrders()" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ totalPages }}</span>
      <button @click="nextPage(); loadPurchaseOrders()" :disabled="page >= totalPages" class="btn btn-secondary btn-sm">下一页</button>
    </div>

    <!-- 新建采购单弹窗（子组件） -->
    <PurchaseOrderForm
      ref="formRef"
      :visible="showPOCreateModal"
      @update:visible="showPOCreateModal = $event"
      :account-sets="accountSets"
      @saved="onFormSaved"
    />

    <!-- 详情/收货/退货弹窗（子组件） -->
    <PurchaseOrderDetail
      ref="detailRef"
      @data-changed="onDetailChanged"
    />
  </div>
</template>

<script setup>
/**
 * 采购订单面板（瘦容器）
 * 负责筛选栏、列表展示，将弹窗逻辑委托给子组件
 */
import { ref, reactive, watch, onMounted, computed } from 'vue'
import { Search, Plus } from 'lucide-vue-next'
import ColumnMenu from '../common/ColumnMenu.vue'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { usePurchaseOrder } from '../../composables/usePurchaseOrder'
import { getPurchaseOrderItems } from '../../api/purchase'
import { getAccountSets } from '../../api/accounting'
import { useProductsStore } from '../../stores/products'
import { useWarehousesStore } from '../../stores/warehouses'
import StatusBadge from '../common/StatusBadge.vue'
import PageToolbar from '../common/PageToolbar.vue'
import DateRangePicker from '../common/DateRangePicker.vue'
import SegmentedControl from '../common/SegmentedControl.vue'
import PurchaseOrderForm from './purchase/PurchaseOrderForm.vue'
import PurchaseOrderDetail from './purchase/PurchaseOrderDetail.vue'

const emit = defineEmits(['data-changed'])

const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()

const viewModeOptions = [
  { value: 'summary', label: '汇总' },
  { value: 'detail', label: '明细' }
]

// 使用 composable 管理列表逻辑
const {
  purchaseOrders, purchaseStatusFilter, purchaseAccountSetFilter,
  purchaseDateStart, purchaseDateEnd, purchaseSearch,
  loadPurchaseOrders, debouncedLoad, handleExport,
  page, totalPages, hasPagination, resetPage, prevPage, nextPage,
  // 排序
  purchaseSort, togglePurchaseSort, sortedPurchaseOrders,
  // 列配置
  columnLabels, visibleColumns, showColumnMenu, menuAttr,
  toggleColumn, isColumnVisible, resetColumns,
  viewMode, setViewMode,
} = usePurchaseOrder()

/** 本页合计 */
const pageSummary = computed(() => {
  const rows = sortedPurchaseOrders.value
  const sum = { total_amount: 0, tax_amount: 0, return_amount: 0, rebate_used: 0, credit_used: 0 }
  for (const o of rows) {
    sum.total_amount += Number(o.total_amount) || 0
    sum.tax_amount += Number(o.tax_amount) || 0
    sum.return_amount += Number(o.return_amount) || 0
    sum.rebate_used += Number(o.rebate_used) || 0
    sum.credit_used += Number(o.credit_used) || 0
  }
  for (const k in sum) sum[k] = Math.round(sum[k] * 100) / 100
  return sum
})

// 展开行状态
const expandedRows = reactive({})
const expandedItems = reactive({})
const loadingItems = reactive({})

const toggleExpand = async (orderId, e) => {
  e?.stopPropagation()
  if (expandedRows[orderId]) {
    delete expandedRows[orderId]
    return
  }
  expandedRows[orderId] = true
  if (!expandedItems[orderId]) {
    loadingItems[orderId] = true
    try {
      const { data } = await getPurchaseOrderItems(orderId)
      expandedItems[orderId] = data
    } catch (err) {
      console.error(err)
    } finally {
      loadingItems[orderId] = false
    }
  }
}

/** 明细模式：自动加载所有订单的物料明细 */
const loadAllItems = async () => {
  const orders = sortedPurchaseOrders.value
  await Promise.all(orders.map(async (o) => {
    if (!expandedItems[o.id]) {
      loadingItems[o.id] = true
      try {
        const { data } = await getPurchaseOrderItems(o.id)
        expandedItems[o.id] = data
      } catch (err) { console.error(err) }
      finally { loadingItems[o.id] = false }
    }
  }))
}

watch(viewMode, (mode) => {
  if (mode === 'detail') loadAllItems()
})

// 财务账套列表
const accountSets = ref([])

// 新建采购单弹窗可见性
const showPOCreateModal = ref(false)

// 子组件引用
const formRef = ref(null)
const detailRef = ref(null)

/** 新建采购单保存后：刷新列表和供应商 */
const onFormSaved = () => {
  loadPurchaseOrders()
  formRef.value?.loadSuppliers()
  emit('data-changed')
}

/** 详情/收货/退货操作后：刷新列表 */
const onDetailChanged = () => {
  loadPurchaseOrders()
  emit('data-changed')
}

// 暴露给父组件（PurchaseView）的方法，保持接口不变
defineExpose({
  refresh: loadPurchaseOrders,
  viewPurchaseOrder: (id) => detailRef.value?.viewPurchaseOrder(id),
  openPurchaseReceive: () => detailRef.value?.openReceive()
})

onMounted(async () => {
  loadPurchaseOrders()
  productsStore.loadProducts()
  warehousesStore.loadWarehouses()
  warehousesStore.loadLocations()
  try {
    const { data } = await getAccountSets()
    accountSets.value = data
  } catch (e) { /* ignore */ }
})
</script>
