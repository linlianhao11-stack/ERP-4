# 客户返利账套隔离 + 充值弹窗 UI 优化 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 客户返利按账套隔离（与供应商一致），充值弹窗内置账套选择器。

**Architecture:** 新增 `CustomerAccountBalance` 模型（类似 `SupplierAccountBalance`），改造返利充值/汇总/扣减/退回 4 处后端逻辑从 `Customer.rebate_balance` 切换到 `CustomerAccountBalance`，前端充值弹窗内新增账套选择器（客户和供应商通用）。

**Tech Stack:** FastAPI + Tortoise ORM + PostgreSQL / Vue 3 + Pinia

---

### Task 1: 新增 CustomerAccountBalance 模型

**Files:**
- Create: `backend/app/models/customer_balance.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: 创建模型文件**

创建 `backend/app/models/customer_balance.py`：

```python
from tortoise import fields, models


class CustomerAccountBalance(models.Model):
    """客户按账套隔离的返利余额"""
    id = fields.IntField(pk=True)
    customer = fields.ForeignKeyField("models.Customer", related_name="account_balances", on_delete=fields.RESTRICT)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="customer_balances", on_delete=fields.RESTRICT)
    rebate_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        table = "customer_account_balances"
        unique_together = (("customer", "account_set"),)
```

**Step 2: 注册到 `__init__.py`**

在 `backend/app/models/__init__.py` 添加 import 和 `__all__` 导出：

```python
from app.models.customer_balance import CustomerAccountBalance
```

在 `__all__` 列表末尾加入 `"CustomerAccountBalance"`。

**Step 3: 验证模型可导入**

```bash
cd backend && python3 -c "from app.models.customer_balance import CustomerAccountBalance; print('OK')"
```

**Step 4: Commit**

```bash
git add backend/app/models/customer_balance.py backend/app/models/__init__.py
git commit -m "feat: add CustomerAccountBalance model"
```

---

### Task 2: 数据库迁移

**Files:**
- Modify: `backend/app/migrations.py`

**Step 1: 在 `run_migrations()` 末尾添加调用**

在 `await migrate_supplier_account_balance()` 之后（`logger.info("数据库初始化完成")` 之前）添加：

```python
await migrate_customer_account_balance()
```

**Step 2: 添加迁移函数**

在文件末尾添加 `migrate_customer_account_balance()` 函数。参照 `migrate_supplier_account_balance()` 的模式：

```python
async def migrate_customer_account_balance():
    """客户返利按账套隔离迁移：新表 + 数据迁移（幂等）"""
    from tortoise import Tortoise
    await Tortoise.generate_schemas(safe=True)

    conn = connections.get("default")

    # 索引
    cab_indexes = [
        ("idx_customer_account_balances_customer", "customer_account_balances", "customer_id"),
        ("idx_customer_account_balances_account_set", "customer_account_balances", "account_set_id"),
    ]
    for name, table, columns in cab_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception as e:
            logger.warning(f"创建索引 {name} 失败（可忽略）: {e}")

    # 迁移现有余额数据到第一个活跃账套
    from app.models.accounting import AccountSet

    first_set = await AccountSet.filter(is_active=True).order_by("id").first()
    if first_set:
        rows = await conn.execute_query_dict(
            "SELECT id, name, rebate_balance FROM customers "
            "WHERE rebate_balance > 0"
        )
        for row in rows:
            result = await conn.execute_query(
                "INSERT INTO customer_account_balances (customer_id, account_set_id, rebate_balance) "
                "VALUES ($1, $2, $3) ON CONFLICT (customer_id, account_set_id) DO NOTHING",
                [row["id"], first_set.id, row["rebate_balance"]]
            )
            if result[0] > 0:
                logger.info(f"迁移: 客户 {row['name']} 返利余额已迁移到账套 {first_set.name}")

    logger.info("客户返利账套隔离迁移完成")
