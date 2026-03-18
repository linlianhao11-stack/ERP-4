# 退货退款流程重构设计

> 2026-03-18 | 方案 B（修订版）：退款管理确认后才推送会计单据

## 背景

现有退货退款流程存在三个核心问题：

1. **单据位置错误**：销售退货退款生成在 ReceiptBill（收款单），正确应为 ReceiptRefundBill（收款退款单）；采购退货退款生成在 DisbursementBill（付款单），正确应为 DisbursementRefundBill（付款退款单）
2. **缺少财务确认环节**：退货时由业务员选择「已退款」，缺少财务确认闭环
3. **会计单据生成时机错误**：不应在退货创建时就生成会计单据，应在财务确认退款后才推送

## 目标流程

### 销售退货

```
业务员创建退货单
  ├─ 选择「需要退款」→ 填写退款方式+退款信息（新弹窗）
  │   → 不生成任何会计单据
  │   → 退货订单标记 needs_refund=true，is_cleared=false
  │   → 出现在：财务管理 > 退款管理（「待退款」状态）
  │   → 财务确认已退款
  │     → 此时创建 ReceiptRefundBill（直接 confirmed 状态）
  │     → 出现在：会计管理 > 应收管理 > 收款退款单（无需再次确认）
  │     → 退货订单 is_cleared=true
  │
  └─ 选择「不需要退款」→ 客户余额增加（在账资金）
      → 退货订单 is_cleared=true（立即结清）
```

### 采购退货

```
业务员创建采购退货单
  ├─ 选择「需要退款」→ 填写退款方式+退款信息
  │   → 不生成任何会计单据
  │   → PurchaseReturn 标记 refund_status="pending"
  │   → 出现在：财务管理 > 退款管理（「待退款」状态）
  │   → 财务确认已收到退款
  │     → 此时创建 DisbursementRefundBill（直接 confirmed 状态）
  │     → 出现在：会计管理 > 应付管理 > 付款退款单（无需再次确认）
  │     → PurchaseReturn.refund_status="completed"
  │
  └─ 选择「不需要退款」→ 供应商在账资金增加
      → PurchaseReturn.refund_status="n/a"
```

### 订单取消退款

```
取消已收款订单 + 选择退款（非余额）
  → 同销售退货流程（标记 needs_refund，不生成会计单据，等待财务确认）
```

## 模型变更

### Order 模型

```python
# 字段语义变更（字段名保持 refunded 不改，只改 UI 语义）：
refunded  # 原义「已退款」→ 新义「需要退款」
# 新增：
refund_info = TextField(default="")  # 退款备注信息（业务员填写）
```

### PurchaseReturn 模型

```python
# 已有 is_refunded 字段，语义改为「需要退款」
# 新增：
refund_info = TextField(default="")  # 退款备注信息
```

### ReceiptRefundBill 扩展

```python
# 变更：
original_receipt = ForeignKeyField("ReceiptBill", null=True, ...)  # 改为 nullable
# 新增：
return_order = ForeignKeyField("Order", null=True, ...)            # 关联退货订单
refund_info = TextField(default="")                                 # 退款备注信息
```

### DisbursementRefundBill 扩展

```python
# 变更：
original_disbursement = ForeignKeyField("DisbursementBill", null=True, ...)  # 改为 nullable
# 新增：
purchase_return = ForeignKeyField("PurchaseReturn", null=True, ...)  # 关联采购退货单
refund_info = TextField(default="")                                   # 退款备注信息
```

### ReceiptBill 清理

移除字段：
- `bill_type`（不再需要 "return_refund" 标记）
- `return_order`（移到 ReceiptRefundBill）

### DisbursementBill 清理

移除字段：
- `bill_type`（不再需要 "return_refund" 标记）
- `purchase_return`（移到 DisbursementRefundBill）

## 后端改造

### 删除：退货时自动创建会计单据的逻辑（3处）

| # | 文件 | 行号 | 场景 | 操作 |
|---|------|------|------|------|
| 1 | orders.py | 224-251 | 销售退货+需要退款 | 删除 ReceiptBill.create 代码块 |
| 2 | orders.py | 860-869 | 取消订单退款 | 删除 ReceiptBill.create 代码块 |
| 3 | purchase_orders.py | 925-945 | 采购退货+需要退款 | 删除 DisbursementBill.create 代码块 |

