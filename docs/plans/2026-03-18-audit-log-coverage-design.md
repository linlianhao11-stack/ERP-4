# 操作日志全面覆盖设计

## 背景

当前操作日志基础设施完整（`OperationLog` 模型 + `log_operation()` 服务 + 前端查看页），但覆盖率严重不足。在约 62 个状态变更端点中，仅 ~6 个有日志记录（约 10%）。用户要求达到**安全审计级别**——所有数据增删改、导出、安全事件都必须记录。

## 现状分析

### 已有日志的模块（无需改动）
- `users.py`: CREATE/UPDATE/TOGGLE/ROLE_CHANGE/PERMISSION_CHANGE ✅
- `backup.py`: CREATE/DOWNLOAD/RESTORE/DELETE ✅
- `stock.py`: RESTOCK/ADJUST/TRANSFER ✅
- `auth.py`: LOGIN_SUCCESS/PASSWORD_CHANGE ✅（但 LOGIN_FAIL 有 bug）
- `purchase_orders.py`: CREATE/PAY/APPROVE/REJECT/CANCEL/RECEIVE/RETURN ✅
- `orders.py`: CREATE/REMARK_UPDATE ✅（取消缺失）

### 缺失模块汇总

| 模块 | 缺失端点数 | 优先级 |
|------|-----------|--------|
| auth（LOGIN_FAIL bug） | 1 | P0 |
| customers | 3 | P0 |
| products（含 import/export） | 5 | P0 |
| vouchers（含 3 个批量操作） | 11 | P1 |
| logistics | 5 | P1 |
| dropship | 9 | P1 |
| invoices | 6 | P1 |
| suppliers | 2 | P1 |
| finance | 2 | P1 |
| orders（cancel 缺失） | 1 | P1 |
| chart_of_accounts | 3 | P2 |
| departments | 3 | P2 |
| warehouses | 3 | P2 |
| payment_methods（CRUD 工厂） | 3 | P2 |
| consignment（return） | 1 | P2 |
| demo（样机管理） | 若干 | P2 |
| **导出端点（跨模块）** | **12+** | **P0** |

## 设计决策

### 实现方式：手动 `log_operation()` 调用
保持现有模式，逐个端点添加。原因：
- 每条日志的 detail 可以包含精确的业务语义
- 与现有代码风格一致
- 可控性强，不会误记无关操作

### 日志命名约定
```
{TARGET_TYPE}_{ACTION}

ACTION 枚举：
- CREATE / UPDATE / DELETE     — 基础 CRUD
- SUBMIT / APPROVE / REJECT    — 审批流
- POST / UNPOST               — 凭证过账
- CANCEL / VOID               — 作废/取消
- CONFIRM                     — 确认
- SHIP                        — 发货
- PAY / REFUND                — 付款/退款
- IMPORT / EXPORT             — 数据导入导出
- BATCH_SUBMIT / BATCH_APPROVE / BATCH_POST — 批量操作
- UPLOAD / DELETE_FILE         — 附件操作

TARGET_TYPE 枚举：
- USER / AUTH（认证）
- ORDER / DROPSHIP_ORDER（订单）
- PURCHASE（采购单）
- CUSTOMER / SUPPLIER（客户/供应商）
- PRODUCT（产品）
- INVOICE（发票）
- VOUCHER（凭证）
- SHIPMENT（发货单）
- STOCK（库存）
- PAYMENT（收付款）
- ACCOUNT（科目）
- DEPARTMENT / WAREHOUSE（部门/仓库）
- CONSIGNMENT（寄售）
- DEMO_UNIT（样机）
- REPORT（报表）
- SYSTEM（系统）
```

