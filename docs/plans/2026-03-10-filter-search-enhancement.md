# 全局筛选搜索增强 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为销售开单、订单明细、欠款明细、收款管理、付款管理、出入库日志六个模块增加筛选、搜索和重置功能。

**Architecture:** 新建 SearchableSelect 通用组件用于客户搜索下拉。各模块独立添加筛选 UI，后端扩展现有接口参数。筛选状态各模块本地管理，不引入全局 store。重置按钮统一用 lucide RotateCcw 图标。

**Tech Stack:** Vue 3 (Composition API) / FastAPI + Tortoise ORM / lucide-vue-next

---

### Task 1: SearchableSelect 通用组件

**Files:**
- Create: `frontend/src/components/common/SearchableSelect.vue`

**Step 1: 创建组件文件**

```vue
<template>
  <div class="searchable-select" ref="wrapperRef">
    <div class="input text-sm flex items-center cursor-pointer" @click="toggle" :class="{ 'text-muted': !selectedLabel }">
      <span class="flex-1 truncate">{{ selectedLabel || placeholder }}</span>
      <span v-if="modelValue" class="ml-1 text-muted hover:text-foreground" @click.stop="clear">&times;</span>
      <span v-else class="ml-1 text-muted">▾</span>
    </div>
    <div v-if="open" class="searchable-select-dropdown">
      <input
        ref="searchInputRef"
        v-model="searchText"
        class="input input-sm w-full mb-1"
        :placeholder="searchPlaceholder"
        @keydown.esc="open = false"
      />
      <div class="searchable-select-options">
        <div
          v-for="opt in filtered"
          :key="opt.id"
          class="searchable-select-option"
          :class="{ active: opt.id == modelValue }"
          @click="select(opt)"
        >
          <div class="truncate">{{ opt.label }}</div>
          <div v-if="opt.sublabel" class="text-xs text-muted truncate">{{ opt.sublabel }}</div>
        </div>
        <div v-if="!filtered.length" class="px-3 py-2 text-xs text-muted text-center">无匹配项</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  options: { type: Array, default: () => [] },
  modelValue: { type: [String, Number], default: '' },
  placeholder: { type: String, default: '请选择' },
  searchPlaceholder: { type: String, default: '搜索...' }
})
const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const searchText = ref('')
const wrapperRef = ref(null)
const searchInputRef = ref(null)

const selectedLabel = computed(() => {
  const opt = props.options.find(o => o.id == props.modelValue)
  return opt ? opt.label : ''
})

const filtered = computed(() => {
  if (!searchText.value) return props.options
  const kw = searchText.value.toLowerCase()
  return props.options.filter(o =>
    (o.label || '').toLowerCase().includes(kw) ||
    (o.sublabel || '').toLowerCase().includes(kw)
  )
})

const toggle = () => {
  open.value = !open.value
  if (open.value) {
    searchText.value = ''
    nextTick(() => searchInputRef.value?.focus())
  }
}

const select = (opt) => {
  emit('update:modelValue', opt.id)
  open.value = false
}

const clear = () => {
  emit('update:modelValue', '')
}

const onClickOutside = (e) => {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))
</script>

<style scoped>
.searchable-select {
  position: relative;
}
.searchable-select-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 50;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 6px;
  margin-top: 2px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.searchable-select-options {
  max-height: 200px;
  overflow-y: auto;
}
.searchable-select-option {
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.searchable-select-option:hover {
  background: var(--color-elevated);
}
.searchable-select-option.active {
  background: var(--color-primary-muted);
}
</style>
```

**Step 2: 验证编译**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 2: 销售开单 — 客户可搜索下拉

**Files:**
- Modify: `frontend/src/components/business/sales/ShoppingCart.vue`

**Step 1: 添加 import**

在 `<script setup>` 的 import 区域（约 line 187-189），在 `import { useFormat }` 之前添加：

```javascript
import SearchableSelect from '../../common/SearchableSelect.vue'
```

