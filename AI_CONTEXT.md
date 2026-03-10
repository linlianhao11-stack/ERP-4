# AI_CONTEXT.md — ERP-4 技术架构索引

> 本文档为 AI 辅助开发提供项目上下文。最后更新: 2026-03-10 / v4.19.0

---

## 1. 项目摘要

轻量级 ERP 系统，面向中小型贸易/零售企业，覆盖 **销售、采购、库存、财务、物流、寄售** 六大核心模块。单体架构，Docker 一键部署，前后端同容器运行。

- **用户规模**: 小团队多角色协作（admin / user），RBAC 权限控制 21 个粒度
- **部署方式**: `docker compose up -d`，PostgreSQL 16 + FastAPI + 前端静态文件打包进同一镜像
- **数据特征**: 单数据库，40 张核心表，支持 SN 码追溯、加权成本核算、应收应付管理、期末结转、三张财务报表

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
├── README.md                   # 项目文档 v4.14.0
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
│       ├── models/             # Tortoise ORM 模型（40 个类）
│       │   ├── user.py         # User
│       │   ├── product.py      # Product
│       │   ├── customer.py     # Customer
│       │   ├── supplier.py     # Supplier
│       │   ├── warehouse.py    # Warehouse, Location
│       │   ├── stock.py        # WarehouseStock, StockLog
│       │   ├── order.py        # Order, OrderItem
│       │   ├── payment.py      # Payment, PaymentOrder, PaymentMethod, DisbursementMethod
│       │   ├── purchase.py     # PurchaseOrder, PurchaseOrderItem, PurchaseReturn, PurchaseReturnItem
│       │   ├── shipment.py     # Shipment, ShipmentItem
│       │   ├── voucher.py      # Voucher, VoucherEntry, SystemSetting
│       │   ├── accounting.py   # AccountSet, ChartOfAccount, AccountingPeriod
│       │   ├── ar_ap.py        # ReceivableBill, ReceiptBill, ReceiptRefundBill, ReceivableWriteOff, PayableBill, DisbursementBill, DisbursementRefundBill
│       │   ├── invoice.py     # Invoice, InvoiceItem
│       │   ├── sales_delivery.py  # SalesDeliveryBill, SalesDeliveryItem
│       │   ├── purchase_receipt.py # PurchaseReceiptBill, PurchaseReceiptItem
│       │   ├── rebate.py       # RebateLog
│       │   ├── sn.py           # SnConfig, SnCode
│       │   ├── operation_log.py # OperationLog
│       │   └── salesperson.py  # Salesperson
│       │
│       ├── routers/            # API 路由（36 个模块）
│       │   ├── auth.py         # /api/auth   — 登录、登出、修改密码
│       │   ├── users.py        # /api/users  — 用户 CRUD
│       │   ├── products.py     # /api/products — 产品 CRUD、Excel 导入
│       │   ├── customers.py    # /api/customers
│       │   ├── suppliers.py    # /api/suppliers — 含统计聚合
│       │   ├── warehouses.py   # /api/warehouses
│       │   ├── locations.py    # /api/locations
│       │   ├── stock.py        # /api/stock — 库存查询、入库、调拨、SN 导出
│       │   ├── orders.py       # /api/orders — 销售/退货/寄售开单（含退货→红字应收+收款退款单钩子）
│       │   ├── finance.py      # /api/finance — 应收、收款确认、凭证
│       │   ├── purchase_orders.py # /api/purchase-orders — 采购全流程（含收货→应付、付款→付款单、退货→退货单+红字应付+付款退款单钩子）
│       │   ├── purchase_returns.py # /api/purchase-returns — 采购退货单 CRUD
│       │   ├── consignment.py  # /api/consignment — 寄售管理
│       │   ├── logistics.py    # /api/logistics — 物流/快递100（含发货→应收钩子）
│       │   ├── dashboard.py    # /api/dashboard — 统计看板
│       │   ├── backup.py       # /api/backup — 备份/恢复/下载
│       │   ├── rebates.py      # /api/rebates
│       │   ├── vouchers.py     # /api/vouchers — 凭证管理
│       │   ├── account_sets.py # /api/account-sets — 账套管理
│       │   ├── chart_of_accounts.py # /api/chart-of-accounts — 科目管理
│       │   ├── accounting_periods.py # /api/accounting-periods — 会计期间
│       │   ├── ledgers.py      # /api/ledgers — 总分类账/明细账/余额表 + 导出
│       │   ├── receivables.py  # /api/receivables — 应收管理（14端点）
│       │   ├── payables.py     # /api/payables — 应付管理（11端点）
│       │   ├── invoices.py    # /api/invoices — 发票管理（7端点：销项推送/进项创建/确认/作废/编辑）
│       │   ├── sales_delivery.py  # /api/sales-delivery — 出库单（4端点：列表/详情/PDF/批量PDF）
│       │   ├── purchase_receipt.py # /api/purchase-receipt — 入库单（4端点：列表/详情/PDF/批量PDF）
│       │   ├── period_end.py  # /api/period-end — 期末处理（6端点：损益结转预览/执行/结账检查/结账/反结账/年度结转）
│       │   ├── financial_reports.py # /api/financial-reports — 财务报表（6端点：3查询+3导出）
│       │   ├── sn.py           # /api/sn — SN 码管理
│       │   ├── salespersons.py # /api/salespersons
│       │   ├── settings.py     # /api/settings — 系统设置
│       │   ├── operation_logs.py # /api/operation-logs
│       │   ├── product_brands.py # /api/product-brands
│       │   ├── payment_methods.py # /api/payment-methods（CRUD 工厂）
│       │   ├── disbursement_methods.py # /api/disbursement-methods（CRUD 工厂）
│       │   └── crud_factory.py # 通用 CRUD 路由工厂
│       │
│       ├── schemas/            # Pydantic 请求/响应模型（20 个文件）
│       │   ├── auth.py, user.py, product.py, customer.py, supplier.py
│       │   ├── warehouse.py, stock.py, order.py, finance.py
│       │   ├── purchase.py, consignment.py, logistics.py
│       │   ├── rebate.py, sn.py, voucher.py, salesperson.py, settings.py
│       │   ├── accounting.py   # 账套/科目/期间 schemas
│       │   ├── ar_ap.py        # 应收应付7个Create schemas
│       │   └── __init__.py
│       │
│       ├── services/           # 业务逻辑层（15 个服务）
│       │   ├── stock_service.py      # 库存变动、加权成本计算
│       │   ├── order_service.py      # 订单创建、退货
│       │   ├── backup_service.py     # pg_dump 备份/恢复、自动备份循环
│       │   ├── logistics_service.py  # 快递100 订阅/回调
│       │   ├── sn_service.py         # SN 码入库/出库
│       │   ├── operation_log_service.py # 操作日志记录
│       │   ├── accounting_init.py    # 预置科目初始化
│       │   ├── ledger_service.py     # 总分类账/明细账/余额表查询
│       │   ├── ledger_export.py      # 账簿 Excel 导出
│       │   ├── ar_service.py         # 应收服务（应收单/收款单创建+确认+凭证生成）
│       │   ├── ap_service.py         # 应付服务（应付单/付款单创建+确认+凭证生成）
│       │   ├── invoice_service.py    # 发票服务（销项推送/进项创建/确认/凭证）
│       │   ├── pdf_print.py          # PDF套打（凭证/出库单/入库单，reportlab 24×14cm）
│       │   ├── period_end_service.py # 期末处理（损益结转/结账检查/结账/反结账/年度结转）
│       │   ├── report_service.py     # 财务报表（资产负债表/利润表/现金流量表）
│       │   └── report_export.py      # 报表导出（Excel+PDF，3报表×2格式）
│       │
│       └── utils/              # 工具函数
│           ├── time.py         # now() UTC、days_between()
│           ├── generators.py   # 订单号生成
│           ├── voucher_no.py   # 共享凭证号生成器（select_for_update 防并发）
│           ├── csv.py          # CSV 导出
│           ├── errors.py       # 错误工具
│           └── query_helpers.py # 查询辅助
│
│   ├── tests/                  # pytest 测试（79 个用例）
│   │   ├── conftest.py         # SQLite 内存测试 DB、async 测试 client
│   │   ├── test_auth.py        # 认证/密码策略测试（6 个用例）
│   │   ├── test_accounting_models.py  # 会计模型测试（9 个用例）
│   │   ├── test_accounting_init.py    # 科目初始化测试（4 个用例）
│   │   ├── test_voucher_models.py     # 凭证模型测试（2 个用例）
│   │   ├── test_ledger_service.py     # 账簿查询测试（10 个用例）
│   │   ├── test_ar_ap_models.py       # 应收应付模型测试（10 个用例）
│   │   ├── test_ar_ap_service.py      # 应收应付服务测试（10 个用例）
│   │   ├── test_phase4_models.py      # 发票/出入库模型测试（4 个用例）
│   │   ├── test_phase4_service.py     # 发票/出入库服务测试（14 个用例）
│   │   ├── test_period_end.py         # 期末处理测试（9 个用例）
│   │   └── test_reports.py            # 财务报表测试（7 个用例）
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
│       ├── views/              # 页面视图（12 个）
│       │   ├── LoginView.vue        # 125 行
│       │   ├── DashboardView.vue    # 160 行 — 统计看板
│       │   ├── SalesView.vue        # 386 行 — 销售开单（瘦容器，子组件在 business/sales/）
│       │   ├── StockView.vue        # 287 行 — 库存管理（瘦容器，子组件在 business/stock/）
│       │   ├── PurchaseView.vue     # 58 行  — 采购（Tabs 容器）
│       │   ├── FinanceView.vue      # 71 行  — 财务（Tabs 容器）
│       │   ├── AccountingView.vue   # 会计（凭证/科目/期间/账簿/应收/应付/发票/出入库/期末处理/财务报表 10个Tab）
│       │   ├── ConsignmentView.vue  # 483 行 — 寄售
│       │   ├── LogisticsView.vue    # 256 行 — 物流（瘦容器，子组件在 business/logistics/）
│       │   ├── CustomersView.vue    # 445 行 — 客户
│       │   ├── SettingsView.vue     # 96 行  — 系统设置（瘦容器，子组件在 business/settings/）
│       │   └── GuideView.vue        # 556 行 — 使用指南
│       │
│       ├── components/
│       │   ├── layout/         # 布局组件
│       │   │   ├── Sidebar.vue      # 66 行 — 桌面侧边栏
│       │   │   └── BottomNav.vue    # 39 行 — 移动端底部导航
│       │   │
│       │   ├── business/       # 业务面板（从大视图拆分）
│       │   │   ├── sales/                    # 销售子组件
│       │   │   │   ├── ProductSelector.vue   # 253 行 — 商品选择表格+筛选
│       │   │   │   ├── ShoppingCart.vue       # 246 行 — 购物车列表
│       │   │   │   └── OrderConfirmModal.vue  # 224 行 — 下单确认弹窗
│       │   │   ├── purchase/                 # 采购子组件
│       │   │   │   ├── PurchaseOrderForm.vue  # 490 行 — 新建/编辑采购单
│       │   │   │   ├── PurchaseOrderDetail.vue # 采购单详情+收货+退货+关联退货单
│       │   │   │   └── PurchaseReturnTab.vue  # 采购退货单列表+详情弹窗
│       │   │   ├── finance/                  # 财务子组件
│       │   │   │   ├── FinanceOrdersTab.vue   # 733 行 — 订单列表+详情+取消
│       │   │   │   └── FinanceUnpaidTab.vue   # 249 行 — 未收款+收款弹窗
│       │   │   ├── logistics/                # 物流子组件
│       │   │   │   └── ShipmentDetailModal.vue # 643 行 — 发货详情+发货表单+物流跟踪
│       │   │   ├── stock/                    # 库存子组件
│       │   │   │   ├── ProductFormModal.vue   # 144 行 — 商品新增/编辑
│       │   │   │   ├── RestockModal.vue       # 217 行 — 入库（含SN码）
│       │   │   │   ├── TransferModal.vue      # 201 行 — 调拨
│       │   │   │   ├── ImportModal.vue        # 101 行 — 导入上传
│       │   │   │   └── ImportPreviewModal.vue # 166 行 — 导入预览
│       │   │   ├── settings/                 # 设置子组件
│       │   │   │   ├── WarehouseSettings.vue  # 348 行 — 仓库+仓位CRUD
│       │   │   │   ├── PaymentMethodSettings.vue # 233 行
│       │   │   │   ├── SalespersonSettings.vue # 128 行
│       │   │   │   ├── UserSettings.vue       # 310 行 — 用户管理
│       │   │   │   ├── PermissionSettings.vue # 178 行 — 权限矩阵
│       │   │   │   └── LogsSettings.vue       # 68 行
│       │   │   ├── FinanceOrdersPanel.vue    # 71 行  — 应收账款（瘦容器）
│       │   │   ├── FinancePaymentsPanel.vue  # 118 行  — 收款记录
│       │   │   ├── FinancePayablesPanel.vue  # 263 行  — 应付账款
│       │   │   ├── FinanceRebatesPanel.vue   # 234 行  — 返利管理
│       │   │   ├── FinanceLogsPanel.vue      # 83 行   — 资金日志
│       │   │   ├── PurchaseOrdersPanel.vue   # 166 行  — 采购订单（瘦容器）
│       │   │   ├── PurchaseSuppliersPanel.vue # 387 行 — 供应商
│       │   │   ├── VoucherPanel.vue           # 凭证管理
│       │   │   ├── ChartOfAccountsPanel.vue   # 科目管理
│       │   │   ├── AccountingPeriodsPanel.vue # 会计期间
│       │   │   ├── LedgerPanel.vue            # 账簿查询（3子Tab）
│       │   │   ├── GeneralLedgerTab.vue       # 总分类账
│       │   │   ├── DetailLedgerTab.vue        # 明细账
│       │   │   ├── TrialBalanceTab.vue        # 余额表
│       │   │   ├── ReceivablePanel.vue        # 应收管理（4子Tab容器）
│       │   │   ├── ReceivableBillsTab.vue     # 应收单列表
│       │   │   ├── ReceiptBillsTab.vue        # 收款单CRUD
│       │   │   ├── ReceiptRefundBillsTab.vue  # 收款退款CRUD
│       │   │   ├── WriteOffBillsTab.vue       # 应收核销CRUD
│       │   │   ├── PayablePanel.vue           # 应付管理（3子Tab容器）
│       │   │   ├── PayableBillsTab.vue        # 应付单列表
│       │   │   ├── DisbursementBillsTab.vue   # 付款单CRUD
│       │   │   ├── DisbursementRefundBillsTab.vue # 付款退款CRUD
│       │   │   ├── InvoicePanel.vue          # 发票管理（2子Tab容器）
│       │   │   ├── SalesInvoiceTab.vue       # 销项发票（列表+推送+详情+编辑）
│       │   │   ├── PurchaseInvoiceTab.vue    # 进项发票（列表+新增+详情+编辑）
│       │   │   ├── SalesDeliveryTab.vue      # 出库单（列表+详情+PDF下载）
│       │   │   ├── PurchaseReceiptTab.vue    # 入库单（列表+详情+PDF下载）
│       │   │   ├── PeriodEndPanel.vue        # 期末处理（损益结转+结账检查+年度结转+反结账）
│       │   │   ├── FinancialReportPanel.vue  # 财务报表容器（期间选择+3子Tab+导出）
│       │   │   ├── BalanceSheetTab.vue       # 资产负债表
│       │   │   ├── IncomeStatementTab.vue    # 利润表
│       │   │   └── CashFlowTab.vue           # 现金流量表
│       │   │
│       │   └── common/         # 通用 UI 组件
│       │       ├── AppTabs.vue      # 34 行 — 标签页切换
│       │       ├── AppTable.vue     # 78 行 — 数据表格
│       │       ├── AppModal.vue     # 57 行 — 模态框
│       │       ├── StatusBadge.vue  # 46 行 — 状态徽章
│       │       └── FilterBar.vue    # 22 行 — 筛选栏
│       │
│       ├── stores/             # Pinia 状态管理（8 个）
│       │   ├── auth.js         # 用户认证、权限检查、idle 超时
│       │   ├── app.js          # Toast 通知、全局 UI 状态
│       │   ├── finance.js      # 财务数据缓存
│       │   ├── accounting.js   # 会计模块（账套列表、当前账套）
│       │   ├── settings.js     # 系统设置（收款方式、凭证编号等）
│       │   ├── warehouses.js   # 仓库/仓位数据
│       │   ├── customers.js    # 客户列表缓存
│       │   └── products.js     # 产品列表缓存
│       │
│       ├── api/                # axios API 模块（19 个）
│       │   ├── index.js        # axios 实例（30s 超时）、拦截器（401→登录、403→提示、5xx→重试）、POST/PUT/DELETE 防重复提交、GET 请求去重（并发共享 Promise）
│       │   ├── auth.js, customers.js, orders.js, finance.js
│       │   ├── products.js, stock.js, purchase.js, warehouses.js
│       │   ├── logistics.js, consignment.js, sn.js
│       │   ├── settings.js, salespersons.js, rebates.js
│       │   ├── brands.js, dashboard.js, vouchers.js
│       │   ├── accounting.js   # 账套/科目/期间/凭证/账簿/应收/应付/发票/出入库/期末/报表 共50+函数
│       │   └── （每个文件导出命名函数，baseURL = '/api'）
│       │
│       ├── composables/        # Vue 组合式函数（12 个）
│       │   ├── useApi.js       # AbortController 可取消请求（组件 unmount 自动 abort）
│       │   ├── useFormat.js    # 金额/日期格式化
│       │   ├── useIdleTimeout.js # 无操作自动登出
│       │   ├── useModal.js     # 模态框状态管理
│       │   ├── usePagination.js # 可复用分页逻辑（page/totalPages/hasPagination/paginationParams）
│       │   ├── usePermission.js # 权限检查
│       │   ├── useSort.js      # 表格排序
│       │   ├── useTable.js     # 表格数据加载/分页
│       │   ├── useSalesCart.js  # 165 行 — 购物车增删改算逻辑
│       │   ├── usePurchaseOrder.js # 采购单列表加载/筛选/导出/分页
│       │   ├── useShipment.js  # 发货列表加载/排序/列配置/分页
│       │   └── useStock.js     # 库存列表（独立 API 调用 + 服务端搜索 + 分页，不依赖 productsStore）
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
- **token_version 机制**: 修改密码/禁用账户/登出时通过 `F('token_version') + 1` 原子递增，旧 token 立即失效
- **登出接口**: `POST /api/auth/logout`，递增 token_version 使当前 token 失效；依赖 `get_current_user_allow_password_change`（允许 must_change_password 用户调用）
- **权限粒度**: 21+ 个权限 key，`require_permission("perm1", "perm2")` OR 关系，SettingsView 权限管理Tab可视化配置
- **首次登录强制改密**: `must_change_password` 字段；change-password 接口递增 token_version 并返回新 token，旧 token 即时失效
- **must_change_password 流程**: 登录时若 must_change_password=true，前端仅写 `localStorage.erp_token`，不调用 `setAuth()`，避免 App.vue 模板切换（`v-if="authStore.user"`）销毁改密表单；change-password 成功后以响应中的新 token 调用 `setAuth()` 完成登录
- **登出防重入**: `logout()` 使用 `_logoutPromise` 共享 Promise 模式（并发调用共享同一 Promise）；401 拦截器对 `/auth/logout` 端点跳过 `_onUnauthorized` 回调，消除 `logout→401→logout` 无限循环
- **登录限频**: 5 次/5 分钟，单锁串行化整个 check-verify-increment 流程，防并发绕过；仅信任 socket IP（不读取 X-Forwarded-For），防限频绕过
- **JWT 异常体系**: `verify_token` 抛出 `TokenExpiredError`/`TokenInvalidError` 异常，替代混合返回类型

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
- **业务层应收**: `Customer.balance` 余额制，收款确认后冲减（FinanceView）
- **财务层应收应付**（AccountingView，按账套隔离）：
  - **应收单** ReceivableBill：发货完成/退货时自动生成，tracked received/unreceived
  - **收款单** ReceiptBill：关联 Payment（并存），draft→confirmed，确认时更新应收单
  - **收款退款** ReceiptRefundBill：关联原收款单，确认时回滚应收
  - **应收核销** ReceivableWriteOff：预收冲应收
  - **应付单** PayableBill：采购收货时自动生成，tracked paid/unpaid
  - **付款单** DisbursementBill：采购付款时自动生成，draft→confirmed
  - **付款退款** DisbursementRefundBill：关联原付款单
  - **期末凭证生成**：已确认的收款/付款/退款/核销单批量生成会计凭证
