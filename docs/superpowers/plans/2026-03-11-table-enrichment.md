# Table Enrichment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich table displays in Purchase Orders, Finance Order Details, and Logistics panels with dynamic column visibility, expandable detail rows, and summary/detail view mode toggle. Detail mode (rowspan flat table) is deferred to Phase 2 — this plan implements Summary mode with expand/collapse only; the view mode toggle UI is added but detail rendering is a placeholder that falls back to summary.

**Architecture:** Extract a shared `useColumnConfig` composable from the existing `useShipment.js` column pattern. Each panel gets a column definition array; the composable handles visibility toggling, localStorage persistence, and view mode state. Backend APIs are extended to return additional fields needed by new columns. Sub-table item data is fetched on-demand when a row is expanded.

**Tech Stack:** Vue 3 Composition API, Tailwind CSS 4, FastAPI, Tortoise ORM, localStorage

**Spec:** `docs/superpowers/specs/2026-03-11-table-enrichment-design.md`

---

## File Structure

### New Files
- `frontend/src/composables/useColumnConfig.js` — shared column visibility + view mode composable

### Modified Files

**Backend:**
- `backend/app/routers/purchase_orders.py` — add `item_count`, `tax_amount`, `rebate_used`, `credit_used`, `account_set_name` to list response; add items endpoint
- `backend/app/routers/finance.py` — add `item_count`, `rebate_used`, `account_set_name` to list; add items endpoint
- `backend/app/routers/logistics.py` — add `remark`, `salesperson_name`, `phone` to list response

**Frontend:**
- `frontend/src/composables/useShipment.js` — refactor to use `useColumnConfig`
- `frontend/src/composables/usePurchaseOrder.js` — add sorting, column config
- `frontend/src/components/business/PurchaseOrdersPanel.vue` — dynamic columns, expand rows, view toggle
- `frontend/src/components/business/finance/FinanceOrdersTab.vue` — dynamic columns, expand rows, view toggle
- `frontend/src/views/LogisticsView.vue` — add new columns to existing column system
- `frontend/src/api/purchase.js` — add getPurchaseOrderItems
- `frontend/src/api/finance.js` — add getOrderItems

---

## Chunk 1: Shared Infrastructure

### Task 1: Create `useColumnConfig` composable

**Files:**
- Create: `frontend/src/composables/useColumnConfig.js`

- [ ] **Step 1: Create the composable**

```javascript
/**
 * useColumnConfig — 可复用的列可见性 + 视图模式管理
 * 从 useShipment.js 列配置模式提取，供所有表格面板共享
 *
 * @param {string} storageKey — localStorage 键名（如 'purchase_columns'）
 * @param {Object} columnDefs — 列定义 { key: { label, defaultVisible, align, width } }
 * @param {Object} options — 可选配置 { supportViewMode: false }
 */
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'

export function useColumnConfig(storageKey, columnDefs, options = {}) {
  const { supportViewMode = false } = options

  // 从定义生成默认可见性映射
  const defaultVisibility = {}
  for (const [key, def] of Object.entries(columnDefs)) {
    defaultVisibility[key] = def.defaultVisible !== false
  }

  // 列标签映射（供模板遍历）
  const columnLabels = {}
  for (const [key, def] of Object.entries(columnDefs)) {
    columnLabels[key] = def.label
  }

  // 从 localStorage 恢复
  let saved = null
  try {
    const raw = localStorage.getItem(storageKey)
    if (raw) saved = JSON.parse(raw)
  } catch { /* 忽略损坏数据 */ }

  const visibleColumns = reactive({ ...defaultVisibility, ...(saved?.columns || {}) })
  const viewMode = ref(saved?.viewMode || 'summary')

  // 持久化到 localStorage
  const persist = () => {
    const data = { columns: { ...visibleColumns } }
    if (supportViewMode) data.viewMode = viewMode.value
    localStorage.setItem(storageKey, JSON.stringify(data))
  }

  // 可见列定义（计算属性）
  const activeColumns = computed(() => {
    return Object.entries(columnDefs)
      .filter(([key]) => visibleColumns[key])
      .map(([key, def]) => ({ key, ...def }))
  })

  const toggleColumn = (key) => {
    visibleColumns[key] = !visibleColumns[key]
    persist()
  }

  const isColumnVisible = (key) => visibleColumns[key]

  const setViewMode = (mode) => {
    viewMode.value = mode
    persist()
  }

  const resetColumns = () => {
    Object.assign(visibleColumns, defaultVisibility)
    if (supportViewMode) viewMode.value = 'summary'
    persist()
  }

  // 列菜单展开状态 + 点击外部关闭（用 storageKey 区分不同面板的菜单）
  const menuAttr = `data-column-menu-${storageKey}`
  const showColumnMenu = ref(false)
  const handleDocClick = (e) => {
    if (showColumnMenu.value && !e.target.closest(`[${menuAttr}]`)) {
      showColumnMenu.value = false
    }
  }

  onMounted(() => document.addEventListener('click', handleDocClick))
  onUnmounted(() => document.removeEventListener('click', handleDocClick))

  return {
    columnDefs,
    columnLabels,
    visibleColumns,
    activeColumns,
    showColumnMenu,
    toggleColumn,
    isColumnVisible,
    resetColumns,
    // 视图模式（仅 supportViewMode 时有意义）
    viewMode,
    setViewMode,
    // 菜单属性名（用于模板 data-attribute）
    menuAttr
  }
}
```