```

**Step 3: Commit**

```bash
git add backend/app/migrations.py
git commit -m "feat: add customer account balance migration"
```

---

### Task 3: 改造返利路由（充值 + 汇总）

**Files:**
- Modify: `backend/app/routers/rebates.py`

**Step 1: 修改 summary 端点**

客户汇总也需要 `account_set_id`，从 `CustomerAccountBalance` 读取：

```python
# 在文件顶部导入
from app.models.customer_balance import CustomerAccountBalance

# 修改 get_rebate_summary 中 target_type == "customer" 的分支：
if target_type == "customer":
    if not account_set_id:
        raise HTTPException(status_code=400, detail="客户返利需要指定账套")
    balances = await CustomerAccountBalance.filter(
        account_set_id=account_set_id
    ).all()
    balance_map = {b.customer_id: b for b in balances}
    customers = await Customer.filter(is_active=True).order_by("name")
    return [{
        "id": c.id, "name": c.name,
        "rebate_balance": float(balance_map[c.id].rebate_balance) if c.id in balance_map else 0,
    } for c in customers]
```

**Step 2: 修改 charge 端点**

客户充值也需要 `account_set_id`，写入 `CustomerAccountBalance`：

```python
# 修改 charge_rebate 中 target_type == "customer" 的分支：
if data.target_type == "customer":
    if not data.account_set_id:
        raise HTTPException(status_code=400, detail="客户返利充值需要指定账套")
    target = await Customer.filter(id=data.target_id, is_active=True).first()
    if not target:
        raise HTTPException(status_code=404, detail="客户不存在")
    target_name = target.name
    bal = await CustomerAccountBalance.filter(
        customer_id=data.target_id, account_set_id=data.account_set_id
    ).first()
    if not bal:
        bal = await CustomerAccountBalance.create(
            customer_id=data.target_id, account_set_id=data.account_set_id,
            rebate_balance=0
        )
    await CustomerAccountBalance.filter(id=bal.id).update(
        rebate_balance=F('rebate_balance') + data.amount
    )
    await bal.refresh_from_db()
    balance_after = bal.rebate_balance
    account_set_id = data.account_set_id
```

**Step 3: Commit**

```bash
git add backend/app/routers/rebates.py
git commit -m "feat: customer rebate summary and charge with account set isolation"
```

---

### Task 4: 改造销售单返利扣减

**Files:**
- Modify: `backend/app/services/order_service.py`

**Step 1: 修改 `process_rebate_deduction()` 函数**

将 `Customer.rebate_balance` 的读写改为 `CustomerAccountBalance`：

```python
# 在文件顶部导入
from app.models.customer_balance import CustomerAccountBalance

# 修改 process_rebate_deduction 函数：
async def process_rebate_deduction(data, customer, order, order_no, user):
    """处理返利扣减。若订单使用了返利，校验余额并扣减。"""
    total_rebate = sum(
        Decimal(str(it.rebate_amount)) if it.rebate_amount else Decimal("0")
        for it in data.items
    )
    if total_rebate > 0 and data.order_type != "RETURN":
        if not customer:
            raise HTTPException(status_code=400, detail="使用返利需要选择客户")
        account_set_id = getattr(order, 'account_set_id', None)
        if not account_set_id:
            raise HTTPException(status_code=400, detail="使用返利需要指定账套")
        bal = await CustomerAccountBalance.filter(
            customer_id=customer.id, account_set_id=account_set_id
        ).select_for_update().first()
        current_balance = bal.rebate_balance if bal else Decimal("0")
        if current_balance < total_rebate:
            raise HTTPException(status_code=400,
                detail=f"客户返利余额不足，可用 ¥{float(current_balance):.2f}，"
                       f"需要 ¥{float(total_rebate):.2f}")
        if not bal:
            raise HTTPException(status_code=400, detail="客户返利余额不足")
        await CustomerAccountBalance.filter(id=bal.id).update(
            rebate_balance=F('rebate_balance') - total_rebate
        )
        await bal.refresh_from_db()
        order.rebate_used = total_rebate
        rebate_remark = f"[返利抵扣] 使用返利 ¥{float(total_rebate):.2f}"
        order.remark = f"{order.remark}\n{rebate_remark}" if order.remark else rebate_remark
        await RebateLog.create(
            target_type="customer", target_id=customer.id,
            type="use", amount=total_rebate,
            balance_after=bal.rebate_balance,
            account_set_id=account_set_id,
            reference_type="ORDER", reference_id=order.id,
            remark=f"销售订单 {order_no} 使用返利", creator=user
        )
    return total_rebate
