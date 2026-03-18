# 操作日志全面覆盖实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将操作日志覆盖率从 ~10% 提升到 100%，达到安全审计级别

**Architecture:** 在现有 `log_operation()` 手动调用模式基础上，逐文件补全所有状态变更端点的日志记录。需要小改 OperationLog 模型使 operator 可空（支持 LOGIN_FAIL 记录匿名用户），扩展 SECURITY_ACTIONS 集合，最后更新前端筛选下拉。

**Tech Stack:** FastAPI + Tortoise ORM（后端）、Vue 3（前端筛选组件）

---

## Task 1: 模型和服务层改造

**Files:**
- Modify: `backend/app/models/operation_log.py:10`
- Modify: `backend/app/services/operation_log_service.py`

**Step 1: 修改 OperationLog 模型，使 operator 可空**

```python
# backend/app/models/operation_log.py:10
# 将:
operator = fields.ForeignKeyField("models.User", related_name="operation_logs", on_delete=fields.RESTRICT)
# 改为:
operator = fields.ForeignKeyField("models.User", related_name="operation_logs", on_delete=fields.RESTRICT, null=True)
```

**Step 2: 生成并执行数据库迁移**

Run: `cd /Users/lin/Desktop/erp-4 && python -m backend.app.migrate`
如果项目不使用自动迁移工具，直接执行 SQL：
```sql
ALTER TABLE operation_logs ALTER COLUMN operator_id DROP NOT NULL;
```

**Step 3: 扩展 SECURITY_ACTIONS 并处理空 user**

```python
# backend/app/services/operation_log_service.py — 完整替换
from app.models import OperationLog
from app.logger import get_logger

logger = get_logger("audit")

# 安全相关的操作类型（双写：DB + 安全日志文件）
SECURITY_ACTIONS = {
    # 认证
    "LOGIN_FAIL", "LOGIN_SUCCESS", "PASSWORD_CHANGE",
    # 用户管理
    "USER_CREATE", "USER_TOGGLE", "USER_ROLE_CHANGE", "USER_PERMISSION_CHANGE",
    # 备份
    "BACKUP_CREATE", "BACKUP_RESTORE", "BACKUP_DELETE", "BACKUP_DOWNLOAD",
    # 删除操作
    "CUSTOMER_DELETE", "SUPPLIER_DELETE", "PRODUCT_DELETE",
    "VOUCHER_DELETE", "SHIPMENT_DELETE", "ORDER_CANCEL",
    # 发票
    "INVOICE_VOID", "INVOICE_CANCEL",
    # 数据导出
    "PRODUCT_EXPORT", "STOCK_EXPORT", "VOUCHER_EXPORT",
    "REPORT_EXPORT", "LEDGER_EXPORT", "ORDER_EXPORT",
    "DEMO_EXPORT", "AI_EXPORT",
    # 批量操作
    "VOUCHER_BATCH_SUBMIT", "VOUCHER_BATCH_APPROVE", "VOUCHER_BATCH_POST",
    "DROPSHIP_BATCH_PAY",
    # 财务关键
    "VOUCHER_POST", "VOUCHER_UNPOST",
}


async def log_operation(user, action, target_type, target_id=None, detail=None):
    try:
        await OperationLog.create(
            action=action, target_type=target_type,
            target_id=target_id, detail=detail,
            operator=user  # 允许 None（如 LOGIN_FAIL）
        )
    except Exception as e:
        logger.error(f"记录操作日志失败: {e}", exc_info=e)
    if action in SECURITY_ACTIONS:
        username = user.username if user and hasattr(user, "username") else "(匿名)"
        logger.info(f"[安全审计] {action} by {username}: {detail}")
```

**Step 4: 提交**

```bash
git add backend/app/models/operation_log.py backend/app/services/operation_log_service.py
git commit -m "feat: OperationLog operator 可空 + 扩展 SECURITY_ACTIONS"
```

---

## Task 2: P0 — 修复 LOGIN_FAIL + 认证日志

**Files:**
- Modify: `backend/app/routers/auth.py:54-57`

**Step 1: 在登录失败分支添加 LOGIN_FAIL 日志**

在 `auth.py` 的 `login` 函数中，找到失败分支（line 54-57）：
```python
        if not user or not verify_password(data.password, user.password_hash):
            attempts.append(now_ts)
            _login_attempts[client_ip] = attempts
            raise HTTPException(status_code=401, detail="用户名或密码错误")
```

