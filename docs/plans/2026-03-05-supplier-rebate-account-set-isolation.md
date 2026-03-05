# 供应商返利按账套隔离 + 付款凭证含返利分录

> 日期: 2026-03-05 | 状态: 已确认

## 背景

当前供应商返利余额（`rebate_balance`）和在账资金（`credit_balance`）是 Supplier 模型上的全局字段，不区分账套。返利抵扣发生在采购单创建时，但在后续流程（审核/付款/详情）中缺乏可见性，且未生成对应的会计凭证。

## 需求

1. 返利余额和在账资金按账套隔离
2. 充值时选择账套
3. 采购流程中清晰展示返利抵扣信息
4. 付款确认时生成含返利分录的会计凭证
5. 返利抵扣时机不变，保持在建单时

## 设计

### 一、数据模型变更

#### 新增模型 `SupplierAccountBalance`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | IntField PK | |
| supplier_id | FK -> Supplier | RESTRICT |
| account_set_id | FK -> AccountSet | RESTRICT |
| rebate_balance | Decimal(12,2) default 0 | 返利余额 |
| credit_balance | Decimal(12,2) default 0 | 在账资金余额 |

- UNIQUE: (`supplier_id`, `account_set_id`)
- 表名: `supplier_account_balances`

#### RebateLog 增加字段

- `account_set_id`: FK -> AccountSet, nullable（兼容历史数据）

#### Supplier 模型

- `rebate_balance` / `credit_balance` 保留但废弃，数据迁移后不再使用

### 二、后端变更

#### 2.1 返利路由 (`rebates.py`)

- `GET /summary` — 增加必填参数 `account_set_id`，从 `SupplierAccountBalance` 读余额
- `POST /charge` — 增加必填参数 `account_set_id`，充值到 `SupplierAccountBalance`
- `GET /logs` — 增加可选参数 `account_set_id` 过滤

#### 2.2 采购单创建 (`purchase_orders.py` -> `create_purchase_order`)

- 返利/在账资金扣减改为操作 `SupplierAccountBalance`（按 PO 的 `account_set_id`）
- `RebateLog` 写入 `account_set_id`
- 若采购单无 `account_set_id` 且使用了返利/在账资金，报错拒绝

#### 2.3 采购单取消 (`cancel_purchase_order`)

- 返利/在账资金退还改为操作 `SupplierAccountBalance`

#### 2.4 采购退货 (`return_purchase_order`)

- 在账资金增加改为操作 `SupplierAccountBalance`

#### 2.5 付款确认 (`confirm_purchase_payment`) — 核心新增

当 `po.rebate_used > 0` 时，生成含返利分录的会计凭证：

```
借：应付账款                  total_amount（应付全额，即已扣返利后的金额 + 返利）
借：主营业务成本-采购返利      -(rebate_used / 1.13)（负数红冲）
借：结转进项税金              -(rebate_used - rebate_used / 1.13)（负数红冲）
  贷：银行存款                total_amount - rebate_used + credit_used 视情况（实付）
```

注意：
- `total_amount` 是已扣除返利后的金额，凭证中应付账款应为 `total_amount + rebate_used`（原价）
- 不对，当前 `total_amount` 存的已经是扣除返利后的金额
- 所以凭证为：
  - 借 应付账款 = total_amount + rebate_used（原始应付）
  - 借 主营业务成本-采购返利 = -(rebate_used / 1.13)
  - 借 结转进项税金 = -(rebate_used - rebate_used / 1.13)
  - 贷 银行存款 = total_amount（实付金额）

验证借贷平衡：
- 借方合计 = (total_amount + rebate_used) + (-(rebate_used / 1.13)) + (-(rebate_used - rebate_used / 1.13))
- = total_amount + rebate_used - rebate_used/1.13 - rebate_used + rebate_used/1.13
- = total_amount
- 贷方合计 = total_amount
- 平衡

税率固定 13%（即除以 1.13）。

若同时有 `credit_used > 0`（在账资金抵扣），实付调整为 `total_amount - credit_used`，在账资金部分另做分录或合并处理（待确认）。

### 三、前端变更

#### 3.1 FinanceRebatesPanel.vue

- 顶部增加账套选择器
- 汇总列表按选中账套筛选
- 充值弹窗传入当前账套
- 返利明细显示账套信息

#### 3.2 PurchaseOrderForm.vue

- 返利/在账资金可用余额改为读取对应账套下的 `SupplierAccountBalance`
- 需要新 API 端点或修改现有端点返回按账套的余额

#### 3.3 PurchaseOrderDetail.vue

- 金额区域展示：原价合计 / 返利抵扣 / 在账资金抵扣 / 实付金额

### 四、数据迁移

- 创建 `supplier_account_balances` 表
- 迁移脚本：将现有 `Supplier.rebate_balance` / `credit_balance` 非零值迁移到指定账套（需运行时确认目标账套 ID）
- `RebateLog` 增加 `account_set_id` 列（ALTER TABLE ADD COLUMN，nullable）
- 历史 RebateLog 的 `account_set_id` 留空

### 五、影响范围

#### 后端文件
- `app/models/supplier.py` — 废弃字段标注
- `app/models/rebate.py` — RebateLog 增加 account_set_id
- 新增 `app/models/supplier_balance.py` — SupplierAccountBalance
- `app/routers/rebates.py` — 全部端点改造
- `app/routers/purchase_orders.py` — 创建/取消/退货/付款
- `app/services/ap_service.py` — 付款凭证生成逻辑
- `app/schemas/rebate.py` — 增加 account_set_id
- `app/schemas/purchase.py` — 可能需要调整
- `app/migrations.py` — 新表 + 新列迁移

#### 前端文件
- `FinanceRebatesPanel.vue` — 账套选择器
- `PurchaseOrderForm.vue` — 余额读取改造
- `PurchaseOrderDetail.vue` — 展示优化
- `api/rebates.js` — 增加 account_set_id 参数
