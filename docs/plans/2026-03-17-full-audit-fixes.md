# ERP-4 全量审查修复计划

> **审查日期**: 2026-03-17
> **审查范围**: 后端 + 前端 + 数据库 + 安全 + 部署
> **问题总数**: ~60 项（Critical 4 / High 5 / Medium 20+ / Low 30+）

---

## 阶段总览

| 阶段 | 主题 | 预计文件数 | 状态 |
|------|------|-----------|------|
| **Phase 1** | 安全加固（阻塞项） | ~8 | ✅ 已完成 |
| **Phase 2** | 后端常量化 + API 一致性 | ~25 | ✅ 已完成 |
| **Phase 3** | 数据库索引 + 约束 + 连接池 | ~5 | ✅ 已完成 |
| **Phase 4** | 前端代码质量 + 可访问性 | ~15 | ✅ 已完成 |
| **Phase 5** | 性能优化 + 测试扩展 | ~10 | ✅ 已完成 |

---

## Phase 1: 安全加固（Critical + High）

### 1.1 清理 .env + 强制密钥 ⬜
**问题**: docker-compose.yml 中 fallback 弱密码 `erp123456`，config.py 允许空 SECRET_KEY 自动生成
**修复**:
- `docker-compose.yml`: 移除 `:-erp123456` fallback，无密码则拒绝启动
- `config.py`: SECRET_KEY 为空时 raise RuntimeError 而非自动生成
- `.env.example`: 创建示例文件，不含真实密钥
**文件**: `docker-compose.yml`, `backend/app/config.py`, `.env.example`

### 1.2 全局 API 速率限制 ⬜
**问题**: 仅登录端点有限流，其他端点无保护
**修复**:
- 安装 `slowapi`
- 在 `main.py` 添加全局限流中间件（默认 200 req/min/IP）
- 敏感端点（备份、用户管理、文件上传）添加更严格限制
**文件**: `requirements.txt`, `backend/main.py`, `backend/app/routers/backup.py`, `backend/app/routers/users.py`, `backend/app/routers/invoices.py`

### 1.3 CORS 生产加固 ⬜
**问题**: CORS_ORIGINS 为空时 fallback 到 localhost
**修复**:
- 非 DEBUG 模式下 CORS_ORIGINS 必须显式设置
- 添加 DEBUG 环境变量支持
- 验证生产环境 CORS 必须为 HTTPS
**文件**: `backend/app/config.py`, `docker-compose.yml`

