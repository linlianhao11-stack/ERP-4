# 代码审查修复计划

**目标：** 修复全量代码审查发现的 5 个 Critical、10 个 Important、8 个 Improvement 问题

**架构：** 按优先级分组，先修 Critical（安全/数据完整性），再修 Important（业务逻辑），最后 Improvement（性能/DRY）

**技术栈：** FastAPI + Tortoise ORM + Vue 3 + Pinia

---

## Task 1: 提取共享 `_next_voucher_no` + 加锁 + 空值保护（C1 + C2 + P1）

**问题：** 6个文件重复相同的13行函数，无数据库锁（TOCTOU竞态），`account_set`不存在时空指针崩溃

**文件：**
- 创建: `backend/app/utils/voucher_no.py`
- 修改: `backend/app/routers/vouchers.py:19-31` — 删除本地函数，改为导入
- 修改: `backend/app/services/ar_service.py:155-167` — 同上
- 修改: `backend/app/services/ap_service.py:138-150` — 同上
- 修改: `backend/app/services/invoice_service.py:18-30` — 同上
- 修改: `backend/app/services/delivery_service.py:16-28` — 同上
- 修改: `backend/app/services/period_end_service.py:19-31` — 同上

**改动：**

1. 创建 `backend/app/utils/voucher_no.py`:
```python
from tortoise import connections

async def next_voucher_no(account_set_id: int, voucher_type: str, period_name: str) -> str:
    """生成凭证号，使用 SELECT FOR UPDATE 防止并发重复"""
    from app.models.accounting import AccountSet, Voucher
    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise ValueError(f"账套 {account_set_id} 不存在")
    prefix = f"{account_set.code}-{voucher_type}-{period_name.replace('-', '')}-"
    last = await Voucher.filter(
        account_set_id=account_set_id,
        voucher_type=voucher_type,
        period_name=period_name,
    ).order_by("-voucher_no").select_for_update().first()
    if last and last.voucher_no.startswith(prefix):
        seq = int(last.voucher_no[len(prefix):]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"
```

2. 在6个文件中：删除本地 `_next_voucher_no` 函数，替换为 `from app.utils.voucher_no import next_voucher_no`，调用处 `_next_voucher_no(` → `await next_voucher_no(`

---

## Task 2: AP 服务事务安全（C3）

**问题：** `create_disbursement_for_po_payment` 无事务包装，payable_bill 修改无 `select_for_update`

**文件：**
- 修改: `backend/app/services/ap_service.py:47-80`

**改动：**

```python
async def create_disbursement_for_po_payment(...) -> DisbursementBill:
    from tortoise import transactions
    async with transactions.in_transaction():
        db = await DisbursementBill.create(...)
        if payable_bill:
            pb = await PayableBill.filter(id=payable_bill.id).select_for_update().first()
            pb.paid_amount += amount
            pb.unpaid_amount = pb.total_amount - pb.paid_amount
            pb.status = "completed" if pb.unpaid_amount <= 0 else "partial"
            await pb.save()
        return db
```

---

## Task 3: Docker SECRET_KEY 安全加固（C4）

**问题：** SECRET_KEY 默认值为已知明文字符串

**文件：**
- 修改: `docker-compose.yml:36`
- 修改: `backend/main.py` — 启动时检查

**改动：**

1. `docker-compose.yml` 删除默认值：
```yaml
SECRET_KEY: ${SECRET_KEY}
```

2. `backend/main.py` 启动事件中加检查：
```python
secret = os.environ.get("SECRET_KEY", "")
if not secret or secret == "change-me-to-a-random-secret-in-production":
    raise RuntimeError("请设置 SECRET_KEY 环境变量")
```

3. 确保 `.env` 文件（已在 .gitignore）中有随机 SECRET_KEY

---

## Task 4: 替换16处原生 confirm() 为 customConfirm（C5）

**问题：** 原生 `confirm()` 在移动端不显示，样式不一致

