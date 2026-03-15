# 弹窗布局优化实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复弹窗 header/footer 随内容滚动的问题，新增展开模式和仓库列

**Architecture:** 将 `.modal` / `.modal-content` 改为 Flex 列布局，仅 `.modal-body` 滚动；按需添加展开按钮；商品明细表格新增仓库列

**Tech Stack:** Vue 3, Tailwind CSS 4, lucide-vue-next, CSS Flexbox

**Spec:** `docs/superpowers/specs/2026-03-15-modal-layout-optimization-design.md`

---

## File Structure

| 文件 | 职责 | 操作 |
|------|------|------|
| `frontend/src/styles/base.css` | 全局样式 — modal flex 布局 + expanded 类 | Modify |
| `frontend/src/components/business/finance/FinanceOrdersTab.vue` | 订单详情弹窗 — 展开按钮 + 仓库列 x2 + footer 标准化 | Modify |
| `frontend/src/views/CustomersView.vue` | 客户订单详情 — 迁移标准 class + 展开按钮 + 仓库列 | Modify |
| `frontend/src/components/business/VoucherDetailModal.vue` | 凭证详情 — footer 按钮 btn-sm | Modify |
| `frontend/src/components/business/purchase/PurchaseOrderDetail.vue` | 采购详情 — 补 modal-body | Modify |
| `frontend/src/components/business/purchase/PurchaseOrderForm.vue` | 采购表单 — 补 modal-body | Modify |
| `frontend/src/components/business/settings/EmployeeSettings.vue` | 员工设置 — 补 modal-body | Modify |
| `frontend/src/components/business/settings/DepartmentSettings.vue` | 部门设置 — 补 modal-body | Modify |
| `frontend/src/components/business/settings/UserSettings.vue` | 用户设置 — 补 modal-body | Modify |
| `frontend/src/components/business/settings/WarehouseSettings.vue` | 仓库设置 — 补 modal-body | Modify |

---

## Chunk 1: CSS 基础 + 组件修改

### Task 1: base.css — Flex 布局 + 展开模式 CSS

**Files:**
- Modify: `frontend/src/styles/base.css:215-267`（modal 样式区域）
- Modify: `frontend/src/styles/base.css:856-857`（移动端 modal 覆写）

**重要注意**：本项目的弹窗容器既用 `.modal` 又用 `.modal-content`，它们在原代码中是联合选择器，功能完全等同。**必须对两者都应用 Flex 布局**，否则使用 `.modal-content` 的弹窗（FinanceOrdersTab、PurchaseOrderDetail、Settings 等）不会生效。

- [ ] **Step 1: 修改 `.modal, .modal-content` 联合选择器**

找到 `base.css` 中（约 line 215-225）：
```css
  .modal,
  .modal-content {
    background: var(--surface);
    border-radius: 20px;
    max-width: 800px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    box-shadow: var(--shadow-lg);
  }
```

替换为：
```css
  .modal,
  .modal-content {
    background: var(--surface);
    border-radius: 20px;
    max-width: 800px;
    width: 100%;
    max-height: 90vh;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
    box-shadow: var(--shadow-lg);
    display: flex;
    flex-direction: column;
    transition: width 0.25s ease-out, max-width 0.25s ease-out, height 0.25s ease-out, max-height 0.25s ease-out;
  }
```

- [ ] **Step 2: 修改 `.modal-header` padding**

找到（约 line 226-232）：
```css
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 24px;
    border-bottom: 1px solid var(--border);
  }
```

替换为：
```css
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
```

- [ ] **Step 3: 修改 `.modal-body` 添加滚动**

找到（约 line 257-259）：
```css
  .modal-body {
    padding: 20px 24px;
  }
```

替换为：
```css
  .modal-body {
    padding: 20px 24px;
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }
```

- [ ] **Step 4: 修改 `.modal-footer` 添加 flex-shrink**

找到（约 line 260-267）：
```css
  .modal-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    padding: 16px 24px;
    border-top: 1px solid var(--border);
  }
```