- **返利系统**: `Customer.rebate_balance` / `Supplier.rebate_balance`，`RebateLog` 记录变动
- **收/付款方式**: 可自定义，CRUD 工厂模式
- **会计模块**：多账套隔离、标准科目表、会计期间、凭证（记/收/付/转）、总分类账/明细账/余额表

### 5.8 前端架构模式
- **大视图拆分**: FinanceView / PurchaseView 为 Tabs 容器，业务逻辑下沉至 `components/business/` 面板
- **API 拦截器**: 401→清空 localStorage + 自动跳登录（对 `/auth/logout` 跳过 `_onUnauthorized` 防无限循环），403→Toast 提示，5xx→GET 自动重试一次
- **请求去重**: POST/PUT/DELETE 拦截器去重（`_pendingRequests` Map），防快速双击
- **请求超时**: axios 全局 30s 超时
- **可取消请求**: `useApi` composable 封装 AbortController，组件卸载自动取消
- **Idle 超时**: 4 小时无操作自动登出（`IDLE_TIMEOUT`），登出调用后端接口使 token 失效
- **登出防重入**: `auth.js` 中 `_logoutPromise` 共享 Promise 模式，并发调用共享同一 Promise，防止 idle 超时与手动登出并发触发双重 logout
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
- **密码强度**: 8+ 字符，必须含字母+数字，拒绝 13 个常见弱密码（含 admin123/changeme/administrator）
- **改密后 token 轮换**: change-password 接口通过 F() 原子递增 `token_version` 并签发新 token，旧 token 即时全局失效
- **请求体限制**: 全局 50MB `RequestSizeLimitMiddleware`
- **文件上传验证**: MIME 白名单 + 文件头魔数校验（防伪造后缀）
- **连接池保护**: asyncpg `command_timeout=30s`，`timeout=10s`
- **行锁 nowait**: `select_for_update(nowait=True)`，冲突返回 409
- **备份恢复**: filename 白名单正则 + `realpath` 路径遍历防护
- **环境变量隔离**: 敏感信息（密码、密钥）通过 `.env` 注入
- **Docker 资源限制**: 每服务 `mem_limit: 512m` + `cpus: 1.0`

