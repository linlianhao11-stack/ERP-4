<template>
  <div class="relative">
    <div class="ai-chart-container" :style="{ height: chartHeight + 'px' }">
      <canvas ref="canvasRef" />
    </div>
    <div class="flex items-center gap-2 mt-1 justify-end">
      <button class="text-xs text-muted hover:text-primary" @click="saveAsImage" title="保存图片">
        <ImageDown :size="14" />
      </button>
      <button class="text-xs text-muted hover:text-primary" @click="showFullscreen = true" title="全屏查看">
        <Maximize2 :size="14" />
      </button>
    </div>

    <!-- 全屏 Modal -->
    <Teleport to="body">
      <div v-if="showFullscreen" class="modal-backdrop" @click.self="showFullscreen = false">
        <div class="modal" style="max-width: 90vw; max-height: 90vh;">
          <div class="flex items-center justify-between p-3 border-b">
            <span class="font-semibold text-sm">{{ config.title || '图表' }}</span>
            <button class="ai-header-btn" @click="showFullscreen = false"><X :size="16" /></button>
          </div>
          <div class="p-4" style="height: 60vh;">
            <canvas ref="fullscreenCanvasRef" />
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ImageDown, Maximize2, X } from 'lucide-vue-next'
import { Chart, registerables } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'

Chart.register(...registerables, ChartDataLabels)

const props = defineProps({
  config: { type: Object, required: true },
})

const canvasRef = ref(null)
const fullscreenCanvasRef = ref(null)
const showFullscreen = ref(false)
let chartInstance = null
let fullscreenChartInstance = null

const PALETTE = [
  'oklch(0.55 0.20 250)', 'oklch(0.65 0.20 145)', 'oklch(0.75 0.18 75)',
  'oklch(0.60 0.25 25)', 'oklch(0.60 0.18 300)', 'oklch(0.70 0.15 200)',
  'oklch(0.58 0.22 220)', 'oklch(0.68 0.20 50)', 'oklch(0.55 0.15 330)',
  'oklch(0.72 0.12 110)', 'oklch(0.50 0.20 280)', 'oklch(0.65 0.15 170)',
]

const chartHeight = computed(() => {
  const type = props.config.chart_type
  if (type === 'pie' || type === 'doughnut') return 220
  const dataCount = props.config.labels?.length || 0
  return dataCount > 8 ? 360 : 280
})

const getColors = () => {
  const style = getComputedStyle(document.documentElement)
  return {
    text: style.getPropertyValue('--text')?.trim() || '#333',
    textMuted: style.getPropertyValue('--text-muted')?.trim() || '#999',
    border: style.getPropertyValue('--border')?.trim() || '#eee',
  }
}

const buildChartConfig = () => {
  const { chart_type, title, labels, datasets } = props.config
  const colors = getColors()
  const isPieType = chart_type === 'pie' || chart_type === 'doughnut'

  const mappedDatasets = (datasets || []).map((ds, i) => ({
    ...ds,
    backgroundColor: isPieType
      ? labels.map((_, j) => PALETTE[j % PALETTE.length])
      : PALETTE[i % PALETTE.length],
    borderColor: isPieType ? 'var(--surface)' : PALETTE[i % PALETTE.length],
    borderWidth: isPieType ? 2 : 2,
  }))

  return {
    type: chart_type || 'bar',
    data: { labels: labels || [], datasets: mappedDatasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: title ? { display: true, text: title, color: colors.text, font: { size: 13 } } : { display: false },
        legend: { position: isPieType ? 'right' : 'top', labels: { color: colors.text, font: { size: 11 } } },
        tooltip: { enabled: true },
        datalabels: isPieType ? {
          color: colors.text,
          font: { size: 11 },
          formatter: (value, ctx) => {
            const total = ctx.dataset.data.reduce((a, b) => a + b, 0)
            const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0
            return pct > 5 ? `${pct}%` : ''
          },
        } : { display: false },
      },
      scales: isPieType ? {} : {
        x: { ticks: { color: colors.textMuted, maxRotation: 45 }, grid: { color: colors.border } },
        y: { ticks: { color: colors.textMuted }, grid: { color: colors.border } },
      },
    },
  }
}

const createChart = () => {
  if (!canvasRef.value) return
  if (chartInstance) chartInstance.destroy()
  chartInstance = new Chart(canvasRef.value, buildChartConfig())
}

const createFullscreenChart = () => {
  nextTick(() => {
    if (!fullscreenCanvasRef.value) return
    if (fullscreenChartInstance) fullscreenChartInstance.destroy()
    fullscreenChartInstance = new Chart(fullscreenCanvasRef.value, buildChartConfig())
  })
}

const saveAsImage = () => {
  if (!chartInstance) return
  const link = document.createElement('a')
  link.download = `${props.config.title || '图表'}.png`
  link.href = chartInstance.toBase64Image()
  link.click()
}

watch(showFullscreen, (val) => {
  if (val) createFullscreenChart()
  else if (fullscreenChartInstance) {
    fullscreenChartInstance.destroy()
    fullscreenChartInstance = null
  }
})

onMounted(createChart)
onUnmounted(() => {
  if (chartInstance) chartInstance.destroy()
  if (fullscreenChartInstance) fullscreenChartInstance.destroy()
})
</script>

<style scoped>
.ai-chart-container {
  position: relative;
  width: 100%;
}
</style>
