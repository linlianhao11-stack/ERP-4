# Table Enrichment Design Spec

## Overview

Enrich table displays in three panels — Purchase Orders (采购订单), Finance Order Details (财务订单明细), and Logistics (物流) — with more columns, column customization, and expandable detail rows.

## Scope

Three panels:
1. **PurchaseOrdersPanel** — `frontend/src/components/business/PurchaseOrdersPanel.vue`
2. **FinanceOrdersTab** — `frontend/src/components/business/finance/FinanceOrdersTab.vue` (actual table implementation)
3. **LogisticsView** — `frontend/src/views/LogisticsView.vue` (already has column selector)

Out of scope: Payment management (付款管理).

## Design Decisions

### View Modes (Purchase & Finance only)

- **Summary mode (default)**: One row per order. Click row to expand inline detail sub-table.
- **Detail mode (Phase 2)**: Flat table with one row per line item, order-level columns merged via rowspan. Phase 1 adds the toggle UI but detail mode falls back to summary view.
- Toggle button in toolbar switches between modes.
- User preference (mode + visible columns) persisted to localStorage.
- Logistics keeps its current single-mode table (already has detail modal).

### Column Customization

All three panels get a `⋯` column selector menu (Logistics already has one). Each column has:
- `key` — unique identifier
- `label` — display name
- `defaultVisible` — whether shown by default
- `align` — left/center/right
- `width` — suggested width
- `sortable` — whether column supports sorting

### Shared Composable: `useColumnConfig`

Extract a reusable composable from the existing `useShipment.js` pattern:

```
useColumnConfig(storageKey, columnDefs) → {
  visibleColumns,    // computed: filtered column defs
  allColumns,        // all column defs with visible state
  toggleColumn,      // toggle a column's visibility
  resetColumns,      // reset column visibility AND view mode to defaults
  viewMode,          // 'summary' | 'detail' (for panels that support it)
  setViewMode        // switch view mode
}
```

- `storageKey` differentiates each panel's localStorage entry.
- `useShipment.js` will be refactored to use `useColumnConfig` internally, preserving its existing `logistics_columns` key for backward compatibility.

### Expandable Rows (Summary Mode)

- Click a summary row → toggle inline sub-table showing line items.
- Expanded state tracked per-order in component local state (not persisted).
- `▶` / `▼` indicator in first column.
- Sub-table columns are fixed (not user-configurable) — they show item-level detail.

## Panel Specifications

### 1. Purchase Orders Panel

**Summary columns (18 total, 10 default visible):**

| Key | Label | Default | Align | Notes |
|-----|-------|---------|-------|-------|
| `po_no` | 采购单号 | visible | left | Always visible, not toggleable |
| `supplier` | 供应商 | visible | left | |
| `date` | 采购日期 | visible | left | `created_at` formatted |
| `total_amount` | 总金额 | visible | right | |
| `tax_amount` | 含税金额 | visible | right | Calculated or from API |
| `item_count` | 品项数 | visible | center | Count of line items |
| `status` | 状态 | visible | center | StatusBadge component |
| `remark` | 备注 | visible | left | Truncated with ellipsis |
| `creator` | 创建人 | visible | left | |
| `account_set` | 账套 | visible | left | |
| `return_amount` | 退货金额 | hidden | right | |
| `target_warehouse` | 目标仓库 | hidden | left | |
| `target_location` | 目标仓位 | hidden | left | |
| `rebate_used` | 返利已用 | hidden | right | |
| `credit_used` | 在账资金已用 | hidden | right | |
| `reviewer` | 审核人 | hidden | left | |
| `reviewed_at` | 审核时间 | hidden | left | |
| `payment_method` | 付款方式 | hidden | left | |

**Expand sub-table columns (fixed):**
物料编码, 物料名称, 规格型号, 数量, 单价, 含税单价, 价税合计, 已收货数, 已退货数

**Backend changes:**

Fields already returned by list API: `po_no`, `supplier_name`, `total_amount`, `status`, `creator_name`, `created_at`, `return_amount`, `target_warehouse_name`, `target_location_code`, `remark`, `reviewed_by_name`, `reviewed_at`, `payment_method`.

Fields that need to be added to list API:
- `tax_amount` — requires annotation: `SUM(item.tax_inclusive_price * item.quantity)` via Tortoise `annotate()` or computed in Python after prefetching items.
- `item_count` — requires annotation: `COUNT(items)` via Tortoise `annotate()` or `len(prefetched_items)`.
- `account_set_name` — add `account_set` to batch query (same pattern as warehouses router).
- `rebate_used` — exists on model, just add to response dict.
- `credit_used` — exists on model, just add to response dict.

Strategy for `tax_amount` and `item_count`: prefetch items in batch (avoid N+1), compute in Python. This reuses the same items data needed for the expand sub-table.

Sub-table item data: fetched via `GET /api/purchase-orders/{po_id}` detail endpoint (already returns items with all needed fields). Frontend fetches on first expand, caches in component state. Brand field is not available in the current items response — remove from sub-table.

### 2. Finance Order Details Panel

**Summary columns (19 total, 14 default visible):**