---

## 6. 当前开发进度

### 版本: v4.17.0 (2026-03-09)

**已完成功能模块**:
- 销售开单（现款/账期/退货）
- 采购全流程（下单→审核→付款→收货→退货）
- 多仓库多仓位库存管理
- SN 码全生命周期追踪
- 寄售管理（调拨/结算/退货）
- 物流追踪（快递100集成）
- 财务管理（应收/收款/返利/凭证）
- **会计模块**（多账套、科目表、会计期间、凭证管理、账簿查询）
- **应收应付管理**（7模型、25端点、业务流程自动衔接、期末凭证生成）
- **发票管理**（销项推送/进项创建/确认/作废/编辑，含明细行）
- **出入库单**（发货→出库单/收货→入库单，PDF套打）
- **期末处理**（损益结转/结账检查/结账/反结账/年度结转）
- **财务报表**（资产负债表/利润表/现金流量表，Excel+PDF导出）
- 自动备份/手动备份/恢复
- 操作日志审计
- RBAC 权限控制（21个权限粒度，SettingsView 可视化管理）
- **第五轮全量审查修复**（19项：并发安全/事务完整性/账套隔离/性能优化）
- **UI 重构**：Modern Industrial 设计系统 — OKLCH 色彩 Token、亮/暗双模式、侧边栏待办角标、仪表盘待办面板

