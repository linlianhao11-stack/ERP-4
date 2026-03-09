<template>
  <div>
    <!-- 筛选栏 -->
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="purchaseStatusFilter" @change="resetPage(); loadPurchaseOrders()" class="input text-sm" style="width:120px">
        <option value="">全部状态</option>
        <option value="pending_review">待审核</option>
        <option value="pending">待付款</option>
        <option value="paid">在途</option>
        <option value="partial">部分到货</option>
        <option value="completed">已完成</option>
        <option value="returned">已退货</option>
        <option value="rejected">已拒绝</option>
      </select>
      <select v-if="accountSets.length" v-model="purchaseAccountSetFilter" @change="resetPage(); loadPurchaseOrders()" class="input text-sm" style="width:120px">
        <option value="">全部账套</option>
        <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <input type="date" v-model="purchaseDateStart" @change="resetPage(); loadPurchaseOrders()" class="input text-sm" style="width:130px">
      <input type="date" v-model="purchaseDateEnd" @change="resetPage(); loadPurchaseOrders()" class="input text-sm" style="width:130px">
      <input v-model="purchaseSearch" @input="debouncedLoad" class="input text-sm flex-1" placeholder="搜索单号/供应商..." style="min-width:120px">
      <button v-if="hasPermission('stock_edit')" @click="formRef?.openProductModal()" class="btn btn-success btn-sm">新建商品</button>
      <button @click="showPOCreateModal = true" class="btn btn-primary btn-sm" v-if="hasPermission('purchase')">新建采购单</button>
      <button @click="detailRef?.openReceive()" class="btn btn-success btn-sm" v-if="hasPermission('purchase_receive')">采购收货</button>
      <button @click="handleExport" class="btn btn-secondary btn-sm hidden md:inline-block">导出Excel</button>
    </div>

    <!-- 移动端卡片列表 -->
    <div class="md:hidden space-y-2">
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
    <div class="card hidden md:block">
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2 text-left">采购单号</th>
              <th class="px-3 py-2 text-left">供应商</th>
              <th class="px-3 py-2 text-right">总金额</th>
              <th class="px-3 py-2 text-center">状态</th>
              <th class="px-3 py-2 text-left">创建人</th>
              <th class="px-3 py-2 text-left">创建时间</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="o in purchaseOrders" :key="o.id" class="hover:bg-elevated cursor-pointer" @click="detailRef?.viewPurchaseOrder(o.id)">
              <td class="px-3 py-2 font-mono text-sm">
                <span v-if="['pending_review','paid','partial'].includes(o.status)" class="todo-dot mr-1.5"></span>{{ o.po_no }}
              </td>
              <td class="px-3 py-2">{{ o.supplier_name }}</td>
              <td class="px-3 py-2 text-right font-semibold">¥{{ fmt(o.total_amount) }}</td>
              <td class="px-3 py-2 text-center">
                <StatusBadge type="purchaseStatus" :status="o.status" />
              </td>
              <td class="px-3 py-2 text-secondary">{{ o.creator_name }}</td>
              <td class="px-3 py-2 text-muted text-xs">{{ fmtDate(o.created_at) }}</td>
            </tr>
          </tbody>
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
import { ref, onMounted } from 'vue'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { usePurchaseOrder } from '../../composables/usePurchaseOrder'
import { getAccountSets } from '../../api/accounting'
import { useProductsStore } from '../../stores/products'
import { useWarehousesStore } from '../../stores/warehouses'
import StatusBadge from '../common/StatusBadge.vue'
import PurchaseOrderForm from './purchase/PurchaseOrderForm.vue'
import PurchaseOrderDetail from './purchase/PurchaseOrderDetail.vue'

const emit = defineEmits(['data-changed'])

const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()

// 使用 composable 管理列表逻辑
const {
  purchaseOrders, purchaseStatusFilter, purchaseAccountSetFilter,
  purchaseDateStart, purchaseDateEnd, purchaseSearch,
  loadPurchaseOrders, debouncedLoad, handleExport,
  page, totalPages, hasPagination, resetPage, prevPage, nextPage
} = usePurchaseOrder()

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
  /** 刷新采购订单列表 */
  refresh: loadPurchaseOrders,
  /** 查看采购订单详情（转发到详情子组件） */
  viewPurchaseOrder: (id) => detailRef.value?.viewPurchaseOrder(id),
  /** 打开采购收货弹窗（转发到详情子组件） */
  openPurchaseReceive: () => detailRef.value?.openReceive()
})

onMounted(async () => {
  // 并行加载各项数据
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
