<!--
  商品新增/编辑弹窗
  通过 product prop 区分新增（null）和编辑（传入商品对象）
-->
<template>
  <teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal">
        <!-- 标题栏 -->
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">{{ product ? '编辑商品' : '新增商品' }}</h3>
          <button @click="close" class="text-[#86868b] text-xl">&times;</button>
        </div>
        <!-- 表单 -->
        <div class="p-4">
          <form @submit.prevent="handleSave" class="space-y-3">
            <div>
              <label class="label">SKU *</label>
              <input v-model="form.sku" class="input" required :disabled="!!form.id">
            </div>
            <div>
              <label class="label">名称 *</label>
              <input v-model="form.name" class="input" required>
            </div>
            <div class="grid form-grid grid-cols-2 gap-3">
              <div>
                <label class="label">品牌</label>
                <input v-model="form.brand" class="input">
              </div>
              <div>
                <label class="label">分类</label>
                <input v-model="form.category" class="input">
              </div>
            </div>
            <div class="grid form-grid grid-cols-2 gap-3">
              <div>
                <label class="label">零售价</label>
                <input v-model.number="form.retail_price" type="number" step="0.01" class="input">
              </div>
              <div v-if="hasPermission('finance')">
                <label class="label">成本价</label>
                <input v-model.number="form.cost_price" type="number" step="0.01" class="input">
              </div>
            </div>
            <div class="flex gap-3 pt-3">
              <button type="button" @click="close" class="btn btn-secondary flex-1">取消</button>
              <button type="submit" class="btn btn-primary flex-1">保存</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
/**
 * 商品新增/编辑弹窗组件
 * 内部管理表单状态，保存后 emit saved 事件通知父组件刷新
 */
import { reactive, watch } from 'vue'
import { useAppStore } from '../../../stores/app'
import { usePermission } from '../../../composables/usePermission'
import { createProduct, updateProduct } from '../../../api/products'

const props = defineProps({
  /** 是否显示弹窗 */
  visible: Boolean,
  /** 要编辑的商品对象，null 表示新增 */
  product: { type: Object, default: null },
})

const emit = defineEmits(['update:visible', 'saved'])

const appStore = useAppStore()
const { hasPermission } = usePermission()

// 表单数据
const form = reactive({
  id: null, sku: '', name: '', brand: '',
  category: '', retail_price: null, cost_price: null,
})

/** 弹窗打开时初始化表单 */
watch(() => props.visible, (val) => {
  if (!val) return
  if (props.product) {
    // 编辑模式：填充已有数据
    Object.assign(form, {
      id: props.product.id,
      sku: props.product.sku,
      name: props.product.name,
      brand: props.product.brand,
      category: props.product.category,
      retail_price: props.product.retail_price,
      cost_price: props.product.cost_price,
    })
  } else {
    // 新增模式：重置表单
    Object.assign(form, {
      id: null, sku: '', name: '', brand: '',
      category: '', retail_price: null, cost_price: null,
    })
  }
})

/** 关闭弹窗 */
const close = () => emit('update:visible', false)

/** 保存商品 */
const handleSave = async () => {
  if (!form.sku || !form.sku.trim()) {
    appStore.showToast('请输入商品SKU', 'error'); return
  }
  if (!form.name || !form.name.trim()) {
    appStore.showToast('请输入商品名称', 'error'); return
  }
  if (form.retail_price == null || form.retail_price === '') {
    appStore.showToast('请输入零售价', 'error'); return
  }
  if (Number(form.retail_price) < 0) {
    appStore.showToast('零售价不能为负数', 'error'); return
  }
  if (form.cost_price == null || form.cost_price === '') {
    appStore.showToast('请输入成本价', 'error'); return
  }
  if (Number(form.cost_price) < 0) {
    appStore.showToast('成本价不能为负数', 'error'); return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    if (form.id) await updateProduct(form.id, form)
    else await createProduct(form)
    appStore.showToast('保存成功')
    close()
    emit('saved')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}
</script>
