# 客户返利账套隔离 + 充值弹窗 UI 优化 设计文档

**目标**：客户返利按账套隔离（与供应商一致），同时将充值弹窗的账套选择从外部筛选移入弹窗内部。

**架构**：新增 `CustomerAccountBalance` 模型实现按账套隔离，改造返利充值/使用/退回的 4 处后端逻辑，前端充值弹窗内置账套选择器。

---

## 一、新模型

### CustomerAccountBalance

```python
class CustomerAccountBalance(Model):
    customer = ForeignKeyField("models.Customer", related_name="account_balances")
    account_set = ForeignKeyField("models.AccountSet", related_name="customer_balances")
    rebate_balance = DecimalField(max_digits=12, decimal_places=2, default=0)
    class Meta:
        table = "customer_account_balances"
        unique_together = (("customer", "account_set"),)
```

与 `SupplierAccountBalance` 结构一致，但无 `credit_balance`（客户无在账资金概念）。

---

## 二、后端改动

### 1. 返利充值 `rebates.py` charge 端点

客户充值时要求 `account_set_id`，写入 `CustomerAccountBalance` 而非 `Customer.rebate_balance`。

### 2. 返利汇总 `rebates.py` summary 端点

客户汇总时要求 `account_set_id`，从 `CustomerAccountBalance` 读取余额。

### 3. 销售单返利扣减 `order_service.py` process_rebate_deduction()

根据 `order.account_set_id` 从 `CustomerAccountBalance` 扣减，使用 `select_for_update()` 保证并发安全。

### 4. 取消订单退回 `orders.py` cancel_order

退回返利到 `CustomerAccountBalance`（根据 `order.account_set_id`）。

---

## 三、数据库迁移

- `migrations.py` 新增 `migrate_customer_account_balance()` 函数
- 通过 `generate_schemas(safe=True)` 创建表
- 用 `INSERT ... ON CONFLICT DO NOTHING` 迁移现有 `Customer.rebate_balance` 非零数据到第一个活跃账套
- `Customer.rebate_balance` 字段保留但废弃

---

## 四、前端 UI 改动

### FinanceRebatesPanel.vue

1. **外部账套选择器**：客户 tab 和供应商 tab 都显示，仅用于查询筛选
2. **充值弹窗内**：
   - 新增 `chargeAccountSetId` 状态和账套 `<select>`
   - 默认值 = 外部筛选的账套
   - 切换账套 → 调 `getRebateSummary` 刷新弹窗内的目标列表和余额
   - 提交时用 `chargeAccountSetId`
3. **从列表点"充值"**：弹窗账套默认选中外部值，可修改；切换后刷新余额显示
4. **从"新增充值"按钮**：弹窗账套默认选中外部值，切换后刷新目标列表

---

## 五、不变的部分

- `Customer.rebate_balance` 字段保留（兼容）
- 客户列表端点 `customers.py` 不改
- 返利明细弹窗不改（已支持 `account_set_id` 筛选）
- 供应商侧逻辑不改（已完成账套隔离）
