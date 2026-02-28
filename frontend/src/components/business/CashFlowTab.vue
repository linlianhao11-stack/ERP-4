<template>
  <div>
    <div v-if="!data" class="text-center py-12 text-[#86868b] text-[13px]">暂无数据</div>
    <template v-else>
      <!-- 经营活动 -->
      <div class="bg-[#f5f5f7] rounded-xl p-4 mb-4">
        <h5 class="text-[14px] font-semibold text-[#1d1d1f] mb-3 border-b border-[#e8e8ed] pb-2">一、经营活动产生的现金流量</h5>
        <div class="space-y-1">
          <div v-for="item in (data.operating?.items || [])" :key="item.key" class="flex justify-between text-[13px] px-2 py-1">
            <span class="text-[#6e6e73]">{{ item.label }}</span>
            <span class="font-mono" :class="amtClass(item.amount)">{{ fmt(item.amount) }}</span>
          </div>
          <div v-if="!data.operating?.items?.length" class="text-center text-[12px] text-[#86868b] py-2">暂无数据</div>
        </div>
        <div class="flex justify-between text-[13px] font-semibold px-2 py-2 bg-white/60 rounded-lg mt-2">
          <span>经营活动现金流量净额</span>
          <span class="font-mono" :class="amtClass(data.operating?.net)">{{ fmt(data.operating?.net) }}</span>
        </div>
      </div>

      <!-- 投资活动 -->
      <div class="bg-[#f5f5f7] rounded-xl p-4 mb-4">
        <h5 class="text-[14px] font-semibold text-[#1d1d1f] mb-3 border-b border-[#e8e8ed] pb-2">二、投资活动产生的现金流量</h5>
        <div class="space-y-1">
          <div v-for="item in (data.investing?.items || [])" :key="item.key" class="flex justify-between text-[13px] px-2 py-1">
            <span class="text-[#6e6e73]">{{ item.label }}</span>
            <span class="font-mono" :class="amtClass(item.amount)">{{ fmt(item.amount) }}</span>
          </div>
          <div v-if="!data.investing?.items?.length" class="text-center text-[12px] text-[#86868b] py-2">暂无数据</div>
        </div>
        <div class="flex justify-between text-[13px] font-semibold px-2 py-2 bg-white/60 rounded-lg mt-2">
          <span>投资活动现金流量净额</span>
          <span class="font-mono" :class="amtClass(data.investing?.net)">{{ fmt(data.investing?.net) }}</span>
        </div>
      </div>

      <!-- 筹资活动 -->
      <div class="bg-[#f5f5f7] rounded-xl p-4 mb-4">
        <h5 class="text-[14px] font-semibold text-[#1d1d1f] mb-3 border-b border-[#e8e8ed] pb-2">三、筹资活动产生的现金流量</h5>
        <div class="space-y-1">
          <div v-for="item in (data.financing?.items || [])" :key="item.key" class="flex justify-between text-[13px] px-2 py-1">
            <span class="text-[#6e6e73]">{{ item.label }}</span>
            <span class="font-mono" :class="amtClass(item.amount)">{{ fmt(item.amount) }}</span>
          </div>
          <div v-if="!data.financing?.items?.length" class="text-center text-[12px] text-[#86868b] py-2">暂无数据</div>
        </div>
        <div class="flex justify-between text-[13px] font-semibold px-2 py-2 bg-white/60 rounded-lg mt-2">
          <span>筹资活动现金流量净额</span>
          <span class="font-mono" :class="amtClass(data.financing?.net)">{{ fmt(data.financing?.net) }}</span>
        </div>
      </div>

      <!-- 汇总 -->
      <div class="bg-[#f5f5f7] rounded-xl p-4">
        <h5 class="text-[14px] font-semibold text-[#1d1d1f] mb-3 border-b border-[#e8e8ed] pb-2">四、现金及现金等价物</h5>
        <div class="space-y-2">
          <div class="flex justify-between text-[13px] font-semibold px-2 py-2 bg-[#0071e3]/10 rounded-lg text-[#0071e3]">
            <span>现金及现金等价物净增加额</span>
            <span class="font-mono">{{ fmt(data.net_increase) }}</span>
          </div>
          <div class="flex justify-between text-[13px] px-2 py-1">
            <span class="text-[#6e6e73]">期初现金及现金等价物余额</span>
            <span class="font-mono">{{ fmt(data.opening_cash) }}</span>
          </div>
          <div class="flex justify-between text-[13px] font-semibold px-2 py-2 bg-white/60 rounded-lg">
            <span>期末现金及现金等价物余额</span>
            <span class="font-mono">{{ fmt(data.closing_cash) }}</span>
          </div>
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

function amtClass(val) {
  if (!val) return ''
  const n = parseFloat(val)
  if (isNaN(n)) return ''
  return n < 0 ? 'text-[#d70015]' : ''
}
</script>