**v4.17.0 — UI 重构：Modern Industrial 设计系统 (2026-03-09)**:
- 建立 OKLCH 色彩 Token 体系（60+ CSS 变量 + Tailwind 4 `@theme` 配置）
- 批量替换 1,370 处硬编码 `[#hex]` → 语义化 Token class
- 亮/暗双模式切换（localStorage 持久化 + FOUC 防闪烁）
- 新增 `GET /api/todo-counts` 端点 — 按权限返回 6 类待办数量
- 侧边栏 iOS 风格红色角标 + 主题切换按钮
- 仪表盘待办事项面板（按权限过滤 + 点击跳转）
- 全局 `:focus-visible` 焦点样式 + `prefers-reduced-motion` 无障碍
- 设计文档: `docs/plans/2026-03-09-ui-refactor.md`

**v4.14.0 — 全量代码审查修复 + 权限管理 (2026-03-04)**:
- 凭证号生成提取共享工具 + select_for_update 防竞态（6文件→1文件）
- AP服务/发票作废事务包装、反结账后续期间检查、token_version 原子更新
- 6个详情端点增加账套隔离、金额正数校验、采购部分收货应付单修复
- 16处原生confirm()→customConfirm()、StockView/CustomersView onMounted
- 现金流量表/凭证批量PDF O(n²)→批量预加载、备份上传流式写入
- 权限管理Tab（SettingsView）、财务钩子错误上报、Docker SECRET_KEY 强制设置

