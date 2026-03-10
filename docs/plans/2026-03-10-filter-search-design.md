# 全局筛选搜索增强 设计文档

**Goal:** 为销售开单、订单明细、欠款明细、收款管理、付款管理、出入库日志六个模块增加筛选、搜索和重置功能。

**Tech Stack:** Vue 3 (Composition API) / FastAPI + Tortoise ORM / lucide-vue-next

---

## 1. 可搜索下拉框组件 — SearchableSelect

**新建** `frontend/src/components/common/SearchableSelect.vue`

替代销售开单的原生 `<select>` 客户选择。通用组件，可复用。

**交互：**
- 默认显示已选项文本或 placeholder
- 点击展开下拉面板，顶部搜索框自动聚焦
- 输入关键字实时过滤列表（客户端模糊匹配）
- 选中后关闭面板；× 按钮可清除选择
- 点击外部自动关闭

**Props：**
- `options: Array<{ id, label, sublabel? }>` — 选项列表
- `modelValue` — 选中值 (v-model)
- `placeholder` — 提示文字
- `searchFields: string[]` — 搜索匹配字段，默认 `['label']`

---

## 2. 各模块改造明细

### 2.1 销售开单 — 客户选择

**修改** `frontend/src/components/business/sales/ShoppingCart.vue`

- 将 `<select>` 替换为 `<SearchableSelect>`
- options 从 customersStore.customers 映射为 `{ id, label: name, sublabel: phone }`
- 搜索匹配 name + phone

### 2.2 订单明细 — 增加状态筛选

**修改** `frontend/src/components/business/finance/FinanceOrdersTab.vue`

新增筛选项：
- 付款状态下拉：全部 / 已结清 / 未结清 / 待确认 / 已取消

**后端** `GET /finance/all-orders` 新增参数：
- `payment_status: Optional[str]` — 值：`cleared` / `uncleared` / `unconfirmed` / `cancelled`

### 2.3 欠款明细 — 增加筛选搜索

**修改** `frontend/src/components/business/finance/FinanceUnpaidTab.vue`

新增筛选项：
- 订单类型下拉：全部 / 赊销(CREDIT) / 寄售结算(CONSIGN_SETTLE)
- 日期范围：开始日期 + 结束日期
- 关键字搜索：订单号 / 客户名模糊搜索
- 重置按钮

**后端** `GET /finance/unpaid-orders` 扩展参数：
- `order_type: Optional[str]`
- `start_date: Optional[str]`
- `end_date: Optional[str]`
- `search: Optional[str]` — 模糊匹配 order_no + customer.name

### 2.4 收款管理 — 增加筛选搜索

**修改** `frontend/src/components/business/FinancePaymentsPanel.vue`

新增筛选项：
- 确认状态下拉：全部 / 待确认 / 已确认
- 日期范围：开始日期 + 结束日期
- 关键字搜索：订单号 / 客户名模糊搜索
- 重置按钮

**后端** `GET /finance/payments` 扩展参数：
- `is_confirmed: Optional[bool]`
- `start_date: Optional[str]`
- `end_date: Optional[str]`
- `search: Optional[str]` — 模糊匹配关联 order_no + customer.name

### 2.5 付款管理 — 增加筛选搜索

**修改** `frontend/src/components/business/FinancePayablesPanel.vue`

新增筛选项：
- 状态下拉：全部 / 待审核 / 待付款 / 已付款 / 已完成 / 已取消
- 日期范围：开始日期 + 结束日期
- 关键字搜索：采购单号 / 供应商名模糊搜索
- 重置按钮

**后端** `GET /purchase/orders` 扩展参数：
- `status: Optional[str]`
- `start_date: Optional[str]`
- `end_date: Optional[str]`
- `search: Optional[str]` — 模糊匹配 po_no + supplier.name

### 2.6 出入库日志 — 增加日期和搜索

**修改** `frontend/src/components/business/FinanceLogsPanel.vue`

新增筛选项：
- 日期范围：开始日期 + 结束日期（后端已支持）
- 关键字搜索：商品名 / 仓库名模糊搜索
- 重置按钮

**后端** `GET /finance/stock-logs` 扩展参数：
- `search: Optional[str]` — 模糊匹配 product.name + warehouse.name
- （start_date / end_date 后端已支持，前端未使用）

---

## 3. 筛选 UI 规范

**布局：** 水平排列，`flex flex-wrap gap-2`，自动换行适配移动端

```
[类型 ▾] [状态 ▾] [开始日期] [结束日期] [🔍 搜索...] [↺]
```

**样式：**
- 下拉/输入框：`input input-sm`
- 搜索框宽度：`w-40` (桌面) / `flex-1` (移动端)
- 重置按钮：`btn btn-secondary btn-sm`，内容为 `<RotateCcw :size="14" />`，title="重置筛选"

**行为：**
- 筛选变化时 → `resetPage()` + 重新加载数据
- 搜索框 → 300ms debounce
- 重置按钮 → 清空所有筛选项为默认值 → resetPage() → reload

---

## 4. 后端改动汇总

| 接口 | 新增参数 | 文件 |
|------|---------|------|
| `GET /finance/all-orders` | `payment_status` | `finance.py` |
| `GET /finance/unpaid-orders` | `order_type`, `start_date`, `end_date`, `search` | `finance.py` |
| `GET /finance/payments` | `is_confirmed`, `start_date`, `end_date`, `search` | `finance.py` |
| `GET /finance/stock-logs` | `search` | `finance.py` |
| `GET /purchase/orders` | `status`, `start_date`, `end_date`, `search` | `purchase_orders.py` |

---

## 不做的事

- **筛选状态持久化**：筛选项不保存到 localStorage，切换 tab 后重置
- **虚拟滚动**：已有分页，不需要
- **全局筛选 store**：各模块独立管理筛选状态，不引入 Pinia
