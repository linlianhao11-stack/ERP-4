# 阶段4：发票 + 出入库单 + PDF套打 — 设计文档

> 状态：设计完成，待实施
> 日期：2026-02-28
> 依赖：阶段3（应收应付）✅ 已完成

## 概述

建立发票管理体系（销项/进项）和出入库单据体系（销售出库单/采购入库单），实现与现有业务流程的自动衔接（发货→出库单、收货→入库单、应收单→发票推送），并提供 PDF 套打功能（记账凭证、出库单、入库单，24×14cm）。

## 关键设计决策

| 决策 | 选择 | 说明 |
|------|------|------|
| 发票生成方式 | 手动从应收单推送 | 用户选择应收单→点击生成发票→税率从产品带入可修改→确认 |
| 进项发票 | 手工录入 | 收到供应商发票后手动创建，关联应付单 |
| 凭证拆税 | 专票/普票统一拆税 | 不含税收入 + 税额，不区分专票普票 |
| 出库单/入库单 | 正式财务单据 | 独立编号、可打印PDF、自动生成凭证 |
| 出入库生成时机 | 发货/收货时自动 | 嵌入现有 logistics.py / purchase_orders.py 钩子 |
| 出库单凭证 | 创建时自动生成 | 借 发出商品 / 贷 库存商品 |
| 入库单凭证 | 创建时自动生成 | 借 库存商品 + 借 进项税 / 贷 应付账款 |
| 发票凭证 | 确认时生成 | 复合凭证：收入确认 + 成本结转 |
| 进项发票凭证 | 不生成 | 仅作税务管理记录，入库单已记录进项税 |
| PDF套打范围 | 3种 | 记账凭证 + 销售出库单 + 采购入库单（发票不打印，实际开票在税务系统） |
| PDF尺寸 | 24×14cm | reportlab + 中文字体（fonts-wqy-zenhei） |
| 模型方案 | 6个新模型（方案A） | Invoice/InvoiceItem + SalesDeliveryBill/Item + PurchaseReceiptBill/Item |

## 凭证生成规则

### 出库单凭证（发货时自动生成）

```
借：发出商品     1407    （成本合计 = Σ quantity × cost_price）
贷：库存商品     1405    （同上金额）
```

### 入库单凭证（收货时自动生成）

```
借：库存商品         1405    （不含税合计）
借：应交税费-进项税   222101  （税额合计）
贷：应付账款         2202    （含税合计，辅助：供应商）
```

### 销项发票凭证（确认时生成，复合凭证5条分录）

```
借：应收账款         1122    （价税合计，辅助：客户）
贷：主营业务收入     6001    （不含税合计）
贷：应交税费-销项税   222102  （税额合计）
借：主营业务成本     6401    （成本合计，从关联出库单获取）
贷：发出商品         1407    （同上金额）
```

### 进项发票

不生成凭证。入库单凭证已记录进项税和应付账款，进项发票仅作为税务管理记录。

### 已有凭证（不变）

- 收款单 → 期末批量：借 银行存款1002 / 贷 应收账款1122
- 付款单 → 期末批量：借 应付账款2202 / 贷 银行存款1002

## 业务流程

### 销售侧完整流程

```
销售订单 → 发货完成 → [自动] 应收单 + 出库单（+凭证）
                         ↓
                   用户从应收单推送 → 发票（草稿）→ 确认（+凭证）
                         ↓
                   收款 → 收款单 → 期末生成凭证
```

### 采购侧完整流程

```
采购订单 → 收货 → [自动] 应付单 + 入库单（+凭证）
                     ↓
              用户手工录入 → 进项发票（仅税务记录，无凭证）
                     ↓
              付款 → 付款单 → 期末生成凭证
```

## 数据模型（6个新模型）