**Step 2: 添加客户选项计算属性**

在 `const { fmt } = useFormat()` 之后（约 line 195）添加：

```javascript
const customerOptions = computed(() =>
  (props.customers || []).map(c => ({
    id: c.id,
    label: c.name,
    sublabel: c.phone || ''
  }))
)
```

需要在 import 行加入 `computed`：

将 `import { useFormat } from '../../../composables/useFormat'` 的上方（已有的 import from vue 行）检查是否有 `computed`，如果没有则添加。

**Step 3: 替换客户选择 UI**

找到客户选择区域（约 line 106-117）：

```html
<!-- 客户选择 -->
<div class="mb-2">
  <select
    :value="customerId"
    @change="$emit('update:customerId', $event.target.value)"
    class="input text-sm"
  >
    <option value="">选客户({{ needCustomer ? '必选' : '可选' }})</option>
    <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
  </select>
</div>
```

替换为：

```html
<!-- 客户选择 -->
<div class="mb-2">
  <SearchableSelect
    :options="customerOptions"
    :modelValue="customerId"
    @update:modelValue="$emit('update:customerId', $event)"
    :placeholder="'选客户(' + (needCustomer ? '必选' : '可选') + ')'"
    searchPlaceholder="搜索客户名/电话"
  />
</div>
```

**Step 4: 验证编译**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 3: 订单明细 — 付款状态筛选

**Files:**
- Modify: `backend/app/routers/finance.py:28-120`
- Modify: `frontend/src/components/business/finance/FinanceOrdersTab.vue`

**Step 1: 后端 — all-orders 增加 payment_status 参数 + shipping_status 返回**

在 `get_all_orders` 函数签名（约 line 28-38）中，在 `unpaid_only` 之前添加 `payment_status` 参数：

```python
@router.get("/all-orders")
async def get_all_orders(
    order_type: Optional[str] = None,
    payment_status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    account_set_id: Optional[int] = None,
    unpaid_only: bool = False,
    offset: int = 0,
    limit: int = 200,
    user: User = Depends(require_permission("finance"))
):
```

在 `if order_type:` 之后（约 line 54 后），添加 payment_status 筛选逻辑：

```python
    if payment_status:
        if payment_status == "cancelled":
            query = query.filter(shipping_status="cancelled")
        elif payment_status == "cleared":
            query = query.filter(is_cleared=True).exclude(shipping_status="cancelled")
        elif payment_status == "uncleared":
            query = query.filter(is_cleared=False).exclude(shipping_status="cancelled")
        elif payment_status == "unconfirmed":
            uc_ids = set()
            for p in await Payment.filter(is_confirmed=False).all():
                if p.order_id:
                    uc_ids.add(p.order_id)
            for po in await PaymentOrder.filter(payment__is_confirmed=False).all():
                uc_ids.add(po.order_id)
            if uc_ids:
                query = query.filter(id__in=list(uc_ids))
            else:
                query = query.filter(id=-1)
```

在响应 dict 中（约 line 101-119），在 `"has_unconfirmed_payment"` 之后添加 `shipping_status`：

```python
            "has_unconfirmed_payment": o.id in unconfirmed_order_ids,
            "shipping_status": o.shipping_status,
```

**Step 2: 前端 — 添加付款状态筛选下拉**

在 FinanceOrdersTab.vue 的 `orderFilter` reactive 对象（约 script 内）添加 `payment_status` 字段：

```javascript
const orderFilter = reactive({ type: '', payment_status: '', start: '', end: '', search: '', account_set_id: '' })
```

在模板的订单类型下拉之后（约 line 18 后，`</select>` 之后），添加付款状态下拉：

```html
          <!-- 付款状态下拉 -->
          <select v-model="orderFilter.payment_status" @change="resetPage(); loadOrders()" class="input w-auto text-sm" style="flex-shrink:0">
            <option value="">全部状态</option>
            <option value="cleared">已结清</option>
            <option value="uncleared">未结清</option>
            <option value="unconfirmed">待确认</option>
            <option value="cancelled">已取消</option>
          </select>
```

