# AI_CONTEXT.md — ERP-4 技术架构索引

> 本文档为 AI 辅助开发提供项目上下文。最后更新: 2026-02-25 / v4.10.0

---

## 1. 项目摘要

轻量级 ERP 系统，面向中小型贸易/零售企业，覆盖 **销售、采购、库存、财务、物流、寄售** 六大核心模块。单体架构，Docker 一键部署，前后端同容器运行。

- **用户规模**: 小团队多角色协作（admin / user），RBAC 权限控制 15 个粒度
- **部署方式**: `docker compose up -d`，PostgreSQL 16 + FastAPI + 前端静态文件打包进同一镜像
- **数据特征**: 单数据库，25 张核心表，支持 SN 码追溯、加权成本核算、自动凭证生成

---

## 2. 技术栈清单

### 后端
| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.12 | 运行时 |
| FastAPI | 0.109.0 | Web 框架 |
| Tortoise ORM | 0.20.0 | 异步 ORM (PostgreSQL) |
| asyncpg | 0.29.0 | PostgreSQL 异步驱动 |
| uvicorn | 0.27.0 | ASGI 服务器（2 workers，`--limit-max-requests 10000`） |
| PyJWT[crypto] | >=2.8.0 | JWT 签发/验证（替代已弃用的 python-jose） |
| passlib | 1.7.4 | 密码哈希 (bcrypt 主选 + pbkdf2_sha256 兼容) |
| pandas + openpyxl | 2.1.4 / 3.1.2 | Excel 导入导出 |
| httpx | 0.27.0 | 快递100 API 调用 |

### 前端
| 组件 | 版本 | 用途 |
|------|------|------|
| Vue | 3.5 | 响应式 UI 框架 |
| Vue Router | 4.6 | SPA 路由 |
| Pinia | 3.0 | 状态管理 |
| Tailwind CSS | 4.1 | 原子化样式 |
| Vite | 7.3 | 构建工具 |
| axios | 1.13 | HTTP 客户端 |
| Chart.js | 4.5 | 仪表盘图表 |
| lucide-vue-next | 0.564 | 图标库 |

### 基础设施
| 组件 | 说明 |
|------|------|
| PostgreSQL 16-alpine | 数据库（Docker 容器） |
| Docker | 多阶段构建，非 root 运行 |
| pg_dump / psql | 备份恢复 |
| 快递100 API | 物流追踪（KD100 webhook） |

---

## 3. 目录结构图

