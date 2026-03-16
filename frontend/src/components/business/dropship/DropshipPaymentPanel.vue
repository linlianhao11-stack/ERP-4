<template>
  <div>
    <!-- 顶部统计卡片 -->
    <div class="grid grid-cols-3 gap-3 mb-4">
      <div class="card p-4">
        <div class="text-xs text-muted mb-1">待付笔数</div>
        <div class="text-2xl font-bold">{{ workbench.total_count ?? 0 }}</div>
      </div>
      <div class="card p-4">
        <div class="text-xs text-muted mb-1">合计金额</div>
        <div class="text-2xl font-bold text-primary">¥{{ fmtMoney(workbench.total_amount) }}</div>
      </div>
      <div class="card p-4">
        <div class="text-xs text-muted mb-1">已预付笔数</div>
        <div class="text-2xl font-bold">{{ workbench.prepaid_count ?? 0 }}</div>
      </div>
    </div>

    <!-- 按供应商分组列表 -->
    <div v-if="loading" class="card p-8 text-center text-muted text-sm">加载中...</div>
    <div v-else-if="!groups.length" class="card p-8 text-center text-muted text-sm">暂无待付款订单</div>
    <div v-else class="space-y-3">
      <div v-for="g in groups" :key="g.supplier_id" class="card">
        <!-- 分组标题 -->
        <button
          type="button"
          class="w-full flex items-center justify-between px-4 py-3 hover:bg-elevated"
          @click="toggleGroup(g.supplier_id)"
        >
          <div class="flex items-center gap-2">
            <ChevronRight :size="16" class="text-muted transition-transform" :class="expandedGroups.has(g.supplier_id) ? 'rotate-90' : ''" />
            <span class="font-semibold text-sm">{{ g.supplier_name }}</span>
            <span class="badge badge-gray text-[10px]">{{ g.order_count }} 笔</span>
          </div>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-1.5 text-xs text-muted cursor-pointer" @click.stop>
              <input type="checkbox" class="w-3.5 h-3.5" :checked="isGroupAllSelected(g)" @change="toggleGroupSelect(g, $event.target.checked)">
              全选
            </label>
            <span class="text-sm font-semibold">¥{{ fmtMoney(g.subtotal) }}</span>
          </div>
        </button>
        <!-- 展开的订单列表 -->
        <div v-if="expandedGroups.has(g.supplier_id)" class="border-t">
          <table class="w-full text-sm">
            <thead class="bg-elevated">
              <tr>
                <th class="px-3 py-2 text-left w-8"></th>
                <th class="px-2 py-2 text-left">单号</th>
                <th class="px-2 py-2 text-left">商品</th>
                <th class="px-2 py-2 text-right">采购额</th>
                <th class="px-2 py-2 text-right">售价</th>
                <th class="px-2 py-2 text-right">毛利</th>
                <th class="px-2 py-2 text-left">客户</th>
                <th class="px-2 py-2 text-center">结算</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              <tr v-for="o in g.orders" :key="o.id" class="hover:bg-elevated">
                <td class="px-3 py-2">
                  <input type="checkbox" class="w-3.5 h-3.5" :checked="selectedIds.has(o.id)" @change="toggleSelect(o)">
                </td>
                <td class="px-2 py-2 font-mono text-xs">
                  {{ o.ds_no }}
                  <span v-if="o.urged_at" class="badge badge-orange text-[10px] ml-1">催</span>
                </td>
                <td class="px-2 py-2">{{ o.product_name }}</td>
                <td class="px-2 py-2 text-right">¥{{ fmtMoney(o.purchase_total) }}</td>
                <td class="px-2 py-2 text-right">¥{{ fmtMoney(o.sale_total) }}</td>
                <td class="px-2 py-2 text-right" :class="Number(o.gross_profit) >= 0 ? 'text-success' : 'text-error'">
                  ¥{{ fmtMoney(o.gross_profit) }}
                </td>
                <td class="px-2 py-2">{{ o.customer_name }}</td>
                <td class="px-2 py-2 text-center">
                  <span v-if="o.settlement_type === 'prepay'" class="badge badge-blue text-[10px]">先款</span>
                  <span v-else-if="o.settlement_type === 'credit'" class="badge badge-yellow text-[10px]">赊销</span>
                  <span v-else class="text-muted">-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 底部操作区 -->
    <div v-if="groups.length" class="card mt-4 p-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <!-- 选中统计 -->
        <div class="text-sm">
          已选 <span class="font-bold text-primary">{{ selectedIds.size }}</span> 笔，
          合计 <span class="font-bold text-primary">¥{{ fmtMoney(selectedTotal) }}</span>
        </div>
        <!-- 付款方式 + 操作 -->
        <div class="flex items-center gap-3">
          <select v-model="payMethod" class="toolbar-select">
            <option value="bank_transfer">银行转账</option>
            <option value="offset_advance">冲减借支</option>
          </select>
          <!-- 冲减借支时选择员工 -->
          <select v-if="payMethod === 'offset_advance'" v-model="selectedEmployee" class="toolbar-select">
            <option :value="null" disabled>选择员工</option>
            <option v-for="e in employees" :key="e.id" :value="e.id">{{ e.name }}</option>
          </select>
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="!selectedIds.size || appStore.submitting || (payMethod === 'offset_advance' && !selectedEmployee)"
            @click="handleBatchPay"
          >
            {{ appStore.submitting ? '付款中...' : '确认付款' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 代采代发付款工作台
 * 按供应商分组展示待付款订单，支持勾选批量付款
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { useFormat } from '../../../composables/useFormat'
import { useAppStore } from '../../../stores/app'
import { useSettingsStore } from '../../../stores/settings'
import { getPaymentWorkbench, batchPayDropship } from '../../../api/dropship'

const { fmtMoney } = useFormat()
const appStore = useAppStore()
const settingsStore = useSettingsStore()

// 工作台数据
const loading = ref(false)
const workbench = reactive({ total_count: 0, total_amount: 0, prepaid_count: 0 })
const groups = ref([])

// 展开/折叠控制
const expandedGroups = ref(new Set())

// 勾选控制
const selectedIds = ref(new Set())
const selectedOrderMap = ref(new Map()) // id -> order，方便计算金额

// 付款方式
const payMethod = ref('bank_transfer')
const selectedEmployee = ref(null)

// 员工列表
const employees = computed(() => settingsStore.employees)

/** 选中订单合计金额 */
const selectedTotal = computed(() => {
  let sum = 0
  for (const o of selectedOrderMap.value.values()) {
    sum += Number(o.purchase_total) || 0
  }
  return Math.round(sum * 100) / 100
})

/** 加载工作台数据 */
const loadData = async () => {
  loading.value = true
  try {
    const { data } = await getPaymentWorkbench()
    groups.value = data.groups || []
    workbench.total_count = data.total_count ?? 0
    workbench.total_amount = data.total_amount ?? 0
    workbench.prepaid_count = data.prepaid_count ?? 0
    // 默认展开第一个分组
    if (groups.value.length && !expandedGroups.value.size) {
      expandedGroups.value.add(groups.value[0].supplier_id)
    }
  } catch (e) {
    console.error('加载付款工作台失败:', e)
  } finally {
    loading.value = false
  }
}

/** 切换分组展开/折叠 */
const toggleGroup = (supplierId) => {
  const s = new Set(expandedGroups.value)
  if (s.has(supplierId)) s.delete(supplierId)
  else s.add(supplierId)
  expandedGroups.value = s
}

/** 勾选/取消单个订单 */
const toggleSelect = (order) => {
  const s = new Set(selectedIds.value)
  const m = new Map(selectedOrderMap.value)
  if (s.has(order.id)) {
    s.delete(order.id)
    m.delete(order.id)
  } else {
    s.add(order.id)
    m.set(order.id, order)
  }
  selectedIds.value = s
  selectedOrderMap.value = m
}

/** 判断整个分组是否全选 */
const isGroupAllSelected = (group) => {
  if (!group.orders?.length) return false
  return group.orders.every(o => selectedIds.value.has(o.id))
}

/** 整组全选/取消 */
const toggleGroupSelect = (group, checked) => {
  const s = new Set(selectedIds.value)
  const m = new Map(selectedOrderMap.value)
  for (const o of group.orders) {
    if (checked) {
      s.add(o.id)
      m.set(o.id, o)
    } else {
      s.delete(o.id)
      m.delete(o.id)
    }
  }
  selectedIds.value = s
  selectedOrderMap.value = m
}

/** 批量付款 */
const handleBatchPay = async () => {
  if (!selectedIds.value.size) return
  if (appStore.submitting) return

  const ok = await appStore.customConfirm(
    `确认支付 ${selectedIds.value.size} 笔订单？`,
    `合计金额 ¥${fmtMoney(selectedTotal.value)}`
  )
  if (!ok) return

  appStore.submitting = true
  try {
    const payload = {
      order_ids: [...selectedIds.value],
      pay_method: payMethod.value,
    }
    if (payMethod.value === 'offset_advance' && selectedEmployee.value) {
      payload.employee_id = selectedEmployee.value
    }
    await batchPayDropship(payload)
    appStore.showToast(`成功支付 ${selectedIds.value.size} 笔订单`)
    selectedIds.value = new Set()
    selectedOrderMap.value = new Map()
    await loadData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '付款失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

onMounted(() => {
  loadData()
  // 加载员工列表
  if (!settingsStore.employees.length) {
    settingsStore.loadEmployees()
  }
})
</script>