**v4.13.0 — 业财一体化会计模块（阶段4-5）(2026-02-28)**:

*阶段4 — 发票+出入库+PDF套打*:
- 6个新模型（Invoice/InvoiceItem + SalesDeliveryBill/Item + PurchaseReceiptBill/Item）
- 3个新路由（invoices/sales_delivery/purchase_receipt，15端点）
- PDF套打（reportlab 24×14cm，3种模板）
- 业务钩子：发货→出库单+凭证、收货→入库单+凭证

*阶段5 — 期末处理+财务报表*:
- 3个新服务（period_end_service/report_service/report_export）
- 2个新路由（period_end/financial_reports，12端点）
- 5个新前端组件（PeriodEndPanel + FinancialReportPanel + 3报表Tab）
- 16个新测试，全量79个通过

*UI补丁*:
- 6个Tab新增详情弹窗（应收/应付/出库/入库/销项发票/进项发票）
- 发票草稿支持编辑（updateInvoice API）
- 应收/应付面板新增"批量生成凭证"按钮

**v4.12.0 — 业财一体化会计模块（阶段1-3）(2026-02-28)**:

*阶段1 — 基础设施*:
- 多账套管理（AccountSet）+ 标准科目表（32个预置科目）+ 会计期间 + 凭证改造（记/收/付/转）
- 5个新模型 + 4个新Router + 迁移脚本 + 科目初始化服务