- [ ] **Step 2: Verify file created correctly**

Run: `node -e "require('./frontend/src/composables/useColumnConfig.js')" 2>&1 || echo "ES module, will verify via build"`

File should exist at `frontend/src/composables/useColumnConfig.js`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useColumnConfig.js
git commit -m "feat: add useColumnConfig composable for shared column visibility"
```

---

### Task 2: Refactor `useShipment.js` to use `useColumnConfig`

**Files:**
- Modify: `frontend/src/composables/useShipment.js`

- [ ] **Step 1: Refactor useShipment to import and use useColumnConfig**

Replace the manual column logic (lines 67-119) with `useColumnConfig`. Keep the same `logistics_columns` storage key. The composable must read old-format localStorage (flat `{ order_no: true, ... }`) for backward compatibility.

In `useColumnConfig.js`, the saved data is parsed as `saved?.columns || {}`. Old format is flat `{ order_no: true }`, new format is `{ columns: { order_no: true } }`. To handle backward compatibility: if `saved` is an object but has no `columns` key, treat the entire object as columns.

Update `useColumnConfig.js` restore logic:

```javascript
// 从 localStorage 恢复（兼容旧格式）
let saved = null
try {
  const raw = localStorage.getItem(storageKey)
  if (raw) {
    const parsed = JSON.parse(raw)
    // 兼容旧格式：如果没有 columns 子键，整个对象就是列配置
    if (parsed && typeof parsed === 'object' && !parsed.columns) {
      saved = { columns: parsed }
    } else {
      saved = parsed
    }
  }
} catch { /* 忽略损坏数据 */ }
```

Then refactor `useShipment.js`:

```javascript
import { useColumnConfig } from './useColumnConfig'

// 在 useShipment() 内部，替换 lines 67-119:
// Task 2 仅迁移现有列定义；新列在 Task 11 添加（需后端 + 模板支持）
const shipmentColumnDefs = {
  order_no: { label: '订单号', defaultVisible: true },
  order_type: { label: '类型', defaultVisible: true },
  customer: { label: '客户', defaultVisible: true },
  shipping_status: { label: '发货状态', defaultVisible: true },
  carrier: { label: '快递公司', defaultVisible: true },
  tracking_no: { label: '快递单号', defaultVisible: true },
  sn: { label: 'SN码', defaultVisible: false },
  shipped_at: { label: '发货时间', defaultVisible: false },
  status: { label: '物流状态', defaultVisible: true },
  last_info: { label: '物流信息', defaultVisible: false },
  actions: { label: '操作', defaultVisible: true }
}

const {
  columnLabels, visibleColumns, showColumnMenu,
  toggleColumn, isColumnVisible, resetColumns
} = useColumnConfig('logistics_columns', shipmentColumnDefs)
```

Remove the old manual column code: `defaultColumns`, `columnLabels`, `_savedColumns`, `visibleColumns`, `showColumnMenu`, `toggleColumn`, `isColumnVisible`, `handleDocClick`, and the `onMounted`/`onUnmounted` for `handleDocClick`.

Keep the existing `onMounted` for `loadShipments` and `loadCarriers`, and `onUnmounted` for `clearTimeout`.

Add `resetColumns` to the return object.

- [ ] **Step 2: Verify Logistics page still works**

Build and check that the Logistics page loads, columns toggle correctly, and existing localStorage preferences are preserved.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useShipment.js frontend/src/composables/useColumnConfig.js
git commit -m "refactor: useShipment uses useColumnConfig, backward-compatible localStorage"
```

---

## Chunk 2: Backend API Extensions

### Task 3: Extend Purchase Orders list API

**Files:**
- Modify: `backend/app/routers/purchase_orders.py:36-78`

- [ ] **Step 1: Add item_count, tax_amount, rebate_used, credit_used, account_set_name to list response**

After line 61 (`select_related` call), add a batch prefetch of items and account sets:

```python
    # 批量预取采购项（用于 item_count 和 tax_amount 计算）
    po_ids = [o.id for o in orders]
    all_items = await PurchaseOrderItem.filter(purchase_order_id__in=po_ids).all() if po_ids else []
    items_by_po = {}
    for item in all_items:
        items_by_po.setdefault(item.purchase_order_id, []).append(item)

    # 批量查询账套名称
    as_ids = list(set(o.account_set_id for o in orders if o.account_set_id))
    as_map = {}
    if as_ids:
        from app.models import AccountSet
        for a in await AccountSet.filter(id__in=as_ids):
            as_map[a.id] = a.name
```

Then update the response dict to include new fields:

