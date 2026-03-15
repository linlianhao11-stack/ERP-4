<template>
  <div>
    <div class="table-container">
      <table class="w-full">
        <thead class="bg-elevated">
          <tr>
            <th class="px-3 py-2">日期</th>
            <th class="px-3 py-2">期间</th>
            <th class="px-3 py-2">凭证字</th>
            <th class="px-3 py-2">凭证号</th>
            <th class="px-3 py-2">摘要</th>
            <th class="px-3 py-2">科目编码</th>
            <th class="px-3 py-2">科目名称</th>
            <th class="px-3 py-2">核算维度</th>
            <th class="px-3 py-2 text-right">借方金额</th>
            <th class="px-3 py-2 text-right">贷方金额</th>
            <th class="px-3 py-2">状态</th>
          </tr>
        </thead>
        <tbody class="divide-y">
          <tr v-for="(e, idx) in entries" :key="e.id"
            :class="['hover:bg-elevated', { 'border-t-2 border-border': isFirstOfVoucher(idx) && idx > 0 }]">
            <td class="px-3 py-2">{{ isFirstOfVoucher(idx) ? e.voucher_date : '' }}</td>
            <td class="px-3 py-2">{{ isFirstOfVoucher(idx) ? e.period_name : '' }}</td>
            <td class="px-3 py-2">{{ isFirstOfVoucher(idx) ? e.voucher_type : '' }}</td>
            <td class="px-3 py-2 font-medium">{{ isFirstOfVoucher(idx) ? e.sequence_no : '' }}</td>
            <td class="px-3 py-2">{{ e.entry_summary }}</td>
            <td class="px-3 py-2 font-mono text-xs">{{ e.account_code }}</td>
            <td class="px-3 py-2">{{ e.account_name }}</td>
            <td class="px-3 py-2 text-xs text-muted">{{ e.aux_info }}</td>
            <td class="px-3 py-2 text-right">{{ formatAmount(e.debit_amount) }}</td>
            <td class="px-3 py-2 text-right">{{ formatAmount(e.credit_amount) }}</td>
            <td class="px-3 py-2">
              <span v-if="isFirstOfVoucher(idx)" :class="statusBadge(e.status)">{{ statusName(e.status) }}</span>
            </td>
          </tr>
          <tr v-if="entries.length === 0">
            <td colspan="11">
              <div class="text-center py-12 text-muted">
                <p class="text-sm font-medium mb-1">暂无分录数据</p>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div v-if="total > pageSize" class="flex justify-center mt-3 gap-2">
      <button @click="page > 1 && (page--, loadList())" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
      <span class="text-[13px] text-muted leading-8">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button @click="page < Math.ceil(total / pageSize) && (page++, loadList())" :disabled="page >= Math.ceil(total / pageSize)" class="btn btn-secondary btn-sm">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useFormat } from '../../composables/useFormat'
import { getVoucherEntries } from '../../api/accounting'

const props = defineProps({
  accountSetId: { type: Number, required: true },
  filters: { type: Object, required: true }, // { period_name?, voucher_type?, status?, search? }
})

const { fmtMoney } = useFormat()

const entries = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50

const statusNames = { draft: '草稿', pending: '待审核', approved: '已审核', posted: '已过账' }
const statusBadgeMap = { draft: 'badge badge-gray', pending: 'badge badge-yellow', approved: 'badge badge-blue', posted: 'badge badge-green' }
const statusName = (s) => statusNames[s] || s
const statusBadge = (s) => statusBadgeMap[s] || 'badge'

const formatAmount = (v) => {
  const n = parseFloat(v)
  return isNaN(n) || n === 0 ? '' : fmtMoney(n)
}

// 判断当前行是否是该凭证的第一行
const isFirstOfVoucher = (idx) => {
  if (idx === 0) return true
  return entries.value[idx].voucher_id !== entries.value[idx - 1].voucher_id
}

const loadList = async () => {
  if (!props.accountSetId) return
  try {
    const { data } = await getVoucherEntries({
      account_set_id: props.accountSetId,
      ...props.filters,
      page: page.value,
      page_size: pageSize,
    })
    entries.value = data.items
    total.value = data.total
  } catch (e) { /* ignore */ }
}

watch(() => props.filters, () => { page.value = 1; loadList() }, { deep: true })
watch(() => props.accountSetId, () => { page.value = 1; loadList() })
onMounted(loadList)

defineExpose({ loadList })
</script>