```

**Step 2: Commit**

```bash
git add backend/app/services/order_service.py
git commit -m "feat: sales order rebate deduction uses CustomerAccountBalance"
```

---

### Task 5: 改造取消订单返利退回

**Files:**
- Modify: `backend/app/routers/orders.py`

**Step 1: 在文件顶部添加导入**

```python
from app.models.customer_balance import CustomerAccountBalance
```

**Step 2: 修改取消订单的返利退回逻辑**

在 `cancel_order` 函数中（约第 559-576 行），将退回 `Customer.rebate_balance` 改为退回 `CustomerAccountBalance`：

```python
# 原代码（约 564-576 行）：
if refund_rebate > 0:
    await Customer.filter(id=customer.id).update(
        rebate_balance=F('rebate_balance') + refund_rebate
    )
    await customer.refresh_from_db()
    await RebateLog.create(
        target_type="customer", target_id=customer.id,
        type="refund", amount=refund_rebate,
        balance_after=customer.rebate_balance,
        reference_type="ORDER", reference_id=order.id,
        remark=f"取消订单 {order.order_no} 退回返利",
        creator=user
    )

# 替换为：
if refund_rebate > 0:
    account_set_id = order.account_set_id
    if account_set_id:
        bal = await CustomerAccountBalance.filter(
            customer_id=customer.id, account_set_id=account_set_id
        ).first()
        if not bal:
            bal = await CustomerAccountBalance.create(
                customer_id=customer.id, account_set_id=account_set_id,
                rebate_balance=0
            )
        await CustomerAccountBalance.filter(id=bal.id).update(
            rebate_balance=F('rebate_balance') + refund_rebate
        )
        await bal.refresh_from_db()
        balance_after = bal.rebate_balance
    else:
        await Customer.filter(id=customer.id).update(
            rebate_balance=F('rebate_balance') + refund_rebate
        )
        await customer.refresh_from_db()
        balance_after = customer.rebate_balance
    await RebateLog.create(
        target_type="customer", target_id=customer.id,
        type="refund", amount=refund_rebate,
        balance_after=balance_after,
        account_set_id=account_set_id,
        reference_type="ORDER", reference_id=order.id,
        remark=f"取消订单 {order.order_no} 退回返利",
        creator=user
    )
```

注意：保留了 `account_set_id` 为空时的兼容处理（历史订单可能无账套）。

**Step 3: Commit**

```bash
git add backend/app/routers/orders.py
git commit -m "feat: cancel order rebate refund uses CustomerAccountBalance"
```

---

### Task 6: 测试

**Files:**
- Modify: `backend/tests/test_supplier_balance.py` → 重命名为 `backend/tests/test_account_balance.py` 或在现有文件中追加

**Step 1: 在 `backend/tests/test_supplier_balance.py` 末尾追加客户返利测试**

```python
from app.models.customer_balance import CustomerAccountBalance


@pytest.mark.asyncio
async def test_customer_account_balance_create():
    """测试 CustomerAccountBalance 创建"""
    customer = await Customer.create(name="测试客户A")
    aset = await AccountSet.create(
        code="CTEST01", name="客户测试账套1", start_year=2026, current_period="2026-01"
    )
    bal = await CustomerAccountBalance.create(
        customer=customer, account_set=aset,
        rebate_balance=Decimal("800")
    )
    assert bal.rebate_balance == Decimal("800")
    assert bal.customer_id == customer.id
    assert bal.account_set_id == aset.id