改为：
```python
        if not user or not verify_password(data.password, user.password_hash):
            attempts.append(now_ts)
            _login_attempts[client_ip] = attempts
            await log_operation(user, "LOGIN_FAIL", "AUTH", None,
                f"登录失败，用户名: {data.username}，IP: {client_ip}")
            raise HTTPException(status_code=401, detail="用户名或密码错误")
```

注意：`user` 可能为 None（用户不存在）或有效 User（密码错误），Task 1 已使 operator 可空。

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && npm run build --prefix frontend`

**Step 3: 提交**

```bash
git add backend/app/routers/auth.py
git commit -m "fix: 补全 LOGIN_FAIL 操作日志记录"
```

---

## Task 3: P0 — 客户模块日志

**Files:**
- Modify: `backend/app/routers/customers.py`

**Step 1: 添加 log_operation 导入和所有 CRUD 日志**

在 customers.py 顶部添加导入：
```python
from app.services.operation_log_service import log_operation
```

在 `create_customer` 函数（line ~27）的 return 前添加：
```python
    await log_operation(user, "CUSTOMER_CREATE", "CUSTOMER", c.id, f"新建客户 {c.name}")
```

在 `update_customer` 函数（line ~36）的 return 前添加：
```python
    await log_operation(user, "CUSTOMER_UPDATE", "CUSTOMER", c.id, f"更新客户 {c.name}")
```

在 `delete_customer` 函数（line ~55）的 return 前添加：
```python
    await log_operation(user, "CUSTOMER_DELETE", "CUSTOMER", c.id, f"删除客户 {c.name}")
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && npm run build --prefix frontend`

**Step 3: 提交**

```bash
git add backend/app/routers/customers.py
git commit -m "feat: 客户模块操作日志（CREATE/UPDATE/DELETE）"
```

---

## Task 4: P0 — 产品模块日志

**Files:**
- Modify: `backend/app/routers/products.py`

**Step 1: 为所有 CRUD + 导入导出端点添加日志**

products.py 已导入 `log_operation`（line 18），但未使用。添加：

在 `export_products`（line ~127）的 return StreamingResponse 前添加：
```python
    await log_operation(user, "PRODUCT_EXPORT", "PRODUCT", None, "导出产品列表 Excel")
```

在 `import_products`（line ~225 区域）事务成功后、return 前添加：
```python
    await log_operation(user, "PRODUCT_IMPORT", "PRODUCT", None,
        f"批量导入产品，新增 {created} 条，更新 {updated} 条")
```
注意：需确认函数内统计变量名（created/updated 计数），按实际变量名调整。

在 `create_product`（line ~531）return 前添加：
```python
    await log_operation(user, "PRODUCT_CREATE", "PRODUCT", p.id, f"新建产品 {p.sku} {p.name}")
```

在 `update_product`（line ~542）return 前添加：
```python
    await log_operation(user, "PRODUCT_UPDATE", "PRODUCT", p.id, f"更新产品 {p.sku} {p.name}")
