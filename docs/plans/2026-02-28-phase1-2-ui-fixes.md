# 阶段1/2 UI遗漏修复

> **状态：✅ 已完成（2026-02-28）**

**Goal:** 补齐阶段1/2实施时遗漏的6处前端UI + 后端schema改造，确保账套管理、科目编辑、凭证反过账、订单账套选择等功能完整可用。

---

## 修复清单

| # | 修复项 | 涉及文件 | 状态 |
|---|--------|---------|------|
| 1-3 | 账套管理（引导卡片+管理弹窗+创建/编辑） | `AccountingView.vue` | ✅ |
| 4 | 科目编辑（复用modal切换编辑模式） | `ChartOfAccountsPanel.vue` | ✅ |
| 5 | 凭证反过账（列表+弹窗按钮） | `VoucherPanel.vue` | ✅ |
| 6A | 后端schema+router改造 | 6个后端文件 | ✅ |
| 6B | 仓库管理加账套关联 | `SettingsView.vue` | ✅ |
| 6C | 销售订单加账套 | `SalesView.vue` | ✅ |
| 6D | 采购单加账套 | `PurchaseOrdersPanel.vue` | ✅ |

## 验证结果
- 前端 build：0 错误
- 后端测试：25/25 通过
- Docker 重建部署成功

---

## 修改文件清单

### Fix 5: 凭证反过账（VoucherPanel.vue）

- import 增加 `unpostVoucher`
- 列表行：posted 状态增加"反过账"按钮（`text-orange-600`），需 `accounting_post` 权限
- 弹窗 footer：posted 状态增加"反过账"按钮（`btn btn-secondary text-orange-600`）
- 新增 `handleUnpost(v)`：confirm → API → 关闭弹窗 → reload

### Fix 4: 科目编辑（ChartOfAccountsPanel.vue）

- import 增加 `updateChartOfAccount`
- 新增 state：`isEditMode`, `editingAccountId`
- 表格操作列增加"编辑"按钮（所有科目可编辑）
- 复用 modal 切换编辑模式：编码/上级/类别/方向 disabled，名称/辅助核算可编辑
- 新增 `openAddForm()`（重置编辑状态）、`openEditAccount(a)`、`handleEdit()`
- `handleEdit` 只发送 `{ name, aux_customer, aux_supplier }`

### Fix 1-3: 账套管理（AccountingView.vue）

- 完整重写，新增 import：`useAuthStore`, `useAppStore`, `createAccountSet`, `updateAccountSet`, `getAccountSet`
- `isAdmin` computed（`authStore.user?.role === 'admin'`）
- 首次进入引导卡片（无账套时显示，admin 可见创建按钮）
- 账套切换器旁增加"⚙ 管理"链接（admin 可见）
- 账套管理弹窗：双状态（列表态/表单态）
  - 列表态：账套卡片 + 编辑按钮 + 新建按钮
  - 表单态：2列网格（编码/名称/公司/税号/法人/地址/开户行/银行账号）
  - 创建时显示启用年份/月份，编辑时显示启用/停用开关
  - 编辑时编码字段 disabled
- 保存后 reload store，创建成功自动选中新账套

### Fix 6A: 后端改造

**schemas:**
- `warehouse.py`：WarehouseUpdate 增加 `account_set_id: Optional[int] = None`
- `order.py`：OrderCreate 增加 `account_set_id: Optional[int] = None`
- `purchase.py`：PurchaseOrderCreate 增加 `account_set_id: Optional[int] = None`

**routers:**
- `warehouses.py`：
  - import AccountSet
  - list 响应增加 `account_set_id` 和 `account_set_name`（批量查询避免 N+1）
- `orders.py`：
  - create_order 增加 account_set resolve：优先 `data.account_set_id`，其次 `warehouse.account_set_id`
  - Order.create 传入 `account_set_id`
- `purchase_orders.py`：
  - create_purchase_order 增加 account_set resolve：优先 `data.account_set_id`，其次 warehouse 查询
  - PurchaseOrder.create 传入 `account_set_id`

### Fix 6B: 仓库管理加账套关联（SettingsView.vue）

- import 增加 `getAccountSets`
- 新增 state：`accountSets`
- `warehouseForm` 增加 `account_set_id`
- 仓库头部：已关联账套显示蓝色标签
- 仓库编辑弹窗：增加"关联账套"下拉（含"不关联"空选项）
- `editWarehouse` 带入 `account_set_id`
- `saveWarehouse` 发送 `account_set_id`
- onMounted 加载 accountSets

### Fix 6C: 销售订单加账套（SalesView.vue）

- import 增加 `getAccountSets`
- 新增 state：`accountSets`
- `orderConfirm` 增加 `account_set_id`
- 下单确认弹窗：收款方式后增加"财务账套"下拉（`v-if="accountSets.length"`）
- 构建 orderConfirm 时从第一个购物车商品的仓库自动带入 `account_set_id`
- `createOrder` 请求增加 `account_set_id`
- onMounted 加载 accountSets

### Fix 6D: 采购单加账套（PurchaseOrdersPanel.vue）

- import 增加 `getAccountSets`
- 新增 state：`accountSets`
- `poForm` 增加 `account_set_id`
- watch `target_warehouse_id` 变化时自动填充 `account_set_id`
- 新建采购单弹窗：目标仓位后增加"财务账套"下拉（`v-if="accountSets.length"`）
- `openNewPO` 从默认仓库带入 `account_set_id`
- `createPurchaseOrder` 请求增加 `account_set_id`
- onMounted 加载 accountSets
