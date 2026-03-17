<!--
  销售工作台表格 - 可编辑商品明细表
  包含数据行（WorksheetRow）和搜索行（ProductSearchRow）
  退货模式下隐藏搜索行，显示预填充的退货商品
-->
<template>
  <div>
    <!-- 多账套警告 -->
    <div v-if="isMultiAccountSet" class="mb-3 p-2.5 bg-warning-subtle border border-warning rounded-lg text-xs">
      <div class="font-semibold text-warning">本单包含多个账套的商品</div>
      <div class="text-secondary mt-0.5">财务将按账套分别生成应收单</div>
    </div>

    <div class="card overflow-hidden">
      <div class="table-container">
        <table class="w-full text-sm worksheet-table">
          <thead>
            <tr class="bg-elevated text-xs text-secondary uppercase tracking-wider">
              <th class="px-3 py-2.5 text-center w-10 font-medium">#</th>
              <th class="px-3 py-2.5 text-left font-medium">商品</th>
              <th class="px-3 py-2.5 text-center w-36 font-medium">数量</th>
              <th class="px-3 py-2.5 text-left w-24 font-medium">单价</th>
              <th v-if="showCost" class="px-3 py-2.5 text-right w-20 md-hide font-medium">成本</th>
              <th class="px-3 py-2.5 text-left w-36 font-medium">仓库</th>
              <th class="px-3 py-2.5 text-left w-28 md-hide font-medium">仓位</th>
              <th class="px-3 py-2.5 text-right w-24 font-medium">小计</th>
              <th class="px-3 py-2.5 text-center w-20 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <!-- 数据行 -->
            <WorksheetRow
              v-for="(item, idx) in cart"
              :key="item._id"
              :item="item"
              :index="idx"
              :order-type="orderType"
              :warehouses="warehouses"
              :show-cost="showCost"
              @remove="$emit('remove-item', $event)"
              @duplicate="$emit('duplicate-line', $event)"
            />

            <!-- 搜索行（退货模式下隐藏） -->
            <ProductSearchRow
              v-if="orderType !== 'RETURN'"
              :products="products"
              :order-type="orderType"
              @add-item="(product, row) => $emit('add-from-search', product, row)"
            />

            <!-- 空状态 -->
            <tr v-if="!cart.length && orderType !== 'RETURN'">
              <td :colspan="showCost ? 9 : 8" class="px-3 py-8 text-center text-muted">
                在上方搜索框输入商品名称开始添加
              </td>
            </tr>
            <tr v-if="!cart.length && orderType === 'RETURN'">
              <td :colspan="showCost ? 9 : 8" class="px-3 py-8 text-center text-muted">
                请在顶栏搜索并选择要退货的原始订单
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { usePermission } from '../../../composables/usePermission'
import WorksheetRow from './WorksheetRow.vue'
import ProductSearchRow from './ProductSearchRow.vue'

defineProps({
  cart: { type: Array, required: true },
  orderType: { type: String, required: true },
  warehouses: { type: Array, required: true },
  products: { type: Array, required: true },
  isMultiAccountSet: { type: Boolean, default: false }
})

defineEmits(['remove-item', 'duplicate-line', 'add-from-search'])

const { hasPermission } = usePermission()
const showCost = hasPermission('finance')
</script>

<style scoped>
.worksheet-table :deep(tbody tr:nth-child(even):not(:last-child)) {
  background: var(--color-elevated);
}
.worksheet-table :deep(tbody tr:hover) {
  background: var(--color-primary-muted);
}
.worksheet-table :deep(thead th) {
  border-bottom: 2px solid var(--color-border);
}
.worksheet-table :deep(tbody td) {
  border-bottom: 1px solid var(--color-border-light);
}
</style>
