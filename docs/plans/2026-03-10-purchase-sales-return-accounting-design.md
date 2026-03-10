# 采购/销售退货 → 会计模块联动设计

## 问题

1. 采购部分退货时，采购页面和导出数据不显示退货信息（数量/金额/退款状态）
2. 采购退货无独立退货单，退货信息散落在原采购单字段上，无法推送到会计模块
3. 采购退货退款不推送到收款管理，出纳无法确认到账
4. 销售退货（refunded=true）不自动生成收款退款单，会计凭证不反映退货

## 设计决策

- 采购退货：新建 `PurchaseReturn` + `PurchaseReturnItem` 独立表
- 销售退货：复用现有 `Order(order_type='RETURN')` 模型，只补齐会计推送
- 采购退货退款：两边都推（付款退款单 + 收款管理待确认）
- 前端展示：采购页新增"退货单"Tab + 采购单详情中展示关联退货单

## 数据模型

### PurchaseReturn（新建）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| return_no | varchar(30) unique | 退货单号 PR-YYYYMMDD-NNN |
| purchase_order_id | FK → PurchaseOrder | 关联原采购单 |
| supplier_id | FK → Supplier | 供应商 |
| account_set_id | FK → AccountSet | 账套（继承原采购单） |
| total_amount | decimal | 退货总金额 |
| is_refunded | bool | true=供应商退款，false=转在账资金 |
| refund_status | varchar(20) | pending / confirmed |
| tracking_no | varchar(50) | 退货物流单号 |
| reason | text | 退货原因 |
| created_by | FK → User | |
| created_at | timestamptz | |

### PurchaseReturnItem（新建）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | |
| return_id | FK → PurchaseReturn | |
| purchase_item_id | FK → PurchaseOrderItem | 关联原采购行 |
| product_id | FK → Product | |
| quantity | int | 退货数量（正数） |
| unit_price | decimal | 退货单价（原采购行均价） |
| amount | decimal | quantity × unit_price |

## 业务流程

### 采购退货

```
采购退货操作
  ├─ 1. 创建 PurchaseReturn + PurchaseReturnItem
  ├─ 2. 扣减库存 + 写 StockLog（已有逻辑保留）
  ├─ 3. 更新原采购单 returned_quantity / return_amount / status
  ├─ 4. 推送会计模块：
  │   ├─ 红字应付单 PayableBill（total_amount 为负）
  │   └─ 付款退款单 DisbursementRefundBill
  ├─ 5. 推送收款管理（仅 is_refunded=true）：
  │   └─ 生成待确认收款记录，出纳确认后 refund_status → confirmed
  └─ 6. is_refunded=false 时：供应商在账资金增加（已有）
```

### 销售退货补齐

```
销售退货订单创建（已有）
  ├─ 已有：红字 ReceivableBill
  └─ 新增（refunded=true 时）：
      └─ 自动生成 ReceiptRefundBill（收款退款单）
```

### 采购导出增强

CSV 增加列：退货数量、退货金额、退款状态

## 变更范围

| 层 | 文件 | 改动 |
|----|------|------|
| 模型 | models/purchase.py | 新增 PurchaseReturn + PurchaseReturnItem |
| 迁移 | migrations.py | 建表 SQL |
| 后端 | routers/purchase_orders.py | 退货接口重构 + 导出增加退货列 |
| 后端 | 新文件 routers/purchase_returns.py | 退货单 CRUD |
| 后端 | routers/orders.py | 销售退货自动生成 ReceiptRefundBill |
| 后端 | services/ap_service.py | create_return_payable_bill() |
| 前端 | PurchaseView.vue | 新增"退货单"Tab |
| 前端 | 新组件 PurchaseReturnTab.vue | 退货单列表 |
| 前端 | PurchaseOrderDetail.vue | 详情展示关联退货单 |
| 前端 | composables/usePurchaseOrder.js | 导出逻辑更新 |