```

在 `delete_product`（line ~552）return 前添加：
```python
    await log_operation(user, "PRODUCT_DELETE", "PRODUCT", p.id, f"删除产品 {p.sku} {p.name}")
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && npm run build --prefix frontend`

**Step 3: 提交**

```bash
git add backend/app/routers/products.py
git commit -m "feat: 产品模块操作日志（CRUD + 导入导出）"
```

---

## Task 5: P0 — 所有导出端点日志

**Files:**
- Modify: `backend/app/routers/stock.py`（export_stock）
- Modify: `backend/app/routers/vouchers.py`（export_voucher_entries）
- Modify: `backend/app/routers/finance.py`（export_orders）
- Modify: `backend/app/routers/purchase_orders.py`（export_purchase_orders）
- Modify: `backend/app/routers/ledgers.py`（3 个 export 端点）
- Modify: `backend/app/routers/financial_reports.py`（3 个 export 端点）
- Modify: `backend/app/routers/demo.py`（export_units）
- Modify: `backend/app/routers/ai_chat.py`（ai_export）

**Step 1: 逐文件添加导出日志**

每个导出端点在 return StreamingResponse 前添加一行 `await log_operation(...)`。以下是每个文件的具体代码：

**stock.py**（已导入 log_operation）：
```python
# export_stock 函数（line ~245），return 前
await log_operation(user, "STOCK_EXPORT", "STOCK", None, "导出库存列表 Excel")
```

**vouchers.py**（需添加导入）：
```python
# 文件顶部添加:
from app.services.operation_log_service import log_operation
# export_voucher_entries 函数（line ~239），return 前
await log_operation(user, "VOUCHER_EXPORT", "VOUCHER", None, "导出凭证分录 Excel")
```

**finance.py**（已导入 log_operation）：
```python
# export_orders 函数（line ~201），return 前
await log_operation(user, "ORDER_EXPORT", "ORDER", None, "导出订单列表 Excel")
```

**purchase_orders.py**（已导入 log_operation）：
```python
# export_purchase_orders 函数（line ~103），return 前
await log_operation(user, "PURCHASE_EXPORT", "PURCHASE_ORDER", None, "导出采购单列表 Excel")
```

**ledgers.py**（需添加导入）：
```python
# 文件顶部添加:
from app.services.operation_log_service import log_operation
# export_general_ledger_api（line ~67），return 前
await log_operation(user, "LEDGER_EXPORT", "LEDGER", None, f"导出总分类账 {result['account_code']} {start_period}")
# export_detail_ledger_api（line ~88），return 前
await log_operation(user, "LEDGER_EXPORT", "LEDGER", None, f"导出明细分类账 {result['account_code']} {start_period}")
# export_trial_balance_api（line ~112），return 前
await log_operation(user, "LEDGER_EXPORT", "LEDGER", None, f"导出科目余额表 {period_name}")
```

**financial_reports.py**（需添加导入）：
```python
# 文件顶部添加:
from app.auth.dependencies import get_current_user
from app.models import User
from app.services.operation_log_service import log_operation
# 每个 export 函数签名需添加 user 参数（如果没有的话）
# api_export_balance_sheet（line ~42），return 前
await log_operation(user, "REPORT_EXPORT", "REPORT", None, f"导出资产负债表 {period_name}")
# api_export_income_statement（line ~66），return 前
await log_operation(user, "REPORT_EXPORT", "REPORT", None, f"导出利润表 {period_name}")
# api_export_cash_flow（line ~90），return 前
await log_operation(user, "REPORT_EXPORT", "REPORT", None, f"导出现金流量表 {period_name}")
```
注意：检查 financial_reports.py 的 export 端点是否已有 `user` 参数依赖。如果没有，需要添加 `user: User = Depends(get_current_user)` 到函数签名。

**demo.py**（需添加导入）：
```python
# 文件顶部添加:
from app.services.operation_log_service import log_operation
# export_units 函数（line ~192），return 前
await log_operation(user, "DEMO_EXPORT", "DEMO_UNIT", None, "导出样机列表 Excel")
```

**ai_chat.py**（需添加导入）：
```python
# 文件顶部添加:
from app.services.operation_log_service import log_operation
# ai_export 函数（line ~113），return 前
await log_operation(user, "AI_EXPORT", "SYSTEM", None, f"AI 对话导出 Excel: {body.title}")
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && npm run build --prefix frontend`

**Step 3: 提交**

```bash
git add backend/app/routers/stock.py backend/app/routers/vouchers.py backend/app/routers/finance.py backend/app/routers/purchase_orders.py backend/app/routers/ledgers.py backend/app/routers/financial_reports.py backend/app/routers/demo.py backend/app/routers/ai_chat.py
git commit -m "feat: 所有导出端点添加操作日志审计"
```

---

## Task 6: P1 — 凭证模块日志（11 个端点）

**Files:**
- Modify: `backend/app/routers/vouchers.py`

**Step 1: 为所有凭证 CRUD 和审批流端点添加日志**

vouchers.py 在 Task 5 已添加导入。补充所有端点日志：

```python
# create_voucher（line ~339），return 前（line ~413 前）
await log_operation(user, "VOUCHER_CREATE", "VOUCHER", v.id, f"创建凭证 {voucher_no}")

# update_voucher（line ~417），return 前（line ~484 前）
await log_operation(user, "VOUCHER_UPDATE", "VOUCHER", v.id, f"更新凭证 {v.voucher_no}")

# delete_voucher（line ~488），return 前（line ~500 前）
await log_operation(user, "VOUCHER_DELETE", "VOUCHER", v.id, f"删除凭证 {v.voucher_no}")

# submit_voucher（line ~504），return 前（line ~515 前）
await log_operation(user, "VOUCHER_SUBMIT", "VOUCHER", v.id, f"提交凭证 {v.voucher_no}")

# approve_voucher（line ~519），return 前（line ~538 前）
await log_operation(user, "VOUCHER_APPROVE", "VOUCHER", v.id, f"审核凭证 {v.voucher_no}")