### SECURITY_ACTIONS 扩展
以下操作类型写入安全日志文件（双写）：
```python
SECURITY_ACTIONS = {
    # 认证（现有）
    "LOGIN_FAIL", "LOGIN_SUCCESS", "PASSWORD_CHANGE",
    # 用户管理（现有）
    "USER_CREATE", "USER_TOGGLE", "USER_ROLE_CHANGE", "USER_PERMISSION_CHANGE",
    # 备份（现有）
    "BACKUP_CREATE", "BACKUP_RESTORE", "BACKUP_DELETE", "BACKUP_DOWNLOAD",
    # 发票作废（现有）
    "INVOICE_VOID",
    # 新增 — 删除操作
    "CUSTOMER_DELETE", "SUPPLIER_DELETE", "PRODUCT_DELETE",
    "VOUCHER_DELETE", "SHIPMENT_DELETE", "ORDER_CANCEL",
    # 新增 — 数据导出
    "PRODUCT_EXPORT", "STOCK_EXPORT", "VOUCHER_EXPORT",
    "REPORT_EXPORT", "LEDGER_EXPORT", "ORDER_EXPORT",
    # 新增 — 批量操作
    "VOUCHER_BATCH_SUBMIT", "VOUCHER_BATCH_APPROVE", "VOUCHER_BATCH_POST",
    "DROPSHIP_BATCH_PAY",
    # 新增 — 财务关键
    "VOUCHER_POST", "VOUCHER_UNPOST", "INVOICE_CANCEL",
}
```

## 分批实施计划

### P0 — 安全关键（第一批）

#### 1. 修复 LOGIN_FAIL bug（auth.py）
在 `login()` 的异常分支添加 `log_operation()` 调用，记录尝试登录的用户名和 IP。

#### 2. 导出端点审计（跨文件）
所有导出端点添加日志（均为 GET 请求，不改数据但需记录数据外流）：
- `products.py`: PRODUCT_EXPORT
- `stock.py`: STOCK_EXPORT
- `vouchers.py`: VOUCHER_EXPORT
- `finance.py`: ORDER_EXPORT
- `purchase_orders.py`: PURCHASE_EXPORT
- `ledgers.py`: LEDGER_EXPORT（总分类账/明细分类账/科目余额表）
- `financial_reports.py`: REPORT_EXPORT（资产负债表/利润表/现金流量表）
- `demo.py`: DEMO_EXPORT

#### 3. 客户 CRUD（customers.py）
- CUSTOMER_CREATE: `f"新建客户 {name}"`
- CUSTOMER_UPDATE: `f"更新客户 {name}"`
- CUSTOMER_DELETE: `f"删除客户 {name}"`

#### 4. 产品 CRUD + 导入（products.py）
- PRODUCT_CREATE: `f"新建产品 {sku} {name}"`
- PRODUCT_UPDATE: `f"更新产品 {sku} {name}"`
- PRODUCT_DELETE: `f"删除产品 {sku} {name}"`
- PRODUCT_IMPORT: `f"批量导入产品 {count} 条"`

### P1 — 业务关键（第二批）

#### 5. 凭证模块（vouchers.py）— 11 个端点
- VOUCHER_CREATE / UPDATE / DELETE / SUBMIT / APPROVE / REJECT / POST / UNPOST
- VOUCHER_BATCH_SUBMIT / BATCH_APPROVE / BATCH_POST
- 批量操作记录总数: `f"批量提交 {count} 张凭证"`

#### 6. 物流模块（logistics.py）— 5 个端点
- SHIPMENT_CREATE: `f"订单 {order_no} 创建发货单，承运商 {carrier}"`
- SHIPMENT_ADD: `f"订单 {order_no} 追加发货单"`
- SHIPMENT_UPDATE: `f"更新发货单 {tracking_no}"`
- SHIPMENT_UPDATE_SN: `f"更新发货单 SN 码"`
- SHIPMENT_DELETE: `f"删除发货单 {tracking_no}，库存已恢复"`

#### 7. 代发货模块（dropship.py）— 9 个端点
- DROPSHIP_CREATE / UPDATE / SUBMIT / URGE / SHIP / COMPLETE / CANCEL
- DROPSHIP_BATCH_PAY: `f"批量支付 {count} 笔代发订单"`
- DROPSHIP_REFRESH_TRACKING

