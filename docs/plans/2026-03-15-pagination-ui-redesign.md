# 分页组件 UI 重设计 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将分页控件移入表格 tfoot，添加页码快捷跳转，统一背景色和高度与表头呼应。

**Architecture:** 扩展 `usePagination` composable 新增 `visiblePages` 和 `goToPage`，然后在 5 个使用分页的组件中将外部 div 分页替换为 tfoot 内的分页行。有 tfoot 的组件（2个）新增分页行，无 tfoot 的组件（3个）同时新增 tfoot + 分页行。

**Tech Stack:** Vue 3 Composition API, Tailwind CSS 4, usePagination composable

---

### Task 1: 扩展 usePagination composable

**Files:**
- Modify: `frontend/src/composables/usePagination.js`

**Step 1: 添加 visiblePages 和 goToPage**

在 `usePagination.js` 中新增 `visiblePages` computed 和 `goToPage` 方法：

```js
/** 可见页码数组，包含数字和省略号标记 */
const visiblePages = computed(() => {
  const tp = totalPages.value
  const cur = page.value
  if (tp <= 5) return Array.from({ length: tp }, (_, i) => i + 1)
  const pages = []
  if (cur <= 3) {
    pages.push(1, 2, 3, '…', tp)
  } else if (cur >= tp - 2) {
    pages.push(1, '…', tp - 2, tp - 1, tp)
  } else {
    pages.push(1, '…', cur - 1, cur, cur + 1, '…', tp)
  }
  return pages
})

/** 跳转到指定页 */
const goToPage = (n) => {
  if (n >= 1 && n <= totalPages.value) page.value = n
}
```

在 return 中新增导出：`visiblePages, goToPage`

**Step 2: 验证构建**

Run: `cd frontend && npm run build`
Expected: 构建成功，无错误

**Step 3: Commit**

```bash
git add frontend/src/composables/usePagination.js
git commit -m "feat: 扩展 usePagination 添加页码导航和跳转功能"
```

---

### Task 2: 修改 PurchaseOrdersPanel（有 tfoot + 有分页）

**Files:**
- Modify: `frontend/src/components/business/PurchaseOrdersPanel.vue`

**Step 1: 在 script setup 中解构新增的导出**

找到从 `usePurchaseOrder` 解构的地方，确保 `total, visiblePages, goToPage` 已导出。如果 `usePurchaseOrder.js` 没有转发这些，需要从中导出。

检查 `frontend/src/composables/usePurchaseOrder.js`，确保它转发 `total, visiblePages, goToPage`。

**Step 2: 移除外部分页 div，在 tfoot 中添加分页行**

将 `PurchaseOrdersPanel.vue` 中的：
```html
<!-- 分页 -->
<div v-if="hasPagination" class="flex items-center justify-center gap-2 py-3">
  <button @click="prevPage(); loadPurchaseOrders()" :disabled="page <= 1" class="btn btn-secondary btn-sm">上一页</button>
  <span class="text-[13px] text-muted leading-8">{{ page }} / {{ totalPages }}</span>
  <button @click="nextPage(); loadPurchaseOrders()" :disabled="page >= totalPages" class="btn btn-secondary btn-sm">下一页</button>
</div>
```

替换为空（删除整个 div）。

同时，在现有 `<tfoot>` 的 `</tr>` 之后、`</tfoot>` 之前，新增分页行：

```html
          <tr v-if="hasPagination">
            <td :colspan="100" class="px-3.5 py-2.5">
              <div class="flex items-center justify-between">
                <span class="text-xs text-muted">共 {{ total }} 条</span>
                <div class="flex items-center gap-1">
                  <button @click="prevPage(); loadPurchaseOrders()" :disabled="page <= 1" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">‹</button>
                  <template v-for="(p, i) in visiblePages" :key="i">
                    <span v-if="p === '…'" class="w-7 h-7 flex items-center justify-center text-xs text-muted cursor-default">…</span>
                    <button v-else @click="goToPage(p); loadPurchaseOrders()" :class="p === page ? 'bg-primary text-white font-medium' : 'text-muted hover:bg-surface-hover hover:text-text'" class="w-7 h-7 flex items-center justify-center rounded-md text-xs">{{ p }}</button>
                  </template>
                  <button @click="nextPage(); loadPurchaseOrders()" :disabled="page >= totalPages" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">›</button>
                </div>
                <span class="text-xs text-muted w-16"></span>
              </div>
            </td>
          </tr>
```

**Step 3: 移除 tfoot 上的 border-t**

将 `<tfoot ... class="bg-elevated font-semibold text-sm border-t">` 改为 `<tfoot ... class="bg-elevated font-semibold text-sm">`

**Step 4: 验证构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

**Step 5: Commit**

```bash
git add frontend/src/components/business/PurchaseOrdersPanel.vue
git commit -m "feat: PurchaseOrdersPanel 分页移入 tfoot 并添加页码导航"
```

---

### Task 3: 修改 FinanceOrdersTab（有 tfoot + 有分页）

**Files:**
- Modify: `frontend/src/components/business/finance/FinanceOrdersTab.vue`

