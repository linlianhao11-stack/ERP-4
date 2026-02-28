# 业财一体化财务会计模块 — 设计与实施计划

> 基于方案B（5部分系列报告）+ 业务确认结果
> 创建日期：2026-02-28
> 状态：待实施

---

## 一、核心架构决策

| 决策点 | 选择 | 说明 |
|--------|------|------|
| 多账套隔离 | 业务层共享，财务层隔离 | 所有人看到两家公司的订单/库存；财务按账套完全独立 |
| 公司归属 | 仓库默认公司 + 订单可手动修改 | Warehouse 绑定默认 account_set_id，Order 自动填充但允许改 |
| 客户/供应商 | 全局共享 | 同一客户可与两家公司交易，应收/应付按账套分开记账 |
| 余额架构 | 双层并行 | Customer.balance 保持业务层余额不变；应收单体系独立记录财务层应收（按账套隔离） |
| 现有模型 | 改造扩展 | 在现有 Voucher/Payment 上加字段，不另建平行模型 |
| 旧凭证自动生成 | 废弃 | 移除现有简单凭证自动生成逻辑，改由新财务体系的"期末批量生成凭证"替代 |
| 应收单时机 | 发货时自动生成 | CASH/CREDIT/CONSIGN_SETTLE/RETURN 发货时均生成应收单（CASH 为已收款状态） |
| 应付单时机 | 收货时 + 付款时 | 采购收货生成应付单（入库单），付款确认生成付款单 |
| 税率 | 产品级别设置 | Product 新增 tax_rate 字段（默认13%），发票明细自动带入可修改 |
| 凭证字 | 记/收/付/转 四种 | 各自独立编号序列 |
| 科目体系 | 预置标准 + 允许自定义 | 创建账套时自动生成贸易企业标准科目，允许增删子科目 |
| 会计年度 | 自然年，起始月份可配置 | 创建账套时选择起始年月 |
| 凭证审核 | 制单人≠审核人（可配置关闭） | 默认严格，系统设置中可关闭此限制（小团队模式） |
| 前端入口 | 新建独立页面 AccountingView | 与现有 FinanceView 并列，现有页面保持业务操作不变 |
| 权限 | 细分 5 个新权限 | accounting_view / accounting_edit / accounting_approve / accounting_post / period_end |
| PDF套打 | 第四阶段必做 | 凭证/出库单/入库单，24×14cm，reportlab + 中文字体 |

---

## 二、订单类型与财务单据对应关系

### 销售侧（应收）

| 订单类型 | 触发时机 | 生成应收单 | 生成出库单 | 说明 |
|----------|----------|------------|------------|------|
| CASH（现款） | 发货时 | 是（已收款状态） | 是 | 应收单用于推送开票，与退货红字抵扣后=实际开票金额 |
| CREDIT（账期） | 发货时 | 是（待收款状态） | 是 | 标准应收流程 |
| CONSIGN_OUT（寄售调拨） | — | 否 | 否 | 仅移库，非收入确认事件 |
| CONSIGN_SETTLE（寄售结算） | 结算时 | 是 | 是 | 寄售货物实际卖出，确认收入 |
| CONSIGN_RETURN（寄售退货） | — | 否 | 否 | 货物退回，无收入事件 |
| RETURN（销售退货） | 退货时 | 是（红字/负数） | 是（红字） | 冲减应收和成本 |

### 采购侧（应付）

| 采购事件 | 触发时机 | 生成应付单 | 生成入库单 | 生成付款单 |
|----------|----------|------------|------------|------------|
| 采购收货 | 收货确认时 | 是 | 是 | — |
| 采购付款 | 付款确认时 | — | — | 是 |
| 采购退货 | 退货时 | 是（红字/负数） | 是（红字） | 付款退款单 |

---

## 三、数据模型设计

### 3.1 新增模型（15张表）

#### AccountSet（账套）— `account_sets`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| code | varchar(20) UNIQUE | 账套编码（如 QL / LC） |
| name | varchar(100) | 账套名称（如 启领 / 链筹） |
| company_name | varchar(200) | 公司全称 |
| tax_id | varchar(30) | 税号 |
| legal_person | varchar(50) | 法人 |
| address | text | 公司地址 |
| bank_name | varchar(100) | 开户行 |
| bank_account | varchar(50) | 银行账号 |
| start_year | int | 启用年度 |
| start_month | int | 启用月份 |
| current_period | varchar(7) | 当前会计期间（如 2026-03） |
| is_active | bool | 是否启用 |
| created_at | datetime | |

