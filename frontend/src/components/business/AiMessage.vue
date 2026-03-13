<template>
  <div class="ai-msg" :class="msg.role">
    <!-- 用户消息 -->
    <div v-if="msg.role === 'user'" class="ai-msg-user">
      {{ msg.content }}
    </div>

    <!-- AI 消息 -->
    <div v-else class="ai-msg-ai">
      <!-- 加载中 -->
      <AiProgressIndicator v-if="msg.loading" :stage="msg.stage" :stage-message="msg.stageMessage" />

      <!-- 澄清 -->
      <template v-else-if="msg.type === 'clarification'">
        <p class="text-sm mb-2">{{ msg.message }}</p>
        <div class="flex flex-wrap gap-2">
          <button v-for="opt in (msg.options || [])" :key="opt" class="btn btn-secondary btn-sm text-xs" @click="$emit('select-option', opt)">
            {{ opt }}
          </button>
        </div>
      </template>

      <!-- 错误 -->
      <template v-else-if="msg.type === 'error'">
        <p class="text-sm text-error">{{ msg.message }}</p>
        <button v-if="msg._retryable" class="btn btn-secondary btn-sm text-xs mt-2" @click="$emit('retry', msg)">
          <RotateCcw :size="12" class="mr-1" /> 重试
        </button>
      </template>

      <!-- 正常回答 -->
      <template v-else-if="msg.type === 'answer'">
        <!-- 文字分析 -->
        <div v-if="msg.analysis" class="ai-analysis text-sm" v-html="renderMarkdown(msg.analysis)" />

        <!-- 数据已过期 -->
        <div v-if="msg._expired && (msg._hasTableData || msg._hasChartConfig)" class="mt-3 p-3 bg-elevated rounded-lg text-center">
          <p class="text-xs text-muted mb-2">数据已过期</p>
          <button class="btn btn-secondary btn-sm text-xs" @click="$emit('select-option', msg._question)">重新查询</button>
        </div>
        <!-- 数据表格 -->
        <div v-else-if="msg.table_data" class="mt-3 border rounded-lg overflow-hidden">
          <div class="overflow-x-auto max-h-[300px]">
            <table class="w-full text-sm">
              <thead class="bg-elevated sticky top-0">
                <tr>
                  <th v-for="col in msg.table_data.columns" :key="col" class="px-3 py-2 text-left text-xs font-medium text-muted whitespace-nowrap">
                    {{ col }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in msg.table_data.rows" :key="ri" class="border-t">
                  <td v-for="(cell, ci) in row" :key="ci" class="px-3 py-1.5 whitespace-nowrap" :class="isNumber(cell) ? 'tabular-nums font-mono text-right' : ''">
                    {{ formatCell(cell) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="px-3 py-1.5 text-xs text-muted border-t bg-elevated">
            共 {{ msg.row_count }} 行
          </div>
        </div>

        <!-- 图表 -->
        <AiChartRenderer v-if="msg.chart_config" :config="msg.chart_config" class="mt-3" />

        <!-- SQL 折叠 -->
        <details v-if="msg.sql" class="mt-3">
          <summary class="text-xs text-muted cursor-pointer">查看 SQL</summary>
          <pre class="mt-1 p-2 bg-elevated rounded text-xs font-mono overflow-x-auto">{{ msg.sql }}</pre>
        </details>

        <!-- 操作栏 -->
        <div class="flex items-center gap-3 mt-3 pt-2 border-t">
          <button v-if="msg.table_data" class="text-xs text-muted hover:text-primary" @click="copyTable" title="复制表格">
            <Copy :size="14" />
          </button>
          <div class="relative" v-if="msg.table_data">
            <button class="text-xs text-muted hover:text-primary" @click="showExportMenu = !showExportMenu" title="导出">
              <Download :size="14" />
            </button>
            <div v-if="showExportMenu" class="absolute bottom-full left-0 mb-1 bg-surface border rounded-lg shadow-lg py-1 z-10 whitespace-nowrap">
              <button class="block w-full text-left px-3 py-1.5 text-xs hover:bg-elevated" @click="$emit('export', msg); showExportMenu = false">导出 Excel</button>
              <button class="block w-full text-left px-3 py-1.5 text-xs hover:bg-elevated" @click="exportCsv(); showExportMenu = false">导出 CSV</button>
            </div>
          </div>
          <button class="text-xs text-muted hover:text-warning" @click="$emit('favorite', msg)" :title="msg._favorited ? '已收藏' : '收藏查询'">
            <Star :size="14" :fill="msg._favorited ? 'currentColor' : 'none'" :class="msg._favorited ? 'text-warning' : ''" />
          </button>
          <div class="flex-1" />
          <button class="text-xs px-2 py-1 rounded" :class="msg.feedback === 'positive' ? 'bg-success-subtle text-success-emphasis' : 'text-muted hover:text-success'" @click="$emit('feedback', msg, 'positive')">
            <ThumbsUp :size="14" />
          </button>
          <button class="text-xs px-2 py-1 rounded" :class="msg.feedback === 'negative' ? 'bg-error-subtle text-error-emphasis' : 'text-muted hover:text-error'" @click="$emit('feedback', msg, 'negative')">
            <ThumbsDown :size="14" />
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Copy, Download, ThumbsUp, ThumbsDown, RotateCcw, Star } from 'lucide-vue-next'
import AiChartRenderer from './AiChartRenderer.vue'
import AiProgressIndicator from './AiProgressIndicator.vue'
import { useAppStore } from '../../stores/app'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

const appStore = useAppStore()

const props = defineProps({
  msg: { type: Object, required: true },
})

defineEmits(['select-option', 'export', 'feedback', 'retry', 'favorite'])

const isNumber = (val) => typeof val === 'number'

const formatCell = (val) => {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'number') {
    return Number.isInteger(val) ? val.toLocaleString() : val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  return String(val)
}

const renderMarkdown = (text) => {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text), {
    ALLOWED_TAGS: ['strong', 'em', 'ul', 'ol', 'li', 'br', 'p', 'h3', 'h4', 'code', 'pre'],
    ALLOWED_ATTR: ['class'],
  })
}