替换为：
```css
  .modal-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    padding: 16px 24px;
    border-top: 1px solid var(--border);
    flex-shrink: 0;
  }
```

- [ ] **Step 5: 在 `.modal-footer` 后新增 `.modal-expanded` 和 `.modal-expand-btn` 样式**

在 `/* Buttons */` 注释行之前，插入：
```css
  .modal-expanded,
  .modal-content.modal-expanded {
    width: 95vw;
    max-width: 95vw;
    height: 95vh;
    max-height: 95vh;
  }
  .modal-expand-btn {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-muted);
    padding: 4px;
    border-radius: 8px;
    line-height: 1;
    transition: all .15s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
  }
  .modal-expand-btn:hover { background: var(--elevated); color: var(--text) }

```

- [ ] **Step 6: 运行 `npm run build` 验证 CSS 无语法错误**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
```

Expected: Build succeeds (exit 0)

- [ ] **Step 7: 提交**

```bash
git add frontend/src/styles/base.css
git commit -m "style: modal flex 布局 + 展开模式 CSS

header/footer 固定、body 滚动、展开按钮样式"
```

---

### Task 2: FinanceOrdersTab.vue — 展开按钮 + 仓库列 + footer 标准化

**Files:**
- Modify: `frontend/src/components/business/finance/FinanceOrdersTab.vue`

**注意**：此文件用 `.modal-content` 而非 `.modal`，Task 1 已对两者都应用了 Flex 布局。该弹窗已有 `modal-header` + `modal-body`。底部操作栏（line 406）用的是内联 `flex gap-3 px-6 py-4 border-t`，不是 `modal-footer`。

- [ ] **Step 1: 添加 lucide 图标导入**

在文件 `<script setup>` 的 import 区域找到 lucide 导入行，添加 `Maximize2, Minimize2`。如果没有 lucide 导入，新增一行：
```js
import { Maximize2, Minimize2 } from 'lucide-vue-next'
```

- [ ] **Step 2: 添加 isExpanded ref**

在 `<script setup>` 的 ref 声明区域添加：
```js
const isDetailExpanded = ref(false)
```

- [ ] **Step 3: 修改弹窗容器添加展开 class**

找到（line 185）：
```html
    <div class="modal-content" style="max-width:920px">
```

替换为：
```html
    <div class="modal-content" :class="{ 'modal-expanded': isDetailExpanded }" style="max-width:920px">
```

- [ ] **Step 4: 修改 modal-header 添加展开按钮**

找到（line 186-189）：
```html
      <div class="modal-header">
        <h3 class="font-semibold">订单详情</h3>
        <button @click="showOrderDetailModal = false; showReturnForm = false" class="modal-close">&times;</button>
      </div>
```

替换为：
```html
      <div class="modal-header">
        <h3 class="font-semibold">订单详情</h3>
        <div class="flex items-center gap-1">
          <button @click="isDetailExpanded = !isDetailExpanded" class="modal-expand-btn hidden md:inline-flex" :aria-label="isDetailExpanded ? '收起弹窗' : '展开弹窗'">
            <Minimize2 v-if="isDetailExpanded" :size="16" />
            <Maximize2 v-else :size="16" />
          </button>
          <button @click="showOrderDetailModal = false; showReturnForm = false" class="modal-close">&times;</button>
        </div>
      </div>
```

- [ ] **Step 5: 在商品明细弹窗表格 thead 中添加仓库列**

找到（约 line 266-271，详情弹窗内的 thead）：
```html
                    <th class="px-3 py-2 text-left text-xs font-semibold text-secondary">商品</th>
                    <th class="px-3 py-2 text-right text-xs font-semibold text-secondary">单价</th>
```

在"商品"和"单价"之间插入：
```html
                    <th class="px-3 py-2 text-left text-xs font-semibold text-secondary">仓库</th>
