<template>
  <div class="flex flex-wrap items-center gap-2 mb-3">
    <slot />
  </div>
</template>

<script setup>
/**
 * 轻量筛选栏容器组件
 *
 * 提供统一的 flex 布局，内容通过默认插槽完全自定义。
 * 各页面的筛选项差异很大（select/input/date/按钮组合各不相同），
 * 因此选择容器 + 插槽模式，而非用 config 驱动。
 *
 * 用法：
 *   <FilterBar>
 *     <select v-model="filter.type" class="input text-sm">...</select>
 *     <input v-model="filter.search" class="input text-sm" placeholder="搜索...">
 *     <button @click="doExport" class="btn btn-primary btn-sm">导出</button>
 *   </FilterBar>
 */
</script>
