# 取消订单退款流程优化设计

## 问题

1. 取消订单时显示服务器错误（后端边界处理不当）
2. 未发货未收款的订单取消时被要求选择退款方式，实际无需退款
3. 已收款订单取消后退款只生成负金额 Payment，未推送到付款管理由出纳确认实际付款

## 设计决策

- 按「发货状态」+「收款状态」决定取消流程复杂度
- 未收款订单直接取消，不走退款向导
- 已收款订单选「现金退款」时：收款管理生成红字退款单（调整应收）+ 付款管理生成待付退款单（出纳付款）
- 已收款订单选「转余额」时：只调 customer.balance，不推送付款管理

## 取消流程矩阵

| 发货状态 | 收款状态 | 取消流程 |
|---------|---------|---------|
| 未发货 | 未收款 (paid=0, rebate=0) | 直接取消：confirm 对话框，无向导 |
| 未发货 | 已收款 (paid>0 或 rebate>0) | 向导 1步：退款金额 + 退返利 + 退款方式选择 |
| 部分发货 | 未收款 | 向导 1步：确认商品（已发/未发）→ 直接取消 |
| 部分发货 | 已收款 | 向导 3步：确认商品 → 逐商品财务分配 → 退款方式选择 |

## 退款方式

### 转入客户余额（balance）
- Customer.balance 扣减退款金额（余额增加，balance 为欠款所以做减法）
- 不生成付款单
- 立即生效

### 现金退款（cash）
- 收款管理：生成 Payment（amount 为负，source="REFUND"，is_confirmed=false）
- 付款管理：生成 DisbursementBill（type="REFUND"），出纳确认后标记完成
- 出纳确认付款后，Payment.is_confirmed → true

## 变更范围

| 层 | 文件 | 改动 |
|----|------|------|
| 前端 | FinanceOrdersTab.vue | cancelStepCount 逻辑重写；未收款订单走 confirm 对话框跳过向导 |
| 后端 | routers/orders.py | cancel 接口：现金退款时额外创建 DisbursementBill；修复边界错误 |
| 后端 | schemas/order.py | CancelRequest 允许 refund_amount/refund_method 可选 |

## 前端向导步骤详情

### 未收款 + 未发货
不弹向导，直接调用 `appStore.customConfirm('确认取消', '确认取消该订单？')` → POST cancel（空 payload 或默认值）

### 未收款 + 部分发货
- Step 1：商品确认（已发货生成新订单 / 未发货释放库存）
- 确认后直接取消（refund_amount=0）

### 已收款 + 未发货
- Step 1（唯一步）：退款金额输入 + 退返利金额输入 + 退款方式选择（转余额/现金退款）

### 已收款 + 部分发货
- Step 1：商品确认
- Step 2：逐商品财务分配（现金+返利）
- Step 3：退款金额 + 退返利 + 退款方式选择

## 后端 DisbursementBill 创建

当 refund_method="cash" 且 refund_amount > 0 时：
```python
# 1. 收款管理退款记录（已有逻辑）
await Payment.create(
    payment_no=pay_no, customer=customer, order=order,
    amount=-refund_amount,
    payment_method=data.refund_payment_method or "cash",
    source="REFUND", is_confirmed=False,
    ...
)

# 2. 付款管理退款单（新增）
from app.models.accounting import DisbursementBill
bill_no = generate_order_no("FKTK")  # 付款退款
await DisbursementBill.create(
    bill_no=bill_no,
    type="REFUND",
    payee_type="customer",
    payee_id=customer.id,
    payee_name=customer.name,
    total_amount=refund_amount,
    status="pending",
    account_set_id=order.account_set_id,
    remark=f"取消订单 {order.order_no} 退款",
    creator=user,
)
```
