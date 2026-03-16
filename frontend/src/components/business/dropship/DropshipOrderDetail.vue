<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal-content" style="max-width:680px; max-height:90vh; display:flex; flex-direction:column">
        <div class="modal-header">
          <div class="flex items-center gap-2">
            <h3 class="modal-title">订单详情</h3>
            <StatusBadge v-if="detail" type="dropshipStatus" :status="detail.status" />
          </div>
          <button @click="close" class="modal-close">&times;</button>
        </div>

        <div v-if="loading" class="modal-body flex items-center justify-center py-12">
          <span class="text-muted">加载中...</span>
        </div>

        <div v-else-if="detail" class="modal-body overflow-y-auto" style="flex:1; min-height:0">
          <div class="space-y-5">

            <!-- 顶部摘要 -->
            <div class="flex items-center justify-between">
              <div>
                <div class="font-mono text-lg font-semibold">{{ detail.ds_no }}</div>
                <div class="text-xs text-muted mt-0.5">{{ fmtDate(detail.created_at) }} · {{ detail.creator_name || '-' }}</div>
              </div>
              <div class="text-right">
                <div class="text-xs text-muted">毛利</div>
                <div class="text-lg font-bold font-mono"
                  :class="Number(detail.gross_profit) >= 0 ? 'text-success' : 'text-error'">
                  ¥{{ fmt(detail.gross_profit) }}
                  <span class="text-xs font-normal text-muted ml-1">{{ Number(detail.gross_margin).toFixed(1) }}%</span>
                </div>
              </div>
            </div>

            <!-- 采购信息 -->
            <section>
              <h4 class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">采购信息</h4>
              <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <div><span class="text-muted">供应商</span><span class="float-right">{{ detail.supplier_name }}</span></div>
                <div><span class="text-muted">商品</span><span class="float-right">{{ detail.product_name }}</span></div>
                <div><span class="text-muted">采购单价</span><span class="float-right font-mono">¥{{ fmt(detail.purchase_price) }}</span></div>
                <div><span class="text-muted">数量</span><span class="float-right">{{ detail.quantity }}</span></div>
                <div><span class="text-muted">采购总额</span><span class="float-right font-mono font-semibold">¥{{ fmt(detail.purchase_total) }}</span></div>
                <div><span class="text-muted">发票类型</span><span class="float-right">{{ detail.invoice_type === 'special' ? '专票' : '普票' }}</span></div>
                <div><span class="text-muted">采购税率</span><span class="float-right">{{ detail.purchase_tax_rate }}%</span></div>
              </div>
            </section>

            <!-- 销售信息 -->
            <section>
              <h4 class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">销售信息</h4>
              <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <div><span class="text-muted">客户</span><span class="float-right">{{ detail.customer_name }}</span></div>
                <div><span class="text-muted">平台订单号</span><span class="float-right font-mono text-xs">{{ detail.platform_order_no || '-' }}</span></div>
                <div><span class="text-muted">销售单价</span><span class="float-right font-mono">¥{{ fmt(detail.sale_price) }}</span></div>
                <div><span class="text-muted">销售总额</span><span class="float-right font-mono font-semibold">¥{{ fmt(detail.sale_total) }}</span></div>
                <div><span class="text-muted">销售税率</span><span class="float-right">{{ detail.sale_tax_rate }}%</span></div>
                <div><span class="text-muted">结算方式</span><span class="float-right">{{ detail.settlement_type === 'prepaid' ? '先款后货' : '赊销' }}</span></div>
              </div>
            </section>

            <!-- 物流信息 -->
            <section v-if="detail.tracking_no">
              <div class="flex items-center justify-between mb-2">
                <h4 class="text-xs font-semibold text-muted uppercase tracking-wider">物流信息</h4>
                <button type="button" @click="handleRefreshTracking" class="text-xs text-primary hover:underline"
                  :disabled="refreshing">
                  {{ refreshing ? '刷新中...' : '刷新物流' }}
                </button>
              </div>
              <div class="bg-elevated rounded-lg p-3 text-sm space-y-2">
                <div class="flex items-center justify-between">
                  <span>{{ detail.carrier_name || detail.carrier_code }}</span>
                  <span class="font-mono text-xs">{{ detail.tracking_no }}</span>
                </div>
                <!-- 物流摘要（最后一条） -->
                <div v-if="latestTracking" class="text-xs text-secondary">
                  {{ latestTracking.time }} — {{ latestTracking.desc }}
                </div>
                <!-- 展开完整时间线 -->
                <button v-if="trackingItems.length > 1" type="button"
                  @click="showFullTracking = !showFullTracking"
                  class="text-xs text-primary hover:underline">
                  {{ showFullTracking ? '收起' : `查看全部 ${trackingItems.length} 条` }}
                </button>
                <div v-if="showFullTracking && trackingItems.length" class="max-h-48 overflow-y-auto mt-2">
                  <div v-for="(item, i) in trackingItems" :key="i" class="flex gap-2 text-xs">
                    <div class="flex flex-col items-center">
                      <div class="w-2 h-2 rounded-full shrink-0 mt-1"
                        :class="i === 0 ? 'bg-success' : 'bg-border'"></div>
                      <div v-if="i < trackingItems.length - 1" class="w-0.5 h-5 bg-border-light"></div>
                    </div>
                    <div class="pb-2">
                      <div class="text-muted">{{ item.time }}</div>
                      <div class="text-text">{{ item.desc }}</div>
                    </div>
                  </div>
                </div>
                <div v-if="!trackingItems.length" class="text-xs text-muted">暂无物流轨迹，请点击刷新获取</div>
              </div>
            </section>

            <!-- 财务单据 -->
            <section v-if="detail.payable_bill_no || detail.disbursement_bill_id || detail.receivable_bill_id">
              <h4 class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">财务单据</h4>
              <div class="text-sm space-y-1">
                <div v-if="detail.payable_bill_no" class="flex justify-between">
                  <span class="text-muted">应付单</span>
                  <span class="font-mono text-xs">{{ detail.payable_bill_no }}</span>
                </div>
                <div v-if="detail.disbursement_bill_id" class="flex justify-between">
                  <span class="text-muted">付款方式</span>
                  <span>{{ detail.payment_method === 'employee_advance' ? '冲减借支' : '银行转账' }}{{ detail.payment_employee_name ? ` · ${detail.payment_employee_name}` : '' }}</span>
                </div>
                <div v-if="detail.receivable_bill_id" class="flex justify-between">
                  <span class="text-muted">应收单</span>
                  <span class="font-mono text-xs">已创建</span>
                </div>
              </div>
            </section>

            <!-- 操作日志（时间线） -->
            <section>
              <h4 class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">操作记录</h4>
              <div class="text-xs space-y-1 text-secondary">
                <div>{{ fmtDate(detail.created_at) }} — 创建订单</div>
                <div v-if="detail.payable_bill_no">提交订单 → 待付款</div>
                <div v-if="detail.disbursement_bill_id">付款完成 → 已付待发</div>
                <div v-if="detail.urged_at">{{ fmtDate(detail.urged_at) }} — 催付款</div>
                <div v-if="detail.shipped_at">{{ fmtDate(detail.shipped_at) }} — 已发货</div>
                <div v-if="detail.status === 'completed'">订单完成</div>
                <div v-if="detail.status === 'cancelled'">
                  订单取消{{ detail.cancel_reason ? `：${detail.cancel_reason}` : '' }}
                </div>
              </div>
            </section>

            <!-- 备注 -->
            <section v-if="detail.note">
              <h4 class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">备注</h4>
              <div class="text-sm text-secondary">{{ detail.note }}</div>
            </section>

          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import StatusBadge from '../../common/StatusBadge.vue'
