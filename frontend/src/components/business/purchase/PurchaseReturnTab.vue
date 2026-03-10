<template>
  <div>
    <!-- 筛选栏 -->
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="filters.supplier_id" class="input input-sm w-36" @change="onFilterChange">
        <option value="">全部供应商</option>
        <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </div>

    <!-- 列表表格 -->
    <div class="table-container">
      <table class="w-full text-[13px]">
        <thead>
          <tr>
            <th>退货单号</th>
            <th>关联采购单</th>
            <th>供应商</th>
            <th class="text-right">退货金额</th>
            <th>退款方式</th>
            <th>退款状态</th>
            <th>退货时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!items.length">
            <td colspan="8">
              <div class="text-center py-12 text-muted">
                <p class="text-sm font-medium mb-1">暂无退货单数据</p>
                <p class="text-xs text-muted">退货单由采购订单退货时自动生成</p>
              </div>
            </td>
          </tr>
          <tr v-for="r in items" :key="r.id" class="cursor-pointer" @click="viewDetail(r)">
            <td class="font-mono text-[12px] max-w-48 truncate" :title="r.return_no">{{ r.return_no }}</td>
            <td class="font-mono text-[12px] text-primary max-w-48 truncate" :title="r.po_no">{{ r.po_no }}</td>
            <td>{{ r.supplier_name }}</td>
            <td class="text-right font-semibold text-warning">{{ fmtMoney(r.total_amount) }}</td>
            <td>{{ r.is_refunded ? '供应商退款' : '转为在账资金' }}</td>
            <td>
              <span :class="refundStatusClass(r.refund_status)">{{ refundStatusLabel(r.refund_status) }}</span>
            </td>
            <td class="text-muted text-xs">{{ fmtDate(r.created_at) }}</td>
            <td @click.stop>
              <button @click="viewDetail(r)" class="text-xs px-2.5 py-1 rounded-md bg-info-subtle text-info-emphasis font-medium">查看</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div v-if="hasPagination" class="flex justify-center mt-3 gap-2">
      <button @click="prevPage(); loadList()" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ totalPages }}</span>
      <button @click="nextPage(); loadList()" :disabled="page >= totalPages" class="btn btn-secondary btn-sm">下一页</button>
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
                <div><span class="text-muted">退款方式：</span>{{ detail.is_refunded ? '供应商退款' : '转为在账资金' }}</div>
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
                  <table class="w-full text-[13px]">
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
import { ref, onMounted } from 'vue'
import { getPurchaseReturns, getPurchaseReturn } from '../../../api/purchase'
import { useAppStore } from '../../../stores/app'
import { useFormat } from '../../../composables/useFormat'
import { usePagination } from '../../../composables/usePagination'
import api from '../../../api/index'

const appStore = useAppStore()
const { fmtMoney, fmtDate } = useFormat()
const { page, pageSize, total, totalPages, hasPagination, paginationParams, setTotal, resetPage, prevPage, nextPage } = usePagination(50)

const items = ref([])
const filters = ref({ supplier_id: '' })
const suppliers = ref([])
const showDetail = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

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