**Step 1: 确保 script setup 中有 total, visiblePages, goToPage**

FinanceOrdersTab 使用的是 `useFinanceOrder` 还是直接 `usePagination`，需确认并确保新增导出可用。

**Step 2: 与 Task 2 相同的模式**

- 移除外部分页 div（lines 202-207）
- 在 tfoot 的 `</tr>` 之后、`</tfoot>` 之前新增分页行（同 Task 2 模板，但 load 函数改为 `loadOrders()`）
- 移除 tfoot 的 `border-t` class

**Step 3: 验证构建**

Run: `cd frontend && npm run build`

**Step 4: Commit**

```bash
git add frontend/src/components/business/finance/FinanceOrdersTab.vue
git commit -m "feat: FinanceOrdersTab 分页移入 tfoot 并添加页码导航"
```

---

### Task 4: 修改 StockView（无 tfoot + 有分页）

**Files:**
- Modify: `frontend/src/views/StockView.vue`

**Step 1: 确保 script setup 中有 total, visiblePages, goToPage**

StockView 使用 `useStock` composable，需确认并转发新增导出。

**Step 2: 在 </tbody> 和 </table> 之间新增 tfoot**

在 `</tbody>` 之后新增完整 tfoot（仅含分页行，无合计行）：

```html
        <tfoot v-if="hasPagination" class="bg-elevated text-sm">
          <tr>
            <td :colspan="100" class="px-3.5 py-2.5">
              <div class="flex items-center justify-between">
                <span class="text-xs text-muted">共 {{ total }} 条</span>
                <div class="flex items-center gap-1">
                  <button @click="prevPage(); loadProductsData()" :disabled="page <= 1" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">‹</button>
                  <template v-for="(p, i) in visiblePages" :key="i">
                    <span v-if="p === '…'" class="w-7 h-7 flex items-center justify-center text-xs text-muted cursor-default">…</span>
                    <button v-else @click="goToPage(p); loadProductsData()" :class="p === page ? 'bg-primary text-white font-medium' : 'text-muted hover:bg-surface-hover hover:text-text'" class="w-7 h-7 flex items-center justify-center rounded-md text-xs">{{ p }}</button>
                  </template>
                  <button @click="nextPage(); loadProductsData()" :disabled="page >= totalPages" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">›</button>
                </div>
                <span class="text-xs text-muted w-16"></span>
              </div>
            </td>
          </tr>
        </tfoot>
```

同时删除外部分页 div。

**Step 3: 验证构建**

Run: `cd frontend && npm run build`

**Step 4: Commit**

```bash
git add frontend/src/views/StockView.vue
git commit -m "feat: StockView 分页移入 tfoot 并添加页码导航"
```

---

### Task 5: 修改 LogisticsView（无 tfoot + 有分页）

**Files:**
- Modify: `frontend/src/views/LogisticsView.vue`

与 Task 4 相同模式：
- 确保 `useShipment` 转发 `total, visiblePages, goToPage`
- 在 `</tbody>` 后新增 tfoot（仅分页行），load 函数为 `loadShipments()`
- 删除外部分页 div

**Step: 验证构建 + Commit**

```bash
git add frontend/src/views/LogisticsView.vue
git commit -m "feat: LogisticsView 分页移入 tfoot 并添加页码导航"
```

---

### Task 6: 修改 PurchaseReturnTab（无 tfoot + 有分页）

**Files:**
- Modify: `frontend/src/components/business/purchase/PurchaseReturnTab.vue`

与 Task 4 相同模式：
- 确保有 `total, visiblePages, goToPage`
- 新增 tfoot（仅分页行），load 函数为 `loadList()`
- 删除外部分页 div

**Step: 验证构建 + Commit**

```bash
git add frontend/src/components/business/purchase/PurchaseReturnTab.vue
git commit -m "feat: PurchaseReturnTab 分页移入 tfoot 并添加页码导航"
```

---

### Task 7: 更新中间 composables 转发新导出

**Files:**
- Modify: `frontend/src/composables/usePurchaseOrder.js`
- Modify: `frontend/src/composables/useStock.js`
- Modify: `frontend/src/composables/useShipment.js`

每个 composable 调用了 `usePagination(20)` 后只转发了部分属性。需要确保 `total`, `visiblePages`, `goToPage` 也被转发出去。

检查每个文件的 return 语句，补充缺失的导出。

**Step: 验证构建 + Commit**

```bash
git add frontend/src/composables/usePurchaseOrder.js frontend/src/composables/useStock.js frontend/src/composables/useShipment.js
git commit -m "feat: composables 转发 visiblePages 和 goToPage"
```

---

### Task 8: 最终验证

**Step 1: 完整构建**

Run: `cd frontend && npm run build`
Expected: 零错误

**Step 2: 视觉验证**

用 preview_snapshot 检查至少 2 个有分页的页面（采购 + 库存），确认：
- 分页行在 tfoot 内
- 背景色与表头一致
- 无多余黑色分割线
- 页码按钮可见

**Step 3: Console 检查**

用 preview_console_logs 确认无 JS 错误
