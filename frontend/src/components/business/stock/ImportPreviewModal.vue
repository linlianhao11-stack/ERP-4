<!--
  导入预览弹窗
  展示解析后的导入数据预览表格，支持确认导入或取消返回
-->
<template>
  <teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal">
        <!-- 标题栏 -->
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">导入预览 - {{ fileName }}</h3>
          <button @click="close" class="text-[#86868b] text-xl">&times;</button>
        </div>
        <!-- 内容 -->
        <div class="p-4">
          <div class="space-y-4">
            <!-- 统计信息 -->
            <div
              class="p-3 rounded-lg"
              :class="previewData.valid_count > 0 ? 'bg-[#e8f8ee] border border-[#a8e6c1]' : 'bg-[#fff8e1] border border-[#ffe082]'"
            >
              <div class="flex justify-between items-center">
                <div><span class="font-semibold text-lg">共 {{ previewData.total }} 条数据</span></div>
                <div class="text-sm">
                  <span class="text-[#34c759] font-semibold">{{ previewData.valid_count }} 条有效</span>
                  <span class="mx-2">|</span>
                  <span class="text-[#86868b]">{{ previewData.skip_count }} 条跳过</span>
                </div>
              </div>
            </div>
            <!-- 预览表格 -->
            <div class="max-h-96 overflow-y-auto border rounded-lg">
              <table class="w-full text-sm">
                <thead class="bg-[#f5f5f7] sticky top-0">
                  <tr>
                    <th class="px-2 py-2 text-left w-12">行</th>
                    <th class="px-2 py-2 text-left">SKU</th>
                    <th class="px-2 py-2 text-left">名称</th>
                    <th class="px-2 py-2 text-left">仓库</th>
                    <th class="px-2 py-2 text-left">仓位</th>
                    <th class="px-2 py-2 text-right">导入数量</th>
                    <th class="px-2 py-2 text-center">库存变化</th>
                    <th class="px-2 py-2 text-right">成本</th>
                    <th class="px-2 py-2 text-left">操作</th>
                  </tr>
                </thead>
                <tbody class="divide-y">
                  <tr
                    v-for="item in previewData.items"
                    :key="item.row"
                    :class="item.status === 'skip' ? 'bg-[#f5f5f7] text-[#86868b]' : ''"
                  >
                    <td class="px-2 py-1.5 text-[#86868b]">{{ item.row }}</td>
                    <td class="px-2 py-1.5 font-mono text-xs">{{ item.sku }}</td>
                    <td class="px-2 py-1.5 truncate max-w-32">{{ item.name }}</td>
                    <td class="px-2 py-1.5">
                      <span v-if="item.warehouse" class="text-xs">{{ item.warehouse }}</span>
                      <span v-else class="text-[#ff6961]">-</span>
                    </td>
                    <td class="px-2 py-1.5">
                      <span v-if="item.location" class="badge badge-blue text-xs">{{ item.location }}</span>
                      <span v-else class="text-[#ff6961]">-</span>
                    </td>
                    <td class="px-2 py-1.5 text-right font-semibold text-[#34c759]">+{{ item.quantity || 0 }}</td>
                    <td class="px-2 py-1.5 text-center">
                      <span v-if="item.current_stock > 0" class="text-xs">
                        {{ item.current_stock }} → <span class="font-semibold text-[#0071e3]">{{ item.after_stock }}</span>
                      </span>
                      <span v-else-if="item.status === 'valid'" class="text-xs text-[#86868b]">
                        0 → <span class="font-semibold">{{ item.after_stock }}</span>
                      </span>
                      <span v-else>-</span>
                    </td>
                    <td class="px-2 py-1.5 text-right">{{ item.cost_price ? '\u00A5' + item.cost_price : '-' }}</td>
                    <td class="px-2 py-1.5">
                      <span v-if="item.current_stock > 0" class="badge badge-purple text-xs">叠加</span>
                      <span v-else-if="item.status === 'valid'" class="badge badge-green text-xs">新增</span>
                      <span v-else class="badge badge-gray text-xs">跳过</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!previewData.items?.length" class="p-6 text-center text-[#86868b]">无数据</div>
            </div>
            <!-- 无有效数据警告 -->
            <div v-if="previewData.valid_count === 0" class="p-3 bg-[#fff8e1] border border-[#ffe082] rounded-lg text-[#ff9f0a] text-sm">
              没有有效的导入数据，请检查Excel文件是否正确填写了仓库、仓位和数量。
            </div>
            <!-- 按钮 -->
            <div class="flex gap-3 pt-3">
              <button type="button" @click="handleCancel" class="btn btn-secondary flex-1">取消</button>
              <button
                type="button"
                @click="handleConfirm"
                class="btn btn-primary flex-1"
                :disabled="previewData.valid_count === 0"
              >
                确认导入 ({{ previewData.valid_count }}条)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
/**
 * 导入预览弹窗组件
 * 展示预览数据，支持确认导入或取消返回导入弹窗
 */
import { computed } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useWarehousesStore } from '../../../stores/warehouses'
import { importProducts } from '../../../api/products'

const props = defineProps({
  /** 是否显示弹窗 */
  visible: Boolean,
  /** 预览数据对象 { total, valid_count, skip_count, items } */
  previewData: { type: Object, default: () => ({ total: 0, valid_count: 0, skip_count: 0, items: [] }) },
  /** 待导入的文件 */
  file: { type: [Object, File], default: null },
})

const emit = defineEmits(['update:visible', 'confirmed', 'cancelled'])

const appStore = useAppStore()
const warehousesStore = useWarehousesStore()

/** 文件名显示 */
const fileName = computed(() => props.file?.name || '')

/** 关闭弹窗 */
const close = () => emit('update:visible', false)

/** 取消：通知父组件回到导入弹窗 */
const handleCancel = () => {
  emit('cancelled')
}

/** 确认导入 */
const handleConfirm = async () => {
  if (appStore.submitting) return
  if (!props.file) {
    appStore.showToast('请先选择文件', 'error'); return
  }
  appStore.submitting = true
  try {
    const formData = new FormData()
    formData.append('file', props.file)
    const { data } = await importProducts(formData)
    appStore.showToast(data.message)
    close()
    emit('confirmed')
    // 导入后刷新仓库/仓位数据
    warehousesStore.loadWarehouses()
    warehousesStore.loadLocations()
  } catch (ex) {
    appStore.showToast('导入失败', 'error')
  } finally {
    appStore.submitting = false
  }
}
</script>