```

- [ ] **Step 6: 在商品明细弹窗表格 tbody 中添加仓库列**

找到（约 line 276-280，详情弹窗内的 tbody 行）：
```html
                    <td class="px-3 py-2.5">
                      <div class="font-medium">{{ item.product_name }}</div>
                      <div class="text-[11px] text-muted font-mono">{{ item.product_sku }}</div>
                    </td>
                    <td class="px-3 py-2.5 text-right">{{ fmt(item.unit_price) }}</td>
```

在商品 `<td>` 和单价 `<td>` 之间插入：
```html
                    <td class="px-3 py-2.5 text-muted">{{ item.warehouse_name || '-' }}</td>
```

- [ ] **Step 7: 在展开行子表 thead 中添加仓库列**

找到（约 line 122-123，展开行子表 thead）：
```html
                        <th class="px-2 py-1.5 text-left font-medium">商品名称</th>
                        <th class="px-2 py-1.5 text-center font-medium">数量</th>
```

在"商品名称"和"数量"之间插入：
```html
                        <th class="px-2 py-1.5 text-left font-medium">仓库</th>
```

- [ ] **Step 8: 在展开行子表 tbody 中添加仓库列**

找到（约 line 135，展开行子表 tbody）：
```html
                        <td class="px-2 py-1.5">{{ item.product_name }}</td>
                        <td class="px-2 py-1.5 text-center">{{ item.quantity }}</td>
```

在"商品名称"和"数量"之间插入：
```html
                        <td class="px-2 py-1.5 text-muted">{{ item.warehouse_name || '-' }}</td>
```

- [ ] **Step 9: 标准化底部操作栏为 modal-footer**

找到（约 line 406）：
```html
      <div v-if="!showReturnForm" class="flex gap-3 px-6 py-4 border-t border-line">
```

替换为：
```html
      <div v-if="!showReturnForm" class="modal-footer">
```

并将该 div 内的按钮 `btn` 后面添加 `btn-sm`，按钮去掉 `flex-1`：
- `class="btn btn-secondary flex-1"` → `class="btn btn-sm btn-secondary"`
- `class="btn btn-primary flex-1"` → `class="btn btn-sm btn-primary"`
- `class="btn flex-1" style="background:var(--error);color:#fff"` → `class="btn btn-sm btn-error"`（如果存在 btn-error，否则保留 style）

- [ ] **Step 10: 重置展开状态**

在关闭弹窗时重置 `isDetailExpanded`。找到 `showOrderDetailModal = false` 的赋值处（关闭按钮和 overlay click），在同一行追加 `isDetailExpanded = false`。

- [ ] **Step 11: 运行 `npm run build` 验证**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
```

Expected: Build succeeds (exit 0)

- [ ] **Step 12: 提交**

```bash
git add frontend/src/components/business/finance/FinanceOrdersTab.vue
git commit -m "feat(FinanceOrdersTab): 订单详情展开模式 + 仓库列 + footer 标准化"
```

---

### Task 3: CustomersView.vue — 迁移标准 class + 展开按钮 + 仓库列

**Files:**
- Modify: `frontend/src/views/CustomersView.vue`

**注意**：该文件有 **3 个弹窗**，全都用 `<div class="modal">` + 内联 `p-4 border-b`（非 `modal-header`）+ `p-4`（非 `modal-body`）。需要全部迁移到标准三段结构。展开按钮只加给订单详情弹窗，仓库列也只加给订单详情弹窗。

**3 个弹窗**：
1. `modal.type === 'customer'`（客户编辑，line 56-104）— form 结构
2. `modal.type === 'customer_trans'`（交易明细，line 107-230）— 包含内联 `max-h-64 overflow-y-auto` 的交易列表
3. `modal.type === 'order_detail'`（订单详情，line 233-354）— 需要展开按钮 + 仓库列

- [ ] **Step 1: 添加 lucide 图标导入**

在 `<script setup>` import 区域添加：
```js
import { Maximize2, Minimize2 } from 'lucide-vue-next'
```

