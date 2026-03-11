<template>
  <div class="page-toolbar">
    <div class="page-toolbar-inner">
      <!-- 左侧：筛选区 -->
      <div class="page-toolbar-filters">
        <slot name="filters" />
      </div>
      <!-- 右侧：操作区 -->
      <div v-if="$slots.actions" class="page-toolbar-actions">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * PageToolbar — 统一页面工具栏
 *
 * 放在 .card 内部顶部，border-bottom 分隔。
 * 单行 flex-wrap 布局，移动端自动换行。
 *
 * 插槽：
 *   #filters — 左侧筛选区（日期、下拉、搜索、重置）
 *   #actions — 右侧操作区（视图切换、按钮）
 *
 * 用法：
 *   <div class="card">
 *     <PageToolbar>
 *       <template #filters>
 *         <DateRangePicker v-model:start="..." v-model:end="..." />
 *         <select class="toolbar-select">...</select>
 *         <input class="toolbar-search" placeholder="搜索..." />
 *       </template>
 *       <template #actions>
 *         <SegmentedControl :options="..." v-model="..." />
 *         <button class="btn btn-primary btn-sm">新建</button>
 *       </template>
 *     </PageToolbar>
 *     <div class="table-container">...</div>
 *   </div>
 */
</script>