在 `loadOrders` 函数中（构建 params 的区域），添加：

```javascript
    if (orderFilter.payment_status) params.payment_status = orderFilter.payment_status
```

**Step 3: 前端 — 添加重置按钮**

在 FinanceOrdersTab.vue 的 `<script setup>` import 区域添加 lucide 图标：

```javascript
import { RotateCcw } from 'lucide-vue-next'
```

在模板的搜索框一行（约 line 47 `<input v-model="orderFilter.search"...>`）后面，添加重置按钮。将搜索行改为 flex 布局：

将第二行搜索区域：
```html
      <!-- 第二行：搜索框 -->
      <input v-model="orderFilter.search" @input="debouncedLoadOrders" class="input w-full md:w-auto text-sm" placeholder="搜索订单号/客户/SN码/快递单号">
```

改为：
```html
      <!-- 第二行：搜索框 + 重置 -->
      <div class="flex items-center gap-2">
        <input v-model="orderFilter.search" @input="debouncedLoadOrders" class="input flex-1 md:w-auto text-sm" placeholder="搜索订单号/客户/SN码/快递单号">
        <button @click="resetOrderFilters" class="btn btn-secondary btn-sm flex-shrink-0" title="重置筛选"><RotateCcw :size="14" /></button>
      </div>
```

添加 `resetOrderFilters` 函数：

```javascript
/** 重置所有订单筛选条件 */
const resetOrderFilters = () => {
  orderFilter.type = ''
  orderFilter.payment_status = ''
  orderFilter.start = ''
  orderFilter.end = ''
  orderFilter.search = ''
  orderFilter.account_set_id = ''
  orderDatePreset.value = ''
  resetPage()
  loadOrders()
}
```

**Step 4: 验证编译**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 4: 欠款明细 — 筛选搜索增强

**Files:**
- Modify: `backend/app/routers/finance.py:262-283` (unpaid-orders endpoint)
- Modify: `frontend/src/api/finance.js`
- Modify: `frontend/src/components/business/finance/FinanceUnpaidTab.vue`

**Step 1: 后端 — 扩展 unpaid-orders 接口**

将 `get_unpaid_orders` 函数（约 line 262-283）替换为：

```python
@router.get("/unpaid-orders")
async def get_unpaid_orders(
    customer_id: Optional[int] = None,
    order_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_permission("finance"))
):
    """获取未结清的账期/寄售结算订单（仅显示实际欠款 > 0 的订单）"""
    query = Order.filter(
        is_cleared=False,
        order_type__in=["CREDIT", "CONSIGN_SETTLE"],
        total_amount__gt=F('paid_amount')
    )
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if order_type:
        query = query.filter(order_type=order_type)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))
    if search:
        query = query.filter(Q(order_no__icontains=search) | Q(customer__name__icontains=search))
    orders = await query.order_by("created_at").select_related("customer", "salesperson")
    return [{
        "id": o.id, "order_no": o.order_no, "order_type": o.order_type,
        "customer_id": o.customer_id, "customer_name": o.customer.name if o.customer else None,
        "salesperson_name": o.salesperson.name if o.salesperson else None,
        "total_amount": float(o.total_amount), "paid_amount": float(o.paid_amount),
        "unpaid_amount": float(o.total_amount - o.paid_amount),
        "created_at": o.created_at.isoformat()
    } for o in orders]
```

**Step 2: 前端 — FinanceUnpaidTab 添加筛选 UI**

在模板的客户筛选 `<div class="card mb-2 p-3">` 内容（line 4-9），替换为完整筛选栏：

