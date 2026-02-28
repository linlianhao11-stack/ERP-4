<template>
  <div>
    <div v-if="!data || !data.rows || data.rows.length === 0" class="text-center py-12 text-[#86868b] text-[13px]">暂无数据</div>
    <template v-else>
      <div class="table-container">
        <table class="w-full text-[13px]">
          <thead>
            <tr>
              <th class="text-left">项目</th>
              <th class="text-right w-40">本期金额</th>
              <th class="text-right w-40">本年累计</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in data.rows" :key="idx" :class="isHeader(row.name) ? 'bg-[#f5f5f7]' : ''">
              <td :class="[isHeader(row.name) ? 'font-semibold text-[#1d1d1f]' : 'text-[#6e6e73]', isSubItem(row.name) ? 'pl-6' : '']">
                {{ row.name }}
              </td>
              <td class="text-right font-mono" :class="isHeader(row.name) ? 'font-semibold' : ''">
                {{ fmt(row.current) }}
              </td>
              <td class="text-right font-mono" :class="isHeader(row.name) ? 'font-semibold' : ''">
                {{ fmt(row.ytd) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup>
const props = defineProps({
  data: { type: Object, default: null },
})

function isHeader(name) {
  if (!name) return false
  return /^[一二三四五六七八九十]/.test(name.trim())
}

function isSubItem(name) {
  if (!name) return false
  return name.startsWith('  ')
}

function fmt(val) {
  if (!val || val === '0') return '-'
  const n = parseFloat(val)
  return isNaN(n) ? val : n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>
