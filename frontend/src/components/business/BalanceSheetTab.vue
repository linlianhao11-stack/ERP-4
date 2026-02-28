<template>
  <div>
    <div v-if="!data" class="text-center py-12 text-[#86868b] text-[13px]">暂无数据</div>
    <template v-else>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- 左侧：资产 -->
        <div class="bg-[#f5f5f7] rounded-xl p-4">
          <h5 class="text-[14px] font-semibold text-[#1d1d1f] mb-3 border-b border-[#e8e8ed] pb-2">资产</h5>

          <!-- 流动资产 -->
          <div class="mb-4">
            <div class="text-[13px] font-semibold text-[#6e6e73] mb-2">流动资产</div>
            <div class="space-y-1">
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>库存现金</span>
                <span class="font-mono">{{ fmt(data.assets.current.cash) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>银行存款</span>
                <span class="font-mono">{{ fmt(data.assets.current.bank) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>应收账款</span>
                <span class="font-mono">{{ fmt(data.assets.current.accounts_receivable) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>预付账款</span>
                <span class="font-mono">{{ fmt(data.assets.current.prepaid) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>其他应收款</span>
                <span class="font-mono">{{ fmt(data.assets.current.other_receivable) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>原材料</span>
                <span class="font-mono">{{ fmt(data.assets.current.raw_material) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>库存商品</span>
                <span class="font-mono">{{ fmt(data.assets.current.inventory) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>在途物资</span>
                <span class="font-mono">{{ fmt(data.assets.current.goods_in_transit) }}</span>
              </div>
              <div class="flex justify-between text-[13px] font-semibold px-2 py-1.5 bg-white/60 rounded-lg mt-1">
                <span>流动资产合计</span>
                <span class="font-mono">{{ fmt(data.assets.current.subtotal) }}</span>
              </div>
            </div>
          </div>

          <!-- 非流动资产 -->
          <div class="mb-4">
            <div class="text-[13px] font-semibold text-[#6e6e73] mb-2">非流动资产</div>
            <div class="space-y-1">
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>固定资产</span>
                <span class="font-mono">{{ fmt(data.assets.non_current.fixed_assets) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>累计折旧</span>
                <span class="font-mono">{{ fmt(data.assets.non_current.accumulated_depreciation) }}</span>
              </div>
              <div class="flex justify-between text-[13px] font-semibold px-2 py-1.5 bg-white/60 rounded-lg mt-1">
                <span>非流动资产合计</span>
                <span class="font-mono">{{ fmt(data.assets.non_current.subtotal) }}</span>
              </div>
            </div>
          </div>

          <!-- 资产总计 -->
          <div class="flex justify-between text-[14px] font-bold px-2 py-2 bg-[#0071e3]/10 rounded-lg text-[#0071e3]">
            <span>资产总计</span>
            <span class="font-mono">{{ fmt(data.assets.total) }}</span>
          </div>
        </div>

        <!-- 右侧：负债 + 所有者权益 -->
        <div class="bg-[#f5f5f7] rounded-xl p-4">
          <h5 class="text-[14px] font-semibold text-[#1d1d1f] mb-3 border-b border-[#e8e8ed] pb-2">负债及所有者权益</h5>

          <!-- 流动负债 -->
          <div class="mb-4">
            <div class="text-[13px] font-semibold text-[#6e6e73] mb-2">流动负债</div>
            <div class="space-y-1">
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>短期借款</span>
                <span class="font-mono">{{ fmt(data.liabilities.current.short_term_loan) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>应付账款</span>
                <span class="font-mono">{{ fmt(data.liabilities.current.accounts_payable) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>预收账款</span>
                <span class="font-mono">{{ fmt(data.liabilities.current.advance_received) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>应付职工薪酬</span>
                <span class="font-mono">{{ fmt(data.liabilities.current.salary_payable) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>应交税费</span>
                <span class="font-mono">{{ fmt(data.liabilities.current.tax_payable) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>其他应付款</span>
                <span class="font-mono">{{ fmt(data.liabilities.current.other_payable) }}</span>
              </div>
              <div class="flex justify-between text-[13px] font-semibold px-2 py-1.5 bg-white/60 rounded-lg mt-1">
                <span>流动负债合计</span>
                <span class="font-mono">{{ fmt(data.liabilities.current.subtotal) }}</span>
              </div>
            </div>
          </div>

          <!-- 所有者权益 -->
          <div class="mb-4">
            <div class="text-[13px] font-semibold text-[#6e6e73] mb-2">所有者权益</div>
            <div class="space-y-1">
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>实收资本</span>
                <span class="font-mono">{{ fmt(data.equity.paid_capital) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>盈余公积</span>
                <span class="font-mono">{{ fmt(data.equity.surplus_reserve) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>本年利润</span>
                <span class="font-mono">{{ fmt(data.equity.current_profit) }}</span>
              </div>
              <div class="flex justify-between text-[13px] px-2 py-1">
                <span>利润分配-未分配利润</span>
                <span class="font-mono">{{ fmt(data.equity.retained_earnings) }}</span>
              </div>
              <div class="flex justify-between text-[13px] font-semibold px-2 py-1.5 bg-white/60 rounded-lg mt-1">
                <span>所有者权益合计</span>
                <span class="font-mono">{{ fmt(data.equity.subtotal) }}</span>
              </div>
            </div>
          </div>

          <!-- 负债+权益总计 -->
          <div class="flex justify-between text-[14px] font-bold px-2 py-2 bg-[#0071e3]/10 rounded-lg text-[#0071e3]">
            <span>负债及所有者权益总计</span>
            <span class="font-mono">{{ fmt(data.total_liabilities_equity) }}</span>
          </div>
        </div>
      </div>

      <!-- 平衡状态 -->
      <div class="flex justify-center mt-4">
        <div
          :class="[
            'inline-flex items-center gap-2 px-4 py-2 rounded-full text-[13px] font-medium',
            data.is_balanced
              ? 'bg-[#e8f8ee] text-[#248a3d]'
              : 'bg-[#ffeaee] text-[#d70015]'
          ]"
        >
          <span class="text-[16px]">{{ data.is_balanced ? '\u2713' : '\u2717' }}</span>
          {{ data.is_balanced ? '资产负债表平衡' : '资产负债表不平衡，请检查凭证' }}
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
const props = defineProps({
  data: { type: Object, default: null },
})

function fmt(val) {
  if (!val || val === '0') return '-'
  const n = parseFloat(val)
  return isNaN(n) ? val : n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>