```python
    return {"items": [{
        "id": o.id, "po_no": o.po_no, "supplier_id": o.supplier_id,
        "supplier_name": o.supplier.name if o.supplier else "",
        "status": o.status, "total_amount": float(o.total_amount),
        "return_amount": float(o.return_amount) if o.return_amount else 0,
        "target_warehouse_name": o.target_warehouse.name if o.target_warehouse else None,
        "target_location_code": o.target_location.code if o.target_location else None,
        "remark": o.remark,
        "creator_name": o.creator.display_name if o.creator else None,
        "reviewed_by_name": o.reviewed_by.display_name if o.reviewed_by else None,
        "reviewed_at": o.reviewed_at.isoformat() if o.reviewed_at else None,
        "paid_by_name": o.paid_by.display_name if o.paid_by else None,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "payment_method": o.payment_method,
        "created_at": o.created_at.isoformat(),
        "account_set_id": o.account_set_id,
        # 新增字段
        "item_count": len(items_by_po.get(o.id, [])),
        "tax_amount": float(sum(i.amount for i in items_by_po.get(o.id, []))),
        "rebate_used": float(o.rebate_used) if o.rebate_used else 0,
        "credit_used": float(o.credit_used) if o.credit_used else 0,
        "account_set_name": as_map.get(o.account_set_id) if o.account_set_id else None,
    } for o in orders], "total": total}
```

- [ ] **Step 2: Add purchase order items endpoint**

Add a new endpoint after the list endpoint (around line 80):

```python
@router.get("/{po_id}/items")
async def get_purchase_order_items(po_id: int, user: User = Depends(require_permission("purchase", "purchase_approve", "purchase_pay", "purchase_receive"))):
    """获取采购订单的物料明细（用于列表行展开）"""
    po = await PurchaseOrder.filter(id=po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="采购单不存在")
    items = await PurchaseOrderItem.filter(purchase_order_id=po_id).select_related("product", "target_warehouse", "target_location")
    return [{
        "id": i.id,
        "product_sku": i.product.sku if i.product else "",
        "product_name": i.product.name if i.product else "",
        "spec": i.product.spec if i.product else "",
        "quantity": i.quantity,
        "tax_inclusive_price": float(i.tax_inclusive_price),
        "tax_rate": float(i.tax_rate),
        "tax_exclusive_price": float(i.tax_exclusive_price),
        "amount": float(i.amount),
        "received_quantity": i.received_quantity,
        "returned_quantity": i.returned_quantity,
    } for i in items]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/purchase_orders.py
git commit -m "feat: extend purchase orders list API with item_count, tax_amount, account_set_name"
```

---

### Task 4: Extend Finance orders list API

**Files:**
- Modify: `backend/app/routers/finance.py:118-140`

- [ ] **Step 1: Add item_count, rebate_used, account_set_name to all-orders response**

After line 106 (the `unconfirmed_order_ids` block), add batch queries:

```python
    # 批量查询品项数
    from app.models import OrderItem, AccountSet
    item_counts = {}
    if order_ids:
        for oi in await OrderItem.filter(order_id__in=order_ids).all():
            item_counts[oi.order_id] = item_counts.get(oi.order_id, 0) + 1

    # 批量查询账套名称（account_set_id 直接可用，无需 select_related）
    as_ids = list(set(o.account_set_id for o in filtered_orders if o.account_set_id))
    as_map = {}
    if as_ids:
        for a in await AccountSet.filter(id__in=as_ids):
            as_map[a.id] = a.name
```

Update the result dict (lines 120-139) to add new fields:

```python
        result.append({
            # ...existing fields...
            "item_count": item_counts.get(o.id, 0),
            "rebate_used": float(o.rebate_used) if o.rebate_used else 0,
            "account_set_name": as_map.get(o.account_set_id) if o.account_set_id else None,
        })
```

- [ ] **Step 2: Add order items endpoint for sub-table expansion**

Add a new endpoint after the `get_all_orders` function:

```python
@router.get("/all-orders/{order_id}/items")
async def get_order_items(order_id: int, user: User = Depends(require_permission("finance"))):
    """获取订单商品明细（用于列表行展开）"""
    order = await Order.filter(id=order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    items = await OrderItem.filter(order_id=order_id).select_related("product")
    return [{
        "id": i.id,
        "product_sku": i.product.sku if i.product else "",
        "product_name": i.product.name if i.product else "",
        "quantity": i.quantity,
        "unit_price": float(i.unit_price),
        "cost_price": float(i.cost_price),
        "amount": float(i.amount),
        "profit": float(i.profit),
        "shipped_qty": i.shipped_qty,
    } for i in items]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/finance.py
git commit -m "feat: extend finance orders API with item_count, account_set_name, items endpoint"
```

---

### Task 5: Extend Logistics list API

**Files:**
- Modify: `backend/app/routers/logistics.py:139,185-202,210,227-244`

- [ ] **Step 1: Add salesperson to select_related**

Line 139 currently:
```python
    all_shipments = await query.order_by("id").select_related("order", "order__customer")
```

Change to:
```python
    all_shipments = await query.order_by("id").select_related("order", "order__customer", "order__salesperson")
```

- [ ] **Step 2: Add remark, salesperson_name, phone to shipment response**

In the main `result.append` block (lines 185-202), add three fields:

```python
        result.append({
            # ...existing fields...
            "remark": order.remark,
            "salesperson_name": order.salesperson.name if order.salesperson else None,
            "phone": first.phone if hasattr(first, 'phone') and first.phone else None,
        })
```

