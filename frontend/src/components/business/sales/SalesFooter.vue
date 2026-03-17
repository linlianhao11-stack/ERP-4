<!--
  销售工作台底栏 - 合计金额、操作按钮
  sticky 固定在内容区底部，左对齐避开右下角 AI 聊天机器人
-->
<template>
  <div class="sticky bottom-0 bg-surface border-t shadow-[0_-2px_8px_rgba(0,0,0,0.06)]" style="z-index: 10">
    <div class="flex items-center justify-end gap-3 py-2.5 pr-20">
      <!-- 多账套分组小计 -->
      <div v-if="isMultiAccountSet" class="flex items-center gap-3 text-xs text-secondary">
        <span v-for="group in accountSetGroups" :key="group.key">
          {{ group.name }}: <span class="font-mono text-foreground">&yen;{{ fmt(group.subtotal) }}</span>
        </span>
      </div>

      <button @click="$emit('clear')" class="text-error text-sm hover:underline" v-show="cartLength">清空</button>

      <!-- 合计 -->
      <div class="flex items-center gap-1">
        <span class="text-sm text-secondary">合计:</span>
        <span class="text-lg font-bold text-primary font-mono">&yen;{{ fmt(cartTotal) }}</span>
      </div>

      <!-- 提交 -->
      <button @click="$emit('submit')" class="btn btn-primary text-sm" :disabled="!cartLength">提交订单</button>
    </div>
  </div>
</template>

<script setup>
import { useFormat } from '../../../composables/useFormat'

defineProps({
  cartTotal: Number,
  cartLength: Number,
  accountSetGroups: Array,
  isMultiAccountSet: Boolean
})

defineEmits(['clear', 'submit'])

const { fmt } = useFormat()
</script>