const showExportMenu = ref(false)

const exportCsv = () => {
  if (!props.msg.table_data) return
  const { columns, rows } = props.msg.table_data
  const bom = '\uFEFF'
  const csv = bom + [
    columns.join(','),
    ...rows.map(r => r.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(','))
  ].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'AI查询结果.csv'
  a.click()
  URL.revokeObjectURL(url)
}

const copyTable = async () => {
  if (!props.msg.table_data) return
  const { columns, rows } = props.msg.table_data
  const tsv = [columns.join('\t'), ...rows.map(r => r.map(c => c ?? '').join('\t'))].join('\n')
  try {
    await navigator.clipboard.writeText(tsv)
    appStore.showToast('已复制到剪贴板')
  } catch {
    appStore.showToast('复制失败', 'error')
  }
}
</script>

<style scoped>
.ai-msg-user {
  background: var(--primary-muted);
  color: var(--text);
  padding: 8px 12px;
  border-radius: 12px 12px 4px 12px;
  max-width: 85%;
  margin-left: auto;
  font-size: 14px;
}
.ai-msg-ai {
  background: var(--elevated);
  padding: 10px 14px;
  border-radius: 4px 12px 12px 12px;
  max-width: 95%;
  font-size: 14px;
}

.ai-analysis :deep(p) { margin-bottom: 0.5em; }
.ai-analysis :deep(ul), .ai-analysis :deep(ol) { padding-left: 1.2em; margin: 0.5em 0; }
.ai-analysis :deep(li) { margin-bottom: 0.25em; }
.ai-analysis :deep(code) { background: var(--elevated); padding: 1px 4px; border-radius: 3px; font-size: 0.85em; }
.ai-analysis :deep(pre) { background: var(--elevated); padding: 8px 12px; border-radius: 6px; overflow-x: auto; margin: 0.5em 0; }
.ai-analysis :deep(pre code) { background: none; padding: 0; }
.ai-analysis :deep(h3), .ai-analysis :deep(h4) { font-weight: 600; margin: 0.75em 0 0.25em; }
</style>