**文件（12个组件）：**
- `DisbursementBillsTab.vue:162` — 1处
- `DisbursementRefundBillsTab.vue:162` — 1处
- `WriteOffBillsTab.vue:162` — 1处
- `ReceiptBillsTab.vue:169` — 1处
- `ReceiptRefundBillsTab.vue:162` — 1处
- `ReceivableBillsTab.vue:210` — 1处
- `PayableBillsTab.vue:210` — 1处
- `ChartOfAccountsPanel.vue:197` — 1处
- `VoucherPanel.vue:362,371` — 2处
- `ReceivablePanel.vue:44` — 1处
- `PayablePanel.vue:41` — 1处
- `SalesInvoiceTab.vue:405,416` — 2处
- `PurchaseInvoiceTab.vue:412,423` — 2处

**改动模式（所有文件 appStore 已导入）：**
```javascript
// 前: if (!confirm(`确认核销单 ${b.bill_no}？`)) return
// 后: if (!await appStore.customConfirm('确认操作', `确认核销单 ${b.bill_no}？`)) return
```

---

## Task 5: 财务钩子错误处理升级（I1）

**问题：** 业务钩子（自动生成应收/应付/出入库单）失败只 log warning，不回滚

**文件：**
- 修改: `backend/app/routers/orders.py:143-155` — 退货AR钩子
- 修改: `backend/app/routers/purchase_orders.py:534-561` — 收货AP钩子

**改动：** 将 `logger.warning` 替换为 `raise HTTPException(500, detail=f"业务操作成功但财务单据生成失败: {e}")`，让前端知道出了问题。

---

## Task 6: 订单取消拆分复制 account_set_id（I2）

**问题：** 取消部分发货订单时，拆分生成的新订单缺少 `account_set_id`

**文件：**
- 修改: `backend/app/routers/orders.py:497-507`

**改动：** 在 `Order.create(...)` 参数中增加：
```python
account_set_id=order.account_set_id,
```

---

## Task 7: 详情端点增加账套隔离（I3）

**问题：** 6个 GET /{id} 端点按主键查询，无账套过滤，可跨账套访问

**文件：**
- 修改: `backend/app/routers/receivables.py:71` — `.filter(id=bill_id)` → `.filter(id=bill_id, account_set_id=account_set_id)`
- 修改: `backend/app/routers/payables.py:71` — 同上
- 修改: `backend/app/routers/vouchers.py:70` — 同上
- 修改: `backend/app/routers/invoices.py:72` — 同上
- 修改: `backend/app/routers/sales_delivery.py:56` — 同上
- 修改: `backend/app/routers/purchase_receipt.py:57` — 同上

**改动模式：** 每个端点增加 `account_set_id: int = Query(...)` 参数，查询加 `account_set_id=account_set_id` 条件。

---

## Task 8: 金额正数校验（I4）

**问题：** 应收/应付单、发票明细缺少 `gt=0` 校验

**文件：**
- 修改: `backend/app/schemas/ar_ap.py:14` — `ReceivableBillCreate.total_amount` 加 `gt=0`
- 修改: `backend/app/schemas/ar_ap.py:52` — `PayableBillCreate.total_amount` 加 `gt=0`
- 修改: `backend/app/schemas/invoice.py:11-12` — `quantity` 加 `gt=0`，`unit_price` 加 `gt=0`

---

## Task 9: 取消发票清理凭证（I5）

**问题：** `cancel_invoice` 不清理关联凭证

**文件：**
- 修改: `backend/app/services/invoice_service.py:277-287`

**改动：**
```python
async def cancel_invoice(invoice_id: int) -> Invoice:
    from tortoise import transactions
    async with transactions.in_transaction():
        inv = await Invoice.filter(id=invoice_id).select_for_update().first()
        if not inv:
            raise ValueError("发票不存在")
        if inv.status == "cancelled":
            raise ValueError("发票已作废")
        # 清理关联凭证
        if inv.voucher_id:
            from app.models.accounting import VoucherEntry, Voucher
            await VoucherEntry.filter(voucher_id=inv.voucher_id).delete()
            await Voucher.filter(id=inv.voucher_id).delete()
            inv.voucher_id = None
        inv.status = "cancelled"
        await inv.save()
    return inv
```

---