```html
    <!-- 筛选栏 -->
    <div class="card mb-2 p-3">
      <div class="flex flex-wrap items-center gap-2">
        <select v-model="financeCustomerId" @change="loadUnpaid" class="input w-auto text-sm">
          <option value="">全部客户</option>
          <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }} ({{ getBalanceLabel(c.balance) }} ¥{{ formatBalance(c.balance) }})</option>
        </select>
        <select v-model="unpaidFilter.order_type" @change="loadUnpaid" class="input w-auto text-sm">
          <option value="">全部类型</option>
          <option value="CREDIT">赊销</option>
          <option value="CONSIGN_SETTLE">寄售结算</option>
        </select>
        <input v-model="unpaidFilter.start" @change="loadUnpaid" type="date" class="input w-auto text-sm hidden md:block">
        <input v-model="unpaidFilter.end" @change="loadUnpaid" type="date" class="input w-auto text-sm hidden md:block">
        <input v-model="unpaidFilter.search" @input="debouncedLoadUnpaid" class="input text-sm flex-1 min-w-[120px]" placeholder="搜索订单号/客户名">
        <button @click="resetUnpaidFilters" class="btn btn-secondary btn-sm flex-shrink-0" title="重置筛选"><RotateCcw :size="14" /></button>
      </div>
    </div>
```

**Step 3: 前端 — 添加筛选相关 script 代码**

在 `<script setup>` 的 import 区域添加：

```javascript
import { RotateCcw } from 'lucide-vue-next'
```

在 `const financeCustomerId = ref('')` 之后（约 line 152 后）添加：

```javascript
/** 欠款筛选条件 */
const unpaidFilter = reactive({ order_type: '', start: '', end: '', search: '' })
```

修改 `loadUnpaid` 函数，传递所有筛选参数：

```javascript
const loadUnpaid = async () => {
  try {
    const p = {}
    if (financeCustomerId.value) p.customer_id = financeCustomerId.value
    if (unpaidFilter.order_type) p.order_type = unpaidFilter.order_type
    if (unpaidFilter.start) p.start_date = unpaidFilter.start
    if (unpaidFilter.end) p.end_date = unpaidFilter.end
    if (unpaidFilter.search) p.search = unpaidFilter.search
    const { data } = await getUnpaidOrders(p)
    unpaidOrders.value = data
  } catch (e) {
    console.error(e)
  }
}
```

添加防抖搜索和重置函数：

```javascript
/** 防抖搜索 */
let _unpaidSearchTimer = null
const debouncedLoadUnpaid = () => {
  clearTimeout(_unpaidSearchTimer)
  _unpaidSearchTimer = setTimeout(loadUnpaid, 300)
}

/** 重置欠款筛选 */
const resetUnpaidFilters = () => {
  financeCustomerId.value = ''
  unpaidFilter.order_type = ''
  unpaidFilter.start = ''
  unpaidFilter.end = ''
  unpaidFilter.search = ''
  loadUnpaid()
}
```

在 import 中添加 `onUnmounted`（如果没有的话），在 onMounted 附近添加清理：

```javascript
onUnmounted(() => clearTimeout(_unpaidSearchTimer))
```

**Step 4: 验证编译**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 5: 收款管理 — 筛选搜索增强

**Files:**
- Modify: `backend/app/routers/finance.py:340-385` (payments endpoint)
- Modify: `frontend/src/api/finance.js`
- Modify: `frontend/src/components/business/FinancePaymentsPanel.vue`

**Step 1: 后端 — 扩展 payments 接口**

将 `list_payments` 函数签名（约 line 340-347）修改为：

```python
@router.get("/payments")
async def list_payments(
    customer_id: Optional[int] = None,
    source: Optional[str] = None,
    is_confirmed: Optional[bool] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    user: User = Depends(require_permission("finance"))
):
```

在 `if source:` 之后（约 line 352 后），添加新筛选条件：