@pytest.mark.asyncio
async def test_customer_balance_isolation():
    """测试不同账套的客户返利余额隔离"""
    customer = await Customer.create(name="测试客户B")
    aset1 = await AccountSet.create(
        code="CSET_A", name="客户账套A", start_year=2026, current_period="2026-01"
    )
    aset2 = await AccountSet.create(
        code="CSET_B", name="客户账套B", start_year=2026, current_period="2026-01"
    )
    await CustomerAccountBalance.create(
        customer=customer, account_set=aset1,
        rebate_balance=Decimal("500")
    )
    await CustomerAccountBalance.create(
        customer=customer, account_set=aset2,
        rebate_balance=Decimal("1200")
    )
    b1 = await CustomerAccountBalance.filter(
        customer=customer, account_set=aset1
    ).first()
    b2 = await CustomerAccountBalance.filter(
        customer=customer, account_set=aset2
    ).first()
    assert b1.rebate_balance == Decimal("500")
    assert b2.rebate_balance == Decimal("1200")
```

**Step 2: 导入 `Customer`**

在文件顶部 `from app.models import Supplier, RebateLog, User` 中追加 `Customer`：

```python
from app.models import Supplier, RebateLog, User, Customer
```

**Step 3: 运行测试**

```bash
cd backend && python3 -m pytest tests/test_supplier_balance.py -v
```

预期：6 个测试全部通过（4 个原有 + 2 个新增）。

**Step 4: Commit**

```bash
git add backend/tests/test_supplier_balance.py
git commit -m "test: add customer account balance isolation tests"
```

---

### Task 7: 前端充值弹窗 UI 优化

**Files:**
- Modify: `frontend/src/components/business/FinanceRebatesPanel.vue`

**Step 1: 新增弹窗内状态**

在 `<script setup>` 中的已有 ref 声明区域添加：

```javascript
const chargeAccountSetId = ref(null)
const chargeTargetList = ref([])
```

**Step 2: 客户 tab 也显示账套选择器**

将模板中 `v-if="rebateTab === 'supplier' && accountSets.length"` 改为 `v-if="accountSets.length"`，使客户 tab 也能看到账套筛选下拉。

同时修改 `loadRebateSummaryData` 函数，客户查询时也传 `account_set_id`：

```javascript
const loadRebateSummaryData = async (targetType) => {
  try {
    const params = { target_type: targetType || rebateTab.value }
    if (selectedAccountSetId.value) {
      params.account_set_id = selectedAccountSetId.value
    }
    const { data } = await getRebateSummary(params)
    rebateSummary.value = data
  } catch (e) {
    console.error(e)
    appStore.showToast(e.response?.data?.detail || '加载返利数据失败', 'error')
  }
}
```

**Step 3: 充值弹窗内添加账套选择器**

在充值弹窗的 modal-body 中，`选择客户/供应商` 下拉之前添加账套选择：

```html
<!-- 弹窗内账套选择（客户和供应商都显示） -->
<div v-if="accountSets.length">
  <label class="label">充值账套 *</label>
  <select v-model="chargeAccountSetId" class="input" @change="onChargeAccountSetChange">
    <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
  </select>
</div>
```

**Step 4: 修改弹窗打开逻辑**

修改 `openRebateCharge` 和 `openRebateChargeNew`，初始化 `chargeAccountSetId` 为外部筛选值：

```javascript
const openRebateCharge = (targetType, targetId, name) => {
  const item = rebateSummary.value.find(x => x.id === targetId)
  rebateChargeForm.target_type = targetType
  rebateChargeForm.target_id = targetId
  rebateChargeForm.target_name = name
  rebateChargeForm.current_balance = item?.rebate_balance || 0
  rebateChargeForm.amount = null
  rebateChargeForm.remark = ''
  chargeAccountSetId.value = selectedAccountSetId.value
  chargeTargetList.value = [...rebateSummary.value]
  showRebateChargeModal.value = true
}