### Invoice（发票主表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | IntField PK | — |
| invoice_no | CharField(30) unique | 编号前缀 XS/JX |
| invoice_type | CharField(20) | special（专票）/ normal（普票） |
| direction | CharField(10) | output（销项）/ input（进项） |
| account_set_id | FK→AccountSet | 账套隔离 |
| customer_id | FK→Customer null | 销项发票关联 |
| supplier_id | FK→Supplier null | 进项发票关联 |
| receivable_bill_id | FK→ReceivableBill null | 销项关联应收单 |
| payable_bill_id | FK→PayableBill null | 进项关联应付单 |
| invoice_date | DateField | 开票日期 |
| total_amount | Decimal(18,2) | 价税合计 |
| amount_without_tax | Decimal(18,2) | 不含税金额 |
| tax_amount | Decimal(18,2) | 税额合计 |
| status | CharField(20) | draft / confirmed / cancelled |
| voucher_id | FK→Voucher null | 关联凭证（仅销项） |
| remark | TextField | — |
| creator_id | FK→User null | — |
| created_at | DatetimeField | — |
| updated_at | DatetimeField | — |

索引：(account_set_id, direction), (account_set_id, status)

### InvoiceItem（发票明细行）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | IntField PK | — |
| invoice_id | FK→Invoice | 所属发票 |
| product_id | FK→Product null | 商品 |
| product_name | CharField(200) | 商品名称快照 |
| quantity | IntField | 数量 |
| unit_price | Decimal(18,2) | 不含税单价 |
| tax_rate | Decimal(5,2) | 税率（如 13.00） |
| tax_amount | Decimal(18,2) | 该行税额 |
| amount_without_tax | Decimal(18,2) | 该行不含税金额 |
| amount | Decimal(18,2) | 该行价税合计 |

### SalesDeliveryBill（销售出库单）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | IntField PK | — |
| bill_no | CharField(30) unique | 编号前缀 CK |
| account_set_id | FK→AccountSet | — |
| customer_id | FK→Customer | — |
| order_id | FK→Order null | 关联销售单 |
| warehouse_id | FK→Warehouse null | 出库仓库 |
| bill_date | DateField | 出库日期 |
| total_cost | Decimal(18,2) | 成本合计（凭证用） |
| total_amount | Decimal(18,2) | 销售金额合计 |
| status | CharField(20) | confirmed（自动生成即确认） |
| voucher_id | FK→Voucher null | 自动生成的凭证 |
| remark | TextField | — |
| creator_id | FK→User null | — |
| created_at | DatetimeField | — |

索引：(account_set_id, customer_id)

### SalesDeliveryItem（出库单明细）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | IntField PK | — |
| delivery_bill_id | FK→SalesDeliveryBill | — |
| order_item_id | FK→OrderItem null | 追溯源数据 |
| product_id | FK→Product | — |
| product_name | CharField(200) | 快照 |
| quantity | IntField | 数量 |
| cost_price | Decimal(18,2) | 成本单价（OrderItem.cost_price） |
| sale_price | Decimal(18,2) | 销售单价 |

### PurchaseReceiptBill（采购入库单）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | IntField PK | — |
| bill_no | CharField(30) unique | 编号前缀 RK |
| account_set_id | FK→AccountSet | — |
| supplier_id | FK→Supplier | — |
| purchase_order_id | FK→PurchaseOrder null | — |
| warehouse_id | FK→Warehouse null | 入库仓库 |
| bill_date | DateField | 入库日期 |
| total_amount | Decimal(18,2) | 含税合计 |
| total_amount_without_tax | Decimal(18,2) | 不含税合计 |
| total_tax | Decimal(18,2) | 税额合计 |
| status | CharField(20) | confirmed |
| voucher_id | FK→Voucher null | — |
| remark | TextField | — |
| creator_id | FK→User null | — |
| created_at | DatetimeField | — |

索引：(account_set_id, supplier_id)

### PurchaseReceiptItem（入库单明细）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | IntField PK | — |
| receipt_bill_id | FK→PurchaseReceiptBill | — |
| purchase_order_item_id | FK→PurchaseOrderItem null | 追溯源数据 |
| product_id | FK→Product | — |
| product_name | CharField(200) | 快照 |
| quantity | IntField | 数量 |
| tax_inclusive_price | Decimal(18,2) | 含税单价 |
| tax_exclusive_price | Decimal(18,2) | 不含税单价 |
| tax_rate | Decimal(5,2) | 税率 |

## 新增预置科目

| 科目代码 | 名称 | 类别 | 方向 | 说明 |
|---------|------|------|------|------|
| 1407 | 发出商品 | asset | debit | 已发货未确认收入的商品成本中转 |

## API 端点