### 新增：退款确认 API（财务管理 > 退款管理）

新增 router `backend/app/routers/refunds.py`：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/finance/refunds` | 待退款列表（合并销售+采购） |
| POST | `/api/finance/refunds/confirm-sales/{order_id}` | 确认销售退款 → 创建 ReceiptRefundBill(confirmed) |
| POST | `/api/finance/refunds/confirm-purchase/{return_id}` | 确认采购退款 → 创建 DisbursementRefundBill(confirmed) |

**确认销售退款逻辑：**
1. 查找退货订单（needs_refund=true, is_cleared=false）
2. 查找关联的红字 ReceivableBill
3. 查找原订单的 ReceiptBill（CASH 订单有，CREDIT 可能没有）
4. 创建 ReceiptRefundBill(status="confirmed", return_order=order, original_receipt=找到的原收款单或null)
5. 更新红字 ReceivableBill 的 received_amount
6. 标记退货订单 is_cleared=true
7. 权限：finance_confirm

**确认采购退款逻辑：**
1. 查找 PurchaseReturn（refund_status="pending"）
2. 查找关联的红字 PayableBill
3. 创建 DisbursementRefundBill(status="confirmed", purchase_return=pr, original_disbursement=null)
4. 更新红字 PayableBill 的 paid_amount
5. 标记 PurchaseReturn.refund_status="completed"
6. 权限：finance_confirm

### 清理：confirm 函数中的旧逻辑

| 文件 | 函数 | 操作 |
|------|------|------|
| ar_service.py:100-109 | confirm_receipt_bill | 移除 bill_type="return_refund" 分支 |
| ap_service.py:108-119 | confirm_disbursement_bill | 移除 bill_type="return_refund" 分支 |
| receivables.py:487 | pending-voucher-bills | 移除 type_label 中的 return_refund 判断 |
| payables.py:393 | pending-voucher-bills | 同上 |

### 凭证生成

不需要改动。ReceiptRefundBill/DisbursementRefundBill 的凭证生成逻辑已存在于 ar_service.py 和 ap_service.py 中。退货退款单创建时直接 confirmed 状态，月末勾选生成凭证时正常参与。

## 前端变更

### 销售退货表单（OrderConfirmModal + FinanceOrderDetailModal）

- 「已退款给客户」checkbox → 「需要退款」checkbox
- 勾选后弹出新弹窗：退款方式选择 + 退款信息输入框
- 不勾选 → 提示「将转为客户在账资金」

### 采购退货表单（PurchaseOrderDetail）

- 「供应商已退款」checkbox → 「需要供应商退款」
- 勾选后展示退款方式 + 退款信息输入框
- 不勾选 → 提示「将转为供应商在账资金」

### 财务管理新增「退款管理」Tab

- 位置：FinanceView.vue 新增一个 Tab
- 数据源：直接查询退货订单 + 采购退货单中需要退款且未确认的记录
- 合并展示销售退款和采购退款，通过类型列区分
- 显示：退货单号、客户/供应商、退款金额、退款方式、退款信息、退货日期
- 操作：「确认已退款」按钮
- 确认后从列表消失（已推送到会计模块）
- 权限：finance_confirm

### 会计模块清理

- ReceiptBillsTab：移除 bill_type="return_refund" 的标签显示逻辑
- DisbursementBillsTab：同上

## 「不需要退款」路径

- 销售退货：客户余额增加（已修复），退货订单 is_cleared=true（新增）
- 采购退货：供应商在账资金增加（现有逻辑），PurchaseReturn.refund_status="n/a"（现有）

## 数据迁移

需要编写迁移脚本处理已有数据：
1. ReceiptBill 中 bill_type="return_refund" 的记录 → 迁移到 ReceiptRefundBill（保持原状态）
2. DisbursementBill 中 bill_type="return_refund" 的记录 → 迁移到 DisbursementRefundBill（保持原状态）
3. 迁移后删除 ReceiptBill/DisbursementBill 上的 bill_type 和 return_order/purchase_return 列

## 权限

复用现有 `finance_confirm` 权限，不新增权限码。

## 不涉及的范围

- 代采代发模块的退款流程（独立体系）
- 审批流程（单级确认，不做多级审批）
- 采购侧在账资金逻辑（现有逻辑不变）