```
erp-4/
├── docker-compose.yml          # 编排：db + erp 两个服务
├── Dockerfile                  # 多阶段构建（node→python）
├── .env                        # 环境变量（不入库）
├── .env.example                # 环境变量模板
├── README.md                   # 项目文档 v4.10.0
├── CHANGELOG.md                # 版本变更记录
├── AI_CONTEXT.md               # 本文件
│
├── backend/
│   ├── main.py                 # FastAPI 入口（lifespan、CORS、路由注册、SPA）
│   ├── requirements.txt        # Python 依赖
│   └── app/
│       ├── config.py           # 全局配置（DB、JWT、KD100、CORS、载体列表）
│       ├── database.py         # Tortoise ORM 初始化/关闭
│       ├── exceptions.py       # 全局异常处理器
│       ├── logger.py           # 结构化 JSON 日志
│       ├── migrations.py       # 增量 DDL 迁移 + 默认数据初始化
│       │
│       ├── auth/
│       │   ├── jwt.py          # create_access_token / verify_token
│       │   └── dependencies.py # get_current_user / require_permission
│       │
│       ├── models/             # Tortoise ORM 模型（25 个类）
│       │   ├── user.py         # User
│       │   ├── product.py      # Product
│       │   ├── customer.py     # Customer
│       │   ├── supplier.py     # Supplier
│       │   ├── warehouse.py    # Warehouse, Location
│       │   ├── stock.py        # WarehouseStock, StockLog
│       │   ├── order.py        # Order, OrderItem
│       │   ├── payment.py      # Payment, PaymentOrder, PaymentMethod, DisbursementMethod
│       │   ├── purchase.py     # PurchaseOrder, PurchaseOrderItem
│       │   ├── shipment.py     # Shipment, ShipmentItem
│       │   ├── voucher.py      # Voucher, VoucherEntry, SystemSetting
│       │   ├── rebate.py       # RebateLog
│       │   ├── sn.py           # SnConfig, SnCode
│       │   ├── operation_log.py # OperationLog
│       │   └── salesperson.py  # Salesperson
│       │
│       ├── routers/            # API 路由（24 个模块）
│       │   ├── auth.py         # /api/auth   — 登录、登出、修改密码
│       │   ├── users.py        # /api/users  — 用户 CRUD
│       │   ├── products.py     # /api/products — 产品 CRUD、Excel 导入
│       │   ├── customers.py    # /api/customers
│       │   ├── suppliers.py    # /api/suppliers — 含统计聚合
│       │   ├── warehouses.py   # /api/warehouses
│       │   ├── locations.py    # /api/locations
│       │   ├── stock.py        # /api/stock — 库存查询、入库、调拨、SN 导出
│       │   ├── orders.py       # /api/orders — 销售/退货/寄售开单
│       │   ├── finance.py      # /api/finance — 应收、收款确认、凭证
│       │   ├── purchase_orders.py # /api/purchase-orders — 采购全流程
│       │   ├── consignment.py  # /api/consignment — 寄售管理
│       │   ├── logistics.py    # /api/logistics — 物流/快递100
│       │   ├── dashboard.py    # /api/dashboard — 统计看板
│       │   ├── backup.py       # /api/backup — 备份/恢复/下载
│       │   ├── rebates.py      # /api/rebates
│       │   ├── vouchers.py     # /api/vouchers — 凭证管理
│       │   ├── sn.py           # /api/sn — SN 码管理
│       │   ├── salespersons.py # /api/salespersons
│       │   ├── settings.py     # /api/settings — 系统设置
│       │   ├── operation_logs.py # /api/operation-logs
│       │   ├── product_brands.py # /api/product-brands
│       │   ├── payment_methods.py # /api/payment-methods（CRUD 工厂）
│       │   ├── disbursement_methods.py # /api/disbursement-methods（CRUD 工厂）
│       │   └── crud_factory.py # 通用 CRUD 路由工厂
│       │
│       ├── schemas/            # Pydantic 请求/响应模型（18 个文件）
│       │   ├── auth.py, user.py, product.py, customer.py, supplier.py
│       │   ├── warehouse.py, stock.py, order.py, finance.py
│       │   ├── purchase.py, consignment.py, logistics.py
│       │   ├── rebate.py, sn.py, voucher.py, salesperson.py, settings.py
│       │   └── __init__.py
│       │
│       ├── services/           # 业务逻辑层（6 个服务）
│       │   ├── stock_service.py      # 库存变动、加权成本计算
│       │   ├── order_service.py      # 订单创建、退货
│       │   ├── backup_service.py     # pg_dump 备份/恢复、自动备份循环
│       │   ├── logistics_service.py  # 快递100 订阅/回调
│       │   ├── sn_service.py         # SN 码入库/出库
│       │   └── operation_log_service.py # 操作日志记录
│       │
│       └── utils/              # 工具函数
│           ├── time.py         # now() UTC、days_between()
│           ├── generators.py   # 订单号生成
│           ├── csv.py          # CSV 导出
│           ├── errors.py       # 错误工具
│           └── query_helpers.py # 查询辅助
│
│   ├── tests/                  # pytest 测试
│   │   ├── conftest.py         # SQLite 内存测试 DB、async 测试 client
│   │   └── test_auth.py        # 认证/密码策略测试（6 个用例）
│   └── pytest.ini              # pytest 配置（asyncio_mode = auto）
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.vue             # 根组件（布局、idle 检测、Toast）
│       ├── main.js             # 入口
│       │
│       ├── router/
│       │   └── index.js        # 11 条路由，beforeEach 权限守卫
│       │
│       ├── views/              # 页面视图（11 个）
│       │   ├── LoginView.vue        # 125 行
│       │   ├── DashboardView.vue    # 160 行 — 统计看板
│       │   ├── SalesView.vue        # 870 行 — 销售开单
│       │   ├── StockView.vue        # 810 行 — 库存管理
│       │   ├── PurchaseView.vue     # 58 行  — 采购（Tabs 容器）
│       │   ├── FinanceView.vue      # 71 行  — 财务（Tabs 容器）
│       │   ├── ConsignmentView.vue  # 483 行 — 寄售
│       │   ├── LogisticsView.vue    # 855 行 — 物流
│       │   ├── CustomersView.vue    # 445 行 — 客户
│       │   ├── SettingsView.vue     # 930 行 — 系统设置
│       │   └── GuideView.vue        # 556 行 — 使用指南
│       │
│       ├── components/
│       │   ├── layout/         # 布局组件
│       │   │   ├── Sidebar.vue      # 66 行 — 桌面侧边栏
│       │   │   └── BottomNav.vue    # 39 行 — 移动端底部导航
│       │   │
│       │   ├── business/       # 业务面板（从大视图拆分）
│       │   │   ├── FinanceOrdersPanel.vue    # 1011 行 — 应收账款
│       │   │   ├── FinancePaymentsPanel.vue  # 118 行  — 收款记录
│       │   │   ├── FinancePayablesPanel.vue  # 263 行  — 应付账款
│       │   │   ├── FinanceRebatesPanel.vue   # 234 行  — 返利管理
│       │   │   ├── FinanceLogsPanel.vue      # 83 行   — 资金日志
│       │   │   ├── PurchaseOrdersPanel.vue   # 1095 行 — 采购订单
│       │   │   └── PurchaseSuppliersPanel.vue # 387 行 — 供应商
│       │   │
│       │   └── common/         # 通用 UI 组件
│       │       ├── AppTabs.vue      # 34 行 — 标签页切换
│       │       ├── AppTable.vue     # 78 行 — 数据表格
│       │       ├── AppModal.vue     # 57 行 — 模态框
│       │       ├── StatusBadge.vue  # 46 行 — 状态徽章
│       │       └── FilterBar.vue    # 22 行 — 筛选栏
│       │
│       ├── stores/             # Pinia 状态管理（7 个）
│       │   ├── auth.js         # 用户认证、权限检查、idle 超时
│       │   ├── app.js          # Toast 通知、全局 UI 状态
│       │   ├── finance.js      # 财务数据缓存
│       │   ├── settings.js     # 系统设置（收款方式、凭证编号等）
│       │   ├── warehouses.js   # 仓库/仓位数据
│       │   ├── customers.js    # 客户列表缓存
│       │   └── products.js     # 产品列表缓存
│       │
│       ├── api/                # axios API 模块（18 个）
│       │   ├── index.js        # axios 实例（30s 超时）、拦截器（401→登录、403→提示、5xx→重试）、POST/PUT/DELETE 防重复提交
│       │   ├── auth.js, customers.js, orders.js, finance.js
│       │   ├── products.js, stock.js, purchase.js, warehouses.js
│       │   ├── logistics.js, consignment.js, sn.js
│       │   ├── settings.js, salespersons.js, rebates.js
│       │   ├── brands.js, dashboard.js, vouchers.js
│       │   └── （每个文件导出命名函数，baseURL = '/api'）
│       │
│       ├── composables/        # Vue 组合式函数（7 个）
│       │   ├── useApi.js       # AbortController 可取消请求（组件 unmount 自动 abort）
│       │   ├── useFormat.js    # 金额/日期格式化
│       │   ├── useIdleTimeout.js # 无操作自动登出
│       │   ├── useModal.js     # 模态框状态管理
│       │   ├── usePermission.js # 权限检查
│       │   ├── useSort.js      # 表格排序
│       │   └── useTable.js     # 表格数据加载/分页
│       │
│       └── utils/
│           └── constants.js    # 全局常量（菜单、权限、订单类型、状态映射、IDLE_TIMEOUT）
│
├── backups/                    # 数据库备份目录（Docker volume 挂载）
├── archive/                    # 历史遗留代码归档
│   ├── main_legacy.py          # 旧版单文件后端（5102 行）
│   └── index_legacy.html       # 旧版单文件前端（2938 行）
└── docs/                       # 文档目录
```

