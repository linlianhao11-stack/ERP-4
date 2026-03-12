<template>
  <div class="ai-chart-container">
    <canvas ref="canvasRef" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

const props = defineProps({
  config: { type: Object, required: true },
})

const canvasRef = ref(null)
let chartInstance = null

const getThemeColors = () => {
  const style = getComputedStyle(document.documentElement)
  return {
    text: style.getPropertyValue('--text').trim() || 'oklch(0.13 0 0)',
    textMuted: style.getPropertyValue('--text-muted').trim() || 'oklch(0.45 0 0)',
    border: style.getPropertyValue('--border').trim() || 'oklch(0.87 0 0)',
    primary: style.getPropertyValue('--primary').trim() || 'oklch(0.55 0.20 250)',
  }
}

const PALETTE = [
  'oklch(0.55 0.20 250)',   // primary blue
  'oklch(0.65 0.20 145)',   // green
  'oklch(0.75 0.18 75)',    // amber
  'oklch(0.60 0.25 25)',    // red
  'oklch(0.60 0.18 300)',   // purple
  'oklch(0.70 0.15 200)',   // teal
]

const renderChart = () => {
  if (!canvasRef.value || !props.config) return
  if (chartInstance) chartInstance.destroy()

  const colors = getThemeColors()
  const cfg = props.config

  const datasets = (cfg.datasets || []).map((ds, i) => ({
    ...ds,
    backgroundColor: ds.backgroundColor || PALETTE[i % PALETTE.length],
    borderColor: ds.borderColor || PALETTE[i % PALETTE.length],
    borderWidth: cfg.chart_type === 'line' ? 2 : 0,
    tension: 0.3,
  }))

  chartInstance = new Chart(canvasRef.value, {
    type: cfg.chart_type || 'bar',
    data: { labels: cfg.labels || [], datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: !!cfg.title,
          text: cfg.title || '',
          color: colors.text,
          font: { size: 14, weight: 500 },
        },
        legend: {
          labels: { color: colors.textMuted, font: { size: 12 } },
        },
      },
      scales: cfg.chart_type === 'pie' || cfg.chart_type === 'doughnut' ? {} : {
        x: { ticks: { color: colors.textMuted }, grid: { color: colors.border } },
        y: { ticks: { color: colors.textMuted }, grid: { color: colors.border } },
      },
    },
  })
}

watch(() => props.config, renderChart, { deep: true })
onMounted(renderChart)
onBeforeUnmount(() => { if (chartInstance) chartInstance.destroy() })
</script>

<style scoped>
.ai-chart-container {
  height: 240px;
  position: relative;
}
</style>