*阶段2 — 账簿查询*:
- 总分类账/明细账/余额表查询 + Excel导出
- LedgerPanel（3子Tab）+ ledger_service + ledger_export

*阶段3 — 应收应付管理（AR/AP）*:
- 7个新模型（ReceivableBill/ReceiptBill/ReceiptRefundBill/ReceivableWriteOff/PayableBill/DisbursementBill/DisbursementRefundBill）
- 应收路由14端点 + 应付路由11端点 + 2个服务层（ar_service/ap_service）
- 业务流程钩子：发货→应收单、退货→红字应收、采购收货→应付单、采购付款→付款单
- 期末批量凭证生成（收/付/退/核销 → 借贷分录）
- 前端9个Vue组件（ReceivablePanel 4子Tab + PayablePanel 3子Tab）
- 45个后端测试全部通过

**v4.11.0 主要改进**（第四轮全量审查，31 项优化）:

*后端安全加固*:
- XFF 信任移除（仅用 socket IP 防限频绕过）、弱密码黑名单扩充（+3）、token_version 改用 F() 原子更新
- verify_token 改用异常体系、登录限频锁持有整个流程、健康检查移除时间字段

*后端数据一致性*:
- supplier credit TOCTOU 修复（select_for_update+事务内检查）、收款分配 re-read 加行锁
- SN 码竞态修复+错误信息脱敏、库存并发创建 IntegrityError 捕获、round→quantize 统一
- 删除发货单 reserved_qty 溢出防护、Schema-Model max_length 不匹配修复（3处）、新增采购单索引