| Key | Label | Default | Align | Notes |
|-----|-------|---------|-------|-------|
| `order_no` | 订单号 | visible | left | Always visible |
| `order_type` | 类型 | visible | center | |
| `customer` | 客户 | visible | left | |
| `total_amount` | 金额 | visible | right | |
| `total_cost` | 成本 | visible | right | |
| `total_profit` | 毛利 | visible | right | |
| `paid_amount` | 已付 | visible | right | |
| `status` | 结清状态 | visible | center | |
| `shipping_status` | 物流 | visible | center | |
| `item_count` | 品项数 | visible | center | New |
| `remark` | 备注 | visible | left | New, truncated |
| `warehouse` | 仓库 | visible | left | New |
| `salesperson` | 业务员 | visible | left | |
| `created_at` | 创建时间 | visible | left | |
| `related_order` | 关联订单 | hidden | left | |
| `refunded` | 退款状态 | hidden | center | |
| `rebate_used` | 返利已用 | hidden | right | |
| `creator` | 创建人 | hidden | left | |
| `account_set` | 账套 | hidden | left | |

**Expand sub-table columns (fixed):**
商品SKU, 商品名称, 数量, 单价, 成本价, 金额, 毛利, 已发货数

**Backend changes:**

Fields already returned by list API: `order_no`, `order_type`, `customer_name`, `total_amount`, `total_cost`, `total_profit`, `paid_amount`, `is_cleared`, `shipping_status`, `salesperson_name`, `created_at`, `remark`, `warehouse_name`, `related_order_no`, `refunded`.

Fields that need to be added to list API:
- `item_count` — annotation or computed from prefetched items.
- `rebate_used` — exists on Order model, add to response dict.
- `account_set_name` — add account_set batch query.
- `creator_name` — add creator to select_related.

Sub-table item data: add `GET /api/finance/all-orders/{order_id}/items` endpoint returning `product_sku`, `product_name`, `quantity`, `unit_price`, `cost_price`, `amount`, `profit`, `shipped_qty`. Frontend fetches on first expand, caches in component state.

### 3. Logistics Panel

**Columns (16 total, 10 default visible):**

Existing 11 columns stay as-is. Add 5 new columns:

| Key | Label | Default | Align | Notes |
|-----|-------|---------|-------|-------|
| `order_amount` | 订单金额 | visible | right | New |
| `remark` | 备注 | visible | left | New, truncated |
| `salesperson` | 业务员 | hidden | left | New |
| `phone` | 收件电话 | hidden | left | New |
| `created_at` | 创建时间 | hidden | left | New |

**Backend changes:**

Fields already returned by list API: `total_amount`, `created_at`, and all existing column fields.

Fields that need to be added:
- `remark` — available on Order model but only returned for pending orders currently. Add to all order responses.
- `salesperson_name` — add `order__salesperson` to `select_related`.
- `phone` — use the first shipment's phone field. For orders with multiple shipments, show the most recent shipment's phone.

**No view mode toggle** — Logistics keeps single table + detail modal.

## Architecture

### New Files
- `frontend/src/composables/useColumnConfig.js` — shared composable

### Modified Files
- `frontend/src/composables/useShipment.js` — refactor to use `useColumnConfig`
- `frontend/src/components/business/PurchaseOrdersPanel.vue` — full table enrichment
- `frontend/src/components/business/finance/FinanceOrdersTab.vue` — full table enrichment
- `frontend/src/views/LogisticsView.vue` — add new columns
- `backend/app/routers/purchase_orders.py` — expand list API response
- `backend/app/routers/finance.py` — expand list API response
- `backend/app/routers/logistics.py` — expand list API response

### Component Structure (Purchase & Finance)

```
Panel
├── Toolbar (search, filters, view mode toggle, ⋯ column selector)
├── Table (summary mode)
│   ├── Header row (dynamic columns)
│   └── Body rows
│       ├── Summary row (click to expand)
│       └── Expand row (sub-table with line items)
└── Table (detail mode — flat, rowspan for order-level columns)
```

### localStorage Keys
- `purchase_columns` — Purchase Orders column visibility + view mode
- `finance_order_columns` — Finance Order Details column visibility + view mode
- `logistics_columns` — Logistics column visibility (existing key, preserved)

## Detail Mode Behavior

- **Sorting**: In detail mode, sorting applies to order-level fields only (sorts orders, items stay grouped under their order). Item-level sorting is not supported.
- **Pagination**: Page boundaries respect order boundaries — an order's items are never split across pages. This means pages may have slightly varying row counts.
- **Column toggling**: Rowspan applies only to order-level columns that are visible. Toggling a column off removes it from the rowspan layout.
- **Expand rows**: Not applicable in detail mode (items are already visible inline).

## Code Quality Guidelines

Per user request, prioritize:
- **Extensibility**: `useColumnConfig` composable makes adding new columns trivial (just add to defs array).
- **Separation of concerns**: Column definitions, visibility logic, and rendering are separate layers.
- **Backward compatibility**: Logistics `logistics_columns` localStorage key preserved.
- **Consistent patterns**: All three panels follow the same composable API.
- **Type safety**: Column defs use structured objects with clear contracts.

## Testing Checklist

- [ ] Column selector toggles columns on/off in all three panels
- [ ] Column preferences persist across page reloads (localStorage)
- [ ] Summary/Detail mode toggle works (Purchase & Finance)
- [ ] View mode preference persists across reloads
- [ ] Expand/collapse rows work in summary mode
- [ ] Sorting still works with dynamic columns
- [ ] Table renders correctly with many columns (horizontal scroll)
- [ ] Mobile responsive — horizontal scroll, no layout break
- [ ] Existing Logistics column preferences are preserved after refactor