#### ChartOfAccount（会计科目）— `chart_of_accounts`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| account_set_id | int FK | 所属账套 |
| code | varchar(20) | 科目编码（如 1001, 100101） |
| name | varchar(100) | 科目名称（如 库存现金） |
| parent_code | varchar(20) null | 上级科目编码 |
| level | int | 科目级次（1-4） |
| category | varchar(20) | 类别：asset/liability/equity/cost/profit_loss |
| direction | varchar(6) | 余额方向：debit/credit |
| is_leaf | bool | 是否末级科目（只有末级可录凭证） |
| is_active | bool | |
| aux_customer | bool default false | 辅助核算-客户 |
| aux_supplier | bool default false | 辅助核算-供应商 |
| created_at | datetime | |
| UNIQUE | (account_set_id, code) | |

#### AccountingPeriod（会计期间）— `accounting_periods`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| account_set_id | int FK | 所属账套 |
| period_name | varchar(7) | 期间名（如 2026-03） |
| year | int | 年度 |
| month | int | 月份 |
| is_closed | bool default false | 是否已结账 |
| closed_at | datetime null | |
| closed_by_id | int FK null | |
| UNIQUE | (account_set_id, period_name) | |

#### ReceivableBill（应收单）— `receivable_bills`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| bill_no | varchar(30) UNIQUE | 单据编号 |
| account_set_id | int FK | 所属账套 |
| customer_id | int FK | 客户 |
| order_id | int FK | 关联销售订单 |
| bill_date | date | 单据日期 |
| total_amount | decimal(18,2) | 应收金额（退货时为负数） |
| received_amount | decimal(18,2) default 0 | 已收金额 |
| unreceived_amount | decimal(18,2) | 未收金额 |
| status | varchar(20) | pending/partial/completed/cancelled |
| voucher_id | int FK null | 关联凭证 |
| voucher_no | varchar(30) null | 凭证号 |
| remark | text | |
| creator_id | int FK | |
| created_at | datetime | |
| updated_at | datetime | |

#### ReceiptBill（收款单）— `receipt_bills`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| bill_no | varchar(30) UNIQUE | |
| account_set_id | int FK | |
| customer_id | int FK | |
| receivable_bill_id | int FK null | 关联应收单 |
| receipt_date | date | 收款日期 |
| amount | decimal(18,2) | 收款金额 |
| payment_method | varchar(50) | 收款方式 |
| is_advance | bool default false | 是否预收款 |
| status | varchar(20) | draft/confirmed |
| confirmed_by_id | int FK null | |
| confirmed_at | datetime null | |
| voucher_id | int FK null | |
| voucher_no | varchar(30) null | |
| remark | text | |
| creator_id | int FK | |
| created_at | datetime | |

#### ReceiptRefundBill（收款退款单）— `receipt_refund_bills`

类似 ReceiptBill，增加：original_receipt_id（关联原收款单）、refund_date、reason

#### ReceivableWriteOff（应收核销单）— `receivable_write_offs`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| bill_no | varchar(30) UNIQUE | |
| account_set_id | int FK | |
| customer_id | int FK | |
| advance_receipt_id | int FK | 关联预收款收款单 |
| receivable_bill_id | int FK | 关联应收单 |
| write_off_date | date | |
| amount | decimal(18,2) | 核销金额 |
| status | varchar(20) | draft/confirmed |
| voucher_id / voucher_no | | 凭证关联 |
| creator_id | int FK | |
| created_at | datetime | |

#### PayableBill（应付单）— `payable_bills`

类似 ReceivableBill，改为：supplier_id、purchase_order_id、paid_amount、unpaid_amount

#### DisbursementBill（付款单）— `disbursement_bills`

类似 ReceiptBill，改为：supplier_id、payable_bill_id、disbursement_method

#### DisbursementRefundBill（付款退款单）— `disbursement_refund_bills`

类似 ReceiptRefundBill，改为 supplier 相关字段