```python
    if is_confirmed is not None:
        query = query.filter(is_confirmed=is_confirmed)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))
    if search:
        # 搜索客户名或关联订单号
        matching_order_ids = set()
        from app.models import PaymentOrder as PO_model
        order_matches = await Order.filter(order_no__icontains=search).values_list("id", flat=True)
        matching_order_ids.update(order_matches)
        po_links = await PaymentOrder.filter(order_id__in=list(matching_order_ids)).values_list("payment_id", flat=True) if matching_order_ids else []
        direct_payment_ids = await Payment.filter(order_id__in=list(matching_order_ids)).values_list("id", flat=True) if matching_order_ids else []
        search_payment_ids = set(po_links) | set(direct_payment_ids)
        if search_payment_ids:
            query = query.filter(Q(customer__name__icontains=search) | Q(id__in=list(search_payment_ids)))
        else:
            query = query.filter(customer__name__icontains=search)
```

**Step 2: API 函数 — getPayments 接受 params**

在 `frontend/src/api/finance.js` 中，将：

```javascript
export const getPayments = () => api.get('/finance/payments')
```

改为：

```javascript
export const getPayments = (params) => api.get('/finance/payments', { params })
```

**Step 3: 前端 — FinancePaymentsPanel 添加筛选 UI**

在模板最外层 `<div>` 内（line 2），在 Mobile cards 之前插入筛选栏：

```html
    <!-- 筛选栏 -->
    <div class="card mb-2 p-3">
      <div class="flex flex-wrap items-center gap-2">
        <select v-model="payFilter.is_confirmed" @change="loadPaymentsData" class="input w-auto text-sm">
          <option value="">全部状态</option>
          <option value="false">待确认</option>
          <option value="true">已确认</option>
        </select>
        <input v-model="payFilter.start" @change="loadPaymentsData" type="date" class="input w-auto text-sm hidden md:block">
        <input v-model="payFilter.end" @change="loadPaymentsData" type="date" class="input w-auto text-sm hidden md:block">
        <input v-model="payFilter.search" @input="debouncedLoadPayments" class="input text-sm flex-1 min-w-[120px]" placeholder="搜索订单号/客户名">
        <button @click="resetPayFilters" class="btn btn-secondary btn-sm flex-shrink-0" title="重置筛选"><RotateCcw :size="14" /></button>
      </div>
    </div>
```

**Step 4: 前端 — 添加筛选 script 代码**

在 import 区域添加：

```javascript
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { RotateCcw } from 'lucide-vue-next'
```

（注意原文件 import 是 `ref, computed, onMounted`，需要加 `reactive, onUnmounted`）

在 `const payments = ref([])` 之后添加：

```javascript
const payFilter = reactive({ is_confirmed: '', start: '', end: '', search: '' })
```

修改 `loadPaymentsData` 传递参数：

```javascript
const loadPaymentsData = async () => {
  try {
    const params = {}
    if (payFilter.is_confirmed !== '') params.is_confirmed = payFilter.is_confirmed
    if (payFilter.start) params.start_date = payFilter.start
    if (payFilter.end) params.end_date = payFilter.end
    if (payFilter.search) params.search = payFilter.search
    const { data } = await getPayments(params)
    payments.value = data
  } catch (e) {
    console.error(e)
    appStore.showToast(e.response?.data?.detail || '加载收款记录失败', 'error')
  }
}
```

添加防抖和重置：

```javascript
let _paySearchTimer = null
const debouncedLoadPayments = () => {
  clearTimeout(_paySearchTimer)
  _paySearchTimer = setTimeout(loadPaymentsData, 300)
}

const resetPayFilters = () => {
  payFilter.is_confirmed = ''
  payFilter.start = ''
  payFilter.end = ''
  payFilter.search = ''
  loadPaymentsData()
}

onUnmounted(() => clearTimeout(_paySearchTimer))
```

**Step 5: 验证编译**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 6: 付款管理 — 筛选搜索增强

**Files:**
- Modify: `frontend/src/components/business/FinancePayablesPanel.vue`

后端 `GET /purchase-orders` 已支持 `status`、`start_date`、`end_date`、`search` 参数，无需改动。