import { getDropshipOrder, refreshDropshipTracking } from '../../../api/dropship'
import { useFormat } from '../../../composables/useFormat'
import { useAppStore } from '../../../stores/app'

const props = defineProps({
  visible: Boolean,
  orderId: Number,
})
const emit = defineEmits(['update:visible', 'status-changed'])

const { fmt, fmtDate } = useFormat()
const appStore = useAppStore()

const detail = ref(null)
const loading = ref(false)
const refreshing = ref(false)
const showFullTracking = ref(false)

const close = () => emit('update:visible', false)

// 解析物流轨迹
const trackingItems = computed(() => {
  if (!detail.value?.last_tracking_info) return []
  try {
    const data = JSON.parse(detail.value.last_tracking_info)
    const items = data?.data || []
    return items.map(item => ({
      time: item.ftime || item.time || '',
      desc: item.context || item.desc || '',
    }))
  } catch {
    return []
  }
})

const latestTracking = computed(() => trackingItems.value[0] || null)

// 加载详情
const loadDetail = async () => {
  if (!props.orderId) return
  loading.value = true
  showFullTracking.value = false
  try {
    const { data } = await getDropshipOrder(props.orderId)
    detail.value = data
  } catch (e) {
    appStore.showToast('加载订单详情失败', 'error')
    close()
  } finally {
    loading.value = false
  }
}

// 刷新物流
const handleRefreshTracking = async () => {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const { data } = await refreshDropshipTracking(props.orderId)
    if (data.last_tracking_info) {
      detail.value.last_tracking_info = data.last_tracking_info
    }
    if (data.status && data.status !== detail.value.status) {
      detail.value.status = data.status
      emit('status-changed')
    }
    appStore.showToast('物流信息已更新')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '物流刷新失败', 'error')
  } finally {
    refreshing.value = false
  }
}

watch(() => props.visible, (v) => {
  if (v) loadDetail()
})
</script>