- [ ] **Step 2: 添加 isDetailExpanded ref**

```js
const isDetailExpanded = ref(false)
```

- [ ] **Step 3: 迁移客户编辑弹窗（customer）到标准结构**

找到（line 58-60）：
```html
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="modal-close">&times;</button>
        </div>
```

替换为：
```html
        <div class="modal-header">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="modal-close">&times;</button>
        </div>
```

找到（line 62）：
```html
        <div class="p-4">
```

替换为：
```html
        <div class="modal-body">
```

找到底部按钮区（line 97-100）：
```html
            <div class="flex gap-3 pt-3">
              <button type="button" @click="closeModal" class="btn btn-secondary flex-1">取消</button>
              <button type="submit" class="btn btn-primary flex-1">保存</button>
            </div>
```

将这个 div 移出 `modal-body`（放在 form 和 `modal-body` 的闭合 `</div>` 之后），改为：
```html
        <div class="modal-footer">
          <button type="button" @click="closeModal" class="btn btn-sm btn-secondary">取消</button>
          <button type="button" @click="saveCustomerHandler" class="btn btn-sm btn-primary">保存</button>
        </div>
```

并将 `<form @submit.prevent="saveCustomerHandler">` 改为普通 `<div>`（因为 submit 逻辑已移到按钮 `@click`）。

- [ ] **Step 4: 迁移交易明细弹窗（customer_trans）到标准结构**

找到（line 109-111）：
```html
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="modal-close">&times;</button>
        </div>
```

替换为：
```html
        <div class="modal-header">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="modal-close">&times;</button>
        </div>
```

找到（line 113）：
```html
        <div class="p-4">
```

替换为：
```html
        <div class="modal-body">
```

**移除内联滚动容器**（line 193）：
```html
          <div class="max-h-64 overflow-y-auto">
```

改为无滚动限制的 div（依赖 `modal-body` 的自然滚动）：
```html
          <div>
```

找到底部按钮区（line 225-227）：
```html
          <div class="flex gap-3 pt-4">
            <button type="button" @click="closeModal" class="btn btn-secondary flex-1">关闭</button>
          </div>
```

移出 `modal-body`，改为：
```html
        <div class="modal-footer">
          <button type="button" @click="closeModal" class="btn btn-sm btn-secondary">关闭</button>
        </div>
```

- [ ] **Step 5: 修改订单详情弹窗容器添加展开 class**

找到（line 234）：
```html
      <div class="modal">
```

替换为：
```html
      <div class="modal" :class="{ 'modal-expanded': isDetailExpanded }">
```

- [ ] **Step 7: 迁移订单详情 header 到标准 modal-header（含展开按钮）**

找到（line 235-241）：
```html
        <div class="p-4 border-b flex justify-between items-center">
          <div class="flex items-center gap-2">
            <button v-if="previousModal" @click="goBackToPrevious" class="text-muted hover:text-primary text-xl" title="返回上一页">←</button>
            <h3 class="font-semibold">{{ modal.title }}</h3>
          </div>
          <button @click="closeModal" class="modal-close">&times;</button>
        </div>
```

替换为：
```html
        <div class="modal-header">
          <div class="flex items-center gap-2">
            <button v-if="previousModal" @click="goBackToPrevious" class="text-muted hover:text-primary text-xl" title="返回上一页">&larr;</button>
            <h3 class="font-semibold">{{ modal.title }}</h3>
          </div>
          <div class="flex items-center gap-1">
            <button @click="isDetailExpanded = !isDetailExpanded" class="modal-expand-btn hidden md:inline-flex" :aria-label="isDetailExpanded ? '收起弹窗' : '展开弹窗'">
              <Minimize2 v-if="isDetailExpanded" :size="16" />
              <Maximize2 v-else :size="16" />
            </button>
            <button @click="closeModal" class="modal-close">&times;</button>
          </div>
        </div>
```

- [ ] **Step 8: 迁移订单详情 body 到标准 modal-body**