# reject_voucher（line ~542），return 前（line ~553 前）
await log_operation(user, "VOUCHER_REJECT", "VOUCHER", v.id, f"驳回凭证 {v.voucher_no}")

# post_voucher（line ~557），return 前（line ~570 前）
await log_operation(user, "VOUCHER_POST", "VOUCHER", v.id, f"过账凭证 {v.voucher_no}")

# unpost_voucher（line ~574），return 前（line ~592 前）
await log_operation(user, "VOUCHER_UNPOST", "VOUCHER", v.id, f"反过账凭证 {v.voucher_no}")

# batch_submit_vouchers（line ~101），return 前（line ~116 前）
await log_operation(user, "VOUCHER_BATCH_SUBMIT", "VOUCHER", None, f"批量提交 {success} 张凭证")

# batch_approve_vouchers（line ~120），return 前（line ~141 前）
await log_operation(user, "VOUCHER_BATCH_APPROVE", "VOUCHER", None, f"批量审核 {success} 张凭证")

# batch_post_vouchers（line ~145），return 前（line ~168 前）
await log_operation(user, "VOUCHER_BATCH_POST", "VOUCHER", None, f"批量过账 {success} 张凭证")
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && npm run build --prefix frontend`

**Step 3: 提交**

```bash
git add backend/app/routers/vouchers.py
git commit -m "feat: 凭证模块全部操作日志（CRUD + 审批流 + 批量操作）"
```

---

## Task 7: P1 — 物流模块日志（5-7 个端点）

**Files:**
- Modify: `backend/app/routers/logistics.py`

**Step 1: 添加导入和所有发货端点日志**

```python
# 文件顶部添加:
from app.services.operation_log_service import log_operation
```

```python
# ship_order_items（line ~300），return 前
await log_operation(user, "SHIPMENT_CREATE", "SHIPMENT", shipment.id,
    f"订单 {order.order_no} 创建发货单，承运商 {data.carrier or '未指定'}")

# add_shipment（line ~520），return 前
await log_operation(user, "SHIPMENT_ADD", "SHIPMENT", shipment.id,
    f"订单 {order.order_no} 追加发货单")

# ship_order（line ~563），return 前
await log_operation(user, "SHIPMENT_UPDATE", "SHIPMENT", shipment.id,
    f"更新发货单 {shipment.tracking_no or shipment.id}")

# update_shipment_sn（line ~603），return 前
await log_operation(user, "SHIPMENT_UPDATE_SN", "SHIPMENT", shipment.id,
    f"更新发货单 SN 码 #{shipment.id}")

# delete_shipment（line ~628），return 前
await log_operation(user, "SHIPMENT_DELETE", "SHIPMENT", shipment.id,
    f"删除发货单 #{shipment.id}，订单 {order.order_no}")
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && npm run build --prefix frontend`

**Step 3: 提交**

```bash
git add backend/app/routers/logistics.py
git commit -m "feat: 物流模块操作日志（发货/追加/更新/删除）"
```

---

## Task 8: P1 — 代发货模块日志（9 个端点）

**Files:**
- Modify: `backend/app/routers/dropship.py`

**Step 1: 添加导入和所有代发货端点日志**

```python
# 文件顶部添加:
from app.services.operation_log_service import log_operation
```

```python
# create_order（line ~501），return 前
await log_operation(user, "DROPSHIP_CREATE", "DROPSHIP_ORDER", order.id,
    f"创建代发订单 {order.ds_no}")

# update_order（line ~519），return 前
await log_operation(user, "DROPSHIP_UPDATE", "DROPSHIP_ORDER", order.id,
    f"更新代发订单 {order.ds_no}")

# submit_order（line ~579），return 前
await log_operation(user, "DROPSHIP_SUBMIT", "DROPSHIP_ORDER", order.id,
    f"提交代发订单 {order.ds_no}")

# urge_payment（line ~597），return 前
await log_operation(user, "DROPSHIP_URGE", "DROPSHIP_ORDER", order.id,
    f"催付代发订单 {order.ds_no}")

# batch_pay（line ~623），return 前
await log_operation(user, "DROPSHIP_BATCH_PAY", "DROPSHIP_ORDER", None,
    f"批量支付代发订单 {len(data.order_ids)} 笔")

# ship_order（line ~641），return 前
await log_operation(user, "DROPSHIP_SHIP", "DROPSHIP_ORDER", order.id,
    f"代发订单 {order.ds_no} 确认发货")

