<template>
  <div class="inline-flex items-center rounded-md overflow-hidden border" style="border-color:var(--border); background:var(--elevated);">
    <button v-for="opt in options" :key="opt.value" type="button"
      @click="$emit('update:modelValue', opt.value)"
      :class="['px-3 py-1 text-xs font-medium transition-colors whitespace-nowrap',
        modelValue === opt.value ? 'bg-primary text-white' : 'text-muted hover:text-text']"
      style="min-height:28px">
      {{ opt.label }}
    </button>
  </div>
</template>

<script setup>
/**
 * SegmentedControl — 分段切换控件
 *
 * 用于汇总/明细等二态或多态切换。
 * 紧凑设计，适合放在工具栏右侧。
 *
 * Props:
 *   modelValue — 当前选中值
 *   options — [{value, label}] 选项列表
 *
 * 用法:
 *   <SegmentedControl v-model="viewMode"
 *     :options="[{value:'summary', label:'汇总'}, {value:'detail', label:'明细'}]" />
 */
defineProps({
  modelValue: { type: String, required: true },
  options: { type: Array, required: true }
})
defineEmits(['update:modelValue'])
</script>
