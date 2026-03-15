<!--
  库存管理视图（瘦容器）
  职责：工具栏 + 搜索 + 卡片/表格列表 + 5个弹窗组件协调
-->
<template>
  <div>
    <!-- 工具栏 -->
    <div class="flex flex-wrap items-center gap-2 mb-2">
      <select v-model="stockWarehouseFilter" @change="resetPage(); loadProductsData()" class="input text-sm" style="width:130px">
        <option value="">全部仓库</option>
        <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
        <template v-if="showVirtualStock">
          <option v-for="vw in virtualWarehouses" :key="'v' + vw.id" :value="vw.id">{{ vw.name }}</option>
        </template>
      </select>
      <label class="flex items-center gap-1.5 text-xs text-muted cursor-pointer whitespace-nowrap select-none">
        <span class="toggle">
          <input type="checkbox" v-model="showVirtualStock" @change="onToggleVirtualStock">
          <span class="slider"></span>
        </span>
        寄售
      </label>
      <div class="flex-1"></div>
      <button @click="openPurchaseReceive" class="btn btn-success btn-sm" v-if="hasPermission('purchase_receive')">采购收货</button>
      <button @click="showRestockModal = true" class="btn btn-primary btn-sm" v-if="hasPermission('stock_edit')">入库</button>
      <button @click="openProductModal()" class="btn btn-secondary btn-sm" v-if="hasPermission('stock_edit')">新增商品</button>
      <button @click="showImportModal = true" class="btn btn-secondary btn-sm hidden md:inline-block" v-if="hasPermission('stock_edit')">导入</button>
      <button @click="handleExportStock" class="btn btn-secondary btn-sm hidden md:inline-block">导出</button>
    </div>

    <!-- 搜索框 -->
    <div class="mb-3">
      <input v-model="productSearch" @input="debouncedSearch" class="input text-sm" placeholder="搜索商品名称、SKU、品牌...">
    </div>

    <!-- 移动端卡片视图 -->
    <div class="md:hidden space-y-2">
      <template v-for="p in stockProducts" :key="'m' + p.id">
        <div
          v-for="(s, idx) in (p.stocks?.length ? (showVirtualStock ? p.stocks : p.stocks.filter(x => !x.is_virtual)) : [])"
          :key="'m' + p.id + '-' + idx"
          class="card p-3"
          :class="{ 'bg-purple-subtle': s.is_virtual }"
        >
          <div class="flex justify-between items-start mb-1.5">
            <div class="flex-1 min-w-0 mr-2">
              <div class="font-medium text-sm truncate">
                <span v-if="!s.is_virtual && s.quantity < 10" class="todo-dot mr-1"></span>{{ p.name }}
              </div>
              <div class="text-xs text-muted font-mono">
                {{ p.sku }}
                <span v-if="p.brand" class="text-muted ml-1">· {{ p.brand }}</span>
              </div>
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-lg font-bold" :class="s.is_virtual ? 'text-purple-emphasis' : 'text-foreground'">{{ s.quantity }}</div>
              <div class="text-xs text-muted">库存</div>
              <div v-if="(s.reserved_qty || 0) > 0" class="text-xs text-warning">预留 {{ s.reserved_qty }} / 可用 {{ s.available_qty ?? s.quantity }}</div>
            </div>
          </div>
          <div class="flex justify-between items-center">
            <div class="flex items-center gap-1.5 text-xs">
              <span :class="s.is_virtual ? 'badge badge-purple' : 'badge badge-blue'">{{ s.is_virtual ? '寄售' : (s.location_code || '-') }}</span>
              <span class="text-muted">{{ s.warehouse_name }}</span>
              <span v-if="!s.is_virtual" :class="getAgeClass(p.age_days)" class="ml-1">{{ p.age_days }}天</span>
            </div>
            <div class="flex items-center gap-2 text-xs flex-shrink-0">
              <template v-if="!s.is_virtual">
                <button @click="openProductModal(p)" class="text-primary">编辑</button>
                <button v-if="hasPermission('stock_edit')" @click="openTransferModal(p, s)" class="text-success">调拨</button>
              </template>
              <span v-else class="text-muted">只读</span>
            </div>
          </div>
        </div>
      </template>
      <div v-if="!hasStockProducts" class="p-8 text-center text-muted text-sm">暂无库存商品</div>
    </div>

    <!-- 桌面表格视图 -->
    <div class="card hidden md:block">
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th v-if="isColumnVisible('brand')" class="px-3 py-2 text-left w-24 cursor-pointer select-none hover:text-primary" @click="toggleStockSort('brand')">
                品牌 <span v-if="stockSort.key === 'brand'" class="text-primary">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('name')" class="px-3 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleStockSort('name')">
                商品名称 <span v-if="stockSort.key === 'name'" class="text-primary">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('warehouse')" class="px-3 py-2 text-left cursor-pointer select-none hover:text-primary" @click="toggleStockSort('warehouse')">
                仓位 <span v-if="stockSort.key === 'warehouse'" class="text-primary">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('retail_price')" class="px-3 py-2 text-right cursor-pointer select-none hover:text-primary" @click="toggleStockSort('retail_price')">
                零售价 <span v-if="stockSort.key === 'retail_price'" class="text-primary">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="hasPermission('finance') && isColumnVisible('cost_price')" class="px-3 py-2 text-right cursor-pointer select-none hover:text-primary" @click="toggleStockSort('cost_price')">
                成本 <span v-if="stockSort.key === 'cost_price'" class="text-primary">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('quantity')" class="px-3 py-2 text-right cursor-pointer select-none hover:text-primary" @click="toggleStockSort('quantity')">
                库存 <span v-if="stockSort.key === 'quantity'" class="text-primary">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('reserved_qty')" class="px-3 py-2 text-right">预留</th>
              <th v-if="isColumnVisible('available_qty')" class="px-3 py-2 text-right">可用</th>
              <th v-if="isColumnVisible('age_days')" class="px-3 py-2 text-center cursor-pointer select-none hover:text-primary" @click="toggleStockSort('age')">
                库龄 <span v-if="stockSort.key === 'age'" class="text-primary">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="isColumnVisible('actions')" class="px-3 py-2 text-center">操作</th>
              <!-- 列选择器 -->
              <th class="col-selector-th">
                <ColumnMenu :labels="columnLabels" :visible="visibleColumns" pinned="name"
                  @toggle="toggleColumn" @reset="resetColumns" />
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr
              v-for="(row, idx) in sortedStockRows"
              :key="row.p.id + '-' + idx"
              class="hover:bg-elevated"
              :class="{ 'bg-purple-subtle': row.s.is_virtual }"
            >
              <td v-if="isColumnVisible('brand')" class="px-3 py-2 text-secondary text-xs">{{ row.p.brand || '-' }}</td>
              <td v-if="isColumnVisible('name')" class="px-3 py-2">
                <div class="font-medium">
                  <span v-if="!row.s.is_virtual && row.s.quantity < 10" class="todo-dot mr-1.5"></span>{{ row.p.name }}
                </div>
                <div class="text-xs text-muted font-mono mt-0.5">{{ row.p.sku }}</div>
              </td>
              <td v-if="isColumnVisible('warehouse')" class="px-3 py-2">
                <span :class="row.s.is_virtual ? 'badge badge-purple' : 'badge badge-blue'">{{ row.s.is_virtual ? '寄售' : (row.s.location_code || '-') }}</span>
                <div class="text-xs text-muted">{{ row.s.warehouse_name }}</div>
              </td>
              <td v-if="isColumnVisible('retail_price')" class="px-3 py-2 text-right">{{ row.p.retail_price }}</td>
              <td v-if="hasPermission('finance') && isColumnVisible('cost_price')" class="px-3 py-2 text-right">{{ row.p.cost_price }}</td>
              <td v-if="isColumnVisible('quantity')" class="px-3 py-2 text-right font-semibold" :class="{ 'text-purple-emphasis': row.s.is_virtual }">{{ row.s.quantity }}</td>
              <td v-if="isColumnVisible('reserved_qty')" class="px-3 py-2 text-right" :class="(row.s.reserved_qty || 0) > 0 ? 'text-warning font-semibold' : 'text-muted'">{{ row.s.reserved_qty || 0 }}</td>
              <td v-if="isColumnVisible('available_qty')" class="px-3 py-2 text-right" :class="(row.s.available_qty ?? row.s.quantity) < (row.s.reserved_qty || 0) ? 'text-error font-semibold' : 'text-success font-semibold'">{{ row.s.available_qty ?? row.s.quantity }}</td>
              <td v-if="isColumnVisible('age_days')" class="px-3 py-2 text-center">
                <span :class="getAgeClass(row.p.age_days)">{{ row.p.age_days }}天</span>
              </td>
              <td v-if="isColumnVisible('actions')" class="px-3 py-2 text-center">
                <template v-if="!row.s.is_virtual">
                  <button @click="openProductModal(row.p)" class="text-primary text-xs mr-2">编辑</button>
                  <button v-if="hasPermission('stock_edit')" @click="openTransferModal(row.p, row.s)" class="text-success text-xs">调拨</button>
                </template>
                <span v-else class="text-xs text-muted">只读</span>
              </td>
              <td></td>
            </tr>
          </tbody>
          <tfoot v-if="hasPagination" class="bg-elevated text-sm">
            <tr>
              <td :colspan="100" class="px-3.5 py-2.5">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-muted">共 {{ pageItemCount }} 条</span>
                  <div class="flex items-center gap-1">
                    <button @click="prevPage(); loadProductsData()" :disabled="page <= 1" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">‹</button>
                    <template v-for="(p, i) in visiblePages" :key="i">
                      <span v-if="p === '…'" class="w-7 h-7 flex items-center justify-center text-xs text-muted cursor-default">…</span>
                      <button v-else @click="goToPage(p); loadProductsData()" :class="p === page ? 'bg-primary text-white font-medium' : 'text-muted hover:bg-surface-hover hover:text-text'" class="w-7 h-7 flex items-center justify-center rounded-md text-xs">{{ p }}</button>
                    </template>
                    <button @click="nextPage(); loadProductsData()" :disabled="page >= totalPages" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">›</button>
                  </div>
                  <span class="text-xs text-muted w-16"></span>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      <div v-if="!hasStockProducts" class="p-8 text-center text-muted text-sm">暂无库存商品</div>
    </div>

    <!-- 商品新增/编辑弹窗 -->
    <ProductFormModal
      v-model:visible="showProductModal"
      :product="editingProduct"
      @saved="loadProductsData"
    />

    <!-- 入库弹窗 -->
    <RestockModal
      v-model:visible="showRestockModal"
      @saved="loadProductsData"
    />

    <!-- 调拨弹窗 -->
    <TransferModal
      v-model:visible="showTransferModal"
      :product="transferProduct"
      :from-stock="transferFromStock"
      @saved="loadProductsData"
    />

    <!-- 导入弹窗 -->
    <ImportModal
      v-model:visible="showImportModal"
      @preview="onImportPreview"
    />

    <!-- 导入预览弹窗 -->
    <ImportPreviewModal
      v-model:visible="showImportPreviewModal"
      :preview-data="importPreviewData"
      :file="importFile"
      @confirmed="onImportConfirmed"
      @cancelled="onImportCancelled"
    />
  </div>