找到（line 242）：
```html
        <div class="p-4">
```

替换为：
```html
        <div class="modal-body">
```

- [ ] **Step 9: 迁移订单详情 footer 到标准 modal-footer + btn-sm**

找到（约 line 349-351）：
```html
          <div class="flex gap-3 pt-4">
            <button type="button" @click="closeModal" class="btn btn-secondary flex-1">关闭</button>
          </div>
```

将这个 div 移出 `modal-body`（关闭 `modal-body` 的 `</div>` 后），改为：
```html
        <div class="modal-footer">
          <button type="button" @click="closeModal" class="btn btn-sm btn-secondary">关闭</button>
        </div>
```

确保 DOM 结构为：`modal-header` → `modal-body`(包含所有内容) → `modal-footer`。

- [ ] **Step 10: 在商品明细表格 thead 中添加仓库列**

找到（line 326-327）：
```html
                  <th class="px-2 py-1 text-left">商品</th>
                  <th class="px-2 py-1 text-right">单价</th>
```

在"商品"和"单价"之间插入：
```html
                  <th class="px-2 py-1 text-left">仓库</th>
```

- [ ] **Step 11: 在商品明细表格 tbody 中添加仓库列**

找到（line 336-340）：
```html
                  <td class="px-2 py-1">
                    <div>{{ item.product_name }}</div>
                    <div class="text-xs text-muted">{{ item.product_sku }}</div>
                  </td>
                  <td class="px-2 py-1 text-right">{{ fmt(item.unit_price) }}</td>
```

在商品 `<td>` 和单价 `<td>` 之间插入：
```html
                  <td class="px-2 py-1 text-muted">{{ item.warehouse_name || '-' }}</td>
```

- [ ] **Step 12: 重置展开状态**

在 `closeModal` 方法中添加 `isDetailExpanded.value = false`。

- [ ] **Step 13: 运行 `npm run build` 验证**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
```

Expected: Build succeeds (exit 0)

- [ ] **Step 14: 提交**

```bash
git add frontend/src/views/CustomersView.vue
git commit -m "feat(CustomersView): 订单详情标准化 + 展开模式 + 仓库列"
```

---

### Task 4: VoucherDetailModal.vue — footer 按钮统一 btn-sm

**Files:**
- Modify: `frontend/src/components/business/VoucherDetailModal.vue:140-145`

- [ ] **Step 1: 修改 5 个 footer 按钮添加 btn-sm**

找到（line 141-145）：
```html
          <button @click="close" class="btn btn-secondary">{{ (isEditing || isCreating) ? '取消' : '关闭' }}</button>
          <button v-if="isCreating" @click="handleCreate" class="btn btn-primary" :disabled="submitting || totalDebit !== totalCredit">{{ submitting ? '保存中...' : '保存' }}</button>
          <button v-if="isEditing" @click="handleUpdate" class="btn btn-primary" :disabled="submitting || totalDebit !== totalCredit">{{ submitting ? '保存中...' : '保存' }}</button>
          <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'posted' && hasPermission('accounting_post')" @click="handleUnpost(detailVoucher)" class="btn btn-warning">反过账</button>
          <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'draft' && hasPermission('accounting_edit')" @click="startEdit" class="btn btn-primary">编辑</button>
```

每行的 `class="btn btn-` 改为 `class="btn btn-sm btn-`：
```html
          <button @click="close" class="btn btn-sm btn-secondary">{{ (isEditing || isCreating) ? '取消' : '关闭' }}</button>
          <button v-if="isCreating" @click="handleCreate" class="btn btn-sm btn-primary" :disabled="submitting || totalDebit !== totalCredit">{{ submitting ? '保存中...' : '保存' }}</button>
          <button v-if="isEditing" @click="handleUpdate" class="btn btn-sm btn-primary" :disabled="submitting || totalDebit !== totalCredit">{{ submitting ? '保存中...' : '保存' }}</button>
          <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'posted' && hasPermission('accounting_post')" @click="handleUnpost(detailVoucher)" class="btn btn-sm btn-warning">反过账</button>
          <button v-if="!isEditing && !isCreating && detailVoucher?.status === 'draft' && hasPermission('accounting_edit')" @click="startEdit" class="btn btn-sm btn-primary">编辑</button>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/business/VoucherDetailModal.vue
