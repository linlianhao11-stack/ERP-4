<!--
  商品导入弹窗
  提供模板下载和文件上传，解析后 emit preview 事件切换到预览弹窗
-->
<template>
  <teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal">
        <!-- 标题栏 -->
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">导入商品</h3>
          <button @click="close" class="text-muted text-xl">&times;</button>
        </div>
        <!-- 内容 -->
        <div class="p-4">
          <div class="space-y-4">
            <!-- 说明 -->
            <div class="p-4 bg-info-subtle rounded-lg">
              <h4 class="font-semibold text-primary mb-2">导入说明</h4>
              <ul class="text-sm text-primary space-y-1">
                <li>支持 .xlsx 和 .xls 格式</li>
                <li>SKU为必填字段，用于匹配商品</li>
                <li>已存在的SKU将更新信息，新SKU将创建商品</li>
              </ul>
            </div>
            <!-- 操作按钮 -->
            <div class="flex gap-3">
              <button type="button" @click="handleDownloadTemplate" class="btn btn-secondary flex-1 text-center">下载模板</button>
              <label class="btn btn-primary flex-1 text-center cursor-pointer">
                选择文件
                <input type="file" @change="handleFileChange" accept=".xlsx,.xls" class="hidden">
              </label>
            </div>
            <div class="flex gap-3 pt-3">
              <button type="button" @click="close" class="btn btn-secondary flex-1">关闭</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
/**
 * 商品导入弹窗组件
 * 下载模板 + 上传文件预览
 * 文件选择后调用预览 API，成功后 emit preview 事件携带文件和预览数据
 */
import { useAppStore } from '../../../stores/app'
import { getTemplate, previewImport } from '../../../api/products'

const props = defineProps({
  /** 是否显示弹窗 */
  visible: Boolean,
})

const emit = defineEmits(['update:visible', 'preview'])

const appStore = useAppStore()

/** 关闭弹窗 */
const close = () => emit('update:visible', false)

/** 下载导入模板 */
const handleDownloadTemplate = async () => {
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const { data } = await getTemplate()
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'import_template.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    appStore.showToast('模板已下载')
  } catch (e) {
    appStore.showToast('下载失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

/** 选择文件后解析预览 */
const handleFileChange = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const { data } = await previewImport(formData)
    // 通知父组件切换到预览弹窗
    emit('preview', { file, previewData: data })
  } catch (ex) {
    appStore.showToast('解析文件失败', 'error')
  }
  // 重置 input 以允许再次选择相同文件
  e.target.value = ''
}
</script>