---

## 4. 核心数据模型

### 4.1 ER 关系概览

```
User ──1:N──> Order ──1:N──> OrderItem ──N:1──> Product
  │                │                        │
  │                ├──1:N──> Shipment ──1:N──> ShipmentItem
  │                │
  │                └──N:1──> Customer ──1:N──> Payment ──1:N──> PaymentOrder
  │
  ├──1:N──> PurchaseOrder ──1:N──> PurchaseOrderItem ──N:1──> Product
  │              │
  │              └──N:1──> Supplier
  │
  └──1:N──> OperationLog

Warehouse ──1:N──> Location
    │                  │
    ├──1:N──> WarehouseStock ──N:1──> Product
    │
    └──1:N──> SnCode ──N:1──> Product
```

### 4.2 模型字段清单

**User** (`users`)
- `id` PK, `username` UNIQUE, `password_hash`, `display_name`, `role` (admin/user)
- `permissions` JSON[], `is_active`, `must_change_password`, `token_version`, `created_at`
- 方法: `has_permission(perm)`

**Product** (`products`)
- `id` PK, `sku` UNIQUE, `name`, `brand`, `category`
- `retail_price`, `cost_price`, `unit`, `description`, `is_active`, `created_at`, `updated_at`

**Customer** (`customers`)
- `id` PK, `name`, `contact_person`, `phone`, `address`
- `balance` (应收余额), `rebate_balance` (返利余额), `is_active`, `created_at`, `updated_at`