**Step 1: 前端 — 添加筛选栏 UI**

在模板最外层 `<div>` 内（line 2），在 Mobile cards 之前插入筛选栏：

```html
    <!-- 筛选栏 -->
    <div class="card mb-2 p-3">
      <div class="flex flex-wrap items-center gap-2">
        <select v-model="poFilter.status" @change="loadPurchaseOrdersData" class="input w-auto text-sm">
          <option value="">全部状态</option>
          <option value="pending_review">待审核</option>
          <option value="pending">待付款</option>
          <option value="paid">已付款</option>
          <option value="completed">已完成</option>
          <option value="cancelled">已取消</option>
          <option value="rejected">已拒绝</option>
          <option value="returned">已退货</option>
        </select>
        <input v-model="poFilter.start" @change="loadPurchaseOrdersData" type="date" class="input w-auto text-sm hidden md:block">
        <input v-model="poFilter.end" @change="loadPurchaseOrdersData" type="date" class="input w-auto text-sm hidden md:block">
        <input v-model="poFilter.search" @input="debouncedLoadPO" class="input text-sm flex-1 min-w-[120px]" placeholder="搜索采购单号/供应商">
        <button @click="resetPOFilters" class="btn btn-secondary btn-sm flex-shrink-0" title="重置筛选"><RotateCcw :size="14" /></button>
      </div>
    </div>
```

**Step 2: 前端 — 添加筛选 script 代码**

修改 import：

```javascript
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { RotateCcw } from 'lucide-vue-next'
```

在 `const purchaseOrders = ref([])` 之后添加：

```javascript
const poFilter = reactive({ status: '', start: '', end: '', search: '' })
```

修改 `loadPurchaseOrdersData` 传递筛选参数：

```javascript
const loadPurchaseOrdersData = async () => {
  try {
    const params = {}
    if (poFilter.status) params.status = poFilter.status
    if (poFilter.start) params.start_date = poFilter.start
    if (poFilter.end) params.end_date = poFilter.end
    if (poFilter.search) params.search = poFilter.search
    const { data } = await getPurchaseOrders(params)
    purchaseOrders.value = data.items || data
  } catch (e) {
    console.error(e)
    appStore.showToast(e.response?.data?.detail || '加载数据失败', 'error')
  }
}
```

移除 `filteredPurchaseOrders` computed（line 176-178），因为筛选现在由服务端完成。将模板中所有 `filteredPurchaseOrders` 替换为 `purchaseOrders`。

添加防抖和重置：

```javascript
let _poSearchTimer = null
const debouncedLoadPO = () => {
  clearTimeout(_poSearchTimer)
  _poSearchTimer = setTimeout(loadPurchaseOrdersData, 300)
}

const resetPOFilters = () => {
  poFilter.status = ''
  poFilter.start = ''
  poFilter.end = ''
  poFilter.search = ''
  loadPurchaseOrdersData()
}

onUnmounted(() => clearTimeout(_poSearchTimer))
```

**Step 3: 验证编译**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 7: 出入库日志 — 日期+搜索增强

**Files:**
- Modify: `backend/app/routers/finance.py:208-259` (stock-logs endpoint)
- Modify: `frontend/src/components/business/FinanceLogsPanel.vue`

**Step 1: 后端 — stock-logs 增加 search 参数**

在 `get_finance_stock_logs` 签名中增加 `search`：

```python
@router.get("/stock-logs")
async def get_finance_stock_logs(
    change_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
    user: User = Depends(require_permission("finance"))
):
```

在 `if end_date:` 过滤之后，添加 search 筛选：

```python
    if search:
        query = query.filter(
            Q(product__name__icontains=search) | Q(product__sku__icontains=search) | Q(warehouse__name__icontains=search)
        )
```

**Step 2: 前端 — FinanceLogsPanel 添加日期和搜索**

修改模板的筛选栏（line 3-20），在类型下拉后添加日期和搜索控件：