- [ ] **Step 3: Add remark and salesperson to pending orders block**

In the pending orders block (lines 227-244), add to the response dict:

```python
            result.append({
                # ...existing fields...
                "remark": o.remark,
                "salesperson_name": None,  # pending orders don't have salesperson loaded
                "phone": None,
            })
```

For pending orders, also add salesperson to the select_related on line 210:

```python
        pending_query = Order.filter(...).select_related("customer", "salesperson")
```

Then use `o.salesperson.name if o.salesperson else None` instead of `None`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/logistics.py
git commit -m "feat: add remark, salesperson_name, phone to logistics list API"
```

---

## Chunk 3: Purchase Orders Panel Enrichment

### Task 6: Add frontend API for purchase order items

**Files:**
- Modify: `frontend/src/api/purchase.js`

- [ ] **Step 1: Add getPurchaseOrderItems function**

```javascript
export const getPurchaseOrderItems = (poId) => api.get(`/purchase-orders/${poId}/items`)
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/purchase.js
git commit -m "feat: add getPurchaseOrderItems API function"
```

---

### Task 7: Enhance `usePurchaseOrder.js` with sorting and column config

**Files:**
- Modify: `frontend/src/composables/usePurchaseOrder.js`

- [ ] **Step 1: Add useSort, useColumnConfig, and column definitions**

Add imports and column definitions:

```javascript
import { ref, computed, onUnmounted } from 'vue'
import { getPurchaseOrders, exportPurchaseOrders as exportPurchaseOrdersApi } from '../api/purchase'
import { useAppStore } from '../stores/app'
import { usePagination } from './usePagination'
import { useSort } from './useSort'
import { useColumnConfig } from './useColumnConfig'