**Supplier** (`suppliers`)
- `id` PK, `name`, `contact_person`, `phone`, `tax_id`, `bank_account`, `bank_name`, `address`
- `rebate_balance`, `credit_balance`, `is_active`, `created_at`, `updated_at`

**Warehouse** (`warehouses`)
- `id` PK, `name`, `is_default`, `is_virtual`, `customer_id` (寄售虚拟仓关联), `is_active`

**Location** (`locations`)
- `id` PK, `warehouse_id` FK, `code`, `name`, `is_active`
- UNIQUE: (`warehouse_id`, `code`)

**WarehouseStock** (`warehouse_stocks`)
- `id` PK, `warehouse_id` FK, `product_id` FK, `location_id` FK
- `quantity`, `reserved_qty`, `weighted_cost`, `weighted_entry_date`, `updated_at`
- UNIQUE: (`warehouse`, `product`, `location`)

**StockLog** (`stock_logs`)
- `id` PK, `product_id` FK, `warehouse_id` FK, `change_type`, `quantity`
- `before_qty`, `after_qty`, `reference_type`, `reference_id`, `remark`, `creator_id` FK, `created_at`

**Order** (`orders`)
- `id` PK, `order_no` UNIQUE, `order_type` (CASH/CREDIT/CONSIGN_OUT/CONSIGN_SETTLE/CONSIGN_RETURN/RETURN)
- `customer_id` FK, `warehouse_id` FK, `related_order_id` FK (退货关联)
- `total_amount`, `total_cost`, `total_profit`, `paid_amount`, `rebate_used`
- `is_cleared`, `refunded`, `remark`, `salesperson_id` FK, `creator_id` FK
- `shipping_status` (pending/partial/completed), `created_at`, `updated_at`

**OrderItem** (`order_items`)
- `id` PK, `order_id` FK, `product_id` FK, `warehouse_id` FK, `location_id` FK
- `quantity`, `unit_price`, `cost_price`, `amount`, `profit`, `rebate_amount`, `shipped_qty`

**Payment** (`payments`)
- `id` PK, `payment_no` UNIQUE, `customer_id` FK, `order_id` FK
- `amount`, `payment_method`, `source` (CREDIT/CASH), `is_confirmed`
- `confirmed_by_id` FK, `confirmed_at`, `remark`, `creator_id` FK, `created_at`

**PaymentOrder** (`payment_orders`) — 收款与订单多对多关联
- `id` PK, `payment_id` FK, `order_id` FK, `amount`, `created_at`

**PaymentMethod** / **DisbursementMethod** (`payment_methods` / `disbursement_methods`)
- `id` PK, `code` UNIQUE, `name`, `sort_order`, `is_active`

**PurchaseOrder** (`purchase_orders`)
- `id` PK, `po_no` UNIQUE, `supplier_id` FK
- `status` (pending_review/pending/paid/partial/completed/cancelled/rejected/returned)
- `total_amount`, `rebate_used`, `target_warehouse_id` FK, `target_location_id` FK
- `remark`, `creator_id` FK, `reviewed_by_id` FK, `reviewed_at`, `payment_method`
- `paid_by_id` FK, `paid_at`, `return_tracking_no`, `is_refunded`, `return_amount`
- `credit_used`, `returned_by_id` FK, `returned_at`, `created_at`, `updated_at`

**PurchaseOrderItem** (`purchase_order_items`)
- `id` PK, `purchase_order_id` FK, `product_id` FK
- `quantity`, `tax_inclusive_price`, `tax_rate`, `tax_exclusive_price`, `amount`
- `received_quantity`, `returned_quantity`, `rebate_amount`
- `target_warehouse_id` FK, `target_location_id` FK, `created_at`

**Shipment** (`shipments`)
- `id` PK, `order_id` FK, `carrier_code`, `carrier_name`, `tracking_no`
- `status`, `status_text`, `last_tracking_info`, `phone`
- `kd100_subscribed`, `sn_code`, `created_at`, `updated_at`