# refresh_tracking（line ~668），return 前
await log_operation(user, "DROPSHIP_REFRESH", "DROPSHIP_ORDER", order.id,
    f"刷新代发订单 {order.ds_no} 物流信息")

# complete_order（line ~714），return 前
await log_operation(user, "DROPSHIP_COMPLETE", "DROPSHIP_ORDER", order.id,
    f"完成代发订单 {order.ds_no}")

# cancel_order（line ~743），return 前
await log_operation(user, "DROPSHIP_CANCEL", "DROPSHIP_ORDER", order.id,
    f"取消代发订单 {order.ds_no}，原因: {data.reason or '未填写'}")
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && npm run build --prefix frontend`

**Step 3: 提交**

```bash
git add backend/app/routers/dropship.py
git commit -m "feat: 代发货模块全部操作日志（9 个端点）"
```

---

## Task 9: P1 — 发票模块补全（6 个端点）

**Files:**
- Modify: `backend/app/routers/invoices.py`

**Step 1: 为缺失端点添加日志**

invoices.py 已导入 `log_operation`，已有 INVOICE_UPDATE 和 INVOICE_VOID 日志。补充缺失的：

```python
# create_invoice_from_receivable（line ~166），return 前
await log_operation(user, "INVOICE_CREATE", "INVOICE", inv.id,
    f"从应收创建发票 {inv.invoice_no}")

# create_invoice_from_payable（line ~188），return 前
await log_operation(user, "INVOICE_CREATE", "INVOICE", inv.id,
    f"从应付创建发票 {inv.invoice_no}")

# create_input_invoice_endpoint（line ~210），return 前
await log_operation(user, "INVOICE_CREATE", "INVOICE", inv.id,
    f"手工创建进项发票 {inv.invoice_no}")

# confirm_invoice_endpoint（line ~294），return 前
await log_operation(user, "INVOICE_CONFIRM", "INVOICE", inv.id,
    f"确认发票 {inv.invoice_no}")

# upload_invoice_pdf（line ~320），return 前
await log_operation(user, "INVOICE_UPLOAD_PDF", "INVOICE", inv.id,
    f"上传发票 PDF {inv.invoice_no}")

# delete_invoice_pdf（line ~434），return 前
await log_operation(user, "INVOICE_DELETE_PDF", "INVOICE", inv.id,
    f"删除发票 PDF {inv.invoice_no} 第 {index + 1} 张")
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && npm run build --prefix frontend`

**Step 3: 提交**

```bash
git add backend/app/routers/invoices.py
git commit -m "feat: 发票模块补全操作日志（创建/确认/PDF 上传删除）"
```

---

## Task 10: P1 — 供应商模块补全

**Files:**
- Modify: `backend/app/routers/suppliers.py`

**Step 1: 为缺失端点添加日志**

suppliers.py 已导入 `log_operation`，已有 SUPPLIER_CREATE 和 CREDIT_REFUND。补充：

```python
# update_supplier（line ~156），return 前
await log_operation(user, "SUPPLIER_UPDATE", "SUPPLIER", s.id, f"更新供应商 {s.name}")

# delete_supplier（line ~167），return 前
await log_operation(user, "SUPPLIER_DELETE", "SUPPLIER", s.id, f"删除供应商 {s.name}")

# import_suppliers（line ~32），return 前（如果有 created 计数）
await log_operation(user, "SUPPLIER_IMPORT", "SUPPLIER", None,
    f"批量导入供应商，新增 {created} 条，跳过 {skipped} 条")
```

**Step 2: 提交**

```bash
git add backend/app/routers/suppliers.py
git commit -m "feat: 供应商模块补全操作日志（UPDATE/DELETE/IMPORT）"
```

---

## Task 11: P1 — 订单取消日志确认

**Files:**
- Check: `backend/app/routers/orders.py`

**Step 1: 确认 ORDER_CANCEL 已有日志**

根据探索结果，orders.py 已有 ORDER_CANCEL 日志（line ~784-785 和 ~884-885）。只需**确认**这些日志完整覆盖了所有取消路径（直接取消 + 拆分取消 + 退款取消）。如果缺失则补全。

**Step 2: 如无需改动则跳过提交**

---

## Task 12: P2 — 科目表模块日志

**Files:**
- Modify: `backend/app/routers/chart_of_accounts.py`

**Step 1: 添加导入和日志**

```python
# 文件顶部添加:
from app.services.operation_log_service import log_operation

# create_account（line ~35），return 前
# 注意：检查创建后的 account 对象变量名
await log_operation(user, "ACCOUNT_CREATE", "ACCOUNT", account.id,
    f"新建科目 {data.code} {data.name}")