#### Invoice（发票）— `invoices`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| invoice_no | varchar(30) UNIQUE | 发票号码 |
| account_set_id | int FK | |
| invoice_type | varchar(20) | special(专票) / normal(普票) |
| direction | varchar(10) | output(销项) / input(进项) |
| customer_id | int FK null | 客户（销项发票） |
| supplier_id | int FK null | 供应商（进项发票） |
| receivable_bill_id | int FK null | 关联应收单 |
| payable_bill_id | int FK null | 关联应付单 |
| invoice_date | date | |
| amount_without_tax | decimal(18,2) | 不含税金额 |
| tax_amount | decimal(18,2) | 税额 |
| total_amount | decimal(18,2) | 价税合计 |
| tax_rate | decimal(5,2) | 税率 |
| status | varchar(20) | draft/issued/reviewed/cancelled |
| reviewed_by_id | int FK null | 审单人 |
| reviewed_at | datetime null | |
| voucher_id | int FK null | |
| voucher_no | varchar(30) null | |
| creator_id | int FK | |
| created_at | datetime | |

#### InvoiceItem（发票明细）— `invoice_items`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| invoice_id | int FK | |
| product_id | int FK null | |
| item_name | varchar(200) | 品名 |
| specification | varchar(100) | 规格型号 |
| unit | varchar(20) | 单位 |
| quantity | decimal(10,2) | |
| unit_price | decimal(18,2) | 单价（不含税） |
| amount | decimal(18,2) | 金额（不含税） |
| tax_rate | decimal(5,2) | |
| tax_amount | decimal(18,2) | |

#### SalesDeliveryBill（销售出库单）— `sales_delivery_bills`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| bill_no | varchar(30) UNIQUE | |
| account_set_id | int FK | |
| order_id | int FK | 关联销售订单 |
| customer_id | int FK | |
| warehouse_id | int FK | 出库仓库 |
| delivery_date | date | 出库日期 |
| total_cost_amount | decimal(18,2) | 成本合计（用于生成凭证） |
| total_sale_amount | decimal(18,2) | 销售合计 |
| status | varchar(20) | draft/confirmed |
| voucher_id / voucher_no | | |
| creator_id | int FK | |
| created_at | datetime | |

#### SalesDeliveryItem — `sales_delivery_items`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| delivery_bill_id | int FK | |
| order_item_id | int FK | 关联订单明细 |
| product_id | int FK | |
| quantity | decimal(10,2) | 出库数量 |
| cost_price | decimal(18,2) | 成本单价（加权平均） |
| cost_amount | decimal(18,2) | 成本金额 |
| sale_price | decimal(18,2) | 销售单价 |
| sale_amount | decimal(18,2) | 销售金额 |

#### PurchaseReceiptBill / PurchaseReceiptItem（采购入库单）

类似销售出库单，改为 supplier_id、purchase_order_id，增加 tax_amount（税额）

### 3.2 改造现有模型

#### Product — 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| tax_rate | decimal(5,2) default 13.00 | 默认税率 |

#### Warehouse — 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| account_set_id | int FK null | 默认归属账套（虚拟仓可为空） |

#### Order — 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| account_set_id | int FK null | 归属账套（从仓库自动填充，可手动修改） |

#### PurchaseOrder — 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| account_set_id | int FK null | 归属账套 |

#### Voucher — 新增/改造字段

| 字段 | 类型 | 说明 |
|------|------|------|
| account_set_id | int FK | 所属账套 |
| period_name | varchar(7) | 会计期间 |
| status | varchar(20) default 'draft' | draft/pending/approved/posted |
| approved_by_id | int FK null | 审核人 |
| approved_at | datetime null | |
| posted_by_id | int FK null | 过账人 |
| posted_at | datetime null | |

#### VoucherEntry — 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| account_id | int FK | 关联会计科目 ChartOfAccount |
| aux_customer_id | int FK null | 辅助核算-客户 |
| aux_supplier_id | int FK null | 辅助核算-供应商 |

#### Payment — 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| account_set_id | int FK null | 归属账套 |

---

## 四、凭证生成规则（期末批量）

### 销售相关凭证

| 来源单据 | 凭证字 | 借方 | 贷方 |
|----------|--------|------|------|
| 销售出库单 | 记 | 主营业务成本 6401（成本金额） | 库存商品 1405（成本金额） |
| 收款单 | 收 | 银行存款 1002（收款金额） | 应收账款 1122（收款金额） |
| 收款退款单 | 收 | 应收账款 1122 | 银行存款 1002 |
| 应收核销单 | 记 | 预收账款 2203 | 应收账款 1122 |

### 采购相关凭证

| 来源单据 | 凭证字 | 借方 | 贷方 |
|----------|--------|------|------|
| 采购入库单 | 记 | 库存商品 1405（不含税）+ 应交税费-进项 2221（税额） | 应付账款 2202（价税合计） |
| 付款单 | 付 | 应付账款 2202 | 银行存款 1002 |
| 付款退款单 | 付 | 银行存款 1002 | 应付账款 2202 |