**ShipmentItem** (`shipment_items`)
- `id` PK, `shipment_id` FK, `order_item_id` FK, `product_id` FK, `quantity`, `sn_codes`, `created_at`

**Voucher** (`vouchers`) — 会计凭证
- `id` PK, `voucher_no` UNIQUE, `voucher_type`, `seq_number`
- `source_type`, `source_id`, `voucher_date`, `company_name`
- `total_debit`, `total_credit`, `tax_rate`, `remark`, `creator_id` FK

**VoucherEntry** (`voucher_entries`)
- `id` PK, `voucher_id` FK, `seq`, `summary`, `account`, `debit_amount`, `credit_amount`

**SystemSetting** (`system_settings`)
- `id` PK, `key` UNIQUE, `value`, `updated_at`

**RebateLog** (`rebate_logs`)
- `id` PK, `target_type`, `target_id`, `type`, `amount`, `balance_after`
- `reference_type`, `reference_id`, `remark`, `creator_id` FK, `created_at`

**SnConfig** (`sn_configs`) — SN 码启用配置
- `id` PK, `warehouse_id` FK, `brand`, `is_active`
- UNIQUE: (`warehouse`, `brand`)

**SnCode** (`sn_codes`) — 序列号追踪
- `id` PK, `sn_code` UNIQUE, `warehouse_id` FK, `product_id` FK, `location_id` FK
- `status` (in_stock/sold/returned), `entry_type`, `entry_reference_id`, `entry_cost`
- `entry_date`, `entry_user_id` FK, `shipment_id` FK, `ship_date`, `ship_user_id` FK

**OperationLog** (`operation_logs`)
- `id` PK, `action`, `target_type`, `target_id`, `detail`, `operator_id` FK, `created_at`

**Salesperson** (`salespersons`)
- `id` PK, `name` UNIQUE, `phone`, `is_active`, `created_at`, `updated_at`

---

## 5. 关键设计模式与规范

### 5.1 认证与授权
- **JWT Bearer Token**: `Authorization: Bearer <token>`，24h 过期
- **token_version 机制**: 修改密码/禁用账户/登出时递增 `user.token_version`，旧 token 立即失效
- **登出接口**: `POST /api/auth/logout`，递增 token_version 使当前 token 失效；依赖 `get_current_user_allow_password_change`（允许 must_change_password 用户调用）
- **权限粒度**: 15 个权限 key，`require_permission("perm1", "perm2")` OR 关系
- **首次登录强制改密**: `must_change_password` 字段；change-password 接口递增 token_version 并返回新 token，旧 token 即时失效
- **must_change_password 流程**: 登录时若 must_change_password=true，前端仅写 `localStorage.erp_token`，不调用 `setAuth()`，避免 App.vue 模板切换（`v-if="authStore.user"`）销毁改密表单；change-password 成功后以响应中的新 token 调用 `setAuth()` 完成登录
- **登出防重入**: `logout()` 内置 `_loggingOut` 布尔守卫；401 拦截器对 `/auth/logout` 端点跳过 `_onUnauthorized` 回调，消除 `logout→401→logout` 无限循环
- **登录限频**: 5 次/5 分钟（`asyncio.Lock` 保护，防并发绕过）

### 5.2 数据库迁移
- **无框架增量迁移**: `migrations.py` 中手写 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- **多 worker 安全**: 所有 DDL 使用 `IF NOT EXISTS`/`IF EXISTS`，避免竞态
- **执行时机**: `lifespan` 启动时 `run_migrations()` → DDL 先行 → 默认数据初始化

### 5.3 库存核算
- **加权平均成本**: `WarehouseStock.weighted_cost` 随入库自动更新
- **库存预留**: `reserved_qty` 字段支持待发货预留
- **三维定位**: `(warehouse, product, location)` 唯一约束
- **SN 码追踪**: 可选，按仓库+品牌配置启用

### 5.4 订单类型
| 类型 | 说明 |
|------|------|
| CASH | 现款销售（即时扣库存） |
| CREDIT | 账期销售（应收） |
| CONSIGN_OUT | 寄售调拨（虚拟仓） |
| CONSIGN_SETTLE | 寄售结算 |
| CONSIGN_RETURN | 寄售退货 |
| RETURN | 销售退货 |

### 5.5 采购流程状态机
```
pending_review → (审核通过) → pending → (付款) → paid → (部分收货) → partial → (全部收货) → completed
      ↓                                                                          ↓
  rejected                                                                    returned
```