### /api/invoices（~10个端点）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /invoices | accounting_view | 发票列表（筛选：direction/status/客户/供应商/日期） |
| GET | /invoices/{id} | accounting_view | 发票详情（含明细行） |
| POST | /invoices/from-receivable | accounting_edit | 从应收单推送生成销项发票 |
| POST | /invoices | accounting_edit | 手工创建进项发票 |
| PUT | /invoices/{id} | accounting_edit | 修改草稿发票 |
| POST | /invoices/{id}/confirm | accounting_approve | 确认发票（销项生成凭证） |
| POST | /invoices/{id}/cancel | accounting_edit | 作废发票 |

### /api/sales-delivery（~4个端点）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /sales-delivery | accounting_view | 出库单列表 |
| GET | /sales-delivery/{id} | accounting_view | 出库单详情（含明细） |
| GET | /sales-delivery/{id}/pdf | accounting_view | 单张PDF下载 |
| POST | /sales-delivery/batch-pdf | accounting_view | 批量PDF下载 |

### /api/purchase-receipt（~4个端点）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /purchase-receipt | accounting_view | 入库单列表 |
| GET | /purchase-receipt/{id} | accounting_view | 入库单详情（含明细） |
| GET | /purchase-receipt/{id}/pdf | accounting_view | 单张PDF下载 |
| POST | /purchase-receipt/batch-pdf | accounting_view | 批量PDF下载 |

### /api/vouchers（扩展现有）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /vouchers/{id}/pdf | accounting_view | 凭证PDF下载 |
| POST | /vouchers/batch-pdf | accounting_view | 批量凭证PDF下载 |

## 前端

### AccountingView 新增Tab

- **发票管理** — 2个子Tab：销项发票 / 进项发票

### 出入库单入口

- 应收管理面板 → 新增「出库单」子Tab
- 应付管理面板 → 新增「入库单」子Tab

### 凭证面板扩展

- 凭证列表行增加「打印」按钮
- 批量选择 + 批量打印

## PDF 套打规格

- **尺寸**: 24cm × 14cm（landscape）
- **库**: reportlab
- **中文字体**: WenQuanYi Zen Hei（Dockerfile 安装 fonts-wqy-zenhei）
- **三种模板**: 记账凭证 / 销售出库单 / 采购入库单
- **批量打印**: 多张合并为一个PDF，每张一页

## 新建/修改文件预估

### 新建文件（~18个）

| 文件 | 用途 |
|------|------|
| backend/app/models/invoice.py | Invoice + InvoiceItem |
| backend/app/models/delivery.py | SalesDeliveryBill/Item + PurchaseReceiptBill/Item |
| backend/app/schemas/invoice.py | 发票相关 schemas |
| backend/app/schemas/delivery.py | 出入库单 schemas |
| backend/app/services/invoice_service.py | 发票推送+确认+凭证生成 |
| backend/app/services/delivery_service.py | 出入库单创建+凭证生成 |
| backend/app/routers/invoices.py | 发票路由 |
| backend/app/routers/sales_delivery.py | 出库单路由 |
| backend/app/routers/purchase_receipt.py | 入库单路由 |
| backend/app/utils/pdf_print.py | PDF套打工具（3种模板） |
| backend/tests/test_invoice.py | 发票测试 |
| backend/tests/test_delivery.py | 出入库单测试 |
| frontend/.../InvoicePanel.vue | 发票管理容器 |
| frontend/.../SalesInvoiceTab.vue | 销项发票Tab |
| frontend/.../PurchaseInvoiceTab.vue | 进项发票Tab |
| frontend/.../SalesDeliveryTab.vue | 出库单Tab |
| frontend/.../PurchaseReceiptTab.vue | 入库单Tab |

### 修改文件（~8个）

| 文件 | 变更 |
|------|------|
| backend/app/models/__init__.py | 导入6个新模型 |
| backend/app/migrations.py | 新增 migrate_accounting_phase4() |
| backend/main.py | 注册3个新路由 |
| backend/app/routers/logistics.py | 钩子：发货→出库单+凭证 |
| backend/app/routers/purchase_orders.py | 钩子：收货→入库单+凭证 |
| backend/requirements.txt | 追加 reportlab |
| Dockerfile | 安装 fonts-wqy-zenhei |
| frontend/src/api/accounting.js | 新增API函数 |
| frontend/src/views/AccountingView.vue | 新增发票Tab |
