<template>
  <div class="flex gap-2 overflow-x-auto" :class="containerClass">
    <span
      v-for="tab in tabs"
      :key="tab.value"
      class="tab"
      :class="{ active: modelValue === tab.value }"
      @click="$emit('update:modelValue', tab.value)"
    >
      {{ tab.label }}
      <span v-if="tab.badge != null" class="ml-1 text-xs opacity-60">({{ tab.badge }})</span>
    </span>
  </div>
</template>

<script setup>
defineProps({
  tabs: {
    type: Array,
    required: true
    // 每项: { value: string, label: string, badge?: number }
  },
  modelValue: {
    type: String,
    required: true
  },
  containerClass: {
    type: String,
    default: 'mb-3 border-b pb-2'
  }
})

defineEmits(['update:modelValue'])
</script>