### 5.6 发货流程
- `Order.shipping_status`: pending → partial → completed
- `OrderItem.shipped_qty`: 逐批发货，`ShipmentItem` 记录每批明细
- SN 码随发货绑定到 `Shipment`

### 5.7 财务体系
- **应收管理**: `Customer.balance` 余额制，收款确认后冲减
- **返利系统**: `Customer.rebate_balance` / `Supplier.rebate_balance`，`RebateLog` 记录变动
- **凭证自动生成**: 销售/采购/收款 → 自动创建 `Voucher` + `VoucherEntry`
- **收/付款方式**: 可自定义，CRUD 工厂模式

### 5.8 前端架构模式
- **大视图拆分**: FinanceView / PurchaseView 为 Tabs 容器，业务逻辑下沉至 `components/business/` 面板
- **API 拦截器**: 401→清空 localStorage + 自动跳登录（对 `/auth/logout` 跳过 `_onUnauthorized` 防无限循环），403→Toast 提示，5xx→GET 自动重试一次
- **请求去重**: POST/PUT/DELETE 拦截器去重（`_pendingRequests` Map），防快速双击
- **请求超时**: axios 全局 30s 超时
- **可取消请求**: `useApi` composable 封装 AbortController，组件卸载自动取消
- **Idle 超时**: 4 小时无操作自动登出（`IDLE_TIMEOUT`），登出调用后端接口使 token 失效
- **登出防重入**: `auth.js` 中 `_loggingOut` 布尔守卫，防止 idle 超时与手动登出并发触发双重 logout
- **常量集中**: `utils/constants.js` 统一管理菜单、权限、状态映射
- **组合式函数**: `composables/` 封装 api、format、modal、sort、table、permission 复用逻辑
- **Store 错误状态**: products / customers store 暴露 `error` ref，加载失败可被 UI 消费

### 5.9 部署与运维
- **Docker 多阶段构建**: Stage 1 (node:20-alpine) 构建前端 → Stage 2 (python:3.12-slim) 运行后端
- **非 root 运行**: `appuser`
- **2 Workers**: uvicorn `--workers 2 --limit-max-requests 10000`（内存泄漏保护）
- **资源限制**: `mem_limit: 512m` + `cpus: 1.0`（db 和 erp 服务）
- **HEALTHCHECK**: 访问 `/health`（含数据库连通性检查）
- **自动备份**: 每日凌晨 3 点 `pg_dump`，60 秒轮询墙钟时间（兼容 Docker Desktop Mac 休眠）
- **备份保留**: 默认 30 天，自动清理
- **日志格式**: 结构化 JSON（`time`, `level`, `module`, `message`, `data`）
- **镜像源参数化**: `NPM_REGISTRY`, `APT_MIRROR`, `PYPI_MIRROR` 支持国内加速