# update_account（line ~76），return 前
await log_operation(user, "ACCOUNT_UPDATE", "ACCOUNT", account.id,
    f"更新科目 {account.code} {account.name}")

# deactivate_account（line ~91），return 前
await log_operation(user, "ACCOUNT_DEACTIVATE", "ACCOUNT", account.id,
    f"停用科目 {account.code} {account.name}")
```

**Step 2: 提交**

```bash
git add backend/app/routers/chart_of_accounts.py
git commit -m "feat: 科目表操作日志（CREATE/UPDATE/DEACTIVATE）"
```

---

## Task 13: P2 — 部门管理日志

**Files:**
- Modify: `backend/app/routers/departments.py`

**Step 1: 添加导入和日志**

```python
# 文件顶部添加:
from app.services.operation_log_service import log_operation

# create_department（line ~28），return 前
await log_operation(user, "DEPARTMENT_CREATE", "DEPARTMENT", dept.id,
    f"新建部门 {data.code} {data.name}")

# update_department（line ~39），return 前
await log_operation(user, "DEPARTMENT_UPDATE", "DEPARTMENT", dept.id,
    f"更新部门 {dept.code} {dept.name}")

# delete_department（line ~54），return 前
await log_operation(user, "DEPARTMENT_DELETE", "DEPARTMENT", dept.id,
    f"删除部门 {dept.code} {dept.name}")
```

注意：检查实际变量名（可能是 `d` 或 `dept`）。

**Step 2: 提交**

```bash
git add backend/app/routers/departments.py
git commit -m "feat: 部门管理操作日志（CREATE/UPDATE/DELETE）"
```

---

## Task 14: P2 — 仓库管理日志

**Files:**
- Modify: `backend/app/routers/warehouses.py`

**Step 1: 添加导入和日志**

```python
# 文件顶部添加:
from app.services.operation_log_service import log_operation

# create_warehouse（line ~44），return 前
await log_operation(user, "WAREHOUSE_CREATE", "WAREHOUSE", wh.id,
    f"新建仓库 {data.name}")

# update_warehouse（line ~59），return 前
await log_operation(user, "WAREHOUSE_UPDATE", "WAREHOUSE", wh.id,
    f"更新仓库 {wh.name}")

# delete_warehouse（line ~79），return 前
await log_operation(user, "WAREHOUSE_DELETE", "WAREHOUSE", wh.id,
    f"删除仓库 {wh.name}")
```

**Step 2: 提交**

```bash
git add backend/app/routers/warehouses.py
git commit -m "feat: 仓库管理操作日志（CREATE/UPDATE/DELETE）"
```

---

## Task 15: P2 — CRUD 工厂日志

**Files:**
- Modify: `backend/app/routers/crud_factory.py`

**Step 1: 改造工厂函数支持日志**

```python
# crud_factory.py — 在顶部添加导入:
from app.services.operation_log_service import log_operation

# create_method（line 49），在 return 前（line 69 前）添加:
        await log_operation(user, f"{entity_name.upper()}_CREATE", entity_name.upper(), m.id,
            f"新增{tag} {code} {name}")

# update_method（line 71），在 return 前（line 90 前）添加:
        await log_operation(user, f"{entity_name.upper()}_UPDATE", entity_name.upper(), m.id,
            f"更新{tag} {m.code} {m.name}")

# delete_method（line 92），在 return 前（line 99 前）添加:
        await log_operation(user, f"{entity_name.upper()}_DELETE", entity_name.upper(), m.id,
            f"删除{tag} {m.code} {m.name}")
```

注意：`entity_name` 和 `tag` 来自工厂参数，确保 action 和 target_type 命名合理。检查 payment_methods.py 传入的 entity_name 值。

**Step 2: 提交**

```bash
git add backend/app/routers/crud_factory.py
git commit -m "feat: CRUD 工厂添加通用操作日志"
```

---

## Task 16: P2 — 寄售归还 + 样机管理日志

**Files:**
- Modify: `backend/app/routers/consignment.py`
- Modify: `backend/app/routers/demo.py`

**Step 1: 寄售归还日志**

```python
# consignment.py 顶部添加:
from app.services.operation_log_service import log_operation

# consignment_return（line ~381），return 前
await log_operation(user, "CONSIGNMENT_RETURN", "CONSIGNMENT", None,
    f"寄售归还，客户 ID: {data.customer_id}，共 {len(data.items)} 项")