### 发票凭证

| 来源单据 | 凭证字 | 借方 | 贷方 |
|----------|--------|------|------|
| 销项专票 | 记 | 应收账款 1122（价税合计） | 主营业务收入 6001（不含税）+ 应交税费-销项 2221（税额） |
| 销项普票 | 记 | 应收账款 1122（含税） | 主营业务收入 6001（含税，全额计入收入） |
| 进项专票 | 记 | 库存商品 1405（不含税）+ 应交税费-进项 2221（税额） | 应付账款 2202（价税合计） |

### 期末结转凭证

| 操作 | 凭证字 | 规则 |
|------|--------|------|
| 结转损益 | 转 | 收入类科目（贷方余额）：借 收入科目 / 贷 本年利润 4103；费用类科目（借方余额）：借 本年利润 / 贷 费用科目 |

---

## 五、预置会计科目表（贸易企业最小集）

### 资产类（1xxx）
- 1001 库存现金
- 1002 银行存款
- 1122 应收账款（辅助：客户）
- 1123 预付账款（辅助：供应商）
- 1221 其他应收款
- 1403 原材料
- 1405 库存商品
- 1601 固定资产
- 1602 累计折旧

### 负债类（2xxx）
- 2001 短期借款
- 2202 应付账款（辅助：供应商）
- 2203 预收账款（辅助：客户）
- 2211 应付职工薪酬
- 2221 应交税费
  - 222101 应交增值税-进项税额
  - 222102 应交增值税-销项税额
- 2241 其他应付款

### 所有者权益类（3xxx / 4xxx）
- 4001 实收资本
- 4101 盈余公积
- 4103 本年利润
- 4104 利润分配-未分配利润

### 成本类（5xxx）
（贸易企业一般不用，暂不预置）

### 损益类（6xxx）
- 6001 主营业务收入
- 6051 其他业务收入
- 6301 营业外收入
- 6401 主营业务成本
- 6402 其他业务成本
- 6403 税金及附加
- 6601 销售费用
- 6602 管理费用
- 6603 财务费用
- 6711 营业外支出
- 6801 所得税费用

---

## 六、新增权限

| 权限标识 | 说明 |
|---------|------|
| accounting_view | 查看凭证、账簿、报表 |
| accounting_edit | 录入/编辑凭证 |
| accounting_approve | 审核凭证 |
| accounting_post | 过账 |
| period_end | 期末处理（结转损益、锁账） |

admin 角色自动拥有全部权限。

---

## 七、五阶段实施计划

### 阶段 1：基础设施（科目体系 + 多账套 + 会计期间 + 凭证改造）

**目标**：搭建财务会计的基础骨架，所有后续功能都依赖此阶段。

**后端任务**：
1. 新建模型：AccountSet、ChartOfAccount、AccountingPeriod
2. 新建 migrations：DDL + 预置标准科目表数据
3. 改造 Voucher 模型：新增 account_set_id、period_name、status 流转、审核/过账字段
4. 改造 VoucherEntry：新增 account_id、辅助核算字段
5. Warehouse/Order/PurchaseOrder/Payment 新增 account_set_id 字段（DDL migration）
6. Product 新增 tax_rate 字段
7. 新建 router：account_sets.py（CRUD）、accounting.py（科目管理、会计期间）
8. 改造 vouchers.py：凭证 CRUD + 状态流转（draft→pending→approved→posted）+ 审核规则（可配置的制单人≠审核人）
9. 新增权限：accounting_view / accounting_edit / accounting_approve / accounting_post / period_end
10. 废弃现有自动凭证生成逻辑

**前端任务**：
1. 新建 AccountingView.vue 页面 + 路由注册
2. 全局账套切换器组件（Header 或 Sidebar）
3. 科目管理面板（树形展示 + 增删子科目）
4. 会计期间管理面板
5. 凭证管理面板（列表 + 录入/编辑 + 审核/过账流程）
6. 凭证录入表单：科目搜索选择、借贷金额、自动平衡提示、辅助核算
7. stores/accounting.js：账套状态、当前期间
8. api/accounting.js：API 调用封装
9. 订单创建页面：增加账套选择（从仓库自动带入）

**核验方法**：
- [ ] 创建"启领"和"链筹"两个账套，切换后科目和凭证互不可见
- [ ] 录入凭证，借贷不平衡时无法保存
- [ ] 完成 draft→pending→approved→posted 全流程
- [ ] 已过账凭证不可编辑
- [ ] 审核人≠制单人（开启时）