const openRebateChargeNew = () => {
  rebateChargeForm.target_type = rebateTab.value
  rebateChargeForm.target_id = null
  rebateChargeForm.target_name = ''
  rebateChargeForm.current_balance = 0
  rebateChargeForm.amount = null
  rebateChargeForm.remark = ''
  chargeAccountSetId.value = selectedAccountSetId.value
  chargeTargetList.value = [...rebateSummary.value]
  showRebateChargeModal.value = true
}
```

**Step 5: 添加弹窗内账套切换处理函数**

```javascript
const onChargeAccountSetChange = async () => {
  // 切换账套后刷新弹窗内的目标列表
  try {
    const params = {
      target_type: rebateChargeForm.target_type,
      account_set_id: chargeAccountSetId.value
    }
    const { data } = await getRebateSummary(params)
    chargeTargetList.value = data
    // 如果已选了目标，更新其余额显示
    if (rebateChargeForm.target_id) {
      const item = data.find(x => x.id === rebateChargeForm.target_id)
      rebateChargeForm.current_balance = item?.rebate_balance || 0
    }
  } catch (e) {
    console.error(e)
  }
}
```

**Step 6: 修改弹窗内的目标下拉数据源**

在 "新增充值" 弹窗中选择客户/供应商的 `<select>`，将 `rebateSummary` 改为 `chargeTargetList`：

```html
<!-- 原来是 v-for="item in rebateSummary" -->
<option v-for="item in chargeTargetList" :key="item.id" :value="item.id">{{ item.name }}（余额: ¥{{ fmt(item.rebate_balance) }}）</option>
```

**Step 7: 修改 `onRebateChargeTargetChange` 数据源**

```javascript
const onRebateChargeTargetChange = () => {
  const item = chargeTargetList.value.find(x => x.id === rebateChargeForm.target_id)
  if (item) {
    rebateChargeForm.target_name = item.name
    rebateChargeForm.current_balance = item.rebate_balance || 0
  } else {
    rebateChargeForm.target_name = ''
    rebateChargeForm.current_balance = 0
  }
}
```

**Step 8: 修改提交逻辑**

在 `handleChargeRebate` 中：

1. 将 `selectedAccountSetId.value` 的校验和使用改为 `chargeAccountSetId.value`
2. 客户充值也需要传 `account_set_id`

```javascript
const handleChargeRebate = async () => {
  if (!rebateChargeForm.amount || rebateChargeForm.amount <= 0) {
    appStore.showToast('请输入充值金额', 'error')
    return
  }
  if (!chargeAccountSetId.value) {
    appStore.showToast('请选择充值账套', 'error')
    return
  }
  if (submitting.value) return
  submitting.value = true
  try {
    const payload = {
      target_type: rebateChargeForm.target_type,
      target_id: rebateChargeForm.target_id,
      amount: rebateChargeForm.amount,
      remark: rebateChargeForm.remark || null,
      account_set_id: chargeAccountSetId.value
    }
    await chargeRebate(payload)
    appStore.showToast('充值成功')
    showRebateChargeModal.value = false
    loadRebateSummaryData(rebateChargeForm.target_type)
    customersStore.loadCustomers()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '充值失败', 'error')
  } finally {
    submitting.value = false
  }
}
```

**Step 9: Commit**

```bash
git add frontend/src/components/business/FinanceRebatesPanel.vue
git commit -m "feat: charge dialog with inline account set selector for both customer and supplier"
```

---

### Task 8: Docker 部署验证

**Step 1: 重新构建并启动**

```bash
docker compose up --build -d
```

**Step 2: 检查启动日志无报错**

```bash
docker compose logs erp --tail 30
```

预期：看到 "客户返利账套隔离迁移完成" 和 "数据库初始化完成"，无错误。

**Step 3: 验证 API**

```bash
curl -s http://localhost:8090/health
```

**Step 4: Commit（如有修复）**

若无需修复则跳过。
