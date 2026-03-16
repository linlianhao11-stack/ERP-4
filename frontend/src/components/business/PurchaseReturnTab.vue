<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <span class="text-xs text-muted">采购退货单（用于冲抵入库凭证）</span>
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
              <th class="px-2 py-2">退货单号</th>
              <th class="px-2 py-2">退货日期</th>
              <th class="px-2 py-2">供应商</th>
              <th class="px-2 py-2">采购单号</th>
              <th class="px-2 py-2 text-right">退货金额</th>
              <th class="px-2 py-2">退款状态</th>
              <th class="px-2 py-2">凭证号</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!items.length">
              <td colspan="7">
                <div class="text-center py-12 text-muted">
                  <p class="text-sm font-medium">暂无采购退货数据</p>
                </div>
              </td>
            </tr>
            <tr v-for="pr in items" :key="pr.id" class="hover:bg-elevated">
              <td class="px-2 py-2 font-mono text-[12px]">{{ pr.return_no }}</td>
              <td class="px-2 py-2">{{ pr.return_date }}</td>
              <td class="px-2 py-2">{{ pr.supplier_name }}</td>
              <td class="px-2 py-2 font-mono text-[12px]">{{ pr.purchase_order_no || '-' }}</td>
              <td class="px-2 py-2 text-right">{{ fmtMoney(pr.total_amount) }}</td>
              <td class="px-2 py-2">
                <span :class="pr.refund_status === 'completed' ? 'badge badge-green' : pr.refund_status === 'pending' ? 'badge badge-yellow' : 'badge badge-gray'">
                  {{ pr.refund_status === 'completed' ? '已退款' : pr.refund_status === 'pending' ? '待退款' : '无需退款' }}
                </span>
              </td>
              <td class="px-2 py-2 font-mono text-[12px]">
                <span v-if="pr.voucher_no">{{ pr.voucher_no }}</span>
                <span v-else class="text-muted">未生成</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { Search } from 'lucide-vue-next'
import PageToolbar from '../common/PageToolbar.vue'
import { getPurchaseReturnsForAP } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useFormat } from '../../composables/useFormat'
import { useSearch } from '../../composables/useSearch'

const accountingStore = useAccountingStore()
const { fmtMoney } = useFormat()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const params = {
    account_set_id: accountingStore.currentAccountSetId,
    page: page.value,
    page_size: pageSize,
  }
  if (searchQuery.value) params.search = searchQuery.value
  const res = await getPurchaseReturnsForAP(params)
  items.value = res.data.items
  total.value = res.data.total
}

const { searchQuery, debouncedSearch } = useSearch(loadList, page)

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => loadList())
</script>