// 采购订单列定义
const purchaseColumnDefs = {
  po_no: { label: '采购单号', defaultVisible: true },
  supplier: { label: '供应商', defaultVisible: true },
  date: { label: '采购日期', defaultVisible: true },
  total_amount: { label: '总金额', defaultVisible: true, align: 'right' },
  tax_amount: { label: '含税金额', defaultVisible: true, align: 'right' },
  item_count: { label: '品项数', defaultVisible: true, align: 'center' },
  status: { label: '状态', defaultVisible: true, align: 'center' },
  remark: { label: '备注', defaultVisible: true },
  creator: { label: '创建人', defaultVisible: true },
  account_set: { label: '账套', defaultVisible: true },
  return_amount: { label: '退货金额', defaultVisible: false, align: 'right' },
  target_warehouse: { label: '目标仓库', defaultVisible: false },
  target_location: { label: '目标仓位', defaultVisible: false },
  rebate_used: { label: '返利已用', defaultVisible: false, align: 'right' },
  credit_used: { label: '在账资金已用', defaultVisible: false, align: 'right' },
  reviewer: { label: '审核人', defaultVisible: false },
  reviewed_at: { label: '审核时间', defaultVisible: false },
  payment_method: { label: '付款方式', defaultVisible: false },
}
```

Inside the composable function, add sorting and column config:

```javascript
export function usePurchaseOrder() {
  // ... existing appStore, pagination ...

  const { sortState: purchaseSort, toggleSort: togglePurchaseSort, genericSort } = useSort()
  const {
    columnLabels, visibleColumns, showColumnMenu, activeColumns,
    toggleColumn, isColumnVisible, resetColumns, viewMode, setViewMode
  } = useColumnConfig('purchase_columns', purchaseColumnDefs, { supportViewMode: true })

  // ... existing filter refs and loadPurchaseOrders ...

  // 排序后的列表
  const sortedPurchaseOrders = computed(() => {
    return genericSort(purchaseOrders.value, {
      po_no: o => o.po_no || '',
      supplier: o => o.supplier_name || '',
      date: o => o.created_at || '',
      total_amount: o => Number(o.total_amount) || 0,
      tax_amount: o => Number(o.tax_amount) || 0,
      status: o => o.status || '',
      creator: o => o.creator_name || '',
    })
  })

  // ... existing return, add new exports:
  return {
    // ... existing ...
    // 排序
    purchaseSort, togglePurchaseSort, sortedPurchaseOrders,
    // 列配置
    columnLabels, visibleColumns, showColumnMenu, activeColumns, menuAttr,
    toggleColumn, isColumnVisible, resetColumns,
    viewMode, setViewMode,
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/composables/usePurchaseOrder.js
git commit -m "feat: add sorting and column config to usePurchaseOrder"
```

---

### Task 8: Rewrite PurchaseOrdersPanel.vue with dynamic columns and expand rows

**Files:**
- Modify: `frontend/src/components/business/PurchaseOrdersPanel.vue`

- [ ] **Step 1: Update script setup imports and composable destructuring**

Add new imports and expand the composable destructuring:

```javascript
import { ref, reactive, onMounted } from 'vue'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { usePurchaseOrder } from '../../composables/usePurchaseOrder'
import { getPurchaseOrderItems } from '../../api/purchase'
import { getAccountSets } from '../../api/accounting'
import { useProductsStore } from '../../stores/products'
import { useWarehousesStore } from '../../stores/warehouses'
import StatusBadge from '../common/StatusBadge.vue'
import PurchaseOrderForm from './purchase/PurchaseOrderForm.vue'
import PurchaseOrderDetail from './purchase/PurchaseOrderDetail.vue'

// Destructure all from composable including new exports
const {
  purchaseOrders, purchaseStatusFilter, purchaseAccountSetFilter,
  purchaseDateStart, purchaseDateEnd, purchaseSearch,
  loadPurchaseOrders, debouncedLoad, handleExport,
  page, totalPages, hasPagination, resetPage, prevPage, nextPage,
  // 排序
  purchaseSort, togglePurchaseSort, sortedPurchaseOrders,
  // 列配置
  columnLabels, visibleColumns, showColumnMenu, menuAttr,
  toggleColumn, isColumnVisible, resetColumns,
  viewMode, setViewMode,
} = usePurchaseOrder()
```

Add expand row state and item fetching:

```javascript
// 展开行状态
const expandedRows = reactive({})
const expandedItems = reactive({})
const loadingItems = reactive({})

const toggleExpand = async (orderId, e) => {
  // 阻止行点击事件（查看详情）
  e?.stopPropagation()
  if (expandedRows[orderId]) {
    delete expandedRows[orderId]
    return
  }
  expandedRows[orderId] = true
  // 如果还没加载过明细，则加载
  if (!expandedItems[orderId]) {
    loadingItems[orderId] = true
    try {
      const { data } = await getPurchaseOrderItems(orderId)
      expandedItems[orderId] = data
    } catch (e) {
      console.error(e)
    } finally {
      loadingItems[orderId] = false
    }
  }
}
```

- [ ] **Step 2: Rewrite the desktop table template**

Replace the desktop table (lines 47-77) with dynamic columns:

```html
    <!-- 桌面端表格 -->
    <div class="card hidden md:block">
      <!-- 工具栏：视图切换 + 列选择 -->
      <div class="flex items-center justify-end gap-2 px-3 py-1.5 border-b">
        <div class="flex items-center gap-1 mr-auto text-xs text-muted">
          <button @click="setViewMode('summary')" :class="['px-2 py-1 rounded', viewMode === 'summary' ? 'bg-primary text-white' : 'hover:bg-elevated']">汇总</button>
          <button @click="setViewMode('detail')" :class="['px-2 py-1 rounded', viewMode === 'detail' ? 'bg-primary text-white' : 'hover:bg-elevated']">明细</button>
        </div>
        <div class="relative" :[menuAttr]="true">
          <button @click="showColumnMenu = !showColumnMenu" class="btn btn-secondary btn-sm text-lg px-2">⋯</button>
          <div v-if="showColumnMenu" class="absolute right-0 top-full mt-1 bg-surface rounded-lg shadow-lg border p-2 z-50 min-w-[140px]">
            <div v-for="(label, key) in columnLabels" :key="key" v-show="key !== 'po_no'"
              @click="toggleColumn(key)"
              class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-elevated cursor-pointer text-sm select-none">
              <span class="w-4 text-center">{{ visibleColumns[key] ? '✓' : '' }}</span>
              <span>{{ label }}</span>
            </div>
            <div class="border-t mt-1 pt-1">
              <div @click="resetColumns" class="px-2 py-1.5 rounded hover:bg-elevated cursor-pointer text-sm text-muted">重置列</div>
            </div>
          </div>
        </div>
      </div>
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th v-if="viewMode === 'summary'" class="px-3 py-2 w-6"></th><!-- 展开图标 -->
              <th v-if="isColumnVisible('po_no')" class="px-3 py-2 text-left cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('po_no')">采购单号 <span v-if="purchaseSort.key === 'po_no'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('supplier')" class="px-3 py-2 text-left cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('supplier')">供应商 <span v-if="purchaseSort.key === 'supplier'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('date')" class="px-3 py-2 text-left cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('date')">采购日期 <span v-if="purchaseSort.key === 'date'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('total_amount')" class="px-3 py-2 text-right cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('total_amount')">总金额 <span v-if="purchaseSort.key === 'total_amount'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('tax_amount')" class="px-3 py-2 text-right">含税金额</th>
              <th v-if="isColumnVisible('item_count')" class="px-3 py-2 text-center">品项数</th>
              <th v-if="isColumnVisible('status')" class="px-3 py-2 text-center cursor-pointer select-none hover:text-primary" @click="togglePurchaseSort('status')">状态 <span v-if="purchaseSort.key === 'status'" class="text-primary">{{ purchaseSort.order === 'asc' ? '↑' : '↓' }}</span></th>
              <th v-if="isColumnVisible('remark')" class="px-3 py-2 text-left">备注</th>
              <th v-if="isColumnVisible('creator')" class="px-3 py-2 text-left">创建人</th>
              <th v-if="isColumnVisible('account_set')" class="px-3 py-2 text-left">账套</th>
              <th v-if="isColumnVisible('return_amount')" class="px-3 py-2 text-right">退货金额</th>
              <th v-if="isColumnVisible('target_warehouse')" class="px-3 py-2 text-left">目标仓库</th>
              <th v-if="isColumnVisible('target_location')" class="px-3 py-2 text-left">目标仓位</th>
              <th v-if="isColumnVisible('rebate_used')" class="px-3 py-2 text-right">返利已用</th>
              <th v-if="isColumnVisible('credit_used')" class="px-3 py-2 text-right">在账资金</th>
              <th v-if="isColumnVisible('reviewer')" class="px-3 py-2 text-left">审核人</th>
              <th v-if="isColumnVisible('reviewed_at')" class="px-3 py-2 text-left">审核时间</th>
              <th v-if="isColumnVisible('payment_method')" class="px-3 py-2 text-left">付款方式</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <template v-for="o in sortedPurchaseOrders" :key="o.id">
              <!-- 汇总行 -->
              <tr class="hover:bg-elevated cursor-pointer" @click="detailRef?.viewPurchaseOrder(o.id)">
                <td v-if="viewMode === 'summary'" class="px-1 py-2 text-center text-muted" @click="toggleExpand(o.id, $event)">
                  <span class="cursor-pointer">{{ expandedRows[o.id] ? '▼' : '▶' }}</span>
                </td>
                <td v-if="isColumnVisible('po_no')" class="px-3 py-2 font-mono text-sm">
                  <span v-if="['pending_review','paid','partial'].includes(o.status)" class="todo-dot mr-1.5"></span>{{ o.po_no }}
                </td>
                <td v-if="isColumnVisible('supplier')" class="px-3 py-2">{{ o.supplier_name }}</td>
                <td v-if="isColumnVisible('date')" class="px-3 py-2 text-muted text-xs">{{ fmtDate(o.created_at) }}</td>
                <td v-if="isColumnVisible('total_amount')" class="px-3 py-2 text-right font-semibold">¥{{ fmt(o.total_amount) }}</td>
                <td v-if="isColumnVisible('tax_amount')" class="px-3 py-2 text-right">¥{{ fmt(o.tax_amount) }}</td>
                <td v-if="isColumnVisible('item_count')" class="px-3 py-2 text-center">{{ o.item_count }}</td>
                <td v-if="isColumnVisible('status')" class="px-3 py-2 text-center"><StatusBadge type="purchaseStatus" :status="o.status" /></td>
                <td v-if="isColumnVisible('remark')" class="px-3 py-2 text-muted text-xs max-w-[150px] truncate">{{ o.remark || '-' }}</td>
                <td v-if="isColumnVisible('creator')" class="px-3 py-2 text-secondary">{{ o.creator_name }}</td>
                <td v-if="isColumnVisible('account_set')" class="px-3 py-2">{{ o.account_set_name || '-' }}</td>
                <td v-if="isColumnVisible('return_amount')" class="px-3 py-2 text-right">{{ o.return_amount ? '¥' + fmt(o.return_amount) : '-' }}</td>
                <td v-if="isColumnVisible('target_warehouse')" class="px-3 py-2">{{ o.target_warehouse_name || '-' }}</td>
                <td v-if="isColumnVisible('target_location')" class="px-3 py-2">{{ o.target_location_code || '-' }}</td>
                <td v-if="isColumnVisible('rebate_used')" class="px-3 py-2 text-right">{{ o.rebate_used ? '¥' + fmt(o.rebate_used) : '-' }}</td>
                <td v-if="isColumnVisible('credit_used')" class="px-3 py-2 text-right">{{ o.credit_used ? '¥' + fmt(o.credit_used) : '-' }}</td>
                <td v-if="isColumnVisible('reviewer')" class="px-3 py-2">{{ o.reviewed_by_name || '-' }}</td>
                <td v-if="isColumnVisible('reviewed_at')" class="px-3 py-2 text-xs text-muted">{{ o.reviewed_at ? fmtDate(o.reviewed_at) : '-' }}</td>
                <td v-if="isColumnVisible('payment_method')" class="px-3 py-2">{{ o.payment_method || '-' }}</td>
              </tr>
              <!-- 展开行：物料明细子表 -->
              <tr v-if="viewMode === 'summary' && expandedRows[o.id]">
                <td :colspan="100" class="bg-elevated/50 px-6 py-3">
                  <div v-if="loadingItems[o.id]" class="text-center text-muted text-sm py-2">加载中...</div>
                  <table v-else-if="expandedItems[o.id]?.length" class="w-full text-xs">
                    <thead>
                      <tr class="text-muted border-b">
                        <th class="px-2 py-1.5 text-left font-medium">物料编码</th>
                        <th class="px-2 py-1.5 text-left font-medium">物料名称</th>
                        <th class="px-2 py-1.5 text-left font-medium">规格型号</th>
                        <th class="px-2 py-1.5 text-center font-medium">数量</th>
                        <th class="px-2 py-1.5 text-right font-medium">单价</th>
                        <th class="px-2 py-1.5 text-right font-medium">含税单价</th>
                        <th class="px-2 py-1.5 text-right font-medium">价税合计</th>
                        <th class="px-2 py-1.5 text-center font-medium">已收货</th>
                        <th class="px-2 py-1.5 text-center font-medium">已退货</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-border-light">
                      <tr v-for="item in expandedItems[o.id]" :key="item.id">
                        <td class="px-2 py-1.5 text-primary font-mono">{{ item.product_sku }}</td>
                        <td class="px-2 py-1.5">{{ item.product_name }}</td>
                        <td class="px-2 py-1.5 text-muted">{{ item.spec || '-' }}</td>
                        <td class="px-2 py-1.5 text-center">{{ item.quantity }}</td>
                        <td class="px-2 py-1.5 text-right">¥{{ fmt(item.tax_exclusive_price) }}</td>
                        <td class="px-2 py-1.5 text-right">¥{{ fmt(item.tax_inclusive_price) }}</td>
                        <td class="px-2 py-1.5 text-right font-medium">¥{{ fmt(item.amount) }}</td>
                        <td class="px-2 py-1.5 text-center">{{ item.received_quantity }}</td>
                        <td class="px-2 py-1.5 text-center">{{ item.returned_quantity || '-' }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-else class="text-muted text-sm text-center py-2">暂无明细</div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
      <div v-if="!purchaseOrders.length" class="p-8 text-center text-muted text-sm">暂无采购订单</div>
    </div>
```

- [ ] **Step 3: Verify the panel renders correctly**

Build frontend and verify:
1. Column selector menu works
2. Expand/collapse rows work
3. Sorting works
4. Mobile card layout still works unchanged

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/business/PurchaseOrdersPanel.vue
git commit -m "feat: purchase orders panel with dynamic columns, expand rows, view toggle"
```

---

## Chunk 4: Finance Orders Tab Enrichment

### Task 9: Add frontend API for finance order items

**Files:**
- Modify: `frontend/src/api/finance.js`

- [ ] **Step 1: Add getOrderItems function**

```javascript
export const getOrderItems = (orderId) => api.get(`/finance/all-orders/${orderId}/items`)
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/finance.js
git commit -m "feat: add getOrderItems API function"
```

---

### Task 10: Enhance FinanceOrdersTab.vue with dynamic columns and expand rows

**Files:**
- Modify: `frontend/src/components/business/finance/FinanceOrdersTab.vue`

This is a large file (975 lines). We only modify the table section (lines 45-83) and add column config to the script.

- [ ] **Step 1: Add imports and column config to script setup**

Add imports after existing imports (around line 476):

```javascript
import { useColumnConfig } from '../../../composables/useColumnConfig'
import { getOrderItems } from '../../../api/finance'
```

Add column definitions and config after the `usePagination` call (around line 504):

```javascript
// 列定义
const financeColumnDefs = {
  order_no: { label: '订单号', defaultVisible: true },
  order_type: { label: '类型', defaultVisible: true, align: 'center' },
  customer: { label: '客户', defaultVisible: true },
  total_amount: { label: '金额', defaultVisible: true, align: 'right' },
  total_cost: { label: '成本', defaultVisible: true, align: 'right' },
  total_profit: { label: '毛利', defaultVisible: true, align: 'right' },
  paid_amount: { label: '已付', defaultVisible: true, align: 'right' },
  status: { label: '结清状态', defaultVisible: true, align: 'center' },
  shipping_status: { label: '发货', defaultVisible: true, align: 'center' },
  item_count: { label: '品项数', defaultVisible: true, align: 'center' },
  remark: { label: '备注', defaultVisible: true },
  warehouse: { label: '仓库', defaultVisible: true },
  salesperson: { label: '业务员', defaultVisible: true },
  created_at: { label: '创建时间', defaultVisible: true },
  related_order: { label: '关联订单', defaultVisible: false },
  refunded: { label: '退款状态', defaultVisible: false, align: 'center' },
  rebate_used: { label: '返利已用', defaultVisible: false, align: 'right' },
  creator: { label: '创建人', defaultVisible: false },
  account_set: { label: '账套', defaultVisible: false },
}

const {
  columnLabels: financeColumnLabels, visibleColumns: financeVisibleColumns,
  showColumnMenu: financeShowColumnMenu,
  toggleColumn: financeToggleColumn, isColumnVisible: financeIsColumnVisible,
  resetColumns: financeResetColumns, viewMode: financeViewMode, setViewMode: financeSetViewMode
} = useColumnConfig('finance_order_columns', financeColumnDefs, { supportViewMode: true })

// 展开行状态
const expandedRows = reactive({})
const expandedItems = reactive({})
const loadingItems = reactive({})

const toggleExpand = async (orderId, e) => {
  e?.stopPropagation()
  if (expandedRows[orderId]) {
    delete expandedRows[orderId]
    return
  }
  expandedRows[orderId] = true
  if (!expandedItems[orderId]) {
    loadingItems[orderId] = true
    try {
      const { data } = await getOrderItems(orderId)
      expandedItems[orderId] = data
    } catch (e) {
      console.error(e)
    } finally {
      loadingItems[orderId] = false
    }
  }
}
```

- [ ] **Step 2: Rewrite the desktop table template**

Replace lines 45-83 (the desktop table) with dynamic columns. Add toolbar with view mode toggle and column selector before the table. Follow the same pattern as the Purchase Orders panel in Task 8.

The table should have:
- View mode toggle (汇总/明细)
- Column selector (⋯ button)
- Dynamic `<th>` with `v-if="financeIsColumnVisible('key')"` and sort support
- Expand row with sub-table for item details
- Use `template v-for` with summary row + expand row pattern

Note: Keep existing sorting via `toggleOrderSort` and `orderSort` — just add `v-if` column visibility guards to existing `<th>` and `<td>` elements.

- [ ] **Step 3: Verify the tab renders correctly**

Build and verify:
1. Column selector works
2. Expand/collapse for item details
3. Existing sorting still works
4. Mobile card layout unchanged
5. Order detail modal still opens on row click

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/business/finance/FinanceOrdersTab.vue frontend/src/api/finance.js
git commit -m "feat: finance orders tab with dynamic columns, expand rows, view toggle"
```

---

## Chunk 5: Logistics Panel Enhancements

### Task 11: Add new columns to LogisticsView

**Files:**
- Modify: `frontend/src/views/LogisticsView.vue`
- Modify: `frontend/src/composables/useShipment.js` (column defs already updated in Task 2)

- [ ] **Step 1: Add new column definitions to `useShipment.js`**

In `useShipment.js`, add the 5 new column entries to `shipmentColumnDefs` (before `actions`):

```javascript
  // 新增列（Task 11 添加，与后端 Task 5 和模板同步）
  order_amount: { label: '订单金额', defaultVisible: true, align: 'right' },
  remark: { label: '备注', defaultVisible: true },
  salesperson: { label: '业务员', defaultVisible: false },
  phone: { label: '收件电话', defaultVisible: false },
  order_created_at: { label: '创建时间', defaultVisible: false },
  actions: { label: '操作', defaultVisible: true }
```

- [ ] **Step 2: Add new column headers and cells to LogisticsView template**

In the table header section (after existing column headers), add new `<th>` elements with `v-if="isColumnVisible('key')"`:

```html
<th v-if="isColumnVisible('order_amount')" class="px-2 py-2 text-right whitespace-nowrap">订单金额</th>
<th v-if="isColumnVisible('remark')" class="px-2 py-2 text-left whitespace-nowrap">备注</th>
<th v-if="isColumnVisible('salesperson')" class="px-2 py-2 text-left whitespace-nowrap">业务员</th>
<th v-if="isColumnVisible('phone')" class="px-2 py-2 text-left whitespace-nowrap">收件电话</th>
<th v-if="isColumnVisible('order_created_at')" class="px-2 py-2 text-left whitespace-nowrap">创建时间</th>
```

Add corresponding `<td>` cells in the table body:

```html
<td v-if="isColumnVisible('order_amount')" class="px-2 py-2 text-right font-semibold">¥{{ fmt(s.total_amount) }}</td>
<td v-if="isColumnVisible('remark')" class="px-2 py-2 text-muted text-xs max-w-[150px] truncate">{{ s.remark || '-' }}</td>
<td v-if="isColumnVisible('salesperson')" class="px-2 py-2">{{ s.salesperson_name || '-' }}</td>
<td v-if="isColumnVisible('phone')" class="px-2 py-2 text-xs">{{ s.phone || '-' }}</td>
<td v-if="isColumnVisible('order_created_at')" class="px-2 py-2 text-muted text-xs">{{ fmtDate(s.created_at) }}</td>
```

Add sort mappings for new columns in `useShipment.js` `sortedShipments` computed:

```javascript
order_amount: s => Number(s.total_amount) || 0,
salesperson: s => s.salesperson_name || '',
```

- [ ] **Step 3: Add resetColumns to the column menu**

Add a "重置列" option at the bottom of the existing column menu dropdown in LogisticsView.vue:

```html
<div class="border-t mt-1 pt-1">
  <div @click="resetColumns" class="px-2 py-1.5 rounded hover:bg-elevated cursor-pointer text-sm text-muted">重置列</div>
</div>
```

Update the destructuring in LogisticsView.vue to include `resetColumns`:

```javascript
const {
  // ...existing...
  resetColumns,
  // ...
} = useShipment()
```

- [ ] **Step 4: Verify Logistics page**

Build and verify:
1. New columns appear/hide correctly via column selector
2. Existing columns unaffected
3. Sorting works for new sortable columns
4. Data displays correctly for `order_amount`, `remark`, `salesperson_name`, `phone`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/LogisticsView.vue frontend/src/composables/useShipment.js
git commit -m "feat: add order_amount, remark, salesperson, phone columns to logistics"
```

---

## Chunk 6: Final Polish and Build Verification

### Task 12: Rebuild backend and verify

- [ ] **Step 1: Rebuild backend Docker container**

```bash
orb start && docker compose up -d --build erp
```

- [ ] **Step 2: Build frontend**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: Verify all three panels**

Test each panel:
1. **Purchase Orders**: Column selector, expand rows, sort, view mode toggle
2. **Finance Orders**: Column selector, expand rows, sort, view mode toggle
3. **Logistics**: New columns visible, column selector, existing features intact

- [ ] **Step 4: Verify localStorage persistence**

1. Toggle some columns off, refresh page — columns should stay hidden
2. Switch to detail mode, refresh — mode should persist
3. Clear localStorage for one panel — should reset to defaults

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: table enrichment — dynamic columns, expand rows, view modes for all panels"
```