</template>

<script setup>
/**
 * 库存管理页面 — 瘦容器
 * 列表逻辑委托给 useStock composable
 * 5个弹窗拆分为独立子组件，各自管理表单状态
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useWarehousesStore } from '../stores/warehouses'
import { useFormat } from '../composables/useFormat'
import { usePermission } from '../composables/usePermission'
import { useStock } from '../composables/useStock'
import ColumnMenu from '../components/common/ColumnMenu.vue'

// 弹窗子组件
import ProductFormModal from '../components/business/stock/ProductFormModal.vue'
import RestockModal from '../components/business/stock/RestockModal.vue'
import TransferModal from '../components/business/stock/TransferModal.vue'
import ImportModal from '../components/business/stock/ImportModal.vue'
import ImportPreviewModal from '../components/business/stock/ImportPreviewModal.vue'

const router = useRouter()
const warehousesStore = useWarehousesStore()
const { getAgeClass } = useFormat()
const { hasPermission } = usePermission()

// 从 composable 获取列表数据和方法
const {
  warehouses, stockWarehouseFilter, showVirtualStock, virtualWarehouses,
  productSearch, stockSort, toggleStockSort,
  stockProducts, sortedStockRows, hasStockProducts,
  loadProductsData, debouncedSearch, onToggleVirtualStock, handleExportStock,
  page, total, totalPages, hasPagination, visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage,
  columnLabels, visibleColumns, showColumnMenu, menuAttr,
  toggleColumn, isColumnVisible, resetColumns,
} = useStock()

// ---- 弹窗可见性 ----
const showProductModal = ref(false)
const showRestockModal = ref(false)
const showTransferModal = ref(false)
const showImportModal = ref(false)
const showImportPreviewModal = ref(false)

// ---- 弹窗数据 ----
/** 当前正在编辑的商品（null=新增） */
const editingProduct = ref(null)
/** 调拨目标商品 */
const transferProduct = ref(null)
/** 调拨源库存信息 */
const transferFromStock = ref(null)
/** 导入文件 */
const importFile = ref(null)
/** 导入预览数据 */
const importPreviewData = ref({ total: 0, valid_count: 0, skip_count: 0, items: [] })