## Task 10: 反结账检查后续期间（I6）

**问题：** `reopen_period` 不检查后续期间是否已结账

**文件：**
- 修改: `backend/app/services/period_end_service.py:372-400`

**改动：** 在 `period.is_closed` 检查之后增加：
```python
# 检查后续期间
later_closed = await AccountingPeriod.filter(
    account_set_id=account_set_id,
    period_name__gt=period_name,
    is_closed=True
).exists()
if later_closed:
    raise ValueError(f"存在已结账的后续期间，请先反结账后续期间")
```

---

## Task 11: token_version 原子更新（I7）

**问题：** `user.token_version += 1` 非原子操作

**文件：**
- 修改: `backend/app/routers/users.py:52,67`

**改动：**
```python
# 替换: user.token_version += 1
await User.filter(id=user.id).update(token_version=F('token_version') + 1)
await user.refresh_from_db()
```

---

## Task 12: 采购部分收货应付单修复（I8）

**问题：** 部分收货只在首次创建应付单，后续收货不更新金额

**文件：**
- 修改: `backend/app/routers/purchase_orders.py:534-561`

**改动：**
```python
# 替换 if not exists 逻辑
exists_pb = await PB.filter(
    account_set_id=po.account_set_id, purchase_order_id=po.id
).first()
received_items = await PurchaseOrderItem.filter(
    purchase_order_id=po.id, received_quantity__gt=0
).all()
received_total = sum(
    (it.amount / it.quantity * it.received_quantity).quantize(Decimal("0.01"))
    for it in received_items if it.quantity > 0
)
if received_total > 0:
    if exists_pb:
        # 更新已有应付单金额
        exists_pb.total_amount = received_total
        exists_pb.unpaid_amount = received_total - exists_pb.paid_amount
        await exists_pb.save()
    else:
        await create_payable_bill(
            account_set_id=po.account_set_id,
            supplier_id=po.supplier_id,
            purchase_order_id=po.id,
            total_amount=received_total,
            status="pending",
            creator=user,
        )
```

---

## Task 13: StockView/CustomersView 添加 onMounted（I9）

**问题：** 两个视图无 onMounted，数据不会主动刷新

**文件：**
- 修改: `frontend/src/views/StockView.vue:437` — import 添加 `onMounted`
- 修改: `frontend/src/views/CustomersView.vue:316` — import 添加 `onMounted`

**改动：**
```javascript
// StockView.vue — 增加
import { ref, reactive, computed, watch, onMounted } from 'vue'
onMounted(() => {
  productsStore.loadProducts()
  warehousesStore.loadWarehouses()
})

// CustomersView.vue — 增加
import { ref, computed, reactive, watch, onMounted } from 'vue'
onMounted(() => {
  customersStore.loadCustomers()
})
```

---

## Task 14: Accounting Store 错误处理（I10）

**问题：** 3处 `catch(e) { /* ignore */ }` 静默吞错

**文件：**
- 修改: `frontend/src/stores/accounting.js:23,37,45`

**改动：**
```javascript
// 替换3处 catch(e) { /* ignore */ } 为：
} catch (e) {
  console.error('加载失败', e)
}
```

---

## Task 15: 现金流量表 O(n²) 查询优化（P4）

**问题：** 每条现金分录都发一次DB查询找对手分录

**文件：**
- 修改: `backend/app/services/report_service.py:323-353`

**改动：** 批量预加载：
```python
# 1. 收集所有 voucher_id
voucher_ids = {ce.voucher_id for ce in cash_entries}
# 2. 一次性加载所有分录
all_entries = await VoucherEntry.filter(voucher_id__in=list(voucher_ids)).all()
# 3. 一次性加载所有科目
account_ids = {e.account_id for e in all_entries}
accounts = {a.id: a for a in await ChartOfAccount.filter(id__in=list(account_ids)).all()}
# 4. 按 voucher_id 分组在内存中匹配
from collections import defaultdict
entries_by_voucher = defaultdict(list)
for e in all_entries:
    entries_by_voucher[e.voucher_id].append(e)
# 5. 遍历不再发DB查询
for ce in cash_entries:
    for counter in entries_by_voucher.get(ce.voucher_id, []):
        if counter.id == ce.id or counter.account_id in cash_account_ids:
            continue
        counter_acct = accounts.get(counter.account_id)
        ...
```

