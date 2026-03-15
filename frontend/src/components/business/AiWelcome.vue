<template>
  <div class="text-center py-6">
    <Sparkles :size="32" class="mx-auto mb-3 opacity-30" />
    <p class="text-sm text-muted mb-4">你好！我是 AI 数据助手，可以帮你查询和分析业务数据。</p>

    <!-- 我的收藏 -->
    <div v-if="favorites.length" class="mb-4 text-left">
      <p class="text-xs text-muted mb-2 px-1">我的收藏</p>
      <div class="flex flex-wrap gap-2">
        <div v-for="(fav, i) in favorites" :key="fav.question" class="group relative">
          <button class="btn btn-secondary btn-sm text-xs" @click="$emit('send', fav.question)">
            <Star :size="10" class="mr-1 text-warning" /> {{ fav.question }}
          </button>
          <button class="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-error text-on-primary text-xs hidden group-hover:flex items-center justify-center" @click.stop="$emit('remove-favorite', i)">
            <X :size="10" />
          </button>
        </div>
      </div>
    </div>

    <!-- 常用查询 -->
    <div v-if="presetQueries.length">
      <p class="text-xs text-muted mb-2 px-1 text-left">常用查询</p>
      <div class="flex flex-wrap gap-2">
        <button v-for="pq in presetQueries" :key="pq.display" class="btn btn-secondary btn-sm text-xs" @click="$emit('send', pq.display, { preset: true })">
          {{ pq.display }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Sparkles, Star, X } from 'lucide-vue-next'

defineProps({
  favorites: { type: Array, default: () => [] },
  presetQueries: { type: Array, default: () => [] },
})

defineEmits(['send', 'remove-favorite'])
</script>