```

**Step 2: 样机管理日志**

demo.py 在 Task 5 已添加导入。为所有状态变更端点添加日志：

```python
# create_unit（line ~315），return 前
await log_operation(user, "DEMO_CREATE", "DEMO_UNIT", unit.id, f"新建样机 {unit.sn or unit.id}")

# update_unit（line ~355），return 前
await log_operation(user, "DEMO_UPDATE", "DEMO_UNIT", unit_id, f"更新样机 #{unit_id}")

# delete_unit（line ~375），return 前
await log_operation(user, "DEMO_DELETE", "DEMO_UNIT", unit_id, f"删除样机 #{unit_id}")

# create_loan（line ~421），return 前
await log_operation(user, "DEMO_LOAN_CREATE", "DEMO_UNIT", loan.unit_id, f"创建借出申请 #{loan.id}")

# approve_loan（line ~442），return 前
await log_operation(user, "DEMO_LOAN_APPROVE", "DEMO_UNIT", loan_id, f"审批借出 #{loan_id}")

# reject_loan（line ~452），return 前
await log_operation(user, "DEMO_LOAN_REJECT", "DEMO_UNIT", loan_id, f"拒绝借出 #{loan_id}")

# lend_unit（line ~462），return 前
await log_operation(user, "DEMO_LEND", "DEMO_UNIT", loan_id, f"执行借出 #{loan_id}")

# return_unit（line ~472），return 前
await log_operation(user, "DEMO_RETURN", "DEMO_UNIT", loan_id, f"归还样机 #{loan_id}")

# sell_unit（line ~485），return 前
await log_operation(user, "DEMO_SELL", "DEMO_UNIT", unit_id, f"出售样机 #{unit_id}")

# convert_unit（line ~495），return 前
await log_operation(user, "DEMO_CONVERT", "DEMO_UNIT", unit_id, f"转自用样机 #{unit_id}")

# scrap_unit（line ~505），return 前
await log_operation(user, "DEMO_SCRAP", "DEMO_UNIT", unit_id, f"报废样机 #{unit_id}")