---

## Task 16: 凭证批量PDF N+1 优化（P5）

**问题：** 批量PDF每个分录查一次科目表

**文件：**
- 修改: `backend/app/routers/vouchers.py:393-442`

**改动：**
```python
# 1. 批量加载所有凭证
vouchers = await Voucher.filter(id__in=ids).prefetch_related("account_set").all()
# 2. 批量加载所有分录
all_entries = await VoucherEntry.filter(voucher_id__in=ids).order_by("voucher_id", "line_no").all()
# 3. 批量加载科目
acct_ids = {e.account_id for e in all_entries}
accounts = {a.id: a for a in await ChartOfAccount.filter(id__in=list(acct_ids)).all()}
# 4. 按 voucher_id 分组
entries_map = defaultdict(list)
for e in all_entries:
    entries_map[e.voucher_id].append(e)
# 5. 生成PDF不再查DB
```

---

## Task 17: 版本号 + 备份上传优化（P7 + P8）

**文件：**
- 修改: `backend/main.py:52` — 版本号 `v4.9.0` → `v4.13.0`
- 修改: `backend/app/routers/backup.py:111-118` — 流式写入

**改动 backup.py：**
```python
try:
    MAX_SIZE = 100 * 1024 * 1024
    total_size = 0
    with open(saved_path, "wb") as f:
        while True:
            chunk = await file.read(8192)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_SIZE:
                raise HTTPException(status_code=400, detail="备份文件过大，最大支持 100MB")
            f.write(chunk)
```

---

## 涉及文件汇总

| # | 文件 | 改动 |
|---|------|------|
| 1 | `backend/app/utils/voucher_no.py` | 新建：共享凭证号生成器 |
| 2 | `backend/app/routers/vouchers.py` | Task 1 + Task 16 |
| 3 | `backend/app/services/ar_service.py` | Task 1 |
| 4 | `backend/app/services/ap_service.py` | Task 1 + Task 2 |
| 5 | `backend/app/services/invoice_service.py` | Task 1 + Task 9 |
| 6 | `backend/app/services/delivery_service.py` | Task 1 |
| 7 | `backend/app/services/period_end_service.py` | Task 1 + Task 10 |
| 8 | `backend/app/services/report_service.py` | Task 15 |
| 9 | `backend/app/routers/orders.py` | Task 5 + Task 6 |
| 10 | `backend/app/routers/purchase_orders.py` | Task 5 + Task 12 |
| 11 | `backend/app/routers/users.py` | Task 11 |
| 12 | `backend/app/routers/receivables.py` | Task 7 |
| 13 | `backend/app/routers/payables.py` | Task 7 |
| 14 | `backend/app/routers/invoices.py` | Task 7 |
| 15 | `backend/app/routers/sales_delivery.py` | Task 7 |
| 16 | `backend/app/routers/purchase_receipt.py` | Task 7 |
| 17 | `backend/app/routers/finance.py` | Task 7 |
| 18 | `backend/app/routers/backup.py` | Task 17 |
| 19 | `backend/app/schemas/ar_ap.py` | Task 8 |
| 20 | `backend/app/schemas/invoice.py` | Task 8 |
| 21 | `backend/main.py` | Task 3 + Task 17 |
| 22 | `docker-compose.yml` | Task 3 |
| 23 | 12个前端 Vue 组件 | Task 4 |
| 24 | `frontend/src/views/StockView.vue` | Task 13 |
| 25 | `frontend/src/views/CustomersView.vue` | Task 13 |
| 26 | `frontend/src/stores/accounting.js` | Task 14 |

共 ~30 个文件

---

## 验证

```bash
# 后端测试
cd /Users/lin/Desktop/erp-4/backend && python3 -m pytest tests/ -v --ignore=tests/test_auth.py

# 前端构建
cd /Users/lin/Desktop/erp-4/frontend && npx vite build
```
