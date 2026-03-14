<!--
  购物车单行商品
  从 ShoppingCart 提取的子组件，避免分组与非分组模式下的代码重复
-->
<template>
  <div>
    <!-- 商品名称和操作按钮 -->
    <div class="flex justify-between items-center mb-1">
      <div class="font-medium truncate text-sm flex-1">{{ item.name }}</div>
      <div class="flex gap-1 ml-2">
        <!-- 复制行按钮（非退货/寄售结算模式） -->
        <button
          v-if="orderType !== 'RETURN' && orderType !== 'CONSIGN_SETTLE'"
          @click="$emit('duplicate-line', idx)"
          class="w-5 h-5 rounded-full bg-info-subtle text-primary text-xs font-bold flex items-center justify-center hover:bg-info-subtle"
          title="从其他仓库再出一行"
        >+</button>
        <!-- 删除按钮 -->
        <button
          @click="$emit('remove-item', idx)"
          class="w-5 h-5 rounded-full bg-error-subtle text-error text-xs font-bold flex items-center justify-center hover:bg-error-subtle"
          title="删除"
        >-</button>
      </div>
    </div>

    <!-- 价格和数量调整 -->
    <div class="flex items-center gap-2 text-sm">
      <span class="text-muted">&yen;</span>
      <input v-model.number="item.unit_price" type="number" step="0.01" class="input input-sm w-16 text-right">
      <span class="text-muted">&times;</span>
      <button @click="item.quantity = Math.max(1, item.quantity - 1)" class="w-6 h-6 rounded border text-xs">-</button>
      <input
        v-model.number="item.quantity"
        type="number"
        min="1"
        class="input input-sm w-14 text-center"
        @blur="item.quantity = Math.max(1, Math.floor(item.quantity) || 1)"
      >
      <button
        @click="$emit('increment-quantity', item)"
        class="w-6 h-6 rounded border text-xs"
      >+</button>
    </div>

    <!-- 仓库/仓位选择（非寄售结算模式） -->
    <div v-if="orderType !== 'CONSIGN_SETTLE'" class="mt-2 space-y-1">
      <select
        v-model="item.warehouse_id"
        @change="$emit('update-warehouse', idx, item.warehouse_id)"
        class="input input-sm text-xs w-full"
      >
        <option value="">选择仓库 *</option>
        <option
          v-for="w in warehouses.filter(x => !x.is_virtual)"
          :key="w.id"
          :value="w.id"
        >{{ w.name }} (可用: {{ item.stocks?.filter(s => s.warehouse_id === w.id).reduce((sum, s) => sum + (s.available_qty ?? s.quantity), 0) || 0 }})</option>
      </select>
      <select
        v-model="item.location_id"
        @change="$emit('update-location', idx, item.location_id)"
        class="input input-sm text-xs w-full"
        :disabled="!item.warehouse_id"
      >
        <option value="">{{ item.warehouse_id ? '选择仓位 *' : '请先选择仓库' }}</option>
        <option
          v-for="loc in getCartItemLocations(item)"
          :key="loc.id"
          :value="loc.id"
        >{{ loc.code }} (可用: {{ (s => s ? (s.available_qty ?? s.quantity) : 0)(item.stocks?.find(s => s.warehouse_id === parseInt(item.warehouse_id) && s.location_id === loc.id)) }})</option>
      </select>
      <!-- 库存提示 -->
      <div v-if="item.warehouse_id && item.location_id" class="text-xs text-secondary">
        可用库存:
        <span :class="getCartStock(item) >= item.quantity ? 'text-success font-semibold' : 'text-error font-semibold'">
          {{ getCartStock(item) }}
        </span> 件
      </div>
    </div>

    <!-- 退货数量上限提示 -->
    <div v-if="orderType === 'RETURN' && item.max_return_qty" class="text-xs text-warning mt-1">
      最多可退: {{ item.max_return_qty }} 件
    </div>

    <!-- 行小计 -->
    <div class="text-right text-primary font-semibold text-sm mt-1">
      &yen;{{ (Math.round(item.unit_price * item.quantity * 100) / 100).toFixed(2) }}
    </div>
  </div>
</template>

<script setup>
/**
 * 购物车单行商品子组件
 * 提供商品编辑、仓库仓位选择、库存提示等功能
 */
defineProps({
  /** 商品行数据 */
  item: Object,
  /** 行索引（在 cart 数组中的原始位置） */
  idx: Number,
  /** 订单类型 */
  orderType: String,
  /** 仓库列表 */
  warehouses: Array,
  /** 获取可用库存的函数 */
  getCartStock: Function,
  /** 获取仓位列表的函数 */
  getCartItemLocations: Function
})

defineEmits([
  'duplicate-line', 'remove-item', 'increment-quantity',
  'update-warehouse', 'update-location'
])
</script>