*前端精度与安全*:
- 金额浮点累加 Math.round 包装、除零守卫、返利单项校验、logout 改用 Promise 模式
- checkAuth 中 logout 加 await、调拨用 available_qty、duplicateCartLine 补 _id
- 导入/导出添加 submitting 守卫、ensureLoaded 改 Promise.all 并行、backup API 路径编码

*DevOps*:
- 测试依赖拆分 requirements-dev.txt、.dockerignore 排除 tests/、db 日志轮转、HEALTHCHECK 60s

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
| `/api/dashboard` | dashboard.py | 163 | 统计看板 + 待办计数 |
| `/api/backup` | backup.py | 176 | 备份/恢复 |
| `/api/rebates` | rebates.py | 72 | 返利日志 |
| `/api/vouchers` | vouchers.py | 214 | 会计凭证 |
| `/api/account-sets` | account_sets.py | — | 账套管理 |
| `/api/chart-of-accounts` | chart_of_accounts.py | — | 科目管理 |
| `/api/accounting-periods` | accounting_periods.py | — | 会计期间 |
| `/api/ledgers` | ledgers.py | — | 总分类账/明细账/余额表 + Excel 导出 |
| `/api/receivables` | receivables.py | — | 应收管理（14端点：应收单/收款单/退款单/核销单 CRUD+确认+期末凭证） |
| `/api/payables` | payables.py | — | 应付管理（11端点：应付单/付款单/退款单 CRUD+确认+期末凭证） |
| `/api/sn` | sn.py | 60 | SN 码管理 |
| `/api/salespersons` | salespersons.py | 44 | 业务员 |
| `/api/settings` | settings.py | 30 | 系统设置 |
| `/api/operation-logs` | operation_logs.py | 22 | 操作日志 |
| `/api/product-brands` | product_brands.py | 18 | 产品品牌 |
| `/api/payment-methods` | payment_methods.py | 4 | 收款方式（工厂） |
| `/api/disbursement-methods` | disbursement_methods.py | 4 | 付款方式（工厂） |
