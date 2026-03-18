<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold">退款管理</h3>
      <button @click="loadData" class="btn btn-sm btn-secondary">刷新</button>
    </div>

    <div v-if="loading" class="text-center text-muted py-8 text-sm">加载中...</div>

    <div v-else-if="!items.length" class="text-center text-muted py-8 text-sm">暂无待退款记录</div>

    <div v-else class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b text-left text-secondary">
            <th class="px-2 py-2">类型</th>
            <th class="px-2 py-2">单号</th>
            <th class="px-2 py-2">客户/供应商</th>
            <th class="px-2 py-2 text-right">退款金额</th>
            <th class="px-2 py-2">退款方式</th>
            <th class="px-2 py-2">退款信息</th>
            <th class="px-2 py-2">日期</th>
            <th class="px-2 py-2">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.type + '-' + item.id" class="border-b border-line hover:bg-elevated">
            <td class="px-2 py-2">
              <span :class="item.type === 'sales' ? 'badge badge-blue' : 'badge badge-orange'" style="font-size:11px">
                {{ item.type === 'sales' ? '销售退款' : '采购退款' }}
              </span>
            </td>
            <td class="px-2 py-2 font-mono text-xs">{{ item.order_no }}</td>
            <td class="px-2 py-2">{{ item.partner_name }}</td>
            <td class="px-2 py-2 text-right font-semibold text-warning">&yen;{{ fmt(item.refund_amount) }}</td>
            <td class="px-2 py-2 text-muted">{{ item.refund_method || '-' }}</td>
            <td class="px-2 py-2 text-muted text-xs">{{ item.refund_info || '-' }}</td>
            <td class="px-2 py-2 text-muted text-xs">{{ fmtDate(item.created_at) }}</td>
            <td class="px-2 py-2">
              <button
                v-if="hasPermission('finance_confirm')"
                @click="handleConfirm(item)"
                :disabled="appStore.submitting"
                class="btn btn-sm btn-primary text-xs"
              >确认已退款</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
/**
 * 退款管理面板
 * 展示待退款列表（销售退款 + 采购退款），支持确认退款操作
 */
import { ref, onMounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useFormat } from '../../../composables/useFormat'
import { usePermission } from '../../../composables/usePermission'
import { getPendingRefunds, confirmSalesRefund, confirmPurchaseRefund } from '../../../api/finance'

const appStore = useAppStore()
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()

const items = ref([])
const loading = ref(false)

const loadData = async () => {
  loading.value = true
  try {
    const { data } = await getPendingRefunds()
    items.value = data.items || data || []
  } catch (e) {
    appStore.showToast('加载退款列表失败', 'error')
  } finally {
    loading.value = false
  }
}

const handleConfirm = async (item) => {
  const typeLabel = item.type === 'sales' ? '销售退款' : '采购退款'
  const confirmed = await appStore.customConfirm(
    '确认退款',
    `确认已完成${typeLabel} ¥${fmt(item.refund_amount)} 给 ${item.partner_name}？`
  )
  if (!confirmed) return

  if (appStore.submitting) return
  appStore.submitting = true
  try {
    if (item.type === 'sales') {
      await confirmSalesRefund(item.id)
    } else {
      await confirmPurchaseRefund(item.id)
    }
    appStore.showToast('退款确认成功')
    await loadData()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认退款失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

onMounted(() => loadData())

defineExpose({ refresh: loadData })
</script>
