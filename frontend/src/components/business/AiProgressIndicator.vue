<template>
  <div class="flex items-center gap-2 text-muted text-sm">
    <div class="ai-progress-bar">
      <div v-for="(s, i) in stages" :key="s" class="ai-progress-segment" :class="{ active: i <= currentIndex, pulse: i === currentIndex }" />
    </div>
    <span>{{ stageMessage }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stage: { type: String, default: 'thinking' },
  stageMessage: { type: String, default: '正在理解问题...' },
})

const stages = ['thinking', 'generating', 'executing', 'analyzing']
const currentIndex = computed(() => stages.indexOf(props.stage))
</script>

<style scoped>
.ai-progress-bar { display: flex; gap: 3px; }
.ai-progress-segment {
  width: 24px; height: 3px; border-radius: 1.5px;
  background: var(--border); transition: background 0.3s;
}
.ai-progress-segment.active { background: var(--primary); }
.ai-progress-segment.pulse { animation: pulse-bar 1.5s infinite; }
@keyframes pulse-bar {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
