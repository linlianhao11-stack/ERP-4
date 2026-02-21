<template>
  <div>
    <!-- Mobile card view -->
    <div v-if="$slots.mobile" class="md:hidden space-y-2">
      <slot name="mobile" />
      <div v-if="empty" class="p-8 text-center text-[#86868b] text-sm">{{ emptyText }}</div>
    </div>

    <!-- Desktop table view -->
    <div class="card" :class="$slots.mobile ? 'hidden md:block' : ''">
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-[#f5f5f7]">
            <tr>
              <th
                v-for="col in columns"
                :key="col.key"
                class="px-3 py-2"
                :class="[
                  col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left',
                  col.sortable ? 'cursor-pointer select-none hover:text-[#0071e3]' : '',
                  col.class || ''
                ]"
                :style="col.width ? { width: col.width } : {}"
                @click="col.sortable && toggleSort(col.key)"
              >
                {{ col.label }}
                <span v-if="col.sortable && sortKey === col.key" class="text-[#0071e3]">
                  {{ sortOrder === 'asc' ? '\u2191' : '\u2193' }}
                </span>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <slot />
          </tbody>
        </table>
        <div v-if="empty && !$slots.mobile" class="p-8 text-center text-[#86868b] text-sm">{{ emptyText }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  columns: {
    type: Array,
    required: true
    // 每项: { key: string, label: string, align?: 'left'|'right'|'center', sortable?: boolean, width?: string, class?: string }
  },
  sortKey: {
    type: String,
    default: ''
  },
  sortOrder: {
    type: String,
    default: 'asc'
  },
  empty: {
    type: Boolean,
    default: false
  },
  emptyText: {
    type: String,
    default: '暂无数据'
  }
})

const emit = defineEmits(['sort'])

function toggleSort(key) {
  if (props.sortKey === key) {
    emit('sort', { key, order: props.sortOrder === 'asc' ? 'desc' : 'asc' })
  } else {
    emit('sort', { key, order: 'asc' })
  }
}
</script>
