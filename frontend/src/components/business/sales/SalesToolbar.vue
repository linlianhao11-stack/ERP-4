<!--
  销售工作台顶栏 - 页面标题 + 订单元信息
  显示订单类型、客户选择、员工选择、退货关联订单搜索
-->
<template>
  <div>
    <h2 class="text-lg font-bold mb-4">销售管理</h2>

    <div class="flex flex-wrap items-center gap-2 mb-4">
      <!-- 订单类型 -->
      <select
        :value="orderType"
        @change="$emit('update:orderType', $event.target.value)"
        class="input input-sm w-40"
      >
        <option value="CASH">现款</option>
        <option value="CREDIT">账期</option>
        <option value="CONSIGN_OUT">寄售调拨</option>
        <option value="CONSIGN_SETTLE">寄售结算</option>
        <option value="RETURN">退货</option>
      </select>

      <!-- 员工选择 -->
      <select
        :value="employeeId"
        @change="$emit('update:employeeId', $event.target.value)"
        class="input input-sm w-40"
      >
        <option value="">选业务员(可选)</option>
        <option v-for="s in employees" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>

      <!-- 退货模式：关联订单搜索 -->
      <div v-if="orderType === 'RETURN'" class="relative w-56">
        <input
          :value="returnOrderSearch"
          @input="$emit('update:returnOrderSearch', $event.target.value)"
          @focus="$emit('update:returnOrderDropdown', true)"
          class="input input-sm w-full"
          placeholder="搜索关联订单 *"
          autocomplete="off"
        >
        <div
          v-if="returnOrderDropdown && filteredReturnOrders.length"
          class="absolute top-full mt-1 w-full bg-surface border rounded shadow-lg max-h-60 overflow-y-auto"
          style="z-index: 30"
        >
          <button
            v-for="o in filteredReturnOrders"
            :key="o.id"
            type="button"
            @click="$emit('select-return-order', o)"
            class="w-full text-left px-2 py-2 hover:bg-elevated cursor-pointer border-b"
          >
            <div class="font-medium text-sm">{{ o.order_no }}</div>
            <div class="text-xs text-muted">{{ o.customer_name }} &middot; {{ o.created_at.split('T')[0] }} &middot; &yen;{{ o.total_amount }}</div>
          </button>
        </div>
        <div v-if="returnOrderDropdown" @click="$emit('update:returnOrderDropdown', false)" class="fixed inset-0" style="z-index: 20"></div>
      </div>

      <!-- 退货关联订单提示 -->
      <div
        v-if="orderType === 'RETURN' && selectedReturnOrder"
        class="text-sm px-2 py-1.5 bg-info-subtle rounded border border-primary text-primary flex items-center"
      >
        <span class="font-medium">退货订单：</span>{{ selectedReturnOrder.order_no }} - {{ selectedReturnOrder.customer_name }}
      </div>

      <!-- 客户选择（放最后，宽度更大以显示长名字） -->
      <div class="w-56">
        <SearchableSelect
          :options="customerOptions"
          :modelValue="customerId"
          @update:modelValue="$emit('update:customerId', $event)"
          :placeholder="'选客户(' + (needCustomer ? '必选' : '可选') + ')'"
          searchPlaceholder="搜索客户名/电话"
        />
      </div>
    </div>

    <!-- 备注 -->
    <div class="mb-3">
      <input
        :value="remark"
        @input="$emit('update:remark', $event.target.value)"
        class="input input-sm w-full max-w-md"
        placeholder="订单备注（可选）"
      >
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import SearchableSelect from '../../common/SearchableSelect.vue'

const props = defineProps({
  orderType: String,
  customerId: [String, Number],
  employeeId: [String, Number],
  customers: Array,
  employees: Array,
  needCustomer: Boolean,
  returnOrderSearch: String,
  returnOrderDropdown: Boolean,
  filteredReturnOrders: Array,
  selectedReturnOrder: Object,
  remark: String
})

defineEmits([
  'update:orderType', 'update:customerId', 'update:employeeId',
  'update:returnOrderSearch', 'update:returnOrderDropdown',
  'search-return-orders', 'select-return-order',
  'update:remark'
])

const customerOptions = computed(() =>
  (props.customers || []).map(c => ({
    id: c.id,
    label: c.name,
    sublabel: c.phone || ''
  }))
)
</script>
