<template>
  <div>
    <div class="card" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <span class="text-xs text-muted">销售退货单（用于冲抵出库凭证）</span>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-[13px]">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2">退货单号</th>
              <th class="px-3 py-2">退货日期</th>
              <th class="px-3 py-2">客户</th>
              <th class="px-3 py-2 text-right">退货金额</th>
              <th class="px-3 py-2 text-right">退货成本</th>
              <th class="px-3 py-2">凭证号</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!items.length">
              <td colspan="6">
                <div class="text-center py-12 text-muted">
                  <p class="text-sm font-medium">暂无销售退货数据</p>
                </div>
              </td>
            </tr>
            <tr v-for="o in items" :key="o.id" class="hover:bg-elevated">
              <td class="px-3 py-2 font-mono text-[12px]">{{ o.order_no }}</td>
              <td class="px-3 py-2">{{ o.return_date }}</td>
              <td class="px-3 py-2">{{ o.customer_name }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(o.total_amount) }}</td>
              <td class="px-3 py-2 text-right">{{ fmtMoney(o.total_cost) }}</td>
              <td class="px-3 py-2 font-mono text-[12px]">
                <span v-if="o.voucher_no">{{ o.voucher_no }}</span>
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
import PageToolbar from '../common/PageToolbar.vue'
import { getSalesReturns } from '../../api/accounting'
import { useAccountingStore } from '../../stores/accounting'
import { useFormat } from '../../composables/useFormat'

const accountingStore = useAccountingStore()
const { fmtMoney } = useFormat()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50

async function loadList() {
  if (!accountingStore.currentAccountSetId) return
  const res = await getSalesReturns({
    account_set_id: accountingStore.currentAccountSetId,
    page: page.value,
    page_size: pageSize,
  })
  items.value = res.data.items
  total.value = res.data.total
}

watch(() => accountingStore.currentAccountSetId, () => { page.value = 1; loadList() })
onMounted(() => loadList())
</script>