将 `<div class="p-3 border-b flex flex-wrap gap-2">` 内容替换为：

```html
    <div class="p-3 border-b flex flex-wrap items-center gap-2">
      <select v-model="logFilter.type" @change="loadLogs" class="input w-auto text-sm">
        <option value="">全部类型</option>
        <option value="RESTOCK">入库</option>
        <option value="SALE">销售出库</option>
        <option value="RETURN">退货入库</option>
        <option value="CONSIGN_OUT">寄售调拨</option>
        <option value="CONSIGN_SETTLE">寄售结算</option>
        <option value="CONSIGN_RETURN">寄售退货</option>
        <option value="ADJUST">库存调整</option>
        <option value="PURCHASE_IN">采购入库</option>
        <option value="PURCHASE_RETURN">采购退货</option>
        <option value="TRANSFER_OUT">调拨出库</option>
        <option value="TRANSFER_IN">调拨入库</option>
        <option value="RESERVE">库存预留</option>
        <option value="RESERVE_CANCEL">取消预留</option>
      </select>
      <input v-model="logFilter.start" @change="loadLogs" type="date" class="input w-auto text-sm hidden md:block">
      <input v-model="logFilter.end" @change="loadLogs" type="date" class="input w-auto text-sm hidden md:block">
      <input v-model="logFilter.search" @input="debouncedLoadLogs" class="input text-sm flex-1 min-w-[120px]" placeholder="搜索商品名/SKU/仓库名">
      <button @click="resetLogFilters" class="btn btn-secondary btn-sm flex-shrink-0" title="重置筛选"><RotateCcw :size="14" /></button>
    </div>
```

**Step 3: 前端 — 添加筛选 script 代码**

修改 import：

```javascript
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { RotateCcw } from 'lucide-vue-next'
```

修改 `logFilter` reactive（line 64）：

```javascript
const logFilter = reactive({ type: '', start: '', end: '', search: '' })
```

修改 `loadLogs` 传递所有参数：

```javascript
const loadLogs = async () => {
  try {
    const params = {}
    if (logFilter.type) params.change_type = logFilter.type
    if (logFilter.start) params.start_date = logFilter.start
    if (logFilter.end) params.end_date = logFilter.end
    if (logFilter.search) params.search = logFilter.search
    const { data } = await getStockLogs(params)
    stockLogs.value = data
  } catch (e) {
    console.error(e)
  }
}
```

添加防抖和重置：

```javascript
let _logSearchTimer = null
const debouncedLoadLogs = () => {
  clearTimeout(_logSearchTimer)
  _logSearchTimer = setTimeout(loadLogs, 300)
}

const resetLogFilters = () => {
  logFilter.type = ''
  logFilter.start = ''
  logFilter.end = ''
  logFilter.search = ''
  loadLogs()
}

onUnmounted(() => clearTimeout(_logSearchTimer))
```

**Step 4: 验证编译**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 8: 构建部署 + 验证

**Step 1: 前端构建**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static
```

**Step 2: Docker 重建部署**

```bash
cd /Users/lin/Desktop/erp-4 && docker compose build erp && docker compose up -d erp
```

**Step 3: 验证场景**

在 8090 端口测试：

1. 销售开单 → 客户下拉 → 输入关键字 → 应实时过滤客户列表 → 选中后正常显示
2. 订单明细 → 付款状态筛选 → 选择"未结清" → 只显示未结清订单
3. 订单明细 → 点击重置按钮 → 所有筛选清空
4. 欠款明细 → 类型/日期/搜索筛选都可用 → 重置按钮清空
5. 收款管理 → 状态/日期/搜索筛选都可用 → 重置按钮清空
6. 付款管理 → 状态/日期/搜索筛选都可用 → 重置按钮清空
7. 出入库日志 → 日期/搜索筛选可用 → 重置按钮清空
8. 各模块搜索框输入后 300ms 自动触发搜索