git commit -m "style(VoucherDetailModal): footer 按钮统一 btn-sm"
```

---

### Task 5: 补 modal-body — PurchaseOrderDetail + PurchaseOrderForm

**Files:**
- Modify: `frontend/src/components/business/purchase/PurchaseOrderDetail.vue:9-99`
- Modify: `frontend/src/components/business/purchase/PurchaseOrderForm.vue:9`

**注意**：这两个文件的 modal-header 后面是 `<div class="space-y-4 p-4">`（非 `modal-body`），底部操作按钮在同一个 div 内。需要将内容区包裹为 `modal-body`，并将操作按钮移到 `modal-footer`。

- [ ] **Step 1: PurchaseOrderDetail — 包裹 modal-body + 迁移 footer**

找到（line 9）：
```html
      <div class="space-y-4 p-4">
```

替换为：
```html
      <div class="modal-body">
        <div class="space-y-4">
```

找到底部操作按钮区（约 line 92-98）：
```html
        <!-- 操作按钮 -->
        <div class="flex gap-3 pt-2 flex-wrap">
          ...buttons...
        </div>
      </div>
```

将操作按钮 div 移出 `modal-body`，改为 `modal-footer`：
```html
        </div>
      </div>
      <div class="modal-footer flex-wrap">
        <button v-if="..." class="btn btn-sm btn-primary">审核通过</button>
        ...（所有按钮加 btn-sm，去掉 flex-1，去掉内联 style 改用语义 class）
        <button @click="showPODetailModal = false" class="btn btn-sm btn-secondary">关闭</button>
      </div>
```

- [ ] **Step 2: PurchaseOrderForm — 包裹 modal-body + 迁移 footer**

找到（line 9）：
```html
      <div class="space-y-4 p-4">
```

替换为：
```html
      <div class="modal-body">
        <div class="space-y-4">
```

找到底部操作按钮区（line 169-173）：
```html
        <!-- 操作按钮 -->
        <div class="flex gap-3 pt-2">
          <button type="button" @click="close" class="btn btn-secondary flex-1">取消</button>
          <button type="button" @click="savePurchaseOrder" class="btn btn-primary flex-1" :disabled="appStore.submitting">{{ appStore.submitting ? '提交中...' : '确认提交' }}</button>
        </div>
```

将操作按钮 div 移出 `modal-body`，关闭内层 `space-y-4` 和 `modal-body` 的 `</div>` 后，改为 `modal-footer`：
```html
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" @click="close" class="btn btn-sm btn-secondary">取消</button>
        <button type="button" @click="savePurchaseOrder" class="btn btn-sm btn-primary" :disabled="appStore.submitting">{{ appStore.submitting ? '提交中...' : '确认提交' }}</button>
      </div>
```

确保去掉原来的 `</div></div>` 闭合标签（原 `space-y-4` 和 `p-4` 的闭合），保持 DOM 树平衡。

- [ ] **Step 3: 运行 `npm run build` 验证**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
```

Expected: Build succeeds (exit 0)

- [ ] **Step 4: 提交**

```bash
git add frontend/src/components/business/purchase/PurchaseOrderDetail.vue frontend/src/components/business/purchase/PurchaseOrderForm.vue
git commit -m "fix(Purchase): 补 modal-body + modal-footer 标准化"
```

---

### Task 6: 补 modal-body — Settings 四文件

**Files:**
- Modify: `frontend/src/components/business/settings/EmployeeSettings.vue:57-78`
- Modify: `frontend/src/components/business/settings/DepartmentSettings.vue:40-47`
- Modify: `frontend/src/components/business/settings/UserSettings.vue:66-91,102`
- Modify: `frontend/src/components/business/settings/WarehouseSettings.vue:87-101,112-119`

