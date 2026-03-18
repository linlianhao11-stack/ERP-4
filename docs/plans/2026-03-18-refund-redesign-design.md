# 退货退款流程重构设计

> 2026-03-18 | 方案 B：扩展 RefundBill 模型，统一退款到正确的会计单据

## 背景

现有退货退款流程存在两个核心问题：

1. **单据位置错误**：销售退货退款生成在 ReceiptBill（收款单），正确应为 ReceiptRefundBill（收款退款单）；采购退货退款生成在 DisbursementBill（付款单），正确应为 DisbursementRefundBill（付款退款单）
2. **缺少财务确认环节**：退货时由业务员选择「已退款」，缺少财务确认闭环

## 目标流程

### 销售退货

```
业务员创建退货单
  ├─ 选择「需要退款」→ 填写退款方式+退款信息（新弹窗）
  │   → 创建 ReceiptRefundBill（draft）
  │   → 出现在：会计管理 > 应收管理 > 收款退款单
  │   → 出现在：财务管理 > 退款管理（财务确认入口）
  │   → 财务确认已退款 → 退货订单 is_cleared=true
  │
  └─ 选择「不需要退款」→ 客户余额增加（在账资金）
      → 退货订单 is_cleared=true（立即结清）
```

### 采购退货

```
业务员创建采购退货单
  ├─ 选择「需要退款」→ 填写退款方式+退款信息
  │   → 创建 DisbursementRefundBill（draft）
  │   → 出现在：会计管理 > 应付管理 > 付款退款单
  │   → 出现在：财务管理 > 退款管理（财务确认入口）
  │   → 财务确认已收到退款 → PurchaseReturn.refund_status="completed"
  │
  └─ 选择「不需要退款」→ 供应商在账资金增加
      → PurchaseReturn.refund_status="n/a"
```

### 订单取消退款

```
取消已收款订单 + 选择退款（非余额）
  → 创建 ReceiptRefundBill（draft）→ 同销售退货流程
```

## 模型变更

### ReceiptRefundBill 扩展

```python
# 现有字段不变，以下为变更：
original_receipt = ForeignKeyField("ReceiptBill", null=True, ...)  # 改为 nullable
# 新增：
return_order = ForeignKeyField("Order", null=True, ...)            # 关联退货订单
refund_info = TextField(default="")                                 # 退款备注信息
```

### DisbursementRefundBill 扩展

```python
# 现有字段不变，以下为变更：
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

## 需要改造的代码路径（3处创建 + 2处确认 + 2处凭证）

### 创建路径

| # | 文件 | 行号 | 场景 | 现状 | 改为 |
|---|------|------|------|------|------|
| 1 | orders.py | 224-251 | 销售退货+需要退款 | ReceiptBill(return_refund) | ReceiptRefundBill |
| 2 | orders.py | 860-869 | 取消订单退款 | ReceiptBill(return_refund) | ReceiptRefundBill |
| 3 | purchase_orders.py | 925-945 | 采购退货+需要退款 | DisbursementBill(return_refund) | DisbursementRefundBill |

### 确认路径

| # | 文件 | 函数 | 新增逻辑 |
|---|------|------|---------|
| 1 | ar_service.py | confirm_receipt_refund | 有 return_order 时：通过 order_id 找红字应收单 + 标记退货订单 is_cleared=true |
| 2 | ap_service.py | confirm_disbursement_refund | 有 purchase_return 时：标记 PurchaseReturn.refund_status="completed" |

### 凭证生成路径

| # | 文件 | 函数 | 变更 |
|---|------|------|------|
| 1 | ar_service.py | generate_ar_vouchers | 退货退款单通过 return_order → order_id 查找 ReceivableBill 获取辅助核算 |
| 2 | ap_service.py | generate_ap_vouchers | 退货退款单通过 purchase_return 查找 PayableBill 获取辅助核算 |

## 前端变更

### 销售退货表单（OrderConfirmModal + FinanceOrderDetailModal）

- 「已退款给客户」checkbox → 「需要退款」checkbox
- 勾选后弹出新弹窗：退款方式选择 + 退款信息输入框
- 不勾选 → 提示「将转为客户在账资金」

### 采购退货表单（PurchaseOrderDetail）

- 「是否已退款」checkbox → 「是否需要退款」
- 勾选后弹出新弹窗（与销售退款弹窗对称设计）
- 不勾选 → 提示「将转为供应商在账资金」

### 财务管理新增「退款管理」Tab

- 位置：FinanceView.vue 新增一个 Tab
- 合并展示销售退款（ReceiptRefundBill）和采购退款（DisbursementRefundBill）
- 通过筛选区分类型
- 操作：确认已退款/确认已收到退款
- 权限：finance_confirm

### 会计模块清理

- ReceiptBillsTab：移除 bill_type="return_refund" 的标签显示逻辑
- DisbursementBillsTab：同上

## 「不需要退款」路径

- 销售退货：客户余额增加（已修复），退货订单 is_cleared=true（新增）
- 采购退货：供应商在账资金增加（现有逻辑），PurchaseReturn.refund_status="n/a"（现有）

## 数据迁移

需要编写迁移脚本处理已有数据：
1. ReceiptBill 中 bill_type="return_refund" 的记录 → 迁移到 ReceiptRefundBill
2. DisbursementBill 中 bill_type="return_refund" 的记录 → 迁移到 DisbursementRefundBill
3. 迁移后清理 ReceiptBill/DisbursementBill 上的废弃字段

## 权限

复用现有 `finance_confirm` 权限，不新增权限码。

## 不涉及的范围

- 代采代发模块的退款流程（独立体系）
- 审批流程（单级确认，不做多级审批）
- 采购侧在账资金逻辑（现有逻辑不变）