// ---- 初始化 ----
onMounted(() => {
  loadProductsData()
  warehousesStore.loadWarehouses()
})

// ---- 弹窗控制方法 ----

/** 打开商品弹窗（新增或编辑） */
const openProductModal = (product = null) => {
  editingProduct.value = product
  showProductModal.value = true
}

/** 打开调拨弹窗 */
const openTransferModal = (product, stock) => {
  transferProduct.value = product
  transferFromStock.value = stock
  showTransferModal.value = true
}

/** 导入弹窗 → 预览弹窗切换 */
const onImportPreview = ({ file, previewData }) => {
  importFile.value = file
  importPreviewData.value = previewData
  showImportModal.value = false
  showImportPreviewModal.value = true
}

/** 导入确认后刷新列表 */
const onImportConfirmed = () => {
  showImportPreviewModal.value = false
  loadProductsData()
}

/** 导入预览取消 → 回到导入弹窗 */
const onImportCancelled = () => {
  showImportPreviewModal.value = false
  importFile.value = null
  importPreviewData.value = { total: 0, valid_count: 0, skip_count: 0, items: [] }
  showImportModal.value = true
}

/** 跳转采购收货页面 */
const openPurchaseReceive = () => {
  router.push({ path: '/purchase', query: { action: 'receive' } })
}
</script>
