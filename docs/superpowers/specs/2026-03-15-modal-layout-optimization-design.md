# 弹窗布局优化设计方案

**日期**: 2026-03-15
**版本**: v1.1
**状态**: 已确认

## 问题描述

当前弹窗（modal）在内容超出视口高度时，整个弹窗（包括 header 标题和关闭按钮、footer 操作按钮）一起滚动，导致：

1. 用户下拉后看不到标题，不知道当前在哪个弹窗
2. 关闭按钮滚出视野，无法快速关闭
3. footer 操作按钮也被滚走，需要滚到底部才能操作

**根因**：`.modal` 设置了 `overflow-y: auto; max-height: 90vh`，整个弹窗作为一个滚动容器，header/body/footer 一起滚动。

## 改动范围

### 一、Modal Flexbox 布局重构（`base.css`）

将 `.modal` 从单一滚动容器改为 Flex 列布局，仅 `.modal-body` 滚动。

**注意**：`base.css` 中 `.modal` 和 `.modal-content` 是联合选择器。本次改动需要将两者**拆分**，仅对 `.modal` 添加 Flex 布局属性，`.modal-content` 保持原有样式不变（它用于非三段结构的弹窗内容容器）。

**改动前**（`base.css` line 215-225）：
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
.modal-header { padding: 20px 24px; }
.modal-body { padding: 20px 24px; }
.modal-footer { /* 无 flex-shrink */ }
```

**改动后**：
```css
/* 共有样式保留联合选择器 */
.modal,
.modal-content {
  background: var(--surface);
  border-radius: 20px;
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  -webkit-overflow-scrolling: touch;
  box-shadow: var(--shadow-lg);
}

/* .modal-content 保持原有滚动行为 */
.modal-content {
  overflow-y: auto;
}

/* .modal 改为 Flex 列布局 */
.modal {
  overflow-y: hidden;
  display: flex;
  flex-direction: column;
}
.modal-header {
  padding: 16px 24px;    /* 行高缩小 */
  flex-shrink: 0;
}
.modal-body {
  padding: 20px 24px;
  flex: 1;
  overflow-y: auto;
  min-height: 0;         /* flex 子元素溢出关键属性 */
}
.modal-footer {
  flex-shrink: 0;
}
```

移动端 `.modal { max-height: 95vh }` 逻辑不变，同样受益于 Flex 布局。

**影响范围**：全局所有使用 `.modal-header` + `.modal-body` + `.modal-footer` 三段结构的弹窗（20+ 个）自动生效。

### 二、展开模式（近全屏切换）

在 header 右侧、关闭按钮 `x` 左边增加展开/收起图标按钮。

**交互**：
- 使用 `lucide-vue-next` 的 `Maximize2`（展开）和 `Minimize2`（收起）图标
- 点击后弹窗在默认尺寸 <-> 近全屏（`95vw x 95vh`）之间切换
- 带 `transition` 过渡动画（0.25s ease-out）
- 移动端隐藏展开按钮（`hidden md:inline-flex`），因为移动端弹窗已接近全屏

**无障碍**：
- 展开按钮设置 `aria-label="展开弹窗"` / `aria-label="收起弹窗"`，随状态切换
- Escape 键行为：无论是否展开，Escape 直接关闭弹窗（不做"先收起再关闭"的二段式）

**CSS**：
```css
.modal.modal-expanded {
  width: 95vw;
  max-width: 95vw;
  height: 95vh;
  max-height: 95vh;
}

.modal {
  transition: width 0.25s ease-out,
              max-width 0.25s ease-out,
              height 0.25s ease-out,
              max-height 0.25s ease-out;
}
```

**组件层面**：
- 不做全局自动注入，各弹窗按需添加展开按钮
- 首批添加展开功能的弹窗：`FinanceOrdersTab.vue`（订单详情）、`CustomersView.vue`（客户订单详情）
- 通过 `ref` 控制 `isExpanded` 状态，切换 `.modal-expanded` class

### 三、Footer 按钮统一 `btn-sm`

扫描所有 `modal-footer` 内的按钮，将未使用 `btn-sm` 的统一加上。

**已确认需要改动的文件**：
- `VoucherDetailModal.vue` — modal-footer 内所有按钮统一添加 `btn-sm`（涉及 `btn-secondary` x1、`btn-primary` x3、`btn-warning` x1，共 5 处）

其余弹窗已使用 `btn-sm`，无需改动。

### 四、商品明细表格新增"仓库"列

**数据来源**：后端 API 已在 OrderItem 中返回 `warehouse_name` 字段（`orders.py` line 480），无需后端改动。

**影响文件及各自列顺序调整**（3 处表格）：

**1. `FinanceOrdersTab.vue` — 订单详情弹窗内商品明细表（line 266 区域）**
```
改前：商品 | 单价 | 数量 | [返利] | 金额 | [毛利]
改后：商品 | 仓库 | 单价 | 数量 | [返利] | 金额 | [毛利]
```

**2. `CustomersView.vue` — 客户页订单详情弹窗内商品明细表（line 326 区域）**
```
改前：商品 | 单价 | 数量 | [返利] | 金额 | [毛利]
改后：商品 | 仓库 | 单价 | 数量 | [返利] | 金额 | [毛利]
```

**3. `FinanceOrdersTab.vue` — 列表展开行商品明细子表（line 122 区域）**
```
改前：商品SKU | 商品名称 | 数量 | 单价 | [成本价] | 金额 | [毛利] | 已发货数
改后：商品SKU | 商品名称 | 仓库 | 数量 | 单价 | [成本价] | 金额 | [毛利] | 已发货数
```

**仓库列样式**：`text-[13px] text-muted`（弹窗表格）/ `text-xs text-muted`（子表），左对齐，无仓库时显示 `-`。

### 五、缺少 `modal-body` 的组件修补

以下组件缺少 `.modal-body` 包裹层，需补上以配合 Flex 布局：

| 组件文件 | 现状 | 改动 |
|----------|------|------|
| `CustomersView.vue` | 3 个弹窗（编辑/交易/订单详情）用内联 `p-4 border-b` 代替 `modal-header`，无 `modal-body` | 迁移到标准 `modal-header` / `modal-body` / `modal-footer` 体系 |
| `PurchaseOrderDetail.vue` | 有 `modal-header`，无 `modal-body` | 内容区包裹 `<div class="modal-body">` |
| `PurchaseOrderForm.vue` | 有 `modal-header`，无 `modal-body` | 表单区包裹 `<div class="modal-body">` |
| `EmployeeSettings.vue` | 有 `modal-header`，无 `modal-body` | 内容区包裹 `modal-body` |
| `DepartmentSettings.vue` | 同上 | 同上 |
| `UserSettings.vue` | 同上 | 同上 |
| `WarehouseSettings.vue` | 同上 | 同上 |

## 技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 布局方案 | Flexbox | 标准解法，兼容性好，语义清晰 |
| 展开尺寸 | 95vw x 95vh | 保留边距让用户意识到在弹窗中 |
| 展开按钮范围 | 按需添加 | 不是所有弹窗都需要展开，避免过度设计 |
| 仓库数据 | 复用已有字段 | 后端已返回 warehouse_name，零后端改动 |

## 不做的事

- 不做弹窗拖拽/调整大小功能
- 不做弹窗全屏模式（100vw x 100vh）
- 不做展开按钮的全局自动注入
- 不改后端 API