# report_loss（line ~515），return 前
await log_operation(user, "DEMO_LOSS", "DEMO_UNIT", unit_id, f"报损样机 #{unit_id}")
```

注意：每个端点的返回值变量名需要根据实际代码确认（如 `unit` vs 返回的 dict）。许多端点调用 service 函数返回对象，确认返回值结构。

**Step 3: 提交**

```bash
git add backend/app/routers/consignment.py backend/app/routers/demo.py
git commit -m "feat: 寄售归还 + 样机管理操作日志"
```

---

## Task 17: 前端筛选下拉更新

**Files:**
- Modify: `frontend/src/components/business/settings/LogsSettings.vue`

**Step 1: 更新筛选选项为分组下拉**

将现有的 12 个选项替换为完整的分组列表：

```html
<select v-model="opLogFilter" class="...">
  <option value="">全部操作</option>
  <optgroup label="认证安全">
    <option value="LOGIN_SUCCESS">登录成功</option>
    <option value="LOGIN_FAIL">登录失败</option>
    <option value="PASSWORD_CHANGE">修改密码</option>
  </optgroup>
  <optgroup label="用户管理">
    <option value="USER_CREATE">创建用户</option>
    <option value="USER_TOGGLE">禁用/启用用户</option>
    <option value="USER_ROLE_CHANGE">角色变更</option>
    <option value="USER_PERMISSION_CHANGE">权限变更</option>
  </optgroup>
  <optgroup label="订单">
    <option value="ORDER_CREATE">创建订单</option>
    <option value="ORDER_CANCEL">取消订单</option>
    <option value="ORDER_UPDATE_REMARK">修改备注</option>
  </optgroup>
  <optgroup label="代发货">
    <option value="DROPSHIP_CREATE">创建代发</option>
    <option value="DROPSHIP_SUBMIT">提交代发</option>
    <option value="DROPSHIP_SHIP">代发发货</option>
    <option value="DROPSHIP_COMPLETE">完成代发</option>
    <option value="DROPSHIP_CANCEL">取消代发</option>
    <option value="DROPSHIP_BATCH_PAY">批量支付</option>
  </optgroup>
  <optgroup label="采购">
    <option value="PURCHASE_CREATE">采购下单</option>
    <option value="PURCHASE_PAY">采购付款</option>
    <option value="PURCHASE_APPROVE">采购审核</option>
    <option value="PURCHASE_REJECT">采购拒绝</option>
    <option value="PURCHASE_CANCEL">采购取消</option>
    <option value="PURCHASE_RECEIVE">采购收货</option>
    <option value="PURCHASE_RETURN">采购退货</option>
  </optgroup>
  <optgroup label="库存">
    <option value="STOCK_RESTOCK">入库</option>
    <option value="STOCK_ADJUST">库存调整</option>
    <option value="STOCK_TRANSFER">库存调拨</option>
  </optgroup>
  <optgroup label="物流">
    <option value="SHIPMENT_CREATE">创建发货单</option>
    <option value="SHIPMENT_UPDATE">更新发货单</option>
    <option value="SHIPMENT_DELETE">删除发货单</option>
  </optgroup>
  <optgroup label="财务收款">
    <option value="PAYMENT_CREATE">账期收款</option>
    <option value="PAYMENT_CONFIRM">确认收款</option>
  </optgroup>
  <optgroup label="发票">
    <option value="INVOICE_CREATE">创建发票</option>
    <option value="INVOICE_UPDATE">更新发票</option>
    <option value="INVOICE_CONFIRM">确认发票</option>
    <option value="INVOICE_VOID">作废发票</option>
    <option value="INVOICE_CANCEL">取消发票</option>
  </optgroup>
  <optgroup label="凭证">
    <option value="VOUCHER_CREATE">创建凭证</option>
    <option value="VOUCHER_SUBMIT">提交凭证</option>
    <option value="VOUCHER_APPROVE">审核凭证</option>
    <option value="VOUCHER_REJECT">驳回凭证</option>
    <option value="VOUCHER_POST">过账</option>
    <option value="VOUCHER_UNPOST">反过账</option>
    <option value="VOUCHER_BATCH_SUBMIT">批量提交</option>
    <option value="VOUCHER_BATCH_APPROVE">批量审核</option>
    <option value="VOUCHER_BATCH_POST">批量过账</option>
  </optgroup>
  <optgroup label="客户/供应商">
    <option value="CUSTOMER_CREATE">新建客户</option>
    <option value="CUSTOMER_UPDATE">更新客户</option>
    <option value="CUSTOMER_DELETE">删除客户</option>
    <option value="SUPPLIER_CREATE">新建供应商</option>
    <option value="SUPPLIER_UPDATE">更新供应商</option>
    <option value="SUPPLIER_DELETE">删除供应商</option>
    <option value="CREDIT_REFUND">在账资金退款</option>
  </optgroup>
  <optgroup label="产品">
    <option value="PRODUCT_CREATE">新建产品</option>
    <option value="PRODUCT_UPDATE">更新产品</option>
    <option value="PRODUCT_DELETE">删除产品</option>
    <option value="PRODUCT_IMPORT">导入产品</option>
  </optgroup>
  <optgroup label="数据导出">
    <option value="PRODUCT_EXPORT">导出产品</option>
    <option value="STOCK_EXPORT">导出库存</option>
    <option value="ORDER_EXPORT">导出订单</option>
    <option value="PURCHASE_EXPORT">导出采购单</option>
    <option value="VOUCHER_EXPORT">导出凭证</option>
    <option value="LEDGER_EXPORT">导出账簿</option>
    <option value="REPORT_EXPORT">导出报表</option>
    <option value="DEMO_EXPORT">导出样机</option>
  </optgroup>
  <optgroup label="系统">
    <option value="BACKUP_CREATE">创建备份</option>
    <option value="BACKUP_RESTORE">恢复备份</option>
    <option value="BACKUP_DOWNLOAD">下载备份</option>
    <option value="BACKUP_DELETE">删除备份</option>
  </optgroup>
</select>
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && npm run build --prefix frontend`

**Step 3: 提交**

```bash
git add frontend/src/components/business/settings/LogsSettings.vue
git commit -m "feat: 操作日志筛选下拉更新为完整分组列表"
```

---

## Task 18: 最终验证 + 数据库迁移

**Step 1: 运行完整构建**

Run: `cd /Users/lin/Desktop/erp-4 && npm run build --prefix frontend`

**Step 2: 检查数据库迁移**

确保 OperationLog 的 operator 字段已改为可空。如果使用 Aerich：
```bash
cd /Users/lin/Desktop/erp-4 && aerich migrate --name audit_log_operator_nullable
aerich upgrade
```
如果手动管理迁移：
```sql
ALTER TABLE operation_logs ALTER COLUMN operator_id DROP NOT NULL;
```

**Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: 操作日志全面覆盖 — 安全审计级别（58 个端点）"
```