**完成状态**：✅ 已完成（2026-02-28）

---

### 阶段 2：账簿查询（总分类账 + 明细分类账 + 科目余额表）

**目标**：基于已过账凭证提供专业的财务查询视图。

**后端任务**：
1. accounting.py 新增 API：
   - GET /api/accounting/general-ledger — 总分类账（期初余额 + 逐笔分录 + 期末余额）
   - GET /api/accounting/detail-ledger — 明细分类账（支持辅助核算筛选）
   - GET /api/accounting/trial-balance — 科目余额表（试算平衡验证）
2. 各 API 支持导出 Excel（pandas + openpyxl）

**前端任务**：
1. 新建 LedgerPanel.vue（三个子 Tab）
2. 总分类账：期间选择、科目选择、传统账簿格式表格、凭证号可点击跳转
3. 明细分类账：辅助核算筛选（客户/供应商）
4. 科目余额表：科目编码层级缩进、合计行、试算平衡指示器
5. 各表支持导出 Excel

**核验方法**：
- [ ] 录入并过账若干凭证后，总分类账期初+本期发生=期末
- [ ] 科目余额表试算平衡（借方合计=贷方合计）
- [ ] 明细账辅助核算筛选正确
- [ ] Excel 导出正常

**完成状态**：✅ 已完成（2026-02-28）

**实施计划**：`docs/plans/2026-02-28-phase2-ledger-queries.md`

---

### 阶段 3：应收应付管理

**目标**：建立完整的 AR/AP 体系，与现有业务流程自动衔接。

**后端任务**：
1. 新建模型：ReceivableBill、ReceiptBill、ReceiptRefundBill、ReceivableWriteOff
2. 新建模型：PayableBill、DisbursementBill、DisbursementRefundBill
3. 新建 router：receivable.py
   - 应收单：自动生成（发货触发）、列表、详情
   - 收款单：创建、出纳确认、列表
   - 退款单：创建、确认、列表
   - 核销单：创建（预收冲应收）、确认、列表
   - 期末凭证批量生成
4. 新建 router：payable.py
   - 应付单：自动生成（收货触发）、列表、详情
   - 付款单：创建（付款触发）、确认、列表
   - 退款单：创建、确认、列表
   - 期末凭证批量生成
5. 修改 logistics.py（发货流程）：发货确认后自动创建应收单 + 出库单（事务内）
6. 修改 purchase_orders.py：收货确认后自动创建应付单 + 入库单；付款确认后创建付款单
7. 修改 orders.py：退货时自动创建红字应收单

**前端任务**：
1. 新建 ReceivablePanel.vue（四个子 Tab：应收单/收款单/退款单/核销单）
2. 新建 PayablePanel.vue（三个子 Tab：应付单/付款单/退款单）
3. 各列表：筛选栏（账套/客户或供应商/状态/日期范围）、表格、凭证号列
4. 操作按钮：确认收款/付款、生成凭证等
5. 在 AccountingView 中注册新面板

**核验方法**：
- [ ] 创建 CREDIT 订单 → 发货 → 自动生成应收单
- [ ] 创建 CASH 订单 → 发货 → 自动生成已收款状态的应收单 + 收款单
- [ ] 退货 → 自动生成红字应收单
- [ ] 出纳确认收款 → 应收单状态更新
- [ ] 采购收货 → 自动生成应付单 + 入库单
- [ ] 采购付款 → 自动生成付款单
- [ ] 采购退货 → 红字应付单 + 付款退款单
- [ ] 期末批量生成凭证成功

**完成状态**：未开始

---

### 阶段 4：发票管理与供应链联动 + PDF 套打

**目标**：完成发票管理、出库/入库单体系、PDF 打印功能。

**后端任务**：
1. 新建模型：Invoice、InvoiceItem、SalesDeliveryBill、SalesDeliveryItem、PurchaseReceiptBill、PurchaseReceiptItem
2. 新建 router：invoices.py
   - 从应收单推送生成销项发票（自动带入产品税率）
   - 手工录入进项发票
   - 开票、审单、作废
   - 期末凭证生成（专票/普票不同分录规则）
3. 新建 router：sales_delivery.py
   - 从销售订单生成出库单（发货时自动，与应收单同步创建）
   - 出库凭证：成本金额（非销售金额）
4. 新建 router：purchase_receipt.py
   - 从采购订单生成入库单（收货时自动）
   - 入库凭证：含税拆分