#### 8. 发票模块补全（invoices.py）— 6 个端点
- INVOICE_CREATE（3 种来源）/ CONFIRM / CANCEL
- INVOICE_UPLOAD_PDF / DELETE_PDF

#### 9. 供应商模块补全（suppliers.py）— 2 个端点
- SUPPLIER_UPDATE / DELETE

#### 10. 财务模块补全（finance.py）— 2 个端点
- PAYMENT_RECORD / PAYMENT_CONFIRM

#### 11. 订单取消（orders.py）— 1 个端点
- ORDER_CANCEL: `f"取消订单 {order_no}，原因：{reason}"`

### P2 — 配置与辅助（第三批）

#### 12. 科目表（chart_of_accounts.py）
- ACCOUNT_CREATE / UPDATE / DEACTIVATE

#### 13. 部门管理（departments.py）
- DEPARTMENT_CREATE / UPDATE / DELETE

#### 14. 仓库管理（warehouses.py）
- WAREHOUSE_CREATE / UPDATE / DELETE

#### 15. 付款方式（payment_methods.py）
- 改造 CRUD 工厂函数，支持传入 target_type 参数自动记录日志
- PAYMENT_METHOD_CREATE / UPDATE / DELETE
- DISBURSEMENT_METHOD_CREATE / UPDATE / DELETE

#### 16. 寄售归还（consignment.py）
- CONSIGNMENT_RETURN

#### 17. 样机管理（demo.py）
- 检查现有日志覆盖，补全缺失操作

### P3 — 前端更新

#### 18. LogsSettings.vue 筛选下拉更新
将所有新增的 action 类型加入筛选选项，按业务模块分组：
```
认证安全: LOGIN_SUCCESS, LOGIN_FAIL, PASSWORD_CHANGE
用户管理: USER_CREATE, USER_TOGGLE, USER_ROLE_CHANGE, USER_PERMISSION_CHANGE
订单: ORDER_CREATE, ORDER_CANCEL, ORDER_REMARK_UPDATE
代发货: DROPSHIP_CREATE, DROPSHIP_SUBMIT, DROPSHIP_SHIP, ...
采购: PURCHASE_CREATE, PURCHASE_PAY, PURCHASE_APPROVE, ...
库存: STOCK_RESTOCK, STOCK_ADJUST, STOCK_TRANSFER
物流: SHIPMENT_CREATE, SHIPMENT_UPDATE, SHIPMENT_DELETE
财务: PAYMENT_CREATE, PAYMENT_CONFIRM, PAYMENT_RECORD
发票: INVOICE_CREATE, INVOICE_UPDATE, INVOICE_VOID, INVOICE_CANCEL, ...
凭证: VOUCHER_CREATE, VOUCHER_SUBMIT, VOUCHER_APPROVE, VOUCHER_POST, ...
客户/供应商: CUSTOMER_CREATE, CUSTOMER_UPDATE, SUPPLIER_CREATE, ...
产品: PRODUCT_CREATE, PRODUCT_UPDATE, PRODUCT_DELETE, PRODUCT_IMPORT, PRODUCT_EXPORT
数据导出: *_EXPORT
系统: BACKUP_CREATE, BACKUP_RESTORE, BACKUP_DOWNLOAD, BACKUP_DELETE
配置: ACCOUNT_*, DEPARTMENT_*, WAREHOUSE_*, PAYMENT_METHOD_*
```

## 约束与注意事项

1. **日志不能影响主流程** — `log_operation()` 内部已有 try/except，失败不阻塞业务
2. **批量操作记一条总日志** — 不按条目展开，避免噪音
3. **导出日志记录筛选条件** — `f"导出库存 Excel（仓库：{warehouse_name}）"`
4. **LOGIN_FAIL 需特殊处理** — 登录失败时可能没有有效 user 对象，需 `operator=None` 或查找用户
5. **保持 detail 中文描述** — 与现有日志风格一致