### 5.10 安全措施
- **CORS 白名单**: 仅允许配置的 origins
- **安全 Headers**: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`
- **密码强度**: 8+ 字符，必须含字母+数字，拒绝 10 个常见弱密码
- **改密后 token 轮换**: change-password 接口递增 `token_version` 并签发新 token，旧 token 即时全局失效
- **请求体限制**: 全局 50MB `RequestSizeLimitMiddleware`
- **文件上传验证**: MIME 白名单 + 文件头魔数校验（防伪造后缀）
- **连接池保护**: asyncpg `command_timeout=30s`，`timeout=10s`
- **行锁 nowait**: `select_for_update(nowait=True)`，冲突返回 409
- **备份恢复**: filename 白名单正则 + `realpath` 路径遍历防护
- **环境变量隔离**: 敏感信息（密码、密钥）通过 `.env` 注入
- **Docker 资源限制**: 每服务 `mem_limit: 512m` + `cpus: 1.0`

---

## 6. 当前开发进度

### 版本: v4.10.0 (2026-02-25)

**已完成功能模块**:
- 销售开单（现款/账期/退货）
- 采购全流程（下单→审核→付款→收货→退货）
- 多仓库多仓位库存管理
- SN 码全生命周期追踪
- 寄售管理（调拨/结算/退货）
- 物流追踪（快递100集成）
- 财务管理（应收/收款/返利/凭证）
- 自动备份/手动备份/恢复
- 操作日志审计
- RBAC 权限控制

**v4.10.0 主要改进**（第三轮全量审查 + 登录流程 Bug 修复，43 项优化）:

*关键 Bug 修复*:
- **[CRITICAL] 首次登录改密表单不显示**: 登录时 must_change_password=true，前端不再调用 setAuth()（避免 App.vue v-if 分支切换销毁 LoginView 组件状态），仅写 localStorage；change-password 后端返回新 token，前端以新 token 完成登录
- **[CRITICAL] 登出无限循环**: logout()→logoutApi()→401→_onUnauthorized()→logout() 死循环（400+ 请求）；双重修复：① 401 拦截器对 /auth/logout 跳过 _onUnauthorized，② logout() 添加 _loggingOut 布尔守卫
- **[IMPORTANT] 登出接口依赖修复**: logout 端点改用 get_current_user_allow_password_change，允许 must_change_password 状态用户正常登出

*后端修复（第三轮审查）*:
- 8 项关键修复：JWT 库替换（python-jose→PyJWT crypto）、密码哈希方案升级（bcrypt+pbkdf2 fallback）、XFF 头改用最后 IP 防伪造、IP 限速原子操作（asyncio.Lock）、SPA fallback 静态扩展名白名单、安全响应头中间件、Decimal 精度修复（付款金额、退款计算）、登出 token_version 递增
- 17 项重要修复：弱密码黑名单、备份路径遍历防护、asyncpg 连接池超时、N+1 查询优化、select_for_update nowait 行锁、全局请求体限制中间件、文件上传魔数校验、Docker 资源限制 + 非 root 用户、uvicorn 多 worker + max-requests
- 18 项次要修复：分页、Schema 约束、日志格式、CSV 注入防护等

*前端修复（第三轮审查）*:
- useApi AbortController 可取消请求、POST/PUT/DELETE 防重复提交、GET 5xx 自动重试、30s 超时、checkAuth 去重 Promise、Store error 状态暴露、路由守卫 async+return 修复

**v4.9.0 主要改进**（第二轮全量审查，29 项优化）:
- 连接池超时保护（`command_timeout=30&timeout=10`）
- 登录限流 `asyncio.Lock` 防并发绕过
- 文件上传 MIME + 魔数双重验证
- 全局 50MB 请求体限制中间件
- 登出接口（递增 token_version 使 token 失效）
- Docker 资源限制（512MB / 1CPU）
- 产品列表分页（offset/limit/total）、用户列表 `.limit(500)` 上限
- 订单 N+1 查询优化（批量预取 entities_cache）
- `select_for_update(nowait=True)` 非阻塞行锁
- SPA fallback 静态扩展名白名单
- 前端 30s 超时 + GET 5xx 自动重试 + POST/PUT/DELETE 去重
- `useApi` composable（AbortController 可取消请求）
- pytest 测试框架搭建（6 个认证测试用例）
- uvicorn 2 workers + `--limit-max-requests 10000`
- Schema 验证增强（SKU 正则、价格/数量上限、items 长度限制）
- 密码策略加强（8+ 位 + 弱密码黑名单）

**v4.8.6 主要改进**（第六轮全量审查，17 个文件，25 个修复）:
- **[CRITICAL]** 手动库存调整加 `select_for_update()` 行锁，防止 TOCTOU 竞态
- **[CRITICAL]** 发货/删除发货单/SN 码操作全面加行锁，消除并发超卖风险
- **[SECURITY]** XFF 头取最后 IP（受信代理添加），防客户端伪造绕过速率限制
- 路由守卫 `next()` 全部加 `return`，消除竞态条件；提取公共权限检查函数
- StockLog 预留操作 before/after 改为记录可用库存变化（quantity - reserved_qty）
- finance.py / orders.py 精度修复（Decimal.quantize 替代 round + float 转换）
- customers.py PostgreSQL 专有 SQL 改为 ORM（兼容性）
- 前端付款类型、状态筛选、返利类型枚举补全；采购数量 parseInt → Number

**v4.8.5 主要改进**（第五轮全量审查，47 个文件）:
- **[CRITICAL]** 修复 `weighted_entry_date` 卖出时错误重置：改为三段逻辑（入库→重算，清零→重置，卖出→不变）
- **[CRITICAL]** 物流单删除恢复库存时同步恢复 `reserved_qty`（此前仅恢复 quantity 导致可用库存永久减少）
- 认证依赖重构：`_authenticate_user` + `get_current_user`（强制改密检查）+ `get_current_user_allow_password_change`
- 9 个后端路由全面修复：TOCTOU 行锁、退款校验、利润计算、Decimal 精度、两阶段导入、流式大小检查、reserved_qty 校验
- 前端 15 个 Vue 组件修复：浮点精度统一 `Math.round`、v-for/v-if 优先级、深拷贝防数据污染、防双击提交、确认弹窗补全、空 catch 块全量替换
- 前端 8 个 JS 文件修复：路由守卫 async 化、store 缓存污染、定时器泄漏、排序空值处理
- 修复后二轮审查验证：3 个并行 agent 复查发现并修复 5 个遗漏

**v4.8.4 主要改进**:
- 全部 ORM 外键添加 `on_delete` 策略（RESTRICT/SET_NULL/CASCADE）
- 服务层竞态条件修复：库存/订单操作使用 `select_for_update()` 行锁
- 财务精度：float 运算全面改为 Decimal
- 修复 CASH 部分赊账 `is_cleared` 误标记 bug
- 删除物流单时回滚 shipped_qty/SN 码/订单状态
- 前端 store `ensureLoaded` 竞态修复（promise 锁）
- 401 拦截器清空 auth store（修复状态残留）
- Docker 单 worker 防备份重复执行
- Schema 全面加固（Field 约束、Literal 枚举、校验器）
- CSV 导出改用标准库防注入

**未覆盖**:
- 测试覆盖率低（仅认证模块 6 个用例，无前端测试）
- 无 CI/CD pipeline
- 无 i18n 国际化
- SalesView（870 行）、StockView（810 行）、SettingsView（930 行）尚未拆分

---

## 7. 环境变量速查

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `POSTGRES_PASSWORD` | 是 | erp123456 | PostgreSQL 密码 |
| `SECRET_KEY` | 是 | (随机生成) | JWT 签名密钥，多 worker 必须固定 |
| `DATABASE_URL` | 否 | postgres://erp@localhost:5432/erp | 数据库连接串 |
| `BACKUP_KEEP_DAYS` | 否 | 30 | 自动备份保留天数 |
| `BACKUP_HOUR` | 否 | 3 | 自动备份执行小时 |
| `LOG_LEVEL` | 否 | INFO | 日志级别 |
| `CORS_ORIGINS` | 否 | localhost:5173,8090 | CORS 白名单（逗号分隔） |
| `KD100_KEY` | 否 | - | 快递100 API Key |
| `KD100_CUSTOMER` | 否 | - | 快递100 Customer ID |
| `KD100_CALLBACK_URL` | 否 | - | 快递100 回调 URL |
| `DEBUG` | 否 | false | true 时启用 uvicorn reload |

---

## 8. API 路由索引

| 前缀 | 文件 | 行数 | 核心功能 |
|------|------|------|----------|
| `/api/auth` | auth.py | 104 | 登录、登出、修改密码 |
| `/api/users` | users.py | 68 | 用户 CRUD |
| `/api/products` | products.py | 467 | 产品 CRUD、Excel 导入/导出 |
| `/api/customers` | customers.py | 111 | 客户 CRUD |
| `/api/suppliers` | suppliers.py | 174 | 供应商 CRUD + 统计 |
| `/api/warehouses` | warehouses.py | 79 | 仓库 CRUD |
| `/api/locations` | locations.py | 54 | 仓位 CRUD |
| `/api/stock` | stock.py | 298 | 库存查询、入库、调拨、SN 导出 |
| `/api/orders` | orders.py | 569 | 销售/退货/寄售开单 |
| `/api/finance` | finance.py | 414 | 应收、收款、凭证 |
| `/api/purchase-orders` | purchase_orders.py | 565 | 采购全流程 |
| `/api/consignment` | consignment.py | 371 | 寄售管理 |
| `/api/logistics` | logistics.py | 596 | 物流追踪 |
| `/api/dashboard` | dashboard.py | 99 | 统计看板 |
| `/api/backup` | backup.py | 176 | 备份/恢复 |
| `/api/rebates` | rebates.py | 72 | 返利日志 |
| `/api/vouchers` | vouchers.py | 214 | 会计凭证 |
| `/api/sn` | sn.py | 60 | SN 码管理 |
| `/api/salespersons` | salespersons.py | 44 | 业务员 |
| `/api/settings` | settings.py | 30 | 系统设置 |
| `/api/operation-logs` | operation_logs.py | 22 | 操作日志 |
| `/api/product-brands` | product_brands.py | 18 | 产品品牌 |
| `/api/payment-methods` | payment_methods.py | 4 | 收款方式（工厂） |
| `/api/disbursement-methods` | disbursement_methods.py | 4 | 付款方式（工厂） |