**注意**：Settings 弹窗都用 `modal-content` + `modal-header`，但 header 后面是 `<form class="space-y-3 p-4">`。需要给 form 添加 `modal-body` 包裹，底部按钮移到 `modal-footer`。

**模式统一**：每个 Settings 弹窗的结构改为：
```html
<div class="modal-content">
  <div class="modal-header">...</div>
  <form @submit.prevent="..." class="modal-body">
    ...表单字段...
  </form>
  <div class="modal-footer">
    <button class="btn btn-sm btn-secondary">取消</button>
    <button class="btn btn-sm btn-primary">保存</button>
  </div>
</div>
```

**注意**：`<form>` 可以直接作为 `modal-body`（`form.modal-body`），因为 `modal-body` 只设置 padding + flex + overflow 样式，不影响 form 功能。但提交按钮移到 `modal-footer` 后不在 form 内，需要用 `form` attribute（HTML5）或改为 form 内 footer。考虑到简单性，保持 footer 在 form 内部：

```html
<div class="modal-content">
  <div class="modal-header">...</div>
  <form @submit.prevent="..." class="modal-body space-y-3">
    ...表单字段...
    <div class="modal-footer" style="margin: 0 -24px -20px; padding-top: 16px;">
      ...buttons...
    </div>
  </form>
</div>
```

**更简单的方案**：直接在 form 外包一层 `modal-body`，form 在里面保持原状，底部按钮拆到 `modal-footer`。submit 事件改到按钮 `@click`：

```html
<div class="modal-content">
  <div class="modal-header">...</div>
  <div class="modal-body">
    <div class="space-y-3">
      ...表单字段（不含提交按钮）...
    </div>
  </div>
  <div class="modal-footer">
    <button type="button" @click="showModal = false" class="btn btn-sm btn-secondary">取消</button>
    <button type="button" @click="save()" class="btn btn-sm btn-primary">保存</button>
  </div>
</div>
```

采用这个方案。`form` 标签可以去掉（改为 div），submit 逻辑移到按钮 `@click`。

- [ ] **Step 1: EmployeeSettings.vue — 补 modal-body + modal-footer**

找到（line 57-78，从 form 到最后的 flex 按钮区）。将 `<form @submit.prevent="saveEmployee" class="space-y-3 p-4">` 改为 `<div class="modal-body"><div class="space-y-3">`，底部按钮移出为 `<div class="modal-footer">`，`btn-primary` 的 `@click` 改为调用 `saveEmployee()`。

- [ ] **Step 2: DepartmentSettings.vue — 同上**

找到（line 40-47）。同样操作。

- [ ] **Step 3: UserSettings.vue — 两个弹窗都补 modal-body**

该文件有 2 个弹窗（用户编辑 + 备份恢复），都需要补。

- [ ] **Step 4: WarehouseSettings.vue — 两个弹窗都补 modal-body**

该文件有 2 个弹窗（仓库编辑 + 仓位编辑），都需要补。

- [ ] **Step 5: 运行 `npm run build` 验证**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
```

Expected: Build succeeds (exit 0)

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/business/settings/
git commit -m "fix(Settings): 四个设置弹窗补 modal-body + modal-footer"
```

---

### Task 7: 最终验证

- [ ] **Step 1: 运行完整构建**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
```

Expected: Build succeeds (exit 0), no warnings related to our changes

- [ ] **Step 2: 启动 preview 验证弹窗行为**

使用 `preview_start` 启动开发服务器，打开订单详情弹窗：
1. 用 `preview_snapshot` 验证 modal-header 固定在顶部
2. 验证展开按钮出现在关闭按钮左侧
3. 验证仓库列出现在商品明细表中
4. 验证 footer 按钮使用 btn-sm

- [ ] **Step 3: 如有视觉问题则修复，否则最终提交确认**