5. requirements.txt 追加 reportlab
6. 新建 utils/pdf_print.py：
   - 凭证套打（24×14cm）
   - 销售出库单套打（24×14cm）
   - 采购入库单套打（24×14cm）
7. Dockerfile：安装中文字体包（fonts-wqy-zenhei）
8. 批量打印 API（返回合并 PDF）

**前端任务**：
1. 新建 InvoicePanel.vue（子 Tab：专票/普票）
2. 新建 SalesDeliveryPanel.vue（出库单列表 + 打印）
3. 新建 PurchaseReceiptPanel.vue（入库单列表 + 打印）
4. 各列表增加"打印"和"批量打印"按钮
5. 凭证列表增加"批量打印"按钮

**核验方法**：
- [ ] 从应收单推送生成发票，税率从产品带入
- [ ] 发票凭证生成正确（专票含税分拆、普票全额收入）
- [ ] 出库凭证金额=成本金额（非销售额）
- [ ] 入库凭证三条分录正确
- [ ] PDF 打印正常，中文显示正确，尺寸 24×14cm
- [ ] 批量选择 3 张凭证打印，得到合并 PDF

**完成状态**：未开始

---

### 阶段 5：期末处理与财务报表

**目标**：实现完整的期末处理流程和标准财务报表。

**后端任务**：
1. 新建 service：period_end_service.py
   - carry_forward_profit_loss()：结转损益（损益科目→本年利润）
   - close_period()：期末结账（含 5 项前置检查）
   - reopen_period()：反结账（admin 权限）
2. 新建 router API：
   - POST /api/accounting/carry-forward-preview — 预览结转
   - POST /api/accounting/carry-forward — 执行结转
   - POST /api/accounting/period-close-check — 结账检查
   - POST /api/accounting/period-close — 结账
   - POST /api/accounting/period-reopen — 反结账
3. 财务报表 API：
   - GET /api/accounting/balance-sheet — 资产负债表
   - GET /api/accounting/income-statement — 利润表
4. 报表模板初始化（标准中国企业会计准则简化版）
5. 报表导出 Excel
6. 凭证创建 API 增加期间检查（已结账期间禁止操作）

**前端任务**：
1. 新建 PeriodEndPanel.vue
   - 当前期间状态显示
   - 结转损益：预览按钮（显示科目和金额）+ 执行按钮
   - 期末结账：5 项检查清单 + 执行按钮 + 确认弹窗
   - 反结账（admin）
   - 会计期间历史列表
2. 新建 FinancialReportPanel.vue
   - 资产负债表：左右两栏（资产 / 负债+权益），期末余额+年初余额
   - 利润表：单栏，本期金额+本年累计
   - 恒等式验证显示
   - 导出 Excel + 打印

**核验方法**：
- [ ] 结转损益后，所有损益类科目余额为零
- [ ] 本年利润科目余额 = 收入合计 - 费用合计
- [ ] 科目余额表试算平衡
- [ ] 资产负债表：资产合计 = 负债合计 + 权益合计（误差<0.01元）
- [ ] 利润表：净利润 = 本年利润科目余额
- [ ] 结账后凭证不可操作
- [ ] 反结账后恢复可操作

**完成状态**：未开始

---

## 八、阶段依赖关系

```
阶段1（基础设施）
  ├── 阶段2（账簿查询）—— 依赖凭证过账数据
  ├── 阶段3（应收应付）—— 依赖账套和科目体系
  │     └── 阶段4（发票+供应链+PDF）—— 依赖应收应付单据
  └── 阶段5（期末+报表）—— 依赖凭证+账簿+科目
```

阶段 2 和阶段 3 可以并行开发（互不依赖），阶段 4 依赖阶段 3，阶段 5 依赖阶段 1+2。

---

## 九、技术要点

1. **金额精度**：所有金额字段使用 Decimal(18,2)，Python 侧使用 decimal.Decimal，前端使用 Math.round(x * 100) / 100
2. **并发安全**：余额变更使用 select_for_update(nowait=True)，状态变更在事务内完成
3. **事务一致性**：发货/收货触发的业务操作和财务单据创建必须在同一事务内
4. **审核分离**：制单人≠审核人（可通过 SystemSetting 配置关闭）
5. **期间锁定**：已结账期间禁止新增/编辑/删除凭证，凭证 API 需检查期间状态
6. **多账套查询**：所有财务 API 必须接收 account_set_id 参数，严格过滤
7. **PDF 中文字体**：Docker 镜像需安装 fonts-wqy-zenhei，reportlab 注册字体