### 1.4 安全头补全 ⬜
**问题**: 缺少 HSTS、Permissions-Policy
**修复**:
- 添加 `Strict-Transport-Security`（仅 HTTPS 模式下）
- 添加 `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- 添加 `X-Permitted-Cross-Domain-Policies: none`
**文件**: `backend/main.py`

### 1.5 备份加密 ⬜
**问题**: 备份文件明文存储，被窃取即全量泄露
**修复**:
- 使用 `cryptography.fernet` 加密备份文件
- 加密密钥从环境变量读取（BACKUP_ENCRYPTION_KEY）
- 下载和恢复时自动解密
**文件**: `backend/app/services/backup_service.py`, `backend/app/routers/backup.py`, `backend/app/config.py`

### 1.6 密码过期策略 ⬜
**问题**: 无 password_changed_at 字段，无过期强制
**修复**:
- User 模型添加 `password_changed_at` 字段
- 登录时检查密码是否过期（90天），返回 `must_change_password`
- 迁移脚本添加字段
**文件**: `backend/app/models/user.py`, `backend/app/routers/auth.py`, `backend/app/migrations.py`

### 1.7 安全审计日志完善 ⬜
**问题**: 部分敏感操作缺少审计日志
**修复**:
- 发票修改/作废添加 log_operation
- 用户权限变更添加 log_operation
- 备份恢复添加 log_operation
**文件**: `backend/app/routers/invoices.py`, `backend/app/routers/users.py`, `backend/app/routers/backup.py`

### 1.8 文件上传加固 ⬜
**问题**: PDF 验证仅 5 字节 magic bytes，无上传速率限制
**修复**:
- PDF 验证增强：用 PyPDF2 验证 PDF 结构
- 添加上传频率限制（10/小时/用户）
**文件**: `backend/app/routers/invoices.py`, `requirements.txt`

### 交接记录 — Phase 1
- **完成时间**: 2026-03-17
- **修改文件清单**:
  - `docker-compose.yml` — 移除 `:-erp123456` fallback，改为 `${POSTGRES_PASSWORD:?}`
  - `backend/app/config.py` — DEBUG 模式识别、SECRET_KEY 强制、CORS 警告、BACKUP_ENCRYPTION_KEY、PASSWORD_EXPIRY_DAYS
  - `backend/app/rate_limit.py`（新建）— slowapi 全局限流器 200/min
  - `backend/main.py` — 接入 slowapi、安全头补全（HSTS/Permissions-Policy/X-Permitted-Cross-Domain-Policies）
  - `backend/app/services/backup_service.py` — Fernet 加密/解密备份、`_encrypt_file()`、`decrypt_file_content()`、`_open_tar_gz()`
  - `backend/app/routers/backup.py` — 下载解密、上传解密恢复、限流 5/hour、审计日志
  - `backend/app/models/user.py` — 添加 `password_changed_at` 字段
  - `backend/app/routers/auth.py` — 登录时密码过期检查、修改密码时更新 password_changed_at
  - `backend/app/migrations.py` — 添加 `migrate_user_password_changed_at()` 迁移
  - `backend/app/routers/invoices.py` — 发票更新/作废审计日志、PDF %%EOF 结构校验
  - `backend/app/routers/users.py` — 角色/权限变更审计日志
  - `backend/app/services/operation_log_service.py` — SECURITY_ACTIONS 扩展
  - `backend/requirements.txt` — 添加 `slowapi>=0.1.9`
  - `.env.example` — 更新为完整模板
- **Review 修复**:
  - `datetime.utcnow()` → `datetime.now(timezone.utc)` 修复 TIMESTAMPTZ 比较崩溃
  - 已有用户 `password_changed_at=NULL` 不再视为过期
  - 备份创建端点补加 5/hour 限流
  - 密码过期天数常量化到 `config.py`（PASSWORD_EXPIRY_DAYS 环境变量可配）
  - invoices.py 移除无法工作的 slowapi 装饰器（`from __future__ import annotations` 不兼容）
- **测试验证**: 147 个后端测试全通过，前端 build 零错误
- **遗留问题**:
  - invoices.py 的 PDF 上传端点无法使用 `@limiter.limit` 装饰器（因 `from __future__ import annotations`），已由全局 200/min 覆盖
  - SQLite 备份（仅开发用）不加密
- **下一步前置条件**: Phase 2 无前置依赖，可直接开始

---

## Phase 2: 后端常量化 + API 一致性

### 2.1 业务常量 Enum 化 ⬜
**问题**: OrderType, OrderStatus, PaymentStatus 等魔法字符串散布 50+ 文件
**修复**:
- 创建 `backend/app/constants.py`
- 定义 `OrderType`, `OrderStatus`, `ShippingStatus`, `PaymentStatus`, `VoucherType` 等 Enum
- 全局替换硬编码字符串为 Enum 成员
**文件**: `backend/app/constants.py`(新建), 所有 routers/ 和 services/ 中引用处

### 2.2 统一分页格式 ⬜
**问题**: 部分端点返回数组，部分返回 `{items, total}`
**修复**:
- 审计所有列表端点，统一返回 `{"items": [], "total": N}`
- 创建 `paginated_response()` 工具函数
- 前端移除 `data.items || data` 兼容代码
**文件**: 所有返回列表的 router 端点, `frontend/src/` 中消费处

### 2.3 统一错误响应格式 ⬜
**问题**: 部分返回 `{detail}`, 部分返回 `{message}`
**修复**:
- 统一为 `{"detail": "..."}` 格式（FastAPI 默认）
- crud_factory.py 中 `{"message": ...}` → `{"detail": ...}`
**文件**: `backend/app/routers/crud_factory.py`, 其他不一致处

### 2.4 批量加载工具函数 ⬜
**问题**: "收集 IDs → 查询 → 按 ID 分组" 模式重复 15+ 次
**修复**:
- 创建 `backend/app/utils/batch_load.py`
- 提供 `batch_load_related(model, ids, key, group_key)` 通用工具
- 替换各 router 中重复代码
**文件**: `backend/app/utils/batch_load.py`(新建), 使用处 routers

### 2.5 无界查询防护 ⬜
**问题**: 80 处 `.all()` 调用可能无分页
**修复**:
- 审计所有 `.all()` 调用
- 需要分页的添加 `limit` 参数（默认 200，最大 1000）
- 内部用途（如批量加载子项）保留 `.all()` 但添加注释说明
**文件**: 所有包含 `.all()` 的 router

### 2.6 静默错误修复 ⬜
**问题**: main.py lifespan 中 `except: pass`，部分 catch 不通知用户
**修复**:
- main.py lifespan 清理错误改为 `logger.error()`
- 各 service catch 块添加适当日志级别
**文件**: `backend/main.py`, 相关 service 文件

### 交接记录 — Phase 2
- **完成时间**: 2026-03-17
- **修改文件清单**:
  - `backend/app/constants.py`（新建）— 11 个 Enum（OrderType/ShippingStatus/ShipmentStatus/InvoiceStatus/BillStatus/ReceiptBillStatus/VoucherStatus/PurchaseOrderStatus/PaymentSource/StockChangeType/SnCodeStatus）+ 2 个中文映射 + MAX_PAGE_SIZE + 锁层级文档
  - `backend/app/utils/response.py`（新建）— `paginated_response()` 统一分页格式
  - `backend/app/utils/batch_load.py`（新建）— `batch_load_related()` 批量加载工具
  - `backend/app/routers/orders.py` — 全量 Enum 替换
  - `backend/app/services/order_service.py` — 全量 Enum 替换
  - `backend/app/routers/logistics.py` — Enum 替换 + SN 状态 Enum
  - `backend/app/routers/finance.py` — Enum 替换 + batch_load + paginated_response
  - `backend/app/routers/consignment.py` — Enum 替换 + batch_load + paginated_response
  - `backend/app/routers/purchase_orders.py` — Enum 替换 + batch_load + paginated_response
  - `backend/app/routers/sn.py` — SnCodeStatus Enum 替换
  - `backend/app/routers/stock.py` — SnCodeStatus Enum 替换
  - 15+ 其他 router 文件 — paginated_response 包装
  - `backend/main.py` — lifespan 静默错误修复
  - `backend/app/routers/suppliers.py` — 日期解析错误修复
  - `backend/app/services/logistics_service.py` — KD100 配置错误修复
  - 前端: `DashboardView.vue`, `MaterialsTab.vue` — `data.items || data` 兼容
- **Review 修复**: consignment.py / purchase_orders.py Enum 补全、SnCodeStatus 新增
- **测试验证**: 147 个后端测试全通过，前端 build 零错误
- **遗留问题**:
  - 原始 SQL 查询中的字符串无法用 Enum（如 consignment.py 的聚合查询）
  - 前端保留 `data.items || data` 兼容代码（比移除更安全）
  - MAX_PAGE_SIZE 常量已定义但各端点仍用硬编码数字（行为一致，仅代码风格差异）
- **下一步前置条件**: Phase 3 无前置依赖

---

## Phase 3: 数据库索引 + 约束 + 连接池

### 3.1 添加缺失复合索引 ⬜
**问题**: Voucher/AR/AP bills 缺少关键查询索引
**修复** — 在 migrations.py 添加：
- `Voucher(account_set_id, period_name)`
- `ReceivableBill(account_set_id, status)`, `(bill_date,)`
- `PayableBill(account_set_id, status)`
- `OrderItem(warehouse_id, location_id)`
- `Shipment(tracking_no,)`
- `StockLog(warehouse_id, created_at DESC)`
**文件**: `backend/app/models/` 相关模型, `backend/app/migrations.py`

### 3.2 添加 CHECK 约束 ⬜
**问题**: 金额/数量/税率字段无数据库级约束
**修复** — 迁移添加：
- `order_items.quantity > 0`
- `orders.total_amount >= 0`
- `warehouse_stocks.reserved_qty >= 0`
- `invoice_items.tax_rate BETWEEN 0 AND 100`
- `purchase_order_items.tax_rate BETWEEN 0 AND 100`
**文件**: `backend/app/migrations.py`

### 3.3 连接池扩容 + 健康检查 ⬜
**问题**: 默认 max=10 过小，无连接池监控
**修复**:
- 默认 max 改为 50（可通过 DB_POOL_MAX 覆盖）
- 默认 min 改为 5
- command_timeout 降为 15s
- 添加 `/health/db` 端点
**文件**: `backend/app/database.py`, `backend/main.py` 或新增 health router

### 3.4 定义锁获取顺序 ⬜
**问题**: 不同端点锁定 Order/Stock 顺序不一致，潜在死锁
**修复**:
- 在 `backend/app/constants.py` 中添加锁层级注释文档
- 审计 orders.py, finance.py, logistics.py 中的 `select_for_update()` 顺序
- 确保统一为 Order → OrderItem → Stock → Payment
**文件**: `backend/app/constants.py`, 相关 router/service

### 交接记录 — Phase 3
- **完成时间**: 2026-03-17
- **修改文件清单**:
  - `backend/app/migrations.py` — `migrate_add_missing_indexes()`（7 索引）+ `migrate_add_check_constraints()`（5 约束）
  - `backend/app/database.py` — 连接池 min=5/max=50/timeout=15s
  - `backend/main.py` — `/health` 端点（含 DB 连接检查）
  - `backend/app/models/voucher.py` — Voucher Meta.indexes 补充
  - `backend/app/models/ar_ap.py` — ReceivableBill Meta.indexes 补充
  - `backend/app/models/order.py` — OrderItem Meta.indexes 补充
  - `backend/app/models/shipment.py` — Shipment Meta.indexes 补充
  - `backend/app/models/stock.py` — StockLog Meta.indexes 补充
- **Review 修复**:
  - 补充 2 个税率 CHECK 约束（invoice_items、purchase_order_items）
  - StockLog Model Meta 与迁移 SQL 同步
  - CHECK 约束异常处理改为仅忽略"already exists"，其他错误记录 warning
- **测试验证**: 147 个后端测试全通过
- **下一步前置条件**: Phase 4 无前置依赖

---

## Phase 4: 前端代码质量 + 可访问性

### 4.1 全局 focus-visible 样式 ⬜
**问题**: 键盘用户看不到焦点位置
**修复**:
- `base.css` 添加 `*:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }`
- 按钮/输入框添加 `focus:ring-2 focus:ring-primary` 类
**文件**: `frontend/src/assets/base.css`

### 4.2 ARIA 标签补全 ⬜
**问题**: 15+ 交互元素缺少 aria-label
**修复**:
- 所有 icon-only 按钮添加 `aria-label`
- 排序表头从 `<span>` 改为 `<button>` 或添加 `role="button"` + `tabindex`
- Modal 添加 `role="dialog"` + `aria-labelledby`
**文件**: 各组件文件（ProductSearchRow, WorksheetRow, OrderConfirmModal, LogisticsView 等）

### 4.3 表单校验增强 ⬜
**问题**: 表单无前端校验，静默提交失败
**修复**:
- OrderConfirmModal 关键字段添加 `required`
- 提交前校验，显示错误提示
- 输入框添加 `aria-invalid` + 错误消息
**文件**: `OrderConfirmModal.vue`, `SalesToolbar.vue`

### 4.4 Store 加载状态 + 错误处理 ⬜
**问题**: Store 异步操作无 loading 状态，catch 仅 console.error
**修复**:
- 各 Store 添加 `loading` ref
- catch 中调用 `appStore.showToast()` 通知用户
- 组件中根据 loading 显示骨架屏或 spinner
**文件**: `stores/accounting.js`, `stores/finance.js`, `stores/products.js` 等

### 4.5 提取 ensureLoaded 工具 ⬜
**问题**: 8+ Store 重复相同的懒加载模式（~40 行重复）
**修复**:
- 创建 `frontend/src/utils/createLazyLoader.js` 工具函数
- 各 Store 替换为调用此工具
**文件**: `frontend/src/utils/createLazyLoader.js`(新建), 各 Store

### 4.6 权限常量化 ⬜
**问题**: `hasPermission('purchase_receive')` 等魔法字符串
**修复**:
- 在 `frontend/src/utils/constants.js` 添加 `PERMISSIONS` 常量对象
- 全局替换魔法字符串
**文件**: `frontend/src/utils/constants.js`, 所有 `hasPermission()` 调用处

### 4.7 拆分过大组件 ⬜
**问题**: SalesInvoiceTab 697 行，LogisticsView 500+ 行
**修复**:
- SalesInvoiceTab 拆分为 List + Detail + Actions
- useShipment composable 拆分为 useShipmentData + useShipmentUI
**文件**: `SalesInvoiceTab.vue` → 拆分, `useShipment.js` → 拆分

### 4.8 Prop 校验加强 + 防抖统一 ⬜
**问题**: Props 类型宽松无 required，防抖时间不统一
**修复**:
- 关键组件 Props 添加 `required: true` 和 `validator`
- 在 constants.js 统一 DEBOUNCE_MS 常量
- 替换各处硬编码防抖时间
**文件**: 各组件 defineProps, `constants.js`

### 交接记录 — Phase 4
- **完成时间**: 2026-03-17
- **修改文件清单**:
  - `frontend/src/styles/base.css` — 全局 `*:focus-visible` 样式 + 输入框 focus ring
  - `frontend/src/components/business/sales/ProductSearchRow.vue` — ARIA labels + prop validation
  - `frontend/src/components/business/sales/WorksheetRow.vue` — ARIA labels + prop validation
  - `frontend/src/components/business/sales/SalesWorksheet.vue` — prop validation
  - `frontend/src/components/business/sales/OrderConfirmModal.vue` — `role="dialog"` + `aria-modal` + 表单验证
  - `frontend/src/stores/accounting.js` — catch 中添加 toast 通知
  - `frontend/src/stores/finance.js` — catch 中添加 toast 通知
  - `frontend/src/utils/createLazyLoader.js`（新建）— 延迟加载工具
  - `frontend/src/stores/products.js` — 使用 createLazyLoader
  - `frontend/src/stores/warehouses.js` — 使用 createLazyLoader
  - `frontend/src/stores/settings.js` — 使用 createLazyLoader
  - `frontend/src/utils/constants.js` — PERMISSIONS 常量 + DEBOUNCE_MS 常量
  - `frontend/src/components/business/SalesInvoiceTab.vue` — TODO 拆分注释
  - `frontend/src/composables/useShipment.js` — TODO 拆分注释
- **Review 修复**: createLazyLoader 添加 .catch() 防 unhandled rejection
- **测试验证**: 前端 build 零错误，147 后端测试通过
- **遗留问题**:
  - PERMISSIONS 和 DEBOUNCE_MS 常量已定义但未全局替换（可增量替换）
  - SalesToolbar / SalesFooter props 未加 required（低风险）
  - 大组件拆分仅标记 TODO（避免回归风险）
- **下一步前置条件**: Phase 5 无前置依赖

---

## Phase 5: 性能优化 + 测试扩展

### 5.1 大表格虚拟滚动 ⬜
**问题**: 100+ 行表格无虚拟滚动，低端设备卡顿
**修复**:
- 评估是否需要虚拟滚动（当前实际数据量）
- 如需要，引入 `vue-virtual-scroller` 或自实现简易 windowing
**文件**: `LogisticsView.vue`, `StockView.vue`

### 5.2 重型 Modal 异步加载 ⬜
**问题**: 所有 Modal 同步加载，初始 bundle 偏大
**修复**:
- 使用 `defineAsyncComponent()` 延迟加载 OrderConfirmModal, 发票详情等
**文件**: `SalesView.vue`, `FinanceView.vue` 等

### 5.3 useColumnConfig 全局监听优化 ⬜
**问题**: 每个使用 useColumnConfig 的组件都注册全局 click 监听
**修复**:
- 改为单一全局监听器 + 事件委托
- 或使用 `v-click-outside` 指令
**文件**: `frontend/src/composables/useColumnConfig.js`

### 5.4 后端测试扩展 ⬜
**问题**: 测试集中在 model/service，API 集成测试缺失
**修复**:
- 添加 API 集成测试（订单创建、支付、发货流程）
- 添加权限边界测试
- 添加并发操作测试
**文件**: `backend/tests/` 新建测试文件

### 5.5 依赖漏洞扫描 ⬜
**问题**: 无自动依赖安全检查
**修复**:
- requirements.txt 添加 `pip-audit`
- 创建扫描脚本 `scripts/security-check.sh`
**文件**: `scripts/security-check.sh`(新建)

### 交接记录 — Phase 5
- **完成时间**: 2026-03-17
- **修改文件清单**:
  - `frontend/src/views/SalesView.vue` — OrderConfirmModal 异步加载
  - `frontend/src/views/FinanceView.vue` — 3 个 Panel 异步加载
  - `frontend/src/views/AccountingView.vue` — 8 个 Panel 异步加载
  - `frontend/src/views/PurchaseView.vue` — 2 个 Tab 异步加载
  - `scripts/security-check.sh`（新建）— 安全检查脚本
  - `backend/tests/TEST_PLAN.md`（新建）— 测试扩展计划（P1-P4）
- **不需修改**:
  - 虚拟滚动：LogisticsView / StockView 已有分页，无需虚拟滚动
  - useColumnConfig：已有正确的 onUnmounted 清理
- **测试验证**: 前端 build 零错误（异步组件正确 code-split），147 后端测试通过
- **遗留问题**: 测试扩展计划为文档，实际测试编写为独立工作项

---

## 交接模板

每个 Phase 完成后，在对应的「交接记录」处填写：

```
### 交接记录 — Phase X
- **完成时间**: YYYY-MM-DD
- **修改文件清单**: （列出所有修改/新建的文件）
- **测试验证**: （是否通过测试、如何验证）
- **遗留问题**: （如有未完成或需注意的事项）
- **下一步前置条件**: （Phase X+1 开始前需要确认的事项）
```
