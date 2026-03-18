# 迭代记录

## v4.30.0 — 退货退款流程重构（2026-03-18）

> 退货退款从「业务员标记已退款」改为「财务确认后推送会计单据」，修正会计单据位置，新增退款管理 Tab。

### 核心变更

- **退款流程**：退货时选择「需要退款」→ 不生成会计单据 → 财务在退款管理确认 → 此时才创建 ReceiptRefundBill/DisbursementRefundBill（直接 confirmed 状态）
- **会计单据位置修正**：销售退货退款从收款单（ReceiptBill）移至收款退款单（ReceiptRefundBill）；采购退货退款从付款单（DisbursementBill）移至付款退款单（DisbursementRefundBill）
- **不需要退款**：直接转为客户/供应商在账资金，订单立即结清

### 新增

- **退款管理 Tab**（财务管理）：合并展示销售/采购待退款记录，财务确认后推送会计模块
- **退款确认 API**：`GET /api/finance/refunds`、`POST /api/finance/refunds/confirm-sales/{id}`、`POST /api/finance/refunds/confirm-purchase/{id}`
- **退款信息字段**：退货时可填写退款备注（银行账号、退款原因等）

### 模型变更

- `ReceiptRefundBill`：新增 `return_order`、`refund_info`；`original_receipt` 改为 nullable
- `DisbursementRefundBill`：新增 `purchase_return`、`refund_info`；`original_disbursement` 改为 nullable
- `ReceiptBill`：移除 `bill_type`、`return_order`
- `DisbursementBill`：移除 `bill_type`、`purchase_return`
- `Order`、`PurchaseReturn`：新增 `refund_info`

### 数据迁移

- `v030_refund_redesign`：自动将 `receipt_bills`/`disbursement_bills` 中 `bill_type='return_refund'` 的记录迁移到对应退款单表

---

## v4.29.0 — 样机管理模块（2026-03-18）

> 新增样机管理完整业务模块，覆盖样机入库、借出/归还、处置（转销售/翻新/报废/丢失），嵌入库存页面二级 Tab。

### 核心功能

- **DemoUnit 模型**：样机台账（编号/SN码/仓库+仓位/状态/成色/持有人/借出统计），支持 7 种状态（在库/借出中/维修中/已售/已报废/已丢失/已转良品）
- **DemoLoan 模型**：借出记录（3 种借出类型：客户试用/业务员携带/展会），含审批流（待审批→已审批→借出中→已归还）
- **DemoDisposal 模型**：处置记录（转销售/翻新转良品/报废/丢失赔偿），自动联动库存、SN码、应收单
- **两种入库方式**：从库存转入（扣减源仓库库存）/ 新采购入库，SN 码强制追踪
- **仓库-仓位联动**：新增样机时源仓库/目标仓库均支持仓位选择，下拉菜单内嵌可用库存显示
- **Excel 导出**：完整样机台账导出（含仓位列）

### 前端组件（7 个）

| 组件 | 说明 |
|------|------|
| `DemoManagementPanel.vue` | 顶层容器（统计卡片 + 内部 Tab） |
| `DemoUnitList.vue` | 样机台账列表（桌面表格+移动卡片，含仓库-仓位列） |
| `DemoUnitForm.vue` | 新增样机表单（仓库-仓位联动+可用库存内嵌下拉） |
| `DemoLoanForm.vue` | 借出申请弹窗 |
| `DemoLoanList.vue` | 借还记录列表 |
| `DemoReturnModal.vue` | 归还确认弹窗 |
| `DemoDisposalModal.vue` | 处置弹窗（转销售/翻新/报废/丢失 4 种类型） |

### 后端

- **14+ API 端点**：样机 CRUD + 借出/审批/拒绝/确认借出/归还 + 转销售/翻新/报废/丢失 + 统计 + Excel 导出
- **v029 迁移**：`demo_units` 表添加 `location_id` 外键
- **服务层**：事务保护、一机一借校验、库存联动、SN 码追踪、应收单自动生成

### Bug 修复

- **刷新丢失 Tab 状态**：StockView 的 topTab 同步到 URL query，刷新后保持样机管理页
- **Tortoise ORM nullable FK**：`select_related` 对 nullable FK 返回 QuerySet 而非 None，改为独立查询

---

## v4.28.0 — 迁移系统版本化改造 + 可观测性（2026-03-17~18）

> 迁移系统从单文件重构为版本化文件目录，新增请求级可观测性。

### 迁移系统

- **版本化迁移运行器**（`runner.py`）：29 个独立迁移文件（v001~v029），幂等执行，`_applied_migrations` 表追踪
- **拆分策略**：种子数据 → 索引 → 会计 → 采购退货 → 发票 → AI → 物流 → 代采 → 权限 → 约束 → 样机
- 删除旧 `migrations.py` 单文件，添加开发者 README

### 可观测性

- **请求日志中间件**：每个 HTTP 请求记录 method/path/status/duration_ms/request_id
- **request_id 追踪**：UUID4 注入每次请求，响应头 `X-Request-ID`
- **慢查询日志**：超过 500ms 的请求自动 WARNING 级别告警

---

## v4.27.0 — 仓位颜色标签 + SN码面板 + 快递扩充（2026-03-16~17）

> 仓位级颜色渲染、订单物流 SN 码面板、快递公司 28 家 + 代采代发通知待办。

### 仓位颜色系统

- **Location 模型**增加 `color` 字段（7 色：blue/green/red/yellow/purple/gray/orange）
- 仓库设置增加颜色选择器，颜色从仓库级迁移到仓位级
- 库存/销售页面仓位标签按颜色渲染
- 提取 `DEFAULT_LOCATION_COLOR` 常量，消除硬编码

### SN码 & 物流

- 订单详情物流卡片新增 SN 码面板（合并数据源 + 一键复制）
- 快递公司从 8 家扩充至 28 家 + 自提/自配送选项
- 代采代发发货对齐物流模块快递选项
- `SearchableSelect` 组件优化，提取共享快递辅助函数

### 代采代发通知

- 侧边栏代采代发模块添加待办 badge
- 仪表盘待办面板添加代采代发三类待办项（待付款/待发货/待收款）
- 代采代发模块接入 `todo-counts` 待办统计

### Bug 修复

- 修复多 worker 启动时迁移并发竞态（`pg_advisory_lock`）
- 修复购物车复制行按钮无响应
- 修复 9 个预存测试失败
- 代采代发订单列表去掉催字 badge，统一使用 `todo-dot` 红点
- v4.17.0 全量代码审查修复（安全加固 + 代码质量 + 数据库优化 + 前端无障碍）

---

## v4.26.1 — 代码质量优化 + 组件拆分（2026-03-16）

> Code Review 修复 + FinanceOrdersTab 组件拆分，提升可维护性。

### 组件拆分

- **FinanceOrdersTab.vue**（1226→574 行，-53%）：按弹窗边界拆分为 3 个独立组件
  - `FinanceOrderDetailModal.vue`（433 行）— 订单详情弹窗 + 退货表单，watch visible 加载数据
  - `FinanceOrderCancelWizard.vue`（319 行）— 3 步取消向导（确认商品→财务分配→退款方式）
  - 父组件保留列表/筛选/导出 + 简单/复杂取消路径分流逻辑

### Bug 修复

- **收款方式下拉框 key 冲突**：`:key` 从 `pm.code` 改为 `pm.id`，避免同名支付方式渲染异常
- **收款方式缺少账套区分**：下拉选项显示「账套名 - 方式名」格式

---

## v4.26.0 — 代采代发模块（2026-03-16）

> 新增代采代发（Dropship）完整业务模块，覆盖订单全生命周期管理、付款工作台、报表分析，含财务联动和物流追踪。

### 核心功能

- **DropshipOrder 模型**：35 个字段，覆盖采购/销售/物流/财务全维度；FK 循环规避（payable/disbursement/receivable_bill_id 使用 IntField）
- **订单全流程**：`draft → pending_payment → paid_pending_ship → shipped → completed`，任意非终态可取消
- **14 个 API 端点**：订单 CRUD + 提交/催付/批量付款/发货/完成/取消 + 月度汇总/毛利分析/应收未收报表 + 付款工作台
- **毛利计算**：区分专票（扣除进项/销项税额）和普票（采购含税作为成本），实时计算毛利和毛利率
- **发货方式**：供应商直发（direct）/ 过手转发（transit，自动生成虚拟出入库记录）

### 财务联动

- **提交**：自动创建 PayableBill（应付单）
- **批量付款**：按供应商合并生成 DisbursementBill + 付款凭证（类型"付"），支持银行转账/冲减借支两种方式
- **发货**：自动创建 ReceivableBill（应收单），关联平台订单号
- **取消回滚**：状态感知 — 草稿直接取消 / 待付取消应付 / 已付取消应付+付款单+红字冲回凭证

### 付款工作台

- 按供应商分组展示待付款订单，支持展开/折叠
- 供应商级全选 + 单笔勾选，实时统计已选金额
- 支持银行转账、冲减借支（关联员工）两种付款方式
- 顶部统计：待付笔数、合计金额、已预付笔数

### 报表

- **月度汇总**：按客户/供应商维度聚合订单数、采购额、销售额、毛利，支持月份切换
- **毛利分析**：按日期范围查看每笔订单的毛利和毛利率，含汇总行
- **应收未收**：展示已发货未收款订单，按发货天数降序排列（账龄预警），含已收/未收金额

### 前端

- **DropshipView**（57 行）：三 Tab 容器（订单/付款工作台/报表），路由 `/dropship`
- **DropshipOrdersPanel**（652 行）：订单列表，移动卡片+桌面表格响应式布局，状态/日期/搜索筛选，排序，列配置，分页摘要
- **DropshipOrderForm**（561 行）：新建/编辑表单，供应商快速创建，毛利实时计算，发货方式悬停说明
- **DropshipPaymentPanel**（272 行）：付款工作台
- **DropshipReportsPanel**（317 行）：报表面板（3 个子 Tab）
- **useDropshipOrder** composable（113 行）：列表状态管理（筛选/排序/列配置/分页/防抖搜索）
- **dropship.js** API 模块（34 行）：16 个导出函数

### 权限

- `dropship`：代采代发通用权限（订单 CRUD/提交/发货/完成/取消/报表）
- `dropship_pay`：批量付款扩展权限
- 启动时自动迁移权限到管理员角色（`_migrate_dropship_permissions`）

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/models/dropship.py` | DropshipOrder 模型 |
| `backend/app/routers/dropship.py` | 14 个 API 端点 |
| `backend/app/services/dropship_service.py` | 业务逻辑层（7 个核心函数） |
| `backend/app/schemas/dropship.py` | 5 个 Pydantic Schema |
| `frontend/src/views/DropshipView.vue` | 页面视图 |
| `frontend/src/components/business/DropshipOrdersPanel.vue` | 订单列表面板 |
| `frontend/src/components/business/dropship/DropshipOrderForm.vue` | 订单表单 |
| `frontend/src/components/business/dropship/DropshipPaymentPanel.vue` | 付款工作台 |
| `frontend/src/components/business/dropship/DropshipReportsPanel.vue` | 报表面板 |
| `frontend/src/composables/useDropshipOrder.js` | 列表 composable |
| `frontend/src/api/dropship.js` | API 模块 |

### 修改文件

- `backend/main.py`：注册 dropship router
- `backend/app/migrations.py`：代采代发建表 + 权限迁移 + receivable_bills 新增 dropship_order_id/platform_order_no 列
- `backend/app/models/ar_ap.py`：ReceivableBill 新增 dropship_order FK + platform_order_no 字段
- `frontend/src/router/index.js`：新增 `/dropship` 路由
- `frontend/src/components/layout/Sidebar.vue`：新增代采代发菜单项
- `frontend/src/utils/constants.js`：新增 dropship 权限和菜单常量

### 性能优化（同期）

- 游标分页替代 offset 分页（大数据集场景）
- 原生 SQL 聚合替代 ORM 循环计算
- 动画精简减少渲染开销

---

## v4.25.0 — 凭证增强 + 辅助核算扩展 + 发票下推 + 全局搜索（2026-03-15）

> 五大计划并行开发：凭证核心功能增强（Plan A）、辅助核算+勾单生成凭证（Plan B）、凭证 PDF 打印重写（Plan C）、发票多单合并下推（Plan D）、Bug 修复+体验优化（Plan E）。含 21 项 Code Review 修复。

### Plan A：凭证核心功能增强

- **VoucherPanel 重构**：619 行拆分为 3 个聚焦子组件（VoucherPanel 208 行 + VoucherListView + VoucherEntryListView），双视图切换（凭证列表/分录列表）
- **凭证号预览**：`GET /api/vouchers/next-number` 端点，新建凭证时实时预览下一个凭证号
- **批量操作**：`POST /api/vouchers/batch-submit`、`batch-approve`、`batch-post`，支持多选批量提交/审核/过账
- **分录列表 API**：`GET /api/vouchers/entries` 分页查询 + `GET /api/vouchers/entries/export` Excel 导出
- **凭证搜索**：`list_vouchers` 端点新增 `search` 参数，支持按凭证号/摘要模糊搜索
- **制单与审核分离**：系统设置新增 maker-checker 开关，强制制单人与审核人不同

### Plan B：辅助核算扩展 + 勾单生成凭证

- **银行账户管理**：新增 BankAccount 模型 + CRUD API（`/api/bank-accounts`），设置页集成管理界面
- **辅助核算扩展**：ChartOfAccount/VoucherEntry 新增 `aux_product`（商品）和 `aux_bank`（银行账户）维度，科目管理页支持 6 维辅助核算标志切换
- **勾单生成凭证**：`GET /api/receivables/pending-voucher-bills` 和 `/api/payables/pending-voucher-bills` 查询待生成凭证的单据，前端 VoucherGenerateModal 支持勾选单据 + 合并模式（`merge_by_partner`）批量生成凭证
- **凭证详情辅助核算展示**：VoucherDetailModal 展示商品/银行账户辅助核算 badge

### Plan C：凭证 PDF 打印重写

- **中式记账凭证格式**：重写 `generate_voucher_pdf`，标准 24x14cm 布局，含公司名/凭证类型/附件数/制单人/审核人等
- **中文大写金额**：新增 `amount_to_chinese` 函数，支持到仟亿级（超限抛 ValueError）
- **路由升级**：单张/批量 PDF 路由传递账套名称、凭证类型、附件数到 PDF 生成，分录含科目代码

### Plan D：发票多单合并下推

- **多单合并推送**：应收单/应付单支持多选合并推送发票，`InvoiceFromReceivableBatch` / `InvoiceFromPayable` Schema 接受 `bill_ids: list`
- **通用推送弹窗**：InvoicePushModal.vue 通用组件，展示已选单据明细表格 + 开票信息
- **防重复校验**：FK 关联 + JSON 字段交叉检查，防止同一单据被重复推送
- **应付单下推**：新增 `POST /api/invoices/from-payable` 端点，PayableBillsTab 集成多选推送
- **Customer 模型**：新增 `invoice_address` / `invoice_phone` 开票信息字段

### Plan E：Bug 修复 + 搜索 + 跨 Tab 刷新

- **全局搜索**：13 个 Tab 组件（应收/应付/发票/出入库）统一添加搜索框，后端 7 个 API 端点新增 `search` 参数
- **跨 Tab 刷新**：ReceivablePanel/PayablePanel 实现 `refreshKey` 模式，收款/退款/核销操作后自动刷新应收/应付单列表
- **useSearch composable**：提取通用搜索 debounce 逻辑（含 `onBeforeUnmount` timer 清理），13 个组件统一复用

### Code Review 修复（21 项）

- **[Critical]** 发票防重复校验从首单 FK 扩展为全量 `__in` 查询 + JSON 字段交叉检查
- **[Critical]** 合并模式凭证补充 `aux_employee_id` / `aux_department_id` 辅助核算
- **[Critical]** 批量提交/审核/过账添加 `transactions.in_transaction()` 事务包裹
- **[Critical]** `list_vouchers` API 补充 `search` 参数 + VoucherListView 传递搜索条件
- **[Critical]** `vouchers.py` 添加 `from __future__ import annotations`
- **[Critical]** ChartOfAccountsPanel `openAddForm` 补充 `aux_product`/`aux_bank` 重置
- **[Critical]** PDF 分录超页面时显示截断提示而非静默丢弃
- **[Important]** invoice push 函数添加事务包裹
- **[Important]** `int | None` 统一为 `Optional[int]`（Python 3.9 兼容）
- **[Important]** 日期参数 `date_from`/`date_to` 修正为 `start_date`/`end_date`（4 个 Tab）
- **[Important]** VoucherPanel 搜索添加 300ms debounce
- **[Important]** PayableBillsTab 补充 ColumnMenu 列可见性控制
- **[Important]** `invoice_type` 字段约束为 `Literal["special", "normal"]`
- **[Important]** 前端推送发票时过滤已取消单据 + toast 提示
- **[Important]** BillRef/GenerateVouchersRequest 提取到共享 `voucher_gen.py` Schema
- **[Important]** 标准库 import 移到文件顶部（receivables.py/payables.py）
- **[Important]** `next-number` 预览去除 `select_for_update` 行锁
- **[Important]** PDF `amount_to_chinese` 支持到仟亿级 + 超限 ValueError
- **[Important]** 清理死代码（`units_dec`/`table_w`）
- **[Suggestion]** `downloadBlob` 提取到 `useDownload` composable
- **[Suggestion]** VoucherDetailModal 银行账户 badge 用青色区分员工 badge

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/models/bank_account.py` | BankAccount 银行账户模型 |
| `backend/app/routers/bank_accounts.py` | 银行账户 CRUD API |
| `backend/app/schemas/voucher_gen.py` | BillRef + GenerateVouchersRequest 共享 Schema |
| `backend/migrations/2026-03-15-plan-b-aux-bank.sql` | 辅助核算扩展迁移 |
| `backend/migrations/2026-03-15-plan-d-invoice-multi-source.sql` | 发票多源关联迁移 |
| `frontend/src/composables/useSearch.js` | 通用搜索 debounce composable |
| `frontend/src/composables/useDownload.js` | Blob 下载工具 composable |
| `frontend/src/components/business/VoucherListView.vue` | 凭证列表视图子组件 |
| `frontend/src/components/business/VoucherEntryListView.vue` | 分录列表视图子组件 |
| `frontend/src/components/business/VoucherGenerateModal.vue` | 勾单生成凭证弹窗 |
| `frontend/src/components/business/InvoicePushModal.vue` | 通用发票推送弹窗 |
| `frontend/src/components/business/settings/BankAccountSettings.vue` | 银行账户管理页 |

### 修改文件（27 个核心文件）

**后端模型**: accounting.py（aux_product/aux_bank）、voucher.py（aux_product/aux_bank FK）、customer.py（invoice_address/phone）、invoice.py（source_bill_ids JSON）

**后端路由**: vouchers.py（batch APIs/entries/search/next-number）、receivables.py（pending-voucher-bills/search/共享 Schema）、payables.py（同上）、invoices.py（from-payable）

**后端服务**: ar_service.py（合并辅助核算/Optional 统一）、ap_service.py（同上）、invoice_service.py（全量防重复/事务包裹）、pdf_print.py（重写 PDF/大写金额/截断提示）

**后端 Schema**: invoice.py（Literal 枚举/min_length）、voucher_gen.py（新建共享）

**前端组件**: VoucherPanel（重构拆分/debounce）、ChartOfAccountsPanel（aux 重置/badge）、VoucherDetailModal（aux 展示）、ReceivableBillsTab（多选推送/状态校验/useSearch）、PayableBillsTab（ColumnMenu/多选推送/状态校验/useSearch）+ 其余 11 个 Tab（useSearch 迁移/日期参数修正）

---

## v4.24.0 — 财务闭环与多账套完整性（2026-03-14）

> 五大财务完整性增强：退货退款自动推送收/付款模块、退款支持选择付款方式、账套从仓库自动推断、收付款方式按账套隔离、凭证辅助核算支持员工/部门维度。Salesperson 模型迁移为 Employee + Department 组织架构。

### 模块 1：退货退款财务闭环

- **销售退货**：确认退货时自动生成 `ReceiptBill(bill_type="return_refund")`，推送至收款模块
- **采购退货**：确认退货时自动生成 `DisbursementBill(bill_type="return_refund")`，推送至付款模块
- **退款方式选择**：退货表单新增退款方式（refund_method）和退款金额（refund_amount）字段
- **退款标识**：收款单/付款单列表中退货退款条目显示红色退款标签和备注
- **退款确认闭环**：确认退款收款单时自动标记退货订单 `is_cleared=True`；确认退款付款单时标记采购退货 `is_refunded=True`

### 模块 2：账套自动推断

- **去掉手动选择器**：订单确认弹窗中移除账套下拉选择器
- **自动推断**：从订单商品所在仓库的 `warehouse.account_set` 自动推断账套
- **多账套订单**：跨多个账套仓库的订单，应收单和收款单按账套拆分生成（事务安全）
- **多账套提示**：购物车和订单确认弹窗中显示多账套警告横幅

### 模块 3：收付款方式按账套隔离

- **数据模型**：PaymentMethod/DisbursementMethod 新增 `account_set` 外键，唯一约束改为 `(account_set, code)`
- **管理页**：收付款方式设置页新增账套 Tab 切换
- **业务联动**：销售开单、收款单、付款单中的付款方式下拉自动按当前账套过滤
- **CRUD Factory**：通用 CRUD 工厂支持 `account_set_id` 参数过滤和创建

### 模块 4：员工/部门辅助核算

- **组织架构**：新增 Department（部门）和 Employee（员工）模型，Employee 含 `is_salesperson` 标志
- **Salesperson 迁移**：删除旧 Salesperson 模型，全局替换为 Employee（含迁移脚本自动映射数据）
- **辅助核算扩展**：ChartOfAccount 新增 `aux_employee`/`aux_department` 标志，VoucherEntry 新增对应外键
- **凭证录入**：凭证页面支持选择员工和部门辅助核算维度
- **自动填充**：应收/应付凭证自动生成时，自动从订单的经办员工填充辅助核算

### 数据库迁移

- **迁移脚本**：`backend/migrations/2026-03-14-financial-integrity.sql`（15 步，仅已有数据库升级时需执行一次）
- **幂等安全**：所有操作带 `IF NOT EXISTS` / `IF EXISTS` 保护

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/models/department.py` | Department + Employee 模型 |
| `backend/app/routers/departments.py` | 部门 CRUD API |
| `backend/app/routers/employees.py` | 员工 CRUD API（含 is_salesperson/department_id 过滤） |
| `frontend/src/api/employees.js` | 部门/员工 API 模块 |
| `frontend/src/components/business/settings/DepartmentSettings.vue` | 部门管理页 |
| `frontend/src/components/business/settings/EmployeeSettings.vue` | 员工管理页 |
| `frontend/src/components/business/sales/CartItem.vue` | 购物车商品行组件 |
| `backend/migrations/2026-03-14-financial-integrity.sql` | 迁移脚本 |
| `backend/tests/test_employee_department.py` | 员工/部门/辅助核算测试（4 用例） |
| `backend/tests/test_payment_method_account_set.py` | 收付款方式账套隔离测试（2 用例） |

### 删除文件

| 文件 | 说明 |
|------|------|
| `backend/app/models/salesperson.py` | 旧业务员模型（→ Employee） |
| `backend/app/routers/salespersons.py` | 旧业务员 API |
| `backend/app/schemas/salesperson.py` | 旧业务员 Schema |
| `frontend/src/api/salespersons.js` | 旧业务员前端 API |
| `frontend/src/components/business/settings/SalespersonSettings.vue` | 旧业务员管理页 |

### 修改文件（40+ 文件）

**后端模型：** order.py（salesperson→employee, refund_method/refund_amount）、payment.py（account_set FK）、ar_ap.py（bill_type, return_order FK）、purchase.py（refund_method）、accounting.py（aux_employee/aux_department）、voucher.py（aux_employee/aux_department FK）

**后端路由：** orders.py（账套自动推断、多账套拆分、退款闭环）、purchase_orders.py（退款推送）、vouchers.py（辅助核算）、crud_factory.py（account_set_id）、receivables.py/payables.py（bill_type）、customers.py/finance.py/logistics.py（salesperson→employee）

**后端服务：** ar_service.py（退款确认闭环）、ap_service.py（退款确认闭环）、order_service.py（Employee 替换）、accounting_init.py（辅助核算预置）

**前端组件：** SalesView、ShoppingCart、OrderConfirmModal、VoucherPanel、ChartOfAccountsPanel、PaymentMethodSettings、ReceiptBillsTab、DisbursementBillsTab、FinanceOrdersTab、PurchaseOrderDetail、SettingsView、App.vue 等

---

## v4.23.0 — AI 数据助手 + 安全加固（2026-03-14）

> 集成 AI 数据助手（NL2SQL），支持自然语言查询业务数据；全面修复 AI 模块 10 项安全/稳定性/体验问题。

### 新增：AI 数据助手

- **自然语言查询**：用户用大白话提问，系统自动生成 SQL 查询 ERP 数据（销售/采购/库存/应收应付等）
- **预设快捷问题**：12 个高频查询模板，意图匹配直接执行，跳过 LLM 调用
- **流式响应（SSE）**：思考→生成→执行→分析，分阶段实时反馈
- **智能图表**：大数据集自动调用分析模型，生成 Chart.js 图表配置
- **细粒度权限**：按 `ai_sales` / `ai_purchase` / `ai_stock` / `ai_ar` / `ai_ap` 控制可访问的数据视图
- **反馈学习**：用户点赞可保存为 few-shot 示例，提升后续查询精度
- **会话持久化**：sessionStorage 保存对话历史，页面刷新不丢失
- **收藏功能**：常用问题可收藏，快速复用
- **导出 Excel**：查询结果一键导出

### 修复：AI 模块 10 项安全/稳定性问题

| # | 类别 | 问题 | 修复 |
|---|------|------|------|
| 1 | Bug | 前端本地回复拦截业务查询（"你好，今天销售怎么样"被当成问候语） | 加 BIZ_KEYWORDS 业务关键词保护，含业务词的消息跳过本地回复 |
| 2 | 安全 | 缓存键碰撞（不同对话上下文返回相同结果） | 缓存键加入 history 的 MD5 摘要 |
| 3 | 稳定性 | SQL 执行无行数上限，可能 OOM | 结果集超过 5000 行自动截断 |
| 4 | 安全 | 数据库错误信息泄露给 LLM | 新增 `_sanitize_db_error()` 脱敏映射 |
| 5 | 安全 | few-shot 反馈无审批机制，任意用户可污染示例库 | 普通用户提交标记 `approved=False` 待审批，admin 直接生效；加去重检查 |
| 6 | 并发 | few-shot 写入竞态条件 | 用 `select_for_update()` + 事务保护 |
| 7 | 安全 | History 输入验证不足 | 校验 role 合法性 + 200KB 总大小限制 |
| 8 | 安全 | 消息清洗不完整（Unicode 控制字符绕过） | 用 `unicodedata.category` 过滤 + 2000 字长度限制 |
| 9 | 准确性 | Prompt 缺少时区信息，CURRENT_DATE 可能与用户预期不一致 | 动态注入当前日期、星期、时区到 system prompt |
| 10 | Bug | 前端 SSE 解析边界处理不完整 + 超时判断不适配 Fetch API + 重试无 loading 防护 | 重构 SSE 解析逻辑 + 修正超时检测 + 加 loading 守卫 |

### 新增 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ai/status` | GET | AI 助手可用性检查（含预设问题列表） |
| `/api/ai/chat` | POST | AI 聊天接口（SSE 流式响应） |
| `/api/ai/chat/export` | POST | 导出查询结果为 Excel |
| `/api/ai/chat/feedback` | POST | 用户反馈（点赞/点踩 + 保存为示例） |

### 修改文件清单

**后端（10+ 文件）：**
- `backend/app/ai/` — AI 模块（意图分类/SQL 校验/DeepSeek 客户端/prompt 构建/schema 注册/限流器）
- `backend/app/services/ai_chat_service.py` — 核心聊天服务（缓存/执行/分析/脱敏）
- `backend/app/routers/ai_chat.py` — API 路由（输入验证/限流/SSE 流）
- `backend/app/ai/prompt_builder.py` — 时区注入

**前端（4 文件）：**
- `frontend/src/composables/useAiChat.js` — 聊天逻辑（SSE 解析/本地回复/重试防护）
- `frontend/src/components/business/AiChatbot.vue` — 聊天浮窗组件
- `frontend/src/components/business/AiWelcome.vue` — 欢迎页组件
- `frontend/src/App.vue` — 集成 AI 浮窗入口

---

## v4.22.0 — 发票 PDF 附件管理 + 备份系统升级 + 安全加固（2026-03-11）

> 发票支持 PDF 附件上传/预览/下载/删除，备份格式从 SQL 升级为 tar.gz（数据库 + 上传文件完整打包），全量代码审查修复 5 个安全漏洞。

### 新增：发票 PDF 附件管理

- **上传**：每张发票支持上传最多 5 个 PDF 附件（单文件 ≤ 10MB），文件头魔数校验（`%PDF`）
- **预览/下载**：详情弹窗内直接预览 PDF（浏览器内联），支持下载
- **删除**：删除附件同步清理磁盘文件
- **存储**：`uploads/invoices/{year}/{month}/` 按年月归档，Docker volume 持久化挂载

### 新增 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/invoices/{id}/upload-pdf` | POST | 上传 PDF 附件 |
| `/api/invoices/{id}/pdf/{index}` | GET | 下载/预览 PDF |
| `/api/invoices/{id}/pdf/{index}` | DELETE | 删除 PDF 附件 |

### 升级：备份系统 SQL → tar.gz

- **备份格式**：从单一 `pg_dump` SQL 文件升级为 `tar.gz` 归档（包含 SQL dump + `uploads/` 目录）
- **恢复兼容**：自动识别 `.sql` 和 `.tar.gz` 格式，兼容旧备份恢复
- **上传恢复**：支持上传 `.sql` 或 `.tar.gz` 备份文件恢复（流式写入，≤ 100MB）
- **自动备份**：每日定时备份同步升级为 tar.gz 格式
- Docker volume 新增 `./uploads:/app/uploads` 挂载

### 安全加固（代码审查 5 项 RED 修复）

| # | 问题 | 修复 |
|---|------|------|
| 1 | `Invoice.pdf_files` 使用可变默认值 `default=[]` | 改为 `default=list` |
| 2 | PDF 下载/删除端点未校验文件路径 | 新增 `_safe_filepath()` 防路径遍历攻击 |
| 3 | 上传文件名直接使用发票号（可能含特殊字符） | `re.sub` 净化 + UUID 片段防并发冲突 |
| 4 | `tar.extractall()` 未设 filter（CVE-2007-4559） | 所有 3 处添加 `filter="data"` |
| 5 | SalesInvoiceTab 事件监听器泄漏 + setTimeout 竞态 | `onBeforeUnmount` 清理 + `await` 替代 |

### 其他修复

- 上传超限（10MB）时自动清理已写入的临时文件
- 备份上传超限（100MB）时同样清理临时文件
- `invoice_service.py` 作废发票 PDF 清理增加路径遍历防护
- `backup_service.py` 中 `import tempfile, shutil` 从函数作用域提升到模块顶层
- SalesInvoiceTab 操作列按钮样式对齐 VoucherPanel（统一边框/间距/悬停效果）
- 操作列表头与按钮居中对齐

### 修改文件清单

**后端（7 文件）：**
- `backend/app/config.py` — 修复 UPLOAD_ROOT 路径计算（2 级 dirname），启动时创建 `uploads/invoices/`
- `backend/app/models/invoice.py` — `pdf_files` 字段 `default=list`
- `backend/app/routers/invoices.py` — 新增 3 个 PDF 端点 + `_safe_filepath()` + 文件名净化
- `backend/app/routers/backup.py` — 上传超限清理
- `backend/app/services/backup_service.py` — tar.gz 备份/恢复 + `filter="data"` + 顶层 import
- `backend/app/services/invoice_service.py` — 作废清理路径校验
- `backend/app/schemas/invoice.py` — 无变更（已有完整 schema）

**前端（2 文件）：**
- `frontend/src/components/business/SalesInvoiceTab.vue` — PDF 上传/预览/删除 UI + 操作列样式统一 + 事件泄漏修复
- `frontend/src/api/accounting.js` — 新增 `uploadInvoicePdf`、`deleteInvoicePdf`、`getInvoicePdfUrl` 函数

**基础设施（2 文件）：**
- `docker-compose.yml` — 新增 `./uploads:/app/uploads` volume 挂载
- `Dockerfile` — 新增 `mkdir -p /app/uploads/invoices`

---

## v4.21.0 — 日历式日期选择器 + 列选择器修复（2026-03-11）

> DateRangePicker 重写为日历弹窗式交互（双击选择日期范围），新建 ColumnMenu 组件修复列选择器溢出问题，全站 9 个面板统一升级。

### 重写：DateRangePicker 日历式交互

- **完全重写 `DateRangePicker.vue`**：从两个独立 `<input type="date">` 升级为单一日历弹窗
- 点击触发器展开日历面板，显示 Calendar 图标 + 当前日期范围文字
- **双击式范围选择**：第一次点击选定开始日期，鼠标悬停实时预览范围，第二次点击确定结束日期
- 日历网格 7×6（周一起始），中文星期表头（一二三四五六日）
- 范围高亮：渐变半圆起止 + 蓝色中间色带，视觉清晰
- 今日指示器：加粗文字 + 蓝色圆点
- 快捷预设保留：今天、本周、本月、上月、近7天、近30天、本季度
- 月份导航：ChevronLeft/ChevronRight 切换月份
- Teleport 定位 + 点击外部关闭
- 完整暗色模式支持（CSS 变量）

### 新建：ColumnMenu 通用组件

- **新建 `ColumnMenu.vue`**：解决列选择器（⋮）下拉菜单被 `.card overflow:hidden` 和 `.table-container overflow-x:auto` 裁切的问题
- 使用 `<Teleport to="body">` + `position: fixed` 完全脱离父级裁切上下文
- **视口感知定位**：优先下方显示 → 空间不足切上方 → 都不够则贴顶+可滚动
- 动态 `max-height`（视口高度 - 16px 安全边距）+ `overflow-y: auto` 滚动
- 水平方向右对齐按钮，自动防超出左右边界
- Props: `labels`（列标签映射）、`visible`（列可见性映射）、`pinned`（固定列不可隐藏）
- Emits: `toggle`（切换列）、`reset`（重置列）

### 全站 9 个面板统一升级 ColumnMenu

| 面板 | pinned 列 |
|------|-----------|
| PurchaseOrdersPanel | `po_no` |
| FinanceOrdersTab | `order_no` |
| LogisticsView | （无） |
| StockView | `name` |
| FinancePaymentsPanel | `payment_no` |
| FinancePayablesPanel | `po_no` |
| VoucherPanel | `voucher_no` |
| ReceivableBillsTab | `bill_no` |
| ReceiptBillsTab | `bill_no` |

### 修改文件清单

**重写：**
- `frontend/src/components/common/DateRangePicker.vue` — 日历弹窗式日期范围选择器

**新建：**
- `frontend/src/components/common/ColumnMenu.vue` — 通用列选择器下拉组件（Teleport + 视口定位）

**前端（9 个面板迁移 ColumnMenu）：**
- `frontend/src/components/business/PurchaseOrdersPanel.vue`
- `frontend/src/components/business/finance/FinanceOrdersTab.vue`
- `frontend/src/views/LogisticsView.vue`
- `frontend/src/views/StockView.vue`
- `frontend/src/components/business/FinancePaymentsPanel.vue`
- `frontend/src/components/business/FinancePayablesPanel.vue`
- `frontend/src/components/business/VoucherPanel.vue`
- `frontend/src/components/business/ReceivableBillsTab.vue`
- `frontend/src/components/business/ReceiptBillsTab.vue`

---

## v4.20.0 — 全局筛选搜索增强 + 寄售库存销售价显示（2026-03-10）

> 六个模块全面添加筛选/搜索/重置功能，新建 SearchableSelect 通用组件，寄售库存改为显示实际销售价。

### 新增：SearchableSelect 通用组件

- **新建 `SearchableSelect.vue`**：可搜索下拉选择框，支持 v-model 双向绑定、模糊搜索（label + sublabel）、清除选择、点击外部关闭、ESC 关闭、自动聚焦搜索框
- 销售开单的客户选择从原生 `<select>` 升级为 SearchableSelect，支持按客户名/电话模糊搜索

### 新增：六模块筛选/搜索/重置

| 模块 | 新增筛选项 | 搜索关键字 |
|------|-----------|-----------|
| 订单明细 | 付款状态（已结清/未结清/待确认/已取消） | — |
| 欠款明细 | 订单类型（赊销/寄售结算）+ 日期范围 | 订单号/客户名 |
| 收款管理 | 确认状态（待确认/已确认）+ 日期范围 | 订单号/客户名 |
| 付款管理 | 采购状态（7种）+ 日期范围 | 采购单号/供应商 |
| 出入库日志 | 日期范围 | 商品名/SKU/仓库名 |

- 所有搜索框 300ms 防抖，避免频繁请求
- 所有模块统一添加重置按钮（lucide RotateCcw 图标）
- 日期控件移动端隐藏（`hidden md:block`），适配小屏

### 后端 API 扩展

- `GET /finance/all-orders` 新增 `payment_status` 参数 + 响应新增 `shipping_status` 字段
- `GET /finance/unpaid-orders` 新增 `order_type`、`start_date`、`end_date`、`search` 参数
- `GET /finance/payments` 新增 `is_confirmed`、`start_date`、`end_date`、`search` 参数
- `GET /finance/stock-logs` 新增 `search` 参数（商品名/SKU/仓库名）

### 筛选栏 UI 统一

- 所有筛选栏输入框统一为 `input-sm`（36px 高度、13px 字体），与会计模块标准一致
- 独立筛选栏（欠款/收款/付款）去掉 `card` 包装，改为 `flex flex-wrap items-center gap-2 mb-3` 裸布局
- 订单明细筛选栏从两行布局改为单行 `flex-wrap` 自动换行

### 寄售库存销售价显示

- 寄售库存列表改为显示实际销售价（来自 CONSIGN_OUT 订单的 unit_price），而非商品零售价
- 同商品不同价格的寄售库存按价格批次分行显示，使用 FIFO 分配剩余数量
- 后端 `/consignment/summary` 和 `/consignment/customer/{id}` 两个端点重写

### 修改文件清单

**新建：**
- `frontend/src/components/common/SearchableSelect.vue` — 可搜索下拉组件
- `docs/plans/2026-03-10-filter-search-design.md` — 筛选搜索设计文档
- `docs/plans/2026-03-10-filter-search-enhancement.md` — 筛选搜索实现计划

**后端：**
- `backend/app/routers/finance.py` — 4 个端点参数扩展 + payment_status/search 筛选逻辑
- `backend/app/routers/consignment.py` — 寄售库存 FIFO 价格批次重写

**前端：**
- `frontend/src/api/finance.js` — getPayments 接受 params
- `frontend/src/components/business/sales/ShoppingCart.vue` — SearchableSelect 替换原生 select
- `frontend/src/components/business/finance/FinanceOrdersTab.vue` — 付款状态筛选 + 重置 + UI 统一
- `frontend/src/components/business/finance/FinanceUnpaidTab.vue` — 完整筛选栏 + 防抖搜索 + 重置
- `frontend/src/components/business/FinancePaymentsPanel.vue` — 完整筛选栏 + 防抖搜索 + 重置
- `frontend/src/components/business/FinancePayablesPanel.vue` — 服务端筛选替代客户端过滤 + 重置
- `frontend/src/components/business/FinanceLogsPanel.vue` — 日期 + 搜索 + 重置
- `frontend/src/views/ConsignmentView.vue` — 销售价显示 + 价格批次分行

---

## v4.19.0 — 采购/销售退货会计联动 + 取消订单优化 + Bug 修复（2026-03-10）

> 采购退货独立建模并推送会计模块，销售退货补齐收款退款单，取消订单流程按收款状态智能简化，全量代码审查修复 10 个 Bug。

### 采购退货 → 会计联动（核心新功能）

- **新增 PurchaseReturn + PurchaseReturnItem 独立模型**，退货信息不再散落在原采购单字段上
- 退货单号规则 `PR-YYYYMMDD-NNN`，关联原采购单 + 供应商 + 账套
- 采购退货时自动推送会计模块：
  - 红字应付单 PayableBill（负金额）
  - 付款退款单 DisbursementRefundBill（draft，出纳确认）
- 退款的退到收款管理生成待确认收款记录（is_refunded=true 时）
- **新增 API**：`GET /api/purchase-returns`（分页列表）、`GET /api/purchase-returns/{id}`（详情）
- **采购导出增强**：CSV 新增 3 列（退货数量、退货金额、退款状态）

### 销售退货 → 会计联动

- 销售退货订单（refunded=true）自动生成 ReceiptRefundBill（收款退款单）
- 关联最近一笔已确认的 ReceiptBill，推送到收款管理

### 前端：采购退货 UI

- **PurchaseView 新增「退货单」Tab**：退货单列表 + 供应商筛选 + 分页 + 详情弹窗
- **PurchaseOrderDetail 新增「关联退货单」区域**：展示该采购单的所有退货记录、退款状态

### 取消订单流程优化

- **未发货 + 未收款** → 直接弹确认对话框取消，不再强制走 3 步向导
- **未发货 + 已收款** → 1 步向导（退款金额 + 退款方式选择）
- **部分发货 + 未收款** → 1 步向导（商品确认）
- **部分发货 + 已收款** → 3 步完整向导（不变）
- 现金退款时自动创建 ReceiptRefundBill 推送到收款管理

### 财务模块 Bug 修复

- **收款弹窗无响应**：FinanceUnpaidTab 被 `v-show="false"` 隐藏，弹窗也被一起隐藏。修复：`<Teleport to="body">` 将弹窗传送到 body 层级

### 全量代码审查修复（10 个 Bug）

- GET 请求去重 `.catch()` 未清理 Map
- `stores/warehouses.js`、`stores/finance.js`：catch 后未 throw，_loaded 标志异常
- `stores/app.js`：新增 `resetTransientState()` 方法
- `stores/auth.js`：logout 时清理瞬态状态；checkAuth 只在 401/403 时登出
- `router/index.js`：500 视为服务器错误而非认证失败
- `views/SalesView.vue`：`cart.value[0]` 可选链保护
- `views/CustomersView.vue`：`related_order` 可选链保护
- `routers/finance.py`：UPDATE 前加 `select_for_update` 防并发
- `routers/orders.py`：`refund_rebate` 上界校验
- `routers/stock.py`：`cost_price` 空值兜底 `Decimal('0')`
- `routers/product_brands.py`：新增 `require_permission("stock_view")`

### 其他修复

- **Dashboard**：`shipped_at` 字段不存在 → 改为 `updated_at`
- **登录页图片**：logo.png 404 修复（SPA fallback 增加静态文件 FileResponse）；外部 Unsplash 背景图替换为 CSS 渐变
- **Docker 镜像源**：OrbStack 配置国内镜像（腾讯云/中科大/网易）

### 修改文件清单

**新建：**
- `backend/app/models/purchase.py` — PurchaseReturn + PurchaseReturnItem 模型
- `backend/app/routers/purchase_returns.py` — 退货单 CRUD API
- `frontend/src/components/business/purchase/PurchaseReturnTab.vue` — 退货单 Tab
- `frontend/src/api/purchase.js` — 退货单 API 函数
- `docs/plans/2026-03-10-purchase-sales-return-accounting-design.md`
- `docs/plans/2026-03-10-purchase-sales-return-accounting.md`
- `docs/plans/2026-03-10-cancel-order-refund-design.md`
- `docs/plans/2026-03-10-cancel-order-refund.md`

**后端核心：**
- `backend/app/routers/orders.py` — 销售退货 ReceiptRefundBill + 取消订单优化
- `backend/app/routers/purchase_orders.py` — 采购退货重构 + 导出增强
- `backend/app/migrations.py` — PurchaseReturn 建表迁移
- `backend/app/models/__init__.py` — 注册新模型
- `backend/main.py` — 注册退货路由 + 静态文件 FileResponse

**前端核心：**
- `frontend/src/components/business/finance/FinanceOrdersTab.vue` — 取消向导重写
- `frontend/src/components/business/finance/FinanceUnpaidTab.vue` — 收款弹窗 Teleport
- `frontend/src/components/business/purchase/PurchaseOrderDetail.vue` — 关联退货单
- `frontend/src/views/PurchaseView.vue` — 退货单 Tab
- `frontend/src/views/LoginView.vue` — CSS 渐变背景

**Bug 修复（10 个文件）：**
- `frontend/src/api/index.js`、`stores/warehouses.js`、`stores/finance.js`、`stores/app.js`、`stores/auth.js`、`router/index.js`、`views/SalesView.vue`、`views/CustomersView.vue`
- `backend/app/routers/finance.py`、`routers/stock.py`、`routers/product_brands.py`、`routers/dashboard.py`

---

## v4.18.0 — 架构级性能优化：分页 + GET 去重 + 动画修复（2026-03-09）

> 全部大表格接入服务端分页（每页50条），GET 请求去重防止并发重复加载，Tab/页面快速切换不再白屏。

### 分页系统

- **新建 `usePagination.js` composable** — 可复用分页逻辑，提供 `page/totalPages/hasPagination/paginationParams`，输出 `{ offset, limit }` 与后端接口匹配
- **FinanceOrdersTab** — 订单明细表格接入分页，筛选/搜索/日期预设/Tab 切换自动回第1页
- **PurchaseOrdersPanel** — 采购订单表格接入分页（composable 层集成）
- **LogisticsView** — 物流列表接入分页，状态 Tab + 搜索联动
- **StockView（最复杂）** — 脱离 productsStore 全量数据，改为独立 API 调用 + 服务端搜索 + 分页；productsStore 保留给 SalesCart 等组件使用

### GET 请求去重

- `api/index.js` 包装 `get` 方法，同一 URL+params 的并发 GET 共享同一个 Promise
- blob/stream 请求（导出）不参与去重
- `finally()` 自动清理 Map，无内存泄漏

### 动画修复（快速切换白屏 Bug）

- 所有 `<Transition name="slide-fade" mode="out-in">` 添加 `:duration="{ enter: 250, leave: 120 }"`，强制 Vue 在指定时间后结束过渡，防止快速切换时 leave 动画未完成导致空白
- CSS 过渡时间恢复为可见值：进入 250ms / 离开 120ms（含 transform）
- 移除 App.vue 的 router-view 过渡（页面级过渡与重组件挂载冲突）
- 涉及 10 个 Tab 容器组件

### 修改文件清单

**新建：**
- `frontend/src/composables/usePagination.js` — 分页 composable

**前端核心：**
- `frontend/src/api/index.js` — GET 请求去重
- `frontend/src/styles/base.css` — slide-fade 过渡时间调整
- `frontend/src/App.vue` — 移除 router-view 过渡

**分页接入（composable + 视图）：**
- `frontend/src/components/business/finance/FinanceOrdersTab.vue` — 分页 UI + 筛选联动
- `frontend/src/composables/usePurchaseOrder.js` + `PurchaseOrdersPanel.vue` — 分页
- `frontend/src/composables/useShipment.js` + `LogisticsView.vue` — 分页
- `frontend/src/composables/useStock.js`（重写：独立 API + 服务端搜索）+ `StockView.vue` — 分页

**动画修复（10 个 Tab 容器）：**
- `AccountingView.vue`, `FinanceView.vue`, `CustomersView.vue`, `SettingsView.vue`, `PurchaseView.vue`
- `ReceivablePanel.vue`, `PayablePanel.vue`, `InvoicePanel.vue`, `LedgerPanel.vue`, `FinancialReportPanel.vue`

---

## v4.17.0 — UI 重构：Modern Industrial 设计系统（2026-03-09）

> 全面重构前端 UI 系统，建立 OKLCH 色彩 Token 体系 + Tailwind 4 主题配置，支持亮/暗双模式切换，消灭 1,370 处硬编码色值。新增侧边栏待办角标和仪表盘待办面板。

### P0：Token 基础设施
- 新建 `styles/theme.css` — Tailwind 4 `@theme` 配置，CSS 变量映射为工具类
- 重写 `styles/base.css` — `:root` / `[data-theme="dark"]` 定义 60+ OKLCH 色彩 Token
- 主色从 Apple Blue `#0071e3` 改为 Steel Blue `oklch(0.55 0.20 250)`
- 中性色改为 Zinc 冷灰（无色温），暗色模式完整覆盖
- `stores/app.js` 新增 `theme` / `setTheme` / `toggleTheme` / `initTheme`
- `index.html` 添加 FOUC 防闪烁内联脚本

### P1：公共组件迁移
- `base.css` 组件层全部迁移 CSS 变量：`.btn` / `.input` / `.badge` / `.modal` / `.tab` / `.toggle` / `.card` 等
- `AppTable.vue` / `constants.js shipmentStatusBadges` 去除 `[#hex]`

### P2：全局色值批量替换
- 57 个 Vue 文件，3 轮脚本执行，共 1,370 处 `[#hex]` → Tailwind Token class
- 替换后 `grep -r '\[#' frontend/src/` 返回 0 结果

### P3：布局与视觉调整
- **后端** 新增 `GET /api/todo-counts` — 按用户权限返回 6 类待办数量（待发货/待审核/在途/待收款/低库存/待处理应收）
- **侧边栏** iOS 风格红色圆形角标 + 亮/暗模式切换按钮
- **仪表盘** 新增待办事项面板（按权限过滤，红色计数标签，点击跳转对应模块）
- 前端 API / Store / Sidebar / DashboardView 四文件联动

### P4：暗色模式完善
- `--shadow-*` 阴影 Token（暗色模式使用更强阴影，亮色保持轻盈）
- `--surface-translucent` 底栏半透明适配双模式
- SVG logo `stroke="white"` → `stroke="currentColor"` + `text-canvas` 适配主题反转
- Toast / Modal / Card 阴影全部改用 CSS 变量

### P5：打磨收尾
- 全局 `:focus-visible` 焦点样式（主色 outline + 2px offset）
- `prefers-reduced-motion` 媒体查询（尊重用户无障碍偏好）

### 修改文件清单

**后端：**
- `app/routers/dashboard.py` — 新增 `GET /api/todo-counts` 端点

**前端核心：**
- `src/styles/base.css` — 完全重写（CSS 变量 + 组件层 + 阴影 Token + 无障碍）
- `src/styles/theme.css` — 新建 Tailwind 4 `@theme` 配置
- `src/stores/app.js` — 主题切换 + todoCounts
- `src/App.vue` — initTheme + loadTodoCounts
- `index.html` — FOUC 防闪烁脚本

**布局组件：**
- `src/components/layout/Sidebar.vue` — 红色角标 + 主题切换 + SVG 适配
- `src/components/layout/BottomNav.vue` — Token class

**页面视图：**
- `src/views/DashboardView.vue` — 待办面板
- `src/views/LoginView.vue` — SVG 适配暗色
- 57 个 Vue 文件 — 批量色值替换

**API：**
- `src/api/dashboard.js` — 新增 `getTodoCounts()`

**配置：**
- `CLAUDE.md` — 主色修正
- `docs/plans/2026-03-09-ui-refactor.md` — 完整设计文档

---

## v4.16.0 — 数据库性能优化 + 发货事务 Bug 修复（2026-03-05）

> 物流列表分页、N+1 查询消除、9 张表添加索引；修复发货操作事务回滚和凭证号重复两个关键 Bug。

### 性能优化

| 优化项 | 文件 | 效果 |
|--------|------|------|
| 物流列表分页 | `logistics.py` | `list_shipments`/`list_pending_orders` 加 offset/limit，返回 `{"items":[], "total":N}` |
| 采购收货消除 N+1 | `purchase_orders.py` | 批量预加载 PurchaseOrderItem/Warehouse/Location/SnConfig，每商品 6→2 次查询 |
| 发货流程消除 N+1 | `logistics.py` | 批量预加载 OrderItem/SnConfig，每商品 3→1 次查询 |
| 9 张表添加索引 | `order.py` `shipment.py` `purchase.py` `payment.py` `sn.py` `operation_log.py` | 高频外键字段加复合索引 |

### Bug 修复

| Bug | 根因 | 修复 |
|-----|------|------|
| 发货后状态仍显示"待发货" | 出库单钩子在事务内部失败（凭证号重复），PostgreSQL 约束违反导致整个事务静默回滚，API 返回 200 但数据未持久化 | 将 AR/出库单钩子移到事务块外部（`logistics.py` L425-500） |
| 凭证号生成重复 | `next_voucher_no` 按 `period_name` 字段查询，已有凭证的 `period_name` 与 `voucher_no` 不匹配导致序号从 001 重新开始 | 改为按 `voucher_no` 前缀查询（`voucher_no.py`） |
| 付款管理列表为空 | `FinancePayablesPanel.vue` 未适配分页返回格式 `{"items":[],"total":N}` | `data` → `data.items \|\| data` |
| 物流列表渲染为空 | `useShipment.js` 同上原因 | `data` → `data.items \|\| data` |

### 修改文件清单

**后端:**
- `app/routers/logistics.py` — 分页参数、N+1 消除、钩子移出事务
- `app/routers/purchase_orders.py` — 收货 N+1 消除
- `app/utils/voucher_no.py` — 按 voucher_no 前缀查询替代 period_name
- `app/models/order.py` `shipment.py` `purchase.py` `payment.py` `sn.py` `operation_log.py` — 添加索引

**前端:**
- `src/composables/useShipment.js` — 适配分页格式
- `src/components/business/FinancePayablesPanel.vue` — 适配分页格式

---

## v4.15.0 — API 索引文档 + 6 大组件拆分重构（2026-03-04）

> 生成完整 API 端点索引文档（192 端点）；将 6 个 800+ 行的大组件拆分为瘦容器 + 19 个子组件 + 4 个 composable。

### API 索引

- 新增 `docs/API_INDEX.md`：按 35 个路由模块列出全部 192 个端点（方法/路径/说明/权限）

### 组件拆分

| 原组件 | 原行数 | 拆分后行数 | 新增子组件 |
|--------|--------|-----------|-----------|
| SettingsView.vue | 1083 | 96 | WarehouseSettings, PaymentMethodSettings, SalespersonSettings, UserSettings, PermissionSettings, LogsSettings |
| SalesView.vue | 939 | 386 | ProductSelector, ShoppingCart, OrderConfirmModal |
| PurchaseOrdersPanel.vue | 1087 | 166 | PurchaseOrderForm, PurchaseOrderDetail |
| FinanceOrdersPanel.vue | 876 | 71 | FinanceOrdersTab, FinanceUnpaidTab |
| LogisticsView.vue | 873 | 256 | ShipmentDetailModal |
| StockView.vue | 841 | 287 | ProductFormModal, RestockModal, TransferModal, ImportModal, ImportPreviewModal |

### 新增 Composable

| 文件 | 行数 | 用途 |
|------|------|------|
| useSalesCart.js | 165 | 购物车增删改算逻辑 |
| usePurchaseOrder.js | 86 | 采购单列表加载/筛选/导出 |
| useShipment.js | 149 | 发货列表加载/排序/列配置 |
| useStock.js | 151 | 库存列表加载/筛选/排序/导出 |

### 文件组织

```
components/business/
├── sales/          ProductSelector, ShoppingCart, OrderConfirmModal
├── purchase/       PurchaseOrderForm, PurchaseOrderDetail
├── finance/        FinanceOrdersTab, FinanceUnpaidTab
├── logistics/      ShipmentDetailModal
├── stock/          ProductFormModal, RestockModal, TransferModal, ImportModal, ImportPreviewModal
└── settings/       WarehouseSettings, PaymentMethodSettings, SalespersonSettings, UserSettings, PermissionSettings, LogsSettings
```

---

## v4.14.0 — 全量代码审查修复 + 权限管理 + 业务补丁（2026-03-04）

> 基于第五轮全量代码审查，修复 5 个 Critical、10 个 Important、4 个 Improvement 问题；新增权限管理系统；修复多个业务 Bug。

### Critical 修复

| # | 问题 | 修复 |
|---|------|------|
| C1 | 凭证号竞态条件（6处重复函数无锁） | 提取共享 `app/utils/voucher_no.py`，加 `select_for_update` 防并发 |
| C2 | `_next_voucher_no` 空值崩溃 | 共享函数增加 `account_set` 存在性检查 |
| C3 | 应付单并发修改无锁 | `create_disbursement_for_po_payment` 加事务包装 + `select_for_update` |
| C4 | Docker SECRET_KEY 已知明文默认值 | 改为 `${SECRET_KEY:?}` 强制设置，无默认值 |
| C5 | 16处原生 `confirm()` 弹窗 | 全部替换为 `appStore.customConfirm()`（12个Vue组件） |

### Important 修复

| # | 问题 | 修复 |
|---|------|------|
| I1 | 财务钩子静默失败 | 改为 `raise HTTPException(500)` 通知前端 |
| I2 | 订单取消拆分未复制 `account_set_id` | 拆分 `Order.create` 补 `account_set_id=order.account_set_id` |
| I3 | 6个详情端点无账套隔离 | 增加可选 `account_set_id` 查询参数过滤 |
| I4 | 金额缺少正数校验 | `PayableBillCreate.total_amount`、`InvoiceItemCreate.quantity/unit_price` 加 `gt=0` |
| I5 | 取消发票不清理凭证 | `cancel_invoice` 事务内删除关联凭证分录 |
| I6 | 反结账不检查后续期间 | `reopen_period` 检查是否存在已结账后续期间 |
| I7 | `token_version` 非原子更新 | 改用 `F('token_version') + 1` 原子操作 |
| I8 | 采购部分收货应付单金额错误 | 多次收货时更新已有应付单金额 |
| I9 | StockView/CustomersView 无 onMounted | 添加 `onMounted` 加载初始数据 |
| I10 | accounting store 静默吞错 | `catch(e) { /* ignore */ }` → `console.error` |

### Improvement 优化

| # | 内容 |
|---|------|
| P1 | `_next_voucher_no` 6处重复 → 抽取 `app/utils/voucher_no.py` 共享工具 |
| P4 | 现金流量表 O(n²) 查询 → 批量预加载（3条SQL） |
| P5 | 凭证批量PDF N+1 查询 → 批量加载（3条SQL） |
| P7 | 版本号 v4.9.0 → v4.13.0 |
| P8 | 备份上传整文件读入内存 → 流式写入 |

### 权限管理系统

| # | 内容 |
|---|------|
| 1 | SettingsView 新增"权限管理"Tab（admin可见）：左侧用户列表 + 右侧模块卡片 + iOS风格开关 |
| 2 | `constants.js` 新增 `permissionGroups`（10个模块分组） |
| 3 | PeriodEndPanel 权限检查从 `isAdmin` 改为 `hasPermission('period_end')` |

### 业务 Bug 修复

| # | 内容 |
|---|------|
| 1 | 客户/采购单列表不显示（API返回格式 `{items:[]}` 前端未解构） |
| 2 | 销售开单数量只能按+-修改 → 改为可手动输入的 `<input type="number">` |
| 3 | 物流列表新增"发货时间"列（可选显示） |
| 4 | 财务Tab"应收管理/应付管理"重命名为"收款管理/付款管理" |
| 5 | Docker 端口绑定 `127.0.0.1` → `0.0.0.0`（局域网访问） |

---

## v4.13.0 — 业财一体化会计模块：阶段4-5 + UI补丁（2026-02-28）

> 完成发票管理、出入库单、PDF套打、期末处理、三张财务报表、Excel/PDF导出，以及6个详情弹窗补全。至此五阶段全部完成，79个后端测试通过。

### 阶段4：发票 + 出入库单 + PDF套打

| # | 类别 | 内容 |
|---|------|------|
| 1 | 模型 | 6 个新模型：Invoice/InvoiceItem + SalesDeliveryBill/SalesDeliveryItem + PurchaseReceiptBill/PurchaseReceiptItem |
| 2 | 路由 | invoices.py（7端点）+ sales_delivery.py（4端点）+ purchase_receipt.py（4端点） |
| 3 | 服务 | pdf_print.py：3种PDF模板（凭证/出库单/入库单），reportlab 24×14cm |
| 4 | 钩子 | 发货完成→出库单+凭证(借1407/贷1405)、采购收货→入库单+凭证(借1405+借222101/贷2202) |
| 5 | 前端 | InvoicePanel(2子Tab：销项/进项) + SalesDeliveryTab + PurchaseReceiptTab |
| 6 | 测试 | 18 个新测试（4模型 + 14服务），全量 63 个通过 |

### 阶段5：期末处理 + 财务报表

| # | 类别 | 内容 |
|---|------|------|
| 1 | 服务 | period_end_service.py：损益结转(预览+执行) + 结账检查(5项) + 结账 + 反结账 + 年度结转(4103→4104) |
| 2 | 服务 | report_service.py：资产负债表 + 利润表(本期+本年累计) + 现金流量表(简易直接法) |
| 3 | 服务 | report_export.py：3张报表 × 2格式(Excel+PDF) = 6个导出函数 |
| 4 | 路由 | period_end.py（6端点：预览/执行/检查/结账/反结账/年度结转）+ financial_reports.py（6端点：3查询+3导出） |
| 5 | 迁移 | admin 用户添加 period_end 权限 |
| 6 | 前端 | PeriodEndPanel（期间状态+损益结转+结账检查+年度结转+反结账+期间历史）|
| 7 | 前端 | FinancialReportPanel（期间选择+3子Tab+导出） + BalanceSheetTab + IncomeStatementTab + CashFlowTab |
| 8 | 前端 | AccountingView 新增"期末处理"和"财务报表" 2个Tab |
| 9 | 测试 | 16 个新测试（9期末 + 7报表），全量 79 个通过 |

### UI补丁：详情弹窗 + API对接补全

| # | 内容 |
|---|------|
| 1 | ReceivablePanel/PayablePanel 新增"批量生成凭证"按钮（接入 generateArVouchers/generateApVouchers） |
| 2 | ReceivableBillsTab/PayableBillsTab 新增"查看"详情弹窗 |
| 3 | SalesDeliveryTab/PurchaseReceiptTab 新增"查看"详情弹窗（含商品明细表） |
| 4 | SalesInvoiceTab/PurchaseInvoiceTab 新增"查看"详情弹窗 + 草稿发票编辑功能（updateInvoice） |

---

## v4.12.0 — 业财一体化会计模块：阶段1-3（2026-02-28）

> 新增完整的会计模块，涵盖多账套管理、科目体系、凭证管理、账簿查询、应收应付管理，与现有业务流程自动衔接。

### 阶段1：基础设施

| # | 类别 | 内容 |
|---|------|------|
| 1 | 模型 | 新增 AccountSet（账套）、ChartOfAccount（科目）、AccountingPeriod（会计期间）模型 |
| 2 | 模型 | 改造 Voucher/VoucherEntry 支持凭证字（记/收/付/转）+ 账套隔离 + 辅助核算 |
| 3 | 服务 | accounting_init.py：32 个预置贸易企业标准科目自动初始化 |
| 4 | 路由 | 4 个新 Router：account_sets/chart_of_accounts/accounting_periods/vouchers |
| 5 | 迁移 | migrate_accounting_phase1()：新表 + 索引 + 5 个会计权限 |
| 6 | 前端 | AccountingView（账套切换/管理弹窗）+ VoucherPanel + ChartOfAccountsPanel + AccountingPeriodsPanel |
| 7 | 前端 | accounting store + API 层 + 路由/权限/菜单注册 |

### 阶段2：账簿查询

| # | 类别 | 内容 |
|---|------|------|
| 1 | 服务 | ledger_service.py：总分类账/明细账/余额表 3 个查询函数 |
| 2 | 服务 | ledger_export.py：3 个 Excel 导出函数（openpyxl） |
| 3 | 路由 | ledgers.py：6 个端点（3 查询 + 3 导出） |
| 4 | 前端 | LedgerPanel + GeneralLedgerTab + DetailLedgerTab + TrialBalanceTab |
| 5 | 测试 | 10 个账簿查询测试用例 |

### 阶段3：应收应付管理（AR/AP）

| # | 类别 | 内容 |
|---|------|------|
| 1 | 模型 | 7 个新模型：ReceivableBill/ReceiptBill/ReceiptRefundBill/ReceivableWriteOff/PayableBill/DisbursementBill/DisbursementRefundBill |
| 2 | Schema | 7 个 Pydantic Create 请求模型 |
| 3 | 服务 | ar_service.py（6函数）+ ap_service.py（5函数）：创建+确认+期末凭证生成 |
| 4 | 路由 | receivables.py（14端点）+ payables.py（11端点） |
| 5 | 钩子 | 发货完成→应收单、退货→红字应收、采购收货→应付单、采购付款→付款单 |
| 6 | 迁移 | 7 表 + 10 索引 + 6 个 AR/AP 权限（accounting_ar/ap_view/edit/confirm） |
| 7 | 前端 | ReceivablePanel（4子Tab）+ PayablePanel（3子Tab）= 9 个新 Vue 组件 |
| 8 | 前端 | 24 个 API 函数 + AccountingView 新增应收/应付 Tab |
| 9 | 测试 | 20 个测试用例（10 模型 + 10 服务），全量 45 个测试通过 |

### UI 修复与美化

| # | 内容 |
|---|------|
| 1 | 账套管理弹窗（无账套引导卡片 → 管理弹窗列表态/表单态） |
| 2 | 科目编辑复用新增 modal（编码/类别/方向 disabled） |
| 3 | 凭证反过账按钮 + 确认弹窗 |
| 4 | 订单/采购单自动带入仓库默认账套 |
| 5 | CSS 类名统一修复 + 操作按钮彩色药丸化 + 表格对齐 |

---

## v4.11.0 — 第四轮全量审查：安全加固+数据一致性+前端精度（2026-02-25）

> 第四轮全量代码审查（8 路并行代理），共完成 31 项修复，覆盖后端安全、数据一致性、前端金额精度、DevOps 优化。

### Critical 修复（12 项）

| # | 类别 | 修复内容 |
|---|------|---------|
| C1 | 安全 | XFF 信任移除，仅用 socket IP 防限频绕过 |
| C2 | 安全 | 弱密码黑名单扩充（+admin123/changeme/administrator） |
| C3 | 安全 | RequestSizeLimitMiddleware chunked 编码说明 |
| C4 | 安全 | token_version 改用 F() 原子更新防并发丢失 |
| C5 | 数据 | supplier credit_balance TOCTOU（select_for_update+事务内检查） |
| C6 | 数据 | 收款分配 re-read 加 select_for_update |
| C7 | 数据 | SN 码竞态修复 + IntegrityError 信息脱敏 |
| C8 | 数据 | 库存并发创建 IntegrityError 捕获重试 |
| C9 | 前端 | 金额浮点累加 Math.round 包装 |
| C10 | 前端 | unit_amount 除零守卫 |
| C11 | 前端 | 返利单项金额校验 |
| C12 | DevOps | DB 弱默认密码警告 + .env.example 强化 |

### Important 修复（19 项）

| # | 类别 | 修复内容 |
|---|------|---------|
| I1 | 后端 | verify_token 改用异常替代混合返回类型 |
| I2 | 后端 | 登录限频锁持有整个 check-verify-increment 流程 |
| I4 | 后端 | 健康检查移除服务器时间字段 |
| I6 | 后端 | round() → Decimal.quantize() 统一 |
| I7 | 后端 | 删除发货单 reserved_qty 溢出防护 |
| I8-10 | 后端 | Schema-Model max_length 不匹配修复（warehouse/supplier/salesperson） |
| I11 | 后端 | 新增 purchase_orders 索引（status, supplier+created_at） |
| I12 | 前端 | checkAuth 中 logout() 加 await |
| I13 | 前端 | tempOldPassword 组件卸载时清除 |
| I14 | 前端 | 调拨用 available_qty 替代 quantity |
| I15 | 前端 | duplicateCartLine 补充 _id |
| I17 | 前端 | 导入/导出操作添加 submitting 防重复 |
| I20 | 前端 | ensureLoaded 改 Promise.all 并行加载 |
| FC-9 | 前端 | backup API 路径 encodeURIComponent |
| I21 | DevOps | 测试依赖拆分 requirements-dev.txt |
| I22 | DevOps | .dockerignore 排除 tests/pytest.ini |
| I23 | DevOps | db 服务添加日志轮转 |
| I24 | DevOps | HEALTHCHECK start-period 10s→60s |
| — | DevOps | .dockerignore 清理无效条目 |

---

## v4.10.0 — 第三轮全量审查与登录流程修复（2026-02-25）

> 基于第三轮全量代码审查（后端 + 前端 + 基础设施七路并行），共完成 45 项修复，涵盖并发安全、外键完整性、权限补全、登录流程修复与无限循环防御。同批次发现并修复 2 个生产级 Bug（强制改密流程卡死、logout 无限循环）。

### Critical（8 项）

| # | 文件 | 修复内容 |
|---|------|----------|
| 1 | `services/stock_service.py` | **RETURN 订单自锁**: `update_weighted_entry_date` 移除嵌套 `in_transaction` 和 `nowait=True`，消除退货流程内事务自死锁 |
| 2 | `routers/orders.py` | **并发双重取消**: `cancel_order` 订单查询改为 `select_for_update()`，防止并发请求同时恢复库存 |
| 3 | `routers/orders.py` | **退款零值校验**: `refund_amount` 判断改为 `is not None`（原 truthy 判断忽略 0 元退款）；移除库存释放后的重复退款金额校验 |
| 4 | `routers/logistics.py` | **shipped_qty 超扣**: 扣减改为 CAS 保护（`shipped_qty__gte=si.quantity` filter），防并发撤单导致字段变负 |
| 5 | `migrations.py` | **级联删除风险**: `order_items.warehouse_id/location_id` FK 由 `ON DELETE CASCADE` 改为 `SET NULL` |
| 6 | `migrations.py` | **级联删除风险**: `shipment_items.product_id/order_item_id` FK 由 `ON DELETE CASCADE` 改为 `RESTRICT` |
| 7 | `models/warehouse.py` + `migrations.py` | **虚拟外键**: `Warehouse.customer_id` 由裸 `IntField` 改为正式 `ForeignKeyField`，DDL 添加外键约束 + `idx_warehouse_customer_virtual` 部分唯一索引 |
| 8 | `api/index.js` | **去重请求误报**: 主动 abort 的重复请求（`ERR_CANCELED`）静默忽略，不触发错误 Toast；`dedupKey` 在 error 拦截器中正确清理 |

### Important（17 项）

| # | 文件 | 修复内容 |
|---|------|----------|
| 1 | `schemas/user.py` | **权限定义缺口**: `VALID_PERMISSIONS` 补全 `"customer"` / `"finance_confirm"` / `"logistics"` / `"settings"` 四个缺失权限 |
| 2 | `schemas/user.py` + `schemas/auth.py` | **密码长度不一致**: `UserCreate/UserUpdate.password` 和 `ChangePasswordRequest.new_password` 最短长度由 6 改为 8，与密码策略对齐 |
| 3 | `services/backup_service.py` | **恢复无安全备份**: 执行 `DROP SCHEMA` 前检查 `pre_backup` 是否创建成功，失败则中止恢复 |
| 4 | `main.py` | **畸形 Content-Length**: `RequestSizeLimitMiddleware` 捕获 `int()` 转换的 `ValueError`，避免 500 错误 |
| 5 | `routers/finance.py` | **收款竞态**: `create_payment` 的客户查询加 `select_for_update()` 行锁 |
| 6 | `routers/purchase_orders.py` | **采购无分页**: 列表接口添加 `offset/limit` 分页，返回 `{items, total}` |
| 7 | `routers/finance.py` | **导出无上限**: 财务导出添加 `.limit(10000)` 防超大结果集 |
| 8 | `routers/customers.py` | **交易无上限**: `get_customer_transactions` 添加 `.limit(500)` |
| 9 | `schemas/stock.py` | **数量无上限**: `RestockRequest.quantity` 和 `StockTransferRequest.quantity` 添加 `le=999999` |
| 10 | `stores/auth.js` | **checkAuth 重复调用**: 添加 `_checkPromise` 去重，并发多次调用共享同一 Promise |
| 11 | `stores/products.js` | **按仓库加载污染全局**: `loadProducts(warehouseId)` 仅更新仓库维度缓存，不再覆盖全局 `products.value` |
| 12 | `composables/useApi.js` | **缺少 put/del**: 添加 `put()` 和 `del()` 方法，支持 AbortController 取消 |
| 13 | `main.py` | **index.html 重复读取**: `_read_index_html()` 生产模式下缓存文件内容，避免每次请求都读磁盘 |
| 14 | `views/SalesView.vue` | **购物车 v-for key**: 使用 `_cartIdCounter` 生成稳定 `item._id` 作为 `:key`，消除 DOM 复用错误 |
| 15 | `views/SalesView.vue` | **退货 AbortController 泄漏**: `onUnmounted` 中止 `_returnOrderAbort` 并置空 |
| 16 | `views/SettingsView.vue` | **重复提交**: 6 个操作处理函数添加 `appStore.submitting` 防重复守卫 |
| 17 | `components/business/PurchaseOrdersPanel.vue` | **定时器泄漏**: `onUnmounted(() => clearTimeout(_poSearchTimer))` |

### Minor（18 项）

| # | 文件 | 修复内容 |
|---|------|----------|
| 1 | `migrations.py` | 添加 `idx_warehouse_customer_virtual` 部分唯一索引（`WHERE is_virtual = true`） |
| 2 | `schemas/warehouse.py` | `WarehouseUpdate.name` 添加 `min_length=1, max_length=200`；`LocationUpdate.code` 添加 `min_length=1, max_length=50` |
| 3 | `schemas/warehouse.py` | `LocationUpdate.name` 添加 `max_length=100` |
| 4 | `schemas/order.py` | `OrderItem.unit_price` 添加 `ge=0` 非负约束 |
| 5 | `schemas/order.py` | `OrderCreate.remark` 添加 `max_length=2000` |
| 6 | `routers/customers.py` | `list_customers` 返回 `{items, total}` 结构（与其他列表接口统一） |
| 7 | `services/order_service.py` | 移除未使用的 `from tortoise.transactions import in_transaction` |
| 8 | `migrations.py` | 添加 `products.category` 和 `products.brand` 字段索引，加速按品类/品牌查询 |
| 9 | `Dockerfile` | 锁定镜像版本：`node:20-alpine` → `node:20.19-alpine`，`python:3.12-slim` → `python:3.12.10-slim` |
| 10 | `utils/constants.js` | 移除 `menuItems` / `bottomNavItems` 中未使用的 emoji `icon` 属性 |
| 11 | `composables/useSort.js` | 移除未使用的 `computed` 导入 |
| 12 | `composables/usePermission.js` | 权限检查委托给 `authStore.hasPermission()`，消除重复逻辑 |
| 13 | `stores/warehouses.js` | 添加 `loading` 和 `error` ref，加载函数正确设置/清除状态 |
| 14 | `views/LogisticsView.vue` | localStorage 恢复列配置改为 `{ ...defaultColumns, ...savedColumns }` 合并默认值，防缺字段 |
| 15 | `stores/auth.js` | `logout()` 移除 `erp_last_active`（已在 `logout` 函数内统一清理） |
| 16 | `schemas/stock.py` | `StockTransferRequest` 注释补全 |
| 17 | `routers/auth.py` | `logout` 改用 `get_current_user_allow_password_change`，强制改密用户也可正常登出 |
| 18 | `api/index.js` | 401 拦截器仅对非 logout 端点触发 `_onUnauthorized`，防重入 |

---

### 登录流程 Bug 修复（同版本热修复）

**Bug 1 — 强制改密表单不显示（登录后卡死在登录页）**

- **根因**: `App.vue` 中 `v-if="authStore.user"` 控制模板分支。`doLogin()` 调用 `authStore.setAuth()` 后 `user` 变为非空，Vue 销毁旧 LoginView 组件（`showChangePwd` 重置为 `false`），重建新实例——改密表单永远不可见。
- **修复**:
  - `LoginView.vue`: `must_change_password` 时仅写 `localStorage.erp_token`，不调用 `authStore.setAuth()`，保持组件存活
  - `routers/auth.py`: `change-password` 接口返回新 `access_token` + `user`（因 `token_version++` 旧 token 已失效）
  - `LoginView.vue`: 改密成功后用新 token 调用 `authStore.setAuth()`，再跳转 `/dashboard`

**Bug 2 — logout 400+ 无限循环**

- **根因**: `logout()` 调用 `logoutApi()` 若返回 401，401 拦截器触发 `_onUnauthorized()` → `authStore.logout()` → `logoutApi()` → 401 → 无限递归，短时间内产生 400+ 并发请求。
- **修复**:
  - `api/index.js`: 401 拦截器检测 `/auth/logout` 端点，跳过 `_onUnauthorized` 调用
  - `stores/auth.js`: `logout()` 添加 `_loggingOut` 重入守卫，并发调用直接返回

---

## v4.9.0 — 第二轮全量审查与系统优化（2026-02-22）

> 基于第二轮全量代码审查（后端 + 前端 + 基础设施三方向并行），共完成 29 项优化，涵盖安全加固、性能提升、前端质量、基础设施和 Schema 验证。

### Phase 1: 安全与稳定性

| # | 文件 | 修复内容 |
|---|------|----------|
| 1 | `database.py` | **连接池超时**: 追加 `command_timeout=30&timeout=10` 参数，防止长查询耗尽连接池 |
| 2 | `routers/auth.py` | **登录限流竞态**: 添加 `asyncio.Lock` 保护 `_login_attempts` 字典的读-检查-写操作，防止并发绕过 |
| 3 | `routers/products.py` | **文件上传 MIME 验证**: 增加 content_type 白名单 + 文件头魔数校验（PK\x03\x04 / OLE2），拒绝伪造后缀 |
| 4 | `main.py` | **请求体大小限制**: 添加 `RequestSizeLimitMiddleware`，全局限制 50MB，超出返回 413 |
| 5 | `routers/auth.py` + `api/auth.js` + `stores/auth.js` | **登出接口**: 新增 `POST /api/auth/logout`（递增 token_version 使旧 Token 立即失效），前端 logout 改为 async 调用 |
| 6 | `docker-compose.yml` | **Docker 资源限制**: db 和 erp 服务均添加 `mem_limit: 512m` + `cpus: 1.0` |
| 7 | `main.py` | **版本号更新**: FastAPI title 更新为 v4.9.0 |

### Phase 2: 性能与可靠性

| # | 文件 | 修复内容 |
|---|------|----------|
| 8 | `routers/products.py` | **产品列表分页**: 添加 `offset/limit` 参数（默认 200，最大 1000），返回 `{items, total}` |
| 9 | `routers/users.py` | **用户列表上限**: 添加 `.limit(500)` 安全上限 |
| 10 | `services/order_service.py` + `routers/orders.py` | **N+1 查询优化**: 订单创建前批量预取 Product/Warehouse/Location（`filter(id__in=...)`），构建 `entities_cache` 字典传入 `resolve_item_entities` |
| 11 | `routers/orders.py` | **移除泛型异常捕获**: 删除 `except Exception` catch-all，让全局异常处理器处理意外错误 |
| 12 | `api/index.js` | **前端超时 + 重试**: axios 添加 `timeout: 30000`，GET 请求 5xx 自动重试一次（1s 延迟） |
| 13 | `services/stock_service.py` | **锁等待优化**: `select_for_update()` 改为 `select_for_update(nowait=True)`，锁冲突返回 409 提示重试 |
| 14 | `main.py` | **SPA fallback 修复**: `'.' in path` 改为 `_STATIC_EXTENSIONS` frozenset 白名单，避免 `/customer/john.doe` 被误判为静态文件 |

### Phase 3: 前端质量

| # | 文件 | 修复内容 |
|---|------|----------|
| 15 | 新建 `composables/useApi.js` | **AbortController 取消机制**: 可取消请求 composable，组件 unmount 时自动 abort 未完成请求 |
| 16 | `api/index.js` | **防重复提交**: 拦截器对相同 POST/PUT/DELETE 请求去重（`_pendingRequests` Map） |
| 17 | `stores/products.js` + `stores/customers.js` | **Store 错误状态**: 添加 `error` ref，加载失败时可被 UI 消费 |

### Phase 4: 基础设施

| # | 文件 | 修复内容 |
|---|------|----------|
| 18 | 新建 `tests/conftest.py` + `tests/test_auth.py` | **后端测试框架**: pytest + pytest-asyncio，SQLite 内存测试 DB，6 个认证/密码测试用例 |
| 19 | `requirements.txt` | 添加 `pytest>=8.0.0` + `pytest-asyncio>=0.23.0` |
| 20 | `Dockerfile` | **多 Worker + 泄漏保护**: CMD 改为 `--workers 2 --limit-max-requests 10000` |
| 21 | `.gitignore` | 添加 `*.log` |

### Phase 5: 验证增强

| # | 文件 | 修复内容 |
|---|------|----------|
| 22 | `schemas/product.py` | **SKU 正则**: `^[A-Za-z0-9\u4e00-\u9fff\-_.]+$`；价格字段添加 `le=99999999`；字符串添加 `max_length` |
| 23 | `schemas/order.py` | 数量 `le=999999`，单价 `le=99999999`，items 列表 `max_length=100` |
| 24 | `auth/password.py` | **密码策略加强**: 最低 8 位 + 10 个常见弱密码黑名单（大小写不敏感匹配） |

---

## v4.8.8 — 全量代码审查与安全加固（第八轮）（2026-02-21）

> 基于第八轮全量代码审查（覆盖后端 Models/Schemas/Routers/Services、基础设施、前端 Views/Components/Stores），共修复 ~45 个问题，涉及并发安全、输入校验、安全依赖升级、前端防重复提交等。

### 安全关键修复（Security Critical）

| # | 文件 | 修复内容 |
|---|------|----------|
| 1 | `requirements.txt` + `auth/jwt.py` | **CVE 修复**: `python-jose[cryptography]==3.3.0` 已弃用且有 CVE，迁移到 `PyJWT[crypto]>=2.8.0`，更新 import 和异常类（`JWTError` → `InvalidTokenError`） |
| 2 | `.dockerignore` | **敏感文件泄露**: 添加 `.env` / `.env.*` 排除规则，防止 `.env` 被打包进 Docker 镜像；修正 `main.py` → `/main.py` 避免误排除 `backend/main.py` |
| 3 | `main.py` | **Swagger 生产暴露**: 添加 `DEBUG` 环境变量检查，非 debug 模式下禁用 `/docs`、`/redoc`、`/openapi.json` |
| 4 | `routers/backup.py` | **路径遍历防护**: 文件名校验从简单的 `".." in filename` 黑名单改为 `re.match(r'^erp_[\w]+\.(sql\|db)$')` 正则白名单 |

### 并发安全修复（Concurrency）

| # | 文件 | 修复内容 |
|---|------|----------|
| 5 | `routers/stock.py` | 库存调拨添加 `select_for_update()` 行锁，防止并发超扣 |
| 6 | `routers/purchase_orders.py` | 采购退货、采购付款操作添加 `select_for_update()` 行锁；付款操作移入事务内执行 |
| 7 | `routers/finance.py` | 批量收款的订单查询添加 `select_for_update()` 行锁，替换 `order.save()` 为 `F()` 原子更新 |
| 8 | `services/order_service.py` | 寄售结算库存扣减从 `stock.quantity -= qty; await stock.save()` 改为 `F('quantity') - qty` 原子更新 |
| 9 | `routers/orders.py` | 取消订单时退款校验提前到库存释放之前，避免不可逆操作后才发现参数错误 |

### 输入校验加固（Schemas & Validation）

| # | 文件 | 修复内容 |
|---|------|----------|
| 10 | `schemas/order.py` | 所有金额字段添加 `ge=0` 约束（rebate_amount、refund_amount 等），防止负数注入 |
| 11 | `schemas/purchase.py` | rebate_amount、credit_amount 添加 `ge=0`；新增 `PurchasePayRequest` schema |
| 12 | `schemas/finance.py` | `payment_method` 添加 `min_length=1` |
| 13 | `schemas/logistics.py` | carrier_code/carrier_name 添加 `min_length=1` |
| 14 | `schemas/customer.py` | phone 添加 `max_length=50` |
| 15 | `schemas/sn.py` | brand 添加 `min_length=1, max_length=100` |
| 16 | `schemas/settings.py` | value 添加 `max_length=1000` |
| 17 | `schemas/product.py` + `schemas/salesperson.py` | Update schema 的 name 字段添加 `min_length=1` |

### 业务逻辑修复

| # | 文件 | 修复内容 |
|---|------|----------|
| 18 | `models/order.py` | `shipping_status` 默认值从 `"completed"` 修正为 `"pending"` |
| 19 | `services/order_service.py` | RETURN 订单创建时传递 `cost_price` 给 `update_weighted_entry_date`，确保退货入库正确更新加权成本 |
| 20 | `services/stock_service.py` | 加权日期/成本计算使用 `Decimal` 替代 `int*int/int` 浮点运算，避免精度丢失 |
| 21 | `auth/password.py` | 提取 `validate_password_strength()` 公共函数，消除 3 处重复密码校验代码 |
| 22 | `routers/users.py` | 管理员重置密码后设置 `must_change_password = True`；添加 `UPDATE_USER` 操作日志 |
| 23 | `utils/csv.py` | CSV 公式注入防护添加 `\n` 到危险字符列表 |
| 24 | `utils/query_helpers.py` | 分页查询添加 `offset = max(0, offset)` 和 `limit = max(1, ...)` 边界保护 |

### 数据库索引优化

| # | 文件 | 修复内容 |
|---|------|----------|
| 25 | `models/order.py` | Order 添加 `("customer_id", "created_at")` 复合索引 |
| 26 | `models/stock.py` | StockLog 添加 `("product_id", "warehouse_id", "created_at")` 复合索引 |
| 27 | `models/rebate.py` | RebateLog 添加 `("target_type", "target_id")` 复合索引 |

### 基础设施改进

| # | 文件 | 修复内容 |
|---|------|----------|
| 28 | `docker-compose.yml` | 端口绑定从 `"8090:8090"` 改为 `"127.0.0.1:8090:8090"`（仅本地监听）；添加 JSON 日志驱动和大小限制 |
| 29 | `frontend/vite.config.js` | 生产构建禁用 sourcemap（`sourcemap: false`），防止源码泄露 |

### 前端修复

| # | 文件 | 修复内容 |
|---|------|----------|
| 30 | `views/StockView.vue` | saveProduct/saveRestock/saveTransfer 添加 `submitting` 防重复提交 |
| 31 | `views/CustomersView.vue` | saveCustomer 添加 `submitting` 防重复提交 |
| 32 | `views/LogisticsView.vue` | submitShip 添加 `submitting` 防重复提交；搜索输入添加 300ms debounce |
| 33 | `views/ConsignmentView.vue` | 结算金额计算使用 `Math.round(x * 100) / 100` 避免浮点精度问题 |
| 34 | `components/FinanceOrdersPanel.vue` | debounce timer 添加 `onUnmounted` 清理；cancelOrder 添加 `submitting` 防重复提交 |
| 35 | `components/FinancePayablesPanel.vue` | 采购付款操作前添加 `customConfirm` 确认弹窗 |
| 36 | `components/PurchaseOrdersPanel.vue` | 搜索输入添加 300ms debounce |
| 37 | `components/FinanceRebatesPanel.vue` | 充值按钮添加 `v-if="hasPermission('finance')"` 权限控制 |
| 38 | `stores/warehouses.js` | `loadWarehouses` 添加 try-catch 错误处理 |
| 39 | `api/index.js` | 响应拦截器添加 404 状态码处理 |

---

## v4.8.7 — 全量代码审查修复（第七轮）（2026-02-21）

> 基于第七轮全量代码审查（18 个问题：4 高危 / 6 重要 / 8 轻微），覆盖后端路由层、认证层、数据库配置、安全中间件、前端状态管理和视图组件。确认 14 个真实问题并全部修复，其余 4 个为误报或已在前轮修复。

### 高危修复（Critical）

| # | 文件 | 修复内容 |
|---|------|----------|
| 1 | `routers/settings.py` + 新建 `models/system_setting.py` | **系统设置持久化**：原 GET/PUT 设置接口返回空值（未对接数据库），新建 `SystemSetting` 模型（key-value 表），设置接口改为真实读写数据库 |
| 2 | `routers/dashboard.py` | **SQL 注入风险**：仪表盘库龄统计使用 `INTERVAL '30 days'` 字符串拼接，改为 Python 层 `timedelta` 计算日期阈值后以参数 `$1`/`$2` 传入 |
| 3 | `routers/consignment.py` | **寄售库存竞态**：寄售结算/退货操作真实仓库库存时无行锁，添加 `select_for_update()` 防并发超扣 |
| 16 | 新建 `auth/password.py` + `routers/auth.py` + `routers/users.py` + `migrations.py` | **密码哈希升级**：从 `pbkdf2_sha256` 迁移到 `bcrypt`，新建 `password.py` 模块（passlib CryptContext，bcrypt 主选 + pbkdf2_sha256 兼容），登录时透明重哈希（`needs_rehash` → 自动升级） |

### 重要修复（Important）

| # | 文件 | 修复内容 |
|---|------|----------|
| 5 | `docker-compose.yml` | **SECRET_KEY 空值风险**：`SECRET_KEY: ${SECRET_KEY}` 在未配置环境变量时为空，添加默认值 `${SECRET_KEY:-change-me-to-a-random-secret-in-production}` |
| 6 | `routers/suppliers.py` | **供应商删除安全**：软删除前检查是否有未完成采购单和在账资金余额，防止误删有业务关联的供应商 |
| 7 | `routers/products.py` | **批量导入容错**：单行导入失败导致整批回滚，改用 PostgreSQL `SAVEPOINT` 逐行隔离，单行错误仅回滚该行，其余继续导入 |
| 9 | `main.py` | **CSP 安全头**：`SecurityHeadersMiddleware` 添加 `Content-Security-Policy` 响应头（`default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'`） |
| 10 | `routers/suppliers.py` + `routers/customers.py` | **月份列表性能**：交易月份列表从 ORM 全表扫描改为 `SELECT DISTINCT TO_CHAR(created_at, 'YYYY-MM')` 数据库聚合 |
| 15 | `database.py` | **数据库连接池**：添加可配置连接池参数（`DB_POOL_MIN`/`DB_POOL_MAX` 环境变量），通过 URL query params `?minsize=2&maxsize=10` 传递 |

### 轻微修复（Minor）

| # | 文件 | 修复内容 |
|---|------|----------|
| 4 | `main.py` | 版本号从 `v4.8.4` 更新为 `v4.8.6` |
| 12 | `routers/products.py` | `WarehouseStock.filter(id=0)` 改为 `WarehouseStock.none()`（语义更清晰，避免无意义查询） |
| 14 | `stores/app.js` | **Toast 队列化**：多条 Toast 不再互相覆盖，改为队列依次显示（最多缓存 3 条），相同消息自动去重，150ms 动画间隔 |
| 17 | `views/SalesView.vue` | **搜索竞态**：`searchReturnOrders` 添加 `AbortController`，快速切换订单类型时取消上次未完成请求，防止旧结果覆盖新结果 |

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/models/system_setting.py` | 系统设置 key-value 模型（Tortoise ORM） |
| `backend/app/auth/password.py` | 密码哈希模块（bcrypt + pbkdf2_sha256 兼容层） |

### 修改文件统计

- 后端路由层：6 个文件（settings、dashboard、consignment、suppliers、customers、products）
- 后端认证层：3 个文件（password.py 新建、auth.py、users.py）
- 后端核心：3 个文件（main.py、database.py、migrations.py）
- 后端模型：2 个文件（system_setting.py 新建、\_\_init\_\_.py）
- 前端：2 个文件（stores/app.js、views/SalesView.vue）
- 部署：1 个文件（docker-compose.yml）
- 总计：**17 个文件，14 个有效修复**

---

## v4.8.6 — 全量代码审查修复（第六轮）（2026-02-20）

> 基于第六轮全量代码审查（48 个问题），覆盖后端路由层、服务层、认证支撑路由、前端 JS/Vue 共 20 个文件。审查发现 48 个问题，确认 25 个真实 bug 并全部修复，其余 23 个为误报或代码已正确。

### 后端路由层

| 文件 | 修复内容 |
|------|----------|
| `orders.py` | `float()` 转换金额改为 `Decimal` 直接相减，消除精度丢失 |
| `finance.py` | `Decimal(str(round(x,2)))` 改为 `Decimal(str(x)).quantize(Decimal('0.01'))` 精度修复；合并重复的搜索关键词提取逻辑 |
| `purchase_orders.py` | 添加采购收货数量除零防护（quantity == 0 时提前返回错误） |
| `stock.py` | **[CRITICAL]** 手动调库存操作改用 `select_for_update()` 行锁防 TOCTOU 竞态；消除双重库存查询改用 `refresh_from_db()` |

### 后端服务层

| 文件 | 修复内容 |
|------|----------|
| `routers/logistics.py` | **[CRITICAL]** 发货扣减库存加 `select_for_update()` 行锁；删除发货单恢复库存加行锁；SN 码重置加行锁；寄售库存恢复添加 `try/except` 错误处理 + 日志 |
| `order_service.py` | RESERVE/RESERVE_CANCEL 操作 StockLog 的 `before_qty`/`after_qty` 改为记录**可用库存**变化（`quantity - reserved_qty`）；删除 3 处不必要的 `refresh_from_db()` |

### 后端认证 & 支撑路由

| 文件 | 修复内容 |
|------|----------|
| `customers.py` | PostgreSQL 专有 `TO_CHAR + $1` 裸 SQL 改为 Tortoise ORM 查询，Python 层提取月份字符串（兼容性修复） |
| `auth.py` | **[SECURITY]** `X-Forwarded-For` 解析改为取最后一个 IP（由受信代理添加），防止客户端伪造 IP 绕过速率限制 |
| `locations.py` | 删除仓位路由补加 `is_active=True` 过滤，与 list/update 路由行为保持一致 |

### 前端 JS 逻辑修复

| 文件 | 修复内容 |
|------|----------|
| `router/index.js` | **[CRITICAL]** 路由守卫所有 `next()` 调用加 `return` 防止后续代码继续执行；提取 `checkPermAndNext` 辅助函数消除重复权限检查逻辑；竞态条件修复（统一异步检查入口） |

### 前端 Vue 组件修复

| 文件 | 修复内容 |
|------|----------|
| `LogisticsView.vue` | `v-for` key 由 `index` 改为 SN 值本身 / 时间+索引组合，防止 DOM 复用错误 |
| `FinanceOrdersPanel.vue` | 付款来源类型枚举补全：CASH（销售收款）、REFUND（退款）、CREDIT（账期回款）、CONSIGN_SETTLE（寄售结算） |
| `PurchaseOrdersPanel.vue` | 税率字段提交前加 `Number()` 转换；三处 `parseInt` 改为 `Number()`（receive_quantity 可含小数） |
| `PurchaseSuppliersPanel.vue` | 在账资金退款金额提交前 `toFixed(2)` 保证浮点精度 |
| `ConsignmentView.vue` | 结算提交前补充 `Number.isFinite`、`isInteger`、正数三重校验，防止 NaN/负数提交 |
| `FinancePayablesPanel.vue` | 应付款面板状态筛选补充 `partial`（部分到货）和 `completed`（已完成）选项 |
| `FinanceRebatesPanel.vue` | 返利流水明细补充 `refund`（退回）类型显示，绿色 `+` 号，与 `use`（使用，红色 `-`）区分 |

### 修改文件统计

- 后端路由层：4 个文件
- 后端服务层：2 个文件
- 后端认证支撑：3 个文件
- 前端 JS：1 个文件
- 前端 Vue 组件：7 个文件
- 总计：**17 个文件，25 个有效修复**

---

## v4.8.5 — 全量代码审查修复（第五轮）（2026-02-20）

> 基于第五轮全量代码审查（51 个问题），覆盖后端服务层、路由层、认证层、Schema 校验、前端 JS 逻辑、Vue 组件共 40+ 个文件。修复完成后进行二轮审查验证，发现并修复 5 个审查遗漏问题。

### 后端服务层（竞态条件 & 逻辑修复）

| 文件 | 修复内容 |
|------|----------|
| `stock_service.py` | **[CRITICAL]** 修复 `weighted_entry_date` else 分支：卖出库存时不再错误重置入库日期，改为三段逻辑（入库→重算加权日期，清零→重置，卖出有剩余→保持不变）；`except Exception` 改为 `except IntegrityError` 精确捕获唯一约束冲突 |
| `order_service.py` | 移除嵌套 `in_transaction()` 块；所有库存/返利/余额操作添加 `select_for_update()` 行锁防 TOCTOU；修复 CASH 退货余额调整（仅 CREDIT 退货调整客户余额） |
| `sn_service.py` | 报告所有重复 SN 码（非仅第一个）；`validate_and_consume_sn_codes` 使用事务 + `select_for_update()` |

### 后端认证层（安全加固）

| 文件 | 修复内容 |
|------|----------|
| `dependencies.py` | 提取 `_authenticate_user` 基础依赖；`get_current_user` 强制检查 `must_change_password`（返回 403）；新增 `get_current_user_allow_password_change` 仅用于改密和获取用户信息 |
| `schemas/auth.py` | `LoginRequest` 添加长度约束；`ChangePasswordRequest` 添加密码复杂度校验器（字母+数字）；`old_password` 添加 `max_length=128` 防 DoS |
| `schemas/user.py` | `UserUpdate.role` 和 `permissions` 改为 `Optional = None`，防止未传字段覆盖现有值 |
| `routers/users.py` | 条件字段更新（仅更新非 None 字段）；管理员自降级防护；密码重置校验强度并递增 `token_version` |
| `routers/auth.py` | 速率限制使用 `X-Forwarded-For` 获取真实 IP；改密/获取用户信息端点使用 `get_current_user_allow_password_change` |

### 后端路由层（业务逻辑 & 数据完整性）

| 文件 | 修复内容 |
|------|----------|
| `logistics.py` | **[CRITICAL]** 删除物流单时恢复源仓库库存（`quantity` + `reserved_qty` 同时恢复）+ 寄售仓扣减 + `shipped_qty` 回滚 + SN 码状态恢复 + 订单发货状态重算 |
| `orders.py` | 退款金额不超过已付金额校验；利润计算扣除返利（`profit = amount - cost - rebate`） |
| `purchase_orders.py` | `balance_after` 不再硬编码为 0，使用 `refresh_from_db()` 获取真实余额；供应商返利/在账资金检查使用 `select_for_update()` 防 TOCTOU |
| `finance.py` | `total_unpaid` 从 float 改为 `Decimal("0")` 起始值，全程 Decimal 运算 |
| `products.py` | 商品导入改为两阶段：先全量校验再写入数据库；DB 错误 `break` 防 PostgreSQL 事务级联失败 |
| `backup.py` | 流式大小检查（8KB 分块读取，超 100MB 立即拒绝） |
| `stock.py` | 库存调整检查 `reserved_qty`（不能低于预留量）；调拨检查可用库存（`quantity - reserved_qty`） |
| `suppliers.py` | `model_dump(exclude_unset=True)` 替代过滤 None（允许显式清空字段） |
| `customers.py` | 删除客户前检查关联订单数量 |

### 后端 Schema & 模型

- `purchase.py` 模型：`tax_rate` 默认值从 `0.13` 改为 `Decimal("0.13")`
- `order.py` 模型：`shipping_status` 默认值改为 `"completed"`（与迁移一致）
- 多个 Schema 文件添加 `Field` 长度/范围约束（product、salesperson、warehouse、supplier、purchase）

### 前端 JS 逻辑修复

| 文件 | 修复内容 |
|------|----------|
| `router/index.js` | 路由守卫改为 async，`user` 为 null 时先 `await checkAuth()`，修复刷新页面权限绕过 |
| `stores/products.js` | 带 `warehouseId` 过滤加载时不标记 `_loaded`，防止缓存污染 |
| `stores/warehouses.js` | `_loaded` 仅在 `loadWarehouses()` 和 `loadLocations()` 均成功后标记 |
| `composables/useFormat.js` | `fmtDate` 输出包含年份 |
| `composables/useSort.js` | 排序字段为 null/undefined 时不崩溃（null 排最后） |
| `composables/useTable.js` | `onUnmounted` 清理 debounce 定时器，防止销毁后回调执行 |
| `utils/helpers.js` | `amountToChinese` 先 `Math.round(n * 100) / 100` 再提取角分，修复浮点精度错误 |
| `stores/app.js` | `confirmDialog` resolve 调用后置 null 防双重触发；`closeModal` 不再清空 `previousModal` |

### 前端 Vue 组件修复

| 文件 | 修复内容 |
|------|----------|
| `SalesView.vue` | 购物车行小计/合计/提交 3 处统一使用 `Math.round(x * 100) / 100` 防浮点误差；非退货订单单价 ≤ 0 校验；表单重置补充 `customer_id` 和 `order_type`；确认弹窗小计同步使用 `Math.round` |
| `StockView.vue` | `v-for` + `v-if` 优先级问题改为 v-for 表达式内过滤（含 `?.` 空值保护） |
| `SettingsView.vue` | 共享的 `newLocationCode/Name` 改为 per-warehouse `newLocationInputs` ref，各仓库独立输入互不干扰 |
| `FinanceView.vue` | 添加 `needsRefresh` 跨 Tab 刷新机制 + `watch(financeTab)` 切换时触发刷新 |
| `PurchaseView.vue` | `onMounted` 中 `await nextTick()` 确保子组件已挂载再调用 `openPurchaseReceive()` |
| `ConsignmentView.vue` | 退货数据 `JSON.parse(JSON.stringify())` 深拷贝防止修改原始数据；`saveConsignReturn` 添加 `appStore.submitting` 防双击；结算/退货按钮添加 `:disabled` + 文字提示 |
| `LogisticsView.vue` | 列菜单点击外部关闭改用 `data-column-menu` 属性选择器（替代 `.relative` 类名误匹配） |
| `FinancePayablesPanel.vue` | 审核通过、拒绝、取消操作均添加 `customConfirm` 确认弹窗 |
| 7 个组件 | 所有空 `catch (e) {}` 块替换为 `console.error(e)` + Toast 提示（CustomersView、FinancePaymentsPanel、FinanceLogsPanel、FinanceRebatesPanel、FinanceOrdersPanel、PurchaseOrdersPanel、PurchaseSuppliersPanel） |

### 二轮审查验证（修复后复查）

修复完成后启动 3 个并行审查 agent 对所有修改进行复查，发现并修复 5 个遗漏：

| 严重度 | 文件 | 问题 | 修复 |
|--------|------|------|------|
| CRITICAL | `stock_service.py:91-94` | else 分支仍在卖出时重置 `weighted_entry_date` | 改为 `elif old_qty + add_qty <= 0`（仅清零时重置） |
| CRITICAL | `logistics.py:567-569` | 删除物流单恢复库存时未恢复 `reserved_qty` | 添加 `reserved_qty=F('reserved_qty') + si.quantity` |
| IMPORTANT | `stock_service.py:24,32` | `except Exception` 过于宽泛 | 改为 `except IntegrityError` |
| IMPORTANT | `schemas/auth.py:8` | `old_password` 无长度限制 | 添加 `Field(min_length=1, max_length=128)` |
| IMPORTANT | `FinancePayablesPanel.vue` | `handleRejectPO` 缺少确认弹窗 | 添加 `customConfirm('拒绝确认', ...)` |

### 修改文件统计

- 后端服务层：3 个文件
- 后端认证层：4 个文件
- 后端路由层：9 个文件
- 后端 Schema/模型：8 个文件
- 前端 JS：8 个文件
- 前端 Vue 组件：15 个文件
- 总计：**47 个文件**

---

## v4.8.4 — 全量代码审查修复（第四轮）（2026-02-19）

> 基于第四轮全量代码审查（90+ 问题），分 5 个维度全面修复：模型约束、服务层竞态、路由业务逻辑、Schema 校验、前端状态管理。

### 后端模型（on_delete 策略 & 完整性约束）

- **全部外键添加 `on_delete` 策略**：根据业务语义分配 `RESTRICT`（不允许删除被引用记录）、`SET_NULL`（置空）、`CASCADE`（级联删除），覆盖 Order、OrderItem、Payment、PurchaseOrder、Shipment、SnCode、StockLog 等所有模型
- **新增时间戳字段**：Customer/Supplier/Salesperson 添加 `updated_at`（auto_now）；PurchaseOrderItem/ShipmentItem/PaymentOrder 添加 `created_at`
- **修复 Order.shipping_status 默认值**：从 `"completed"` 改为 `"pending"`（新订单应为待发货）
- **新增 5 个数据库索引**：`shipments(tracking_no)`、`operation_logs(target_type, target_id)`、`operation_logs(created_at)`、`sn_codes(warehouse_id, product_id, status)`、`stock_logs(warehouse_id, product_id)`
- **新增时间戳列迁移**：`migrate_add_timestamp_columns()` 为 6 个新列执行幂等 DDL

### 后端服务层（竞态条件 & 精度修复）

- **stock_service.py**：`update_weighted_entry_date` 使用 `in_transaction()` + `select_for_update()` 防竞态；全部 float 运算改为 Decimal；`calculate_inventory_age` 改为同步函数；添加负库存防护
- **order_service.py**：`process_item_stock` 所有分支（CASH/CREDIT/CONSIGN_OUT/CONSIGN_SETTLE）使用 `in_transaction()` + `select_for_update()` 行锁；**修复 CASH 部分赊账 `is_cleared` 误标记为 True 的 bug**；`release_cancelled_stock` 使用 ID 直接访问避免未加载关联，释放部分数量并记录警告
- **sn_service.py**：`validate_and_add_sn_codes` 事务 + `IntegrityError` 捕获 + `bulk_create` 批量创建；`validate_and_consume_sn_codes` 支持 product_id/warehouse_id 参数校验
- **logistics_service.py**：HTTP 请求添加 `timeout=10`；响应状态码检查后再解析 JSON
- **operation_log_service.py**：日志写入包裹 try/except，防止日志失败导致业务中断
- **backup_service.py**：`auto_backup_loop` 中阻塞操作改用 `asyncio.to_thread()` 避免阻塞事件循环

### 后端路由（业务逻辑 & 安全修复）

| 文件 | 修复内容 |
|------|----------|
| `purchase_orders.py` | 修复可变默认参数 `body: dict = {}` → `None`；取消采购单时退还返利/在账资金；库存扣减改用原子 `F()` 表达式 |
| `customers.py` | 删除客户时检查 `rebate_balance != 0` |
| `locations.py` | 更新仓位时添加 `is_active=True` 过滤；使用 `exclude_unset=True` |
| `warehouses.py` | 创建/更新仓库默认标志包裹事务；使用 `exclude_unset=True` |
| `consignment.py` | 寄售退货虚拟仓库存记录 null 检查 |
| `logistics.py` | KD100 回调空 key 防护；`add_shipment` 添加订单类型校验；**`delete_shipment` 回滚 shipped_qty/SN 码/订单发货状态**（原代码仅删除记录不回滚数据） |
| `products.py` | `update_product` 改用 `exclude_unset=True`（修复无法将字段设为空值） |
| `stock.py` | CSV 导出从手动拼接改用 `csv.writer` 标准库（防 CSV 注入） |

### 后端 Schema & Auth & Core

- **Schema 全面加固**：`auth.py` 密码长度 8-128；`order.py` items 非空；`product.py` 价格 ≥ 0；`rebate.py` target_type Literal 校验、amount > 0；`consignment.py` quantity > 0、items 非空；`logistics.py` quantity > 0、items 非空；`user.py` permissions 字段校验器；`customer.py` name 长度 1-200
- **jwt.py**：分离 `ExpiredSignatureError` 处理，返回 `{"error": "expired"}` 供前端区分
- **dependencies.py**：`user_id` 类型校验（`isinstance(user_id, int)`）；过期 token 提示消息改进；权限不足提示显示所有可选权限
- **logger.py**：添加 `propagate = False` 防日志重复输出
- **database.py**：`generate_schemas` 添加 `safe=True` 防表已存在报错
- **time.py**：`to_naive()` 先转 UTC 再剥离时区（修复非 UTC 时区转换错误）
- **csv.py**：数值类型保留原始值（负数不再被错误引号包裹）
- **errors.py**：移除误导的 `-> HTTPException` 返回类型注解
- **main.py**：移除 index.html 缓存（确保前端部署后立即生效）；交换中间件注册顺序（CORS 优先）

### 前端修复

| 文件 | 修复内容 |
|------|----------|
| `api/index.js` | 401 拦截器通过 `setApiUnauthorizedHandler` 回调清空 auth store（修复 401 后 UI 状态残留） |
| `App.vue` | 注册 `setApiUnauthorizedHandler(() => authStore.logout())` |
| `stores/finance.js` | `ensureLoaded` 竞态修复：使用 promise 锁防并发重复请求，仅在成功后标记 `_loaded` |
| `stores/products.js` | `ensureLoaded` 竞态修复：同上 |
| `stores/customers.js` | `ensureLoaded` 竞态修复：同上 |
| `stores/warehouses.js` | `ensureLoaded` 竞态修复：同上 |
| `composables/useModal.js` | `isVisible()` 缓存 computed 引用（修复每次调用创建新 computed 的内存泄漏） |
| `composables/useIdleTimeout.js` | 事件处理器添加 5 秒节流（减少 mousemove/scroll 触发的 localStorage 写入频率） |
| `composables/useFormat.js` | `fmt()` 使用 `Number(v)` 转换（修复传入非数值字符串时 `.toFixed()` 崩溃） |
| `views/LogisticsView.vue` | `JSON.parse(localStorage)` 添加 try/catch（防止损坏数据导致页面白屏） |

### Dockerfile

- `--workers 2` → `--workers 1`：单 worker 防止 lifespan 双重执行（自动备份循环重复运行）

### 修改文件统计

- 后端模型：11 个文件 + migrations.py
- 后端服务：6 个文件
- 后端路由：8 个文件
- 后端 Schema/Auth/Core：15 个文件
- 前端：10 个文件
- 部署：1 个文件（Dockerfile）

---

## v4.8.3 — 前端组件拆分 & 全量验证修复（2026-02-17）

> 将两个超大视图组件拆分为独立业务面板，并对 v4.8.2 全量修复计划进行逐项验证，修复发现的 5 个遗留问题。

### 前端组件拆分

#### FinanceView.vue 拆分（1645 → 72 行）

将财务管理页面从单体组件拆分为 5 个独立业务面板：

| 子组件 | 职责 | 行数 |
|--------|------|------|
| `FinanceOrdersPanel.vue` | 订单明细 + 欠款明细（含订单详情、取消订单 3 步向导、收款、凭证预览） | ~700 |
| `FinancePaymentsPanel.vue` | 应收管理（收款记录、确认收款） | ~150 |
| `FinancePayablesPanel.vue` | 应付管理（采购订单付款确认、审核通过/拒绝） | ~260 |
| `FinanceLogsPanel.vue` | 出入库日志（排序、筛选） | ~120 |
| `FinanceRebatesPanel.vue` | 返利管理（客户/供应商返利充值、明细查看） | ~200 |

- 父组件仅保留 Tab 导航和跨面板事件协调
- `FinanceOrdersPanel` 使用 `v-show` 保持筛选状态（覆盖"订单明细"和"欠款明细"两个 Tab）
- 跨面板通信：`FinancePaymentsPanel` emit `view-order` → 父组件切换 Tab 并调用 `ordersPanel.viewOrder()`

#### PurchaseView.vue 拆分（1478 → 58 行）

将采购管理页面拆分为 2 个独立业务面板：

| 子组件 | 职责 | 行数 |
|--------|------|------|
| `PurchaseOrdersPanel.vue` | 采购订单（筛选、新建、详情、收货、退货、新建商品、税率设置、凭证） | ~850 |
| `PurchaseSuppliersPanel.vue` | 供应商管理（列表、新增/编辑、详情含采购历史和在账资金、退款） | ~300 |

- 父组件保留 Tab 导航、路由参数处理（`?action=receive`）、跨面板事件协调
- 各面板独立加载数据，通过 `defineExpose({ refresh })` 暴露刷新接口

#### 组件设计原则

- **Props/Emits/Expose 契约**：每个面板通过 `defineExpose` 暴露刷新方法，通过 `defineEmits` 向父组件发送事件
- **独立数据加载**：各面板在 `onMounted` 中独立加载所需数据，无需父组件传递
- **Store 共享**：共享数据（客户、产品、仓库）通过 Pinia 单例 store 访问，无需 prop drilling

### 全量验证修复

对 v4.8.2 计划中全部 47 个修改项进行逐项代码验证，发现并修复 5 个遗留问题：

#### Bug 修复

| 严重性 | 文件 | 问题 | 修复 |
|--------|------|------|------|
| 中 | `backend/app/routers/finance.py` | 财务订单列表 `total` 在 search 过滤前计算，分页 total 与实际结果不匹配 | 将搜索关键词过滤从 Python 层移到数据库层（`Q(order_no__icontains=...) \| Q(customer__name__icontains=...)`），确保 total 在所有筛选后计算 |
| 中 | `backend/app/routers/users.py` | 管理员编辑用户密码时缺少字母+数字混合校验，可绕过密码强度策略 | 在 `update_user` 接口密码更新前增加与 `create_user` 一致的校验逻辑 |
| 中 | `backend/app/routers/stock.py` | 库存导出库龄计算使用裸 `datetime.now()`，与 TIMESTAMPTZ 字段可能产生时区冲突 | 改用 `days_between(now(), entry_date)` 统一时区处理 |
| 低 | `backend/app/auth/dependencies.py` | `require_permission` 未调用 User 模型的 `has_permission()` 方法，权限检查逻辑重复 | 改用 `any(user.has_permission(p) for p in permissions)` 复用模型方法 |
| 低 | `frontend/.../PurchaseOrdersPanel.vue` | `cancelPurchaseOrder` 已 import 但从未使用（死代码） | 移除未使用的 import |

### 改动文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/views/FinanceView.vue` | 重写 | 1645 → 72 行，拆分为 Tab 导航 + 5 个子面板 |
| `frontend/src/views/PurchaseView.vue` | 重写 | 1478 → 58 行，拆分为 Tab 导航 + 2 个子面板 |
| `frontend/src/components/business/FinanceOrdersPanel.vue` | 新建 | 订单明细 + 欠款明细面板 |
| `frontend/src/components/business/FinancePaymentsPanel.vue` | 新建 | 应收管理面板 |
| `frontend/src/components/business/FinancePayablesPanel.vue` | 新建 | 应付管理面板 |
| `frontend/src/components/business/FinanceLogsPanel.vue` | 新建 | 出入库日志面板 |
| `frontend/src/components/business/FinanceRebatesPanel.vue` | 新建 | 返利管理面板 |
| `frontend/src/components/business/PurchaseOrdersPanel.vue` | 新建 | 采购订单面板 |
| `frontend/src/components/business/PurchaseSuppliersPanel.vue` | 新建 | 供应商管理面板 |
| `backend/app/routers/finance.py` | 修改 | 搜索过滤移到数据库层，修复分页 total |
| `backend/app/routers/users.py` | 修改 | 编辑用户密码增加强度校验 |
| `backend/app/routers/stock.py` | 修改 | 库龄计算统一时区处理 |
| `backend/app/auth/dependencies.py` | 修改 | require_permission 复用 has_permission() |

---

## v4.8.2 — 全量代码审查修复（2026-02-16）

> 基于第三次全量代码审查（63 个问题：18 高危 / 34 中等 / 11 低危），分 5 批完成安全性、性能、错误处理、架构、配置全方位修复。

### 安全性修复

- **Docker 敏感信息环境变量化**：`docker-compose.yml` 中 `POSTGRES_PASSWORD`、`DATABASE_URL`、`SECRET_KEY` 改为 `${VAR}` 引用，移除废弃的 `version: "3.8"`，添加显式网络定义
- **新增 `.env.example`**：列出所有环境变量及说明，`.env` 已加入 `.gitignore`
- **Dockerfile 安全加固**：添加非 root 用户 `appuser`、HEALTHCHECK、镜像源参数化（ARG）、uvicorn `--workers 2`
- **删除默认密码暴露**：GuideView.vue 中不再展示 admin/admin123 明文密码，改为"请联系管理员获取初始账号"
- **日志脱敏**：`migrations.py` 初始化日志不再输出明文密码
- **用户更新 Schema 分离**：新增 `UserUpdate`（password 可选），PUT 接口不再强制要求传密码
- **JWT Token 版本机制**：User 模型新增 `token_version` 字段，修改密码或禁用用户时递增版本号，旧 Token 自动失效
- **备份文件名白名单校验**：`backup_service.py` 添加正则白名单 `^[a-zA-Z0-9_.\-]+$` + `os.path.realpath()` 防路径穿越
- **CORS 收紧**：`allow_methods` 限制为 `GET/POST/PUT/DELETE/OPTIONS`，`allow_headers` 限制为 `Authorization/Content-Type`
- **KD100 回调 URL 默认值清空**：不再在代码中暴露生产域名
- **密码强度增强**：创建用户和修改密码时要求包含字母和数字
- **遗留代码归档**：根目录旧版 `main.py`（5102行）和 `index.html`（2938行）移至 `archive/` 目录

### 性能优化

- **寄售客户详情 N+1 修复**：`consignment.py` 批量查询 OrderItem 按 order_id 分组，消除循环内逐条查询
- **产品导入预览批量优化**：`products.py` 预先批量查询 Product/Warehouse/Location/WarehouseStock 到字典，循环中字典查找替代单条查询
- **供应商统计改用数据库聚合**：`suppliers.py` 使用 Tortoise ORM `annotate(Count/Sum)` 替代 Python 全量加载统计
- **订单列表 / 财务订单列表添加 offset 分页**：`orders.py`、`finance.py` 新增 `offset` 参数，返回 `{"items": [...], "total": N}`
- **SN 码导出优化**：`stock.py` 仅查询当前导出范围内的 SN 码，而非全部 in_stock

### 错误处理改进

- **migrations.py 异常日志化**：5 处 `except Exception: pass` 改为 `logger.warning` 记录异常与上下文
- **健康检查增加数据库检测**：`/health` 端点执行 `SELECT 1` 验证 DB 连接，返回 `db: true/false` 和 `status: ok/degraded`
- **日期解析异常保护**：`orders.py`、`finance.py` 共 4 处 `datetime.fromisoformat()` 添加 try/except，返回 400 而非 500
- **前端 settings store 错误处理**：9 个空 `catch` 块改为 `console.error` 输出错误信息
- **Toast 防覆盖**：`app.js` 添加 `clearTimeout` 防止多次 showToast 时 timer 覆盖导致提示消失

### 架构与代码质量

- **User 模型 `has_permission()` 方法**：统一权限检查逻辑，admin 角色自动拥有全部权限
- **通用 CRUD 工厂**：新增 `crud_factory.py`，`payment_methods.py` 和 `disbursement_methods.py` 从 ~70 行精简为 3 行工厂调用
- **Schema 提取**：内联 Schema 移至 `schemas/voucher.py`（VoucherGenerateRequest）和 `schemas/settings.py`（SettingUpdate）
- **前端 iconMap 统一**：从 App.vue / Sidebar.vue / BottomNav.vue 三处提取到 `constants.js` 统一导出
- **前端 IDLE_TIMEOUT 统一**：从 auth.js 和 useIdleTimeout.js 提取到 `constants.js`
- **API 拦截器 403 处理**：`api/index.js` 新增 403 状态码处理，提示"无权限执行此操作"

### 配置与工具

- **日志级别可配置**：`logger.py` 从 `LOG_LEVEL` 环境变量读取，默认 INFO
- **开发模式热重载条件化**：`main.py` 根据 `DEBUG` 环境变量决定是否启用 reload
- **数据库默认连接安全化**：`config.py` 默认 DATABASE_URL 移除密码（仅 localhost 开发用）
- **时间处理统一 UTC**：`time.py` 的 `now()` 返回 `datetime.now(timezone.utc)`
- **订单号随机部分加长**：`generators.py` 从 `token_hex(4)`（8字符）改为 `token_hex(6)`（12字符），降低碰撞概率
- **清理未使用 import**：`products.py` 移除 `urllib.parse.quote`，`stock_service.py` 移除 `SnConfig/SnCode`
- **Order 模型增加 updated_at**：`auto_now=True` 自动记录最后修改时间

### 修改文件统计

- 后端：24 个文件修改 + 4 个新建（`.env.example`、`.gitignore`、`crud_factory.py`、`schemas/settings.py`）
- 前端：10 个文件修改
- 配置/部署：3 个文件修改（docker-compose.yml、Dockerfile、.gitignore）
- 归档：2 个遗留文件移至 `archive/`

---

## v4.8.1 — 代码质量提升 & Bug 修复（2026-02-15）

### Bug 修复

- **采购成本价注释**：明确采购成本价 = 实际付款金额（扣除返利后）÷ 数量，反映真实资金成本，在代码和 README 中标注"请勿修改"
- **可退货数量计算错误**：退货订单中商品数量为负数导致 `available_return_quantity` 可能为负，修正为使用 `abs()` 并增加下限保护
- **采购金额浮点精度**：采购订单行金额改用 `Decimal` 替代 `round(float)`，避免财务计算精度丢失
- **收款金额精度**：`finance.py` 中客户余额更新时对金额先 `round(2)` 再转 `Decimal`
- **客户交易月份查询性能**：从加载全部订单改为 SQL `DISTINCT TO_CHAR` 聚合，消除大客户的内存风险

### 安全 & 并发

- **发货库存竞态条件**：发货扣减库存改用条件更新 `filter(quantity__gte=qty).update()`，防止并发超扣
- **物流跟踪静默失败**：快递100订阅/刷新异常从 `except: pass` 改为记录 warning 日志

### 代码质量

- **前端 Store 错误处理**：`customers.js`、`finance.js`（4处）、`warehouses.js`（2处）所有空 `catch` 块添加 `console.error`
- **LogisticsView 内存泄漏**：`document.addEventListener` 改为提取命名函数，`onUnmounted` 时正确移除
- **搜索输入防抖**：FinanceView 订单搜索添加 300ms 防抖，避免每次按键触发 API 调用

---

## v4.8 — 订单取消财务闭环 & UI 优化（2026-02-15）

### 核心变更

完善订单取消的完整财务闭环——取消订单时自动处理退款、退返利、拆单（部分发货场景），并对多处 UI 进行体验优化。

### 新增功能

#### 订单取消完整财务闭环
- 新增 `GET /api/orders/{id}/cancel-preview` 取消预览端点，返回拆单预览、逐商品财务分配默认值
- 重写 `POST /api/orders/{id}/cancel` 取消端点，支持完整财务回退：
  - **全部取消**（pending）：释放库存预留 → 退返利 → 退款（余额/现金二选一） → 标记 cancelled
  - **部分取消**（partial）：释放未发货库存 → 原订单标记 cancelled → 生成新订单（订单号+"-S"后缀，仅含已发货部分） → 迁移 Shipment/Payment 到新订单 → 退差额
- 新订单支持**逐商品财务分配**：每个已发货商品可独立设置使用多少现金、多少返利（影响开票单价）
- 新订单通过 `related_order` 关联原订单，双向可跳转查看

#### 订单详情退款信息展示
- 后端 `GET /api/orders/{id}` 新增 `rebate_refund_records`（退返利记录）和 `related_children`（拆分子订单）字段
- 前端订单详情弹窗：
  - Payment 记录正确区分"销售收款"/"账期回款"/"退款"三种来源
  - 退款记录橙色显示，带负号
  - 新增退回返利金额显示
  - 被取消的原订单显示拆分订单链接，新订单显示关联原订单链接

### UI 优化

#### 取消订单步骤式弹窗
- 原简单确认框改为 3 步引导式弹窗：
  - **步骤 1**：确认商品——绿色区块显示已发货商品（保留），红色区块显示取消商品（释放库存）
  - **步骤 2**：逐商品财务分配——表格形式显示每个商品的金额/使用现金/使用返利，每行联动，按比例预填可调整
  - **步骤 3**：退款确认——退款金额、退返利金额、退款方式（余额/现金）
- 步骤指示器圆点导航，根据场景自动跳过不需要的步骤
- 弹窗宽度增加到 640px

#### 购物车 sticky 全高
- 销售页面购物车从 `max-height: 70vh` 改为 `calc(100vh - 2rem)`
- 添加 `position: sticky; top: 1rem` 桌面端固定定位，滚动时购物车始终可见

#### 物流表格列可配置
- 搜索栏右侧新增 `⋯` 按钮，点击弹出列显示配置下拉菜单
- 10 列均可独立开关，SN码和物流信息默认隐藏
- 列偏好保存到 `localStorage`，刷新不丢失
- 表格添加 `min-width: 900px` + `overflow-x: auto`，窄屏横向滚动不压缩排版

### 改动文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/schemas/order.py` | 修改 | 新增 CancelItemAllocation、CancelRequest schema |
| `backend/app/routers/orders.py` | 修改 | 新增 cancel-preview 端点；重写 cancel 端点（完整财务闭环+逐商品分配）；get_order 返回退款记录和子订单 |
| `frontend/src/api/orders.js` | 修改 | 新增 cancelPreview API |
| `frontend/src/views/FinanceView.vue` | 修改 | 取消弹窗改为步骤式引导+逐商品分配；订单详情新增退款/退返利/拆分订单展示 |
| `frontend/src/views/SalesView.vue` | 修改 | 购物车 sticky 全高 |
| `frontend/src/views/LogisticsView.vue` | 修改 | 列可配置+横向滚动 |
| `frontend/index.html` | 修改 | 标题更新为 v4.8 |

### 新增 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/orders/{id}/cancel-preview` | 取消预览（拆单预览+逐商品默认财务分配） |

### 变更 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/orders/{id}/cancel` | 重写：支持拆单、财务回退、逐商品分配 |
| GET | `/api/orders/{id}` | 新增 rebate_refund_records、related_children 字段 |

---

## v4.7 — 发货流程重构：库存预留 & 拆单发货（2026-02-15）

### 核心变更

将库存扣减时机从**订单创建时**改为**发货确认时**，支持拆单发货，清晰记录每个包裹的商品明细和SN码。

### 新增功能

#### 库存预留机制
- 创建 CASH/CREDIT/CONSIGN_OUT 订单时，库存不再直接扣减，改为**预留**（`reserved_qty += qty`）
- 可用库存 = 实际库存 - 预留数量，销售页面和库存页面均展示可用库存
- 发货时才真正扣减库存（`quantity -= qty, reserved_qty -= qty`）

#### 发货操作（物流模块）
- 新增 `POST /api/logistics/{order_id}/ship` 发货端点
- 发货人可选择订单中的部分商品和数量进行发货（支持拆单）
- 每次发货创建独立的物流单（Shipment）和商品明细（ShipmentItem）
- 支持按商品行拆分和按数量拆分两种拆单方式
- 发货时校验SN码（跟随仓库配置：启用则必填，未启用则选填）
- 寄售调拨订单发货时自动执行虚拟仓入库

#### 订单发货状态
- Order 模型新增 `shipping_status` 字段：`pending`（待发货）→ `partial`（部分发货）→ `completed`（已完成）
- OrderItem 模型新增 `shipped_qty` 字段，追踪每个商品行的已发数量
- 历史订单自动迁移为 `completed` 状态

#### 订单取消
- 新增 `POST /api/orders/{order_id}/cancel` 取消端点
- 取消订单时释放未发货商品的预留库存
- 仅 `pending` 和 `partial` 状态的订单可取消

#### 待发货订单列表
- 新增 `GET /api/logistics/pending-orders` 端点
- 返回所有待发货/部分发货的订单及商品明细（含剩余未发数量）

#### ShipmentItem 模型
- 新增 `shipment_items` 表，记录每个包裹内的商品明细
- 字段：shipment_id, order_item_id, product_id, quantity, sn_codes

#### 快递公司列表
- 新增跨越速运（kuayue）到快递100快递公司列表

### 前端改动

#### 物流管理页面（LogisticsView.vue）
- 完整重构发货流程UI
- 新增发货表单：显示订单商品明细（总数量/已发/剩余），支持勾选商品+填数量+填SN码
- 每个物流单展示 ShipmentItem 商品明细
- 状态标签按 `shipping_status` 筛选

#### 财务订单明细（FinanceView.vue）
- 订单表格新增"发货"列，显示发货状态徽章
- 手机端订单卡片同步显示发货状态
- 订单详情弹窗显示发货状态，`pending`/`partial` 状态显示"取消订单"按钮

#### 库存管理页面（StockView.vue）
- 桌面端表格新增"预留"和"可用"两列
- 预留 > 0 时橙色高亮显示
- 手机端卡片同步显示预留/可用信息

#### 销售页面（SalesView.vue）
- 商品列表库存显示改为可用库存（`available_qty`）
- 购物车仓库/仓位下拉显示可用库存而非总库存
- 标签从"库存"改为"可用"

### 改动文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/models/stock.py` | 修改 | WarehouseStock 新增 reserved_qty |
| `backend/app/models/order.py` | 修改 | Order 新增 shipping_status；OrderItem 新增 shipped_qty |
| `backend/app/models/shipment.py` | 修改 | 新增 ShipmentItem 模型 |
| `backend/app/models/__init__.py` | 修改 | 导出 ShipmentItem |
| `backend/app/migrations.py` | 修改 | 新增 migrate_shipping_flow() 幂等迁移 |
| `backend/app/config.py` | 修改 | CARRIER_LIST 新增跨越速运 |
| `backend/app/routers/orders.py` | 修改 | 订单创建改预留；新增取消端点；查询返回 shipping_status |
| `backend/app/routers/logistics.py` | 修改 | 新增发货端点和待发货订单列表；物流详情返回 ShipmentItem |
| `backend/app/routers/products.py` | 修改 | 商品列表返回 reserved_qty 和 available_qty |
| `backend/app/schemas/logistics.py` | 修改 | 新增 ShipItemRequest 和 ShipRequest |
| `frontend/src/api/logistics.js` | 修改 | 新增 shipOrder 和 getPendingOrders |
| `frontend/src/api/orders.js` | 修改 | 新增 cancelOrder |
| `frontend/src/utils/constants.js` | 修改 | 新增 shippingStatusNames 和 shippingStatusBadges |
| `frontend/src/views/LogisticsView.vue` | 重写 | 发货流程UI完整重构 |
| `frontend/src/views/FinanceView.vue` | 修改 | 订单列表显示发货状态+取消按钮 |
| `frontend/src/views/StockView.vue` | 修改 | 新增预留和可用列 |
| `frontend/src/views/SalesView.vue` | 修改 | 库存显示改为可用库存 |

### 新增 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/logistics/{order_id}/ship` | 发货操作（选择商品+数量，扣减库存） |
| GET | `/api/logistics/pending-orders` | 待发货/部分发货订单列表 |
| POST | `/api/orders/{order_id}/cancel` | 取消订单，释放预留库存 |

### 数据库变更（自动迁移）

- `warehouse_stocks` 表新增: `reserved_qty` INT DEFAULT 0
- `orders` 表新增: `shipping_status` VARCHAR(20) DEFAULT 'completed'
- `order_items` 表新增: `shipped_qty` INT DEFAULT 0（历史数据回填 `ABS(quantity)`）
- 新增 `shipment_items` 表（shipment_id, order_item_id, product_id, quantity, sn_codes）

---

## v4.6 — 采购退货 & 供应商在账资金管理（2026-02-14）

### 新增功能

#### 采购退货
- 已完成的采购单支持部分退货或全部退货
- 退货时选择具体商品和数量，自动扣减对应仓库库存
- 生成 `PURCHASE_RETURN` 类型出库日志
- 全部退货后采购单状态变为"已退货"，部分退货保持"已完成"
- 支持填写退货物流单号

#### 供应商在账资金
- 退货未退款时，退货金额自动转为供应商"在账资金"
- 创建新采购单时可使用在账资金抵扣（类似返利机制）
- 支持手动在账资金退款操作（场景：短期内无二次采购计划）
- 在账资金流水记录完整追溯（退货转入/采购抵扣/手动退款）

#### 供应商详情
- 供应商表格/卡片可点击查看详情弹窗
- 详情包含：采购统计（单数/金额/已完成/已退货）、返利余额、在账资金
- 采购历史记录列表（支持按月筛选，点击跳转采购单详情）
- 在账资金流水明细

### 改动文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/models/purchase.py` | 修改 | PurchaseOrder 新增退货字段；PurchaseOrderItem 新增 returned_quantity |
| `backend/app/models/supplier.py` | 修改 | Supplier 新增 credit_balance 字段 |
| `backend/app/migrations.py` | 修改 | 新增 migrate_purchase_return_fields() 幂等迁移 |
| `backend/app/schemas/purchase.py` | 修改 | 新增 PurchaseReturnRequest；PurchaseOrderCreate 增加 credit_amount |
| `backend/app/schemas/supplier.py` | 修改 | 新增 CreditRefundRequest |
| `backend/app/routers/purchase_orders.py` | 修改 | 新增退货端点；详情/创建/列表/导出适配退货字段 |
| `backend/app/routers/suppliers.py` | 修改 | 新增 transactions 和 credit-refund 端点；list 返回 credit_balance |
| `frontend/src/api/purchase.js` | 修改 | 新增 returnPurchaseOrder/getSupplierTransactions/refundSupplierCredit |
| `frontend/src/utils/constants.js` | 修改 | 新增 returned 状态和 PURCHASE_RETURN 日志类型 |
| `frontend/src/views/PurchaseView.vue` | 修改 | 退货弹窗/供应商详情弹窗/在账资金抵扣UI/退款弹窗 |
| `frontend/src/views/FinanceView.vue` | 修改 | 应付管理增加已退货状态显示 |
| `frontend/vite.config.js` | 修改 | 开发代理端口修正为 8090 |

### 新增 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/purchase-orders/{id}/return` | 采购退货（选择商品和数量） |
| GET | `/api/suppliers/{id}/transactions` | 供应商详情（统计+采购记录+在账资金流水） |
| POST | `/api/suppliers/{id}/credit-refund` | 供应商在账资金退款 |

### 数据库变更（自动迁移）

- `purchase_orders` 表新增: return_tracking_no, is_refunded, return_amount, credit_used, returned_by_id, returned_at
- `purchase_order_items` 表新增: returned_quantity
- `suppliers` 表新增: credit_balance

---

## v4.5 — 全量代码审查与安全加固（2026-02-12）

### 审查范围
全量前后端代码审查，后端 5,052 行（80 个 .py 文件），前端 8,411 行（45 个 .vue/.js 文件）。
共发现 100 项问题，按优先级分为 5 个层级。全部 5 个优先级共 34 项已修复（8 BUG + 6 安全 + 6 性能 + 6 架构 + 8 代码质量）。

### 已修复 BUG

#### BUG-1: 前端路由权限未校验
- **文件**: `frontend/src/router/index.js`
- **问题**: 路由定义了 `meta.perm` 但 `beforeEach` 守卫只检查 token 存在，从未校验用户权限。任何登录用户可访问所有页面。
- **修复**: `beforeEach` 中增加 `authStore.hasPermission(to.meta.perm)` 校验，无权限时重定向 dashboard。

#### BUG-2: 空闲超时功能完全失效
- **文件**: `frontend/src/composables/useIdleTimeout.js`, `frontend/src/App.vue`
- **问题**: 引用了不存在的 `authStore.isLoggedIn`；不接受回调参数；超时用 `alert()` 阻塞。
- **修复**: 改为检查 `!!authStore.token`，支持 `onTimeout` 回调参数，改用 `showToast()` 通知。

#### BUG-3: 寄售退货仓位下拉未按仓库筛选
- **文件**: `frontend/src/views/ConsignmentView.vue`
- **问题**: 退货弹窗仓位下拉显示全部仓位，未根据仓库过滤。
- **修复**: 新增 `getReturnLocations(warehouseId)` 方法按仓库筛选；仓库变更时重置仓位。

#### BUG-4: OrderItem 模型缺少 warehouse_id/location_id 字段
- **文件**: `backend/app/models/order.py`, `backend/app/migrations.py`, `backend/app/routers/orders.py`
- **问题**: 寄售退货创建 OrderItem 传入 warehouse_id/location_id，但模型无此字段，数据被静默丢弃。
- **修复**: 模型增加 `warehouse` 和 `location` 可选外键；添加幂等迁移；订单创建时传入字段。

#### BUG-5: 库存调整未考虑仓位维度
- **文件**: `backend/app/schemas/stock.py`, `backend/app/routers/stock.py`
- **问题**: `StockAdjustRequest` 不含 `location_id`，多仓位时 `.first()` 返回随机记录。
- **修复**: Schema 增加 `location_id` 必填字段；路由增加仓位校验；查询增加仓位条件。

#### BUG-6: 多仓库商品成本价错误覆盖
- **文件**: `backend/app/routers/stock.py`, `backend/app/routers/purchase_orders.py`
- **问题**: 入库/采购收货将单仓库加权成本直接写入全局 `product.cost_price`，多仓库时跳变。
- **修复**: 改用 `get_product_weighted_cost()` 计算所有仓库的数量加权平均成本。

#### BUG-7: 物流页面移动端数据未排序
- **文件**: `frontend/src/views/LogisticsView.vue`
- **问题**: 桌面端用 `sortedShipments`，移动端用未排序的 `shipments`。
- **修复**: 移动端改为遍历 `sortedShipments`。

#### BUG-8: /health 端点被 SPA catch-all 拦截
- **文件**: `backend/main.py`
- **问题**: SPA `/{full_path:path}` 注册在 `/health` 之前，健康检查返回 HTML。
- **修复**: 将 `/health` 路由移到 catch-all 之前。

### 修改文件汇总

| 文件 | 变更类型 | 对应 BUG |
|------|---------|---------|
| `frontend/src/router/index.js` | 修改 | BUG-1 路由权限 |
| `frontend/src/composables/useIdleTimeout.js` | 重写 | BUG-2 空闲超时 |
| `frontend/src/App.vue` | 修改 | BUG-2 alert→toast |
| `frontend/src/views/ConsignmentView.vue` | 修改 | BUG-3 仓位筛选 |
| `frontend/src/views/LogisticsView.vue` | 修改 | BUG-7 移动端排序 |
| `backend/app/models/order.py` | 修改 | BUG-4 OrderItem 字段 |
| `backend/app/migrations.py` | 修改 | BUG-4 迁移 + PostgreSQL 兼容 |
| `backend/app/routers/orders.py` | 修改 | BUG-4 OrderItem 创建 |
| `backend/app/schemas/stock.py` | 修改 | BUG-5 增加 location_id |
| `backend/app/routers/stock.py` | 修改 | BUG-5 调整逻辑 + BUG-6 成本价 |
| `backend/app/routers/purchase_orders.py` | 修改 | BUG-6 成本价 |
| `backend/main.py` | 修改 | BUG-8 路由顺序 |

### 已修复安全问题

#### SEC-1: 并发单号重复（竞态条件）
- **文件**: `backend/app/utils/generators.py`, `backend/app/routers/vouchers.py`
- **修复**: 订单号随机部分从 `token_hex(2)` 升级为 `token_hex(4)`（碰撞概率降低 6.5 万倍）；凭证生成用 `@transactions.atomic()` + `select_for_update()` 防并发

#### SEC-2: 登录限流内存泄漏修复
- **文件**: `backend/app/routers/auth.py`
- **修复**: 改为每 60 秒定期清理过期记录（替代原来仅在 dict 超 10000 项时才清理的机制）；移除无用的 `LOGIN_MAX_IPS` 配置

#### SEC-3: CORS 默认值收紧
- **文件**: `backend/app/config.py`
- **修复**: CORS 默认从 `"*"` 改为仅允许 `localhost:5173` 和 `localhost:8090`；生产环境通过 `CORS_ORIGINS` 环境变量配置

#### SEC-4: 默认管理员首次登录强制改密
- **文件**: `backend/app/models/user.py`, `backend/app/migrations.py`, `backend/app/routers/auth.py`, `frontend/src/views/LoginView.vue`
- **修复**: User 模型增加 `must_change_password` 字段；默认 admin 创建时设为 true；登录接口返回该标志；前端登录页增加强制改密表单；改密后自动置为 false

#### SEC-5: Settings 端点增加 key 白名单
- **文件**: `backend/app/routers/settings.py`
- **修复**: 新增 `ALLOWED_KEYS = {"company_name"}` 白名单，GET/PUT 均校验，非法 key 返回 400

#### SEC-6: 迁移 SQL 参数化
- **文件**: `backend/app/migrations.py`
- **修复**: UPDATE 语句从 f-string 拼接改为 `$1` 参数化查询

### 安全加固修改文件汇总

| 文件 | 变更类型 | 对应项 |
|------|---------|--------|
| `backend/app/utils/generators.py` | 修改 | SEC-1 订单号随机位数 |
| `backend/app/routers/vouchers.py` | 修改 | SEC-1 凭证事务+行锁 |
| `backend/app/routers/auth.py` | 重写 | SEC-2 限流清理 + SEC-4 改密标志 |
| `backend/app/config.py` | 修改 | SEC-3 CORS 默认值 |
| `backend/app/models/user.py` | 修改 | SEC-4 must_change_password 字段 |
| `backend/app/migrations.py` | 修改 | SEC-4 迁移 + SEC-6 参数化 |
| `backend/app/routers/settings.py` | 修改 | SEC-5 key 白名单 |
| `frontend/src/views/LoginView.vue` | 重写 | SEC-4 强制改密 UI |

### 已修复性能优化（Phase 3）

#### PERF-1: N+1 查询修复（7+ 处）
- 所有 N+1 查询改为批量查询 + 内存关联（products, finance, stock, warehouses, consignment, orders, purchase_orders）

#### PERF-2: 整表数据加载优化
- `finance.py` — 物流搜索改为 DB 级 `icontains` 筛选
- `dashboard.py` — 库存总值+库龄分布改为单条 SQL 聚合
- `logistics.py` — 状态筛选改为 DB 级预过滤 + `select_related`

#### PERF-3: 列表端点限制
- 已有 `limit` 参数（默认 100-200），cap 1000

#### PERF-4: 前端按需加载
- `App.vue` — `loadAll()` 拆分为 `loadEssentials()` + `loadForRoute()`
- 各 store 增加 `ensureLoaded()` + `_loaded` 标志
- `router.afterEach` 钩子按路由触发加载

#### PERF-5: 数据库索引
- 新增 12 个复合索引（幂等迁移 `CREATE INDEX IF NOT EXISTS`）

#### PERF-6: SPA index.html 缓存
- `main.py` — 首次读取后缓存到全局变量

### 性能优化修改文件汇总

| 文件 | 变更类型 | 对应项 |
|------|---------|--------|
| `backend/app/routers/products.py` | 修改 | PERF-1 商品列表/导出批量查询库存 |
| `backend/app/routers/finance.py` | 修改 | PERF-1 收款/导出批量查询 + PERF-2 搜索优化 |
| `backend/app/routers/stock.py` | 修改 | PERF-1 SN码批量统计 |
| `backend/app/routers/warehouses.py` | 修改 | PERF-1 仓库列表批量查仓位 |
| `backend/app/routers/consignment.py` | 修改 | PERF-1 寄售汇总/客户批量查询 |
| `backend/app/routers/orders.py` | 修改 | PERF-1 退货明细批量查 |
| `backend/app/routers/purchase_orders.py` | 修改 | PERF-1 采购导出/待收货批量查 |
| `backend/app/routers/dashboard.py` | 修改 | PERF-2 SQL聚合替代Python循环 |
| `backend/app/routers/logistics.py` | 修改 | PERF-2 DB级预过滤 |
| `backend/app/migrations.py` | 修改 | PERF-5 12个索引 |
| `backend/main.py` | 修改 | PERF-6 HTML缓存 |
| `frontend/src/App.vue` | 修改 | PERF-4 按需加载 |
| `frontend/src/stores/products.js` | 修改 | PERF-4 ensureLoaded |
| `frontend/src/stores/warehouses.js` | 修改 | PERF-4 ensureLoaded |
| `frontend/src/stores/customers.js` | 修改 | PERF-4 ensureLoaded |
| `frontend/src/stores/finance.js` | 修改 | PERF-4 ensureLoaded |

### 已修复架构改进（Phase 4）

#### ARCH-1: Service 层空壳清理
- 删除 5 个空壳文件（order_service, finance_service, purchase_service, consignment_service, voucher_service）

#### ARCH-2: 财务操作增加事务
- `finance.py` — `confirm_payment` 包裹 `in_transaction()`

#### ARCH-3: 前端代码去重
- 5 个 view 的自定义 `hasPermission` 统一替换为 `usePermission` composable

#### ARCH-4: API 全局错误处理
- `api/index.js` 响应拦截器 500+ 错误自动 toast
- `App.vue` 注册回调避免循环依赖

#### ARCH-5: API 文件拆分
- `salespersons.js` 中无关函数拆分到 `dashboard.js`、`sn.js`、`brands.js`

#### ARCH-6: 表单客户端验证
- 商品创建：SKU/名称必填，价格 ≥ 0
- 客户创建：名称必填
- 入库操作：数量 > 0，成本价 ≥ 0
- 销售订单：数量 > 0，单价 ≥ 0

### 架构改进修改文件汇总

| 文件 | 变更类型 | 对应项 |
|------|---------|--------|
| `backend/app/services/*.py` (5个) | 删除 | ARCH-1 清理空壳 |
| `backend/app/routers/finance.py` | 修改 | ARCH-2 事务包裹 |
| `frontend/src/api/index.js` | 修改 | ARCH-4 全局错误处理 |
| `frontend/src/App.vue` | 修改 | ARCH-4 注册错误回调 |
| `frontend/src/api/salespersons.js` | 修改 | ARCH-5 移除无关函数 |
| `frontend/src/api/dashboard.js` | 新增 | ARCH-5 拆分 |
| `frontend/src/api/sn.js` | 新增 | ARCH-5 拆分 |
| `frontend/src/api/brands.js` | 新增 | ARCH-5 拆分 |
| `frontend/src/stores/settings.js` | 修改 | ARCH-5 更新导入 |
| `frontend/src/views/DashboardView.vue` | 修改 | ARCH-3 + ARCH-5 去重+导入 |
| `frontend/src/views/CustomersView.vue` | 修改 | ARCH-3 + ARCH-6 去重+验证 |
| `frontend/src/views/SettingsView.vue` | 修改 | ARCH-3 + ARCH-5 去重+导入 |
| `frontend/src/views/StockView.vue` | 修改 | ARCH-3 + ARCH-5 + ARCH-6 去重+导入+验证 |
| `frontend/src/views/PurchaseView.vue` | 修改 | ARCH-3 + ARCH-5 去重+导入 |
| `frontend/src/views/SalesView.vue` | 修改 | ARCH-6 订单验证 |

### 已修复代码质量（Phase 5）

#### QUAL-1: 后端 Schema 校验加强
- 所有 Schema 增加 Pydantic `Field` 约束：quantity `gt=0`，price `ge=0`，order_type `Literal` 枚举，tax_rate `ge=0, le=1`

#### QUAL-2: request.json() 替换为 Pydantic Schema
- `payment_methods.py` → `PaymentMethodCreate` / `PaymentMethodUpdate`
- `settings.py` → `SettingUpdate`
- `vouchers.py` → `VoucherGenerateRequest`

#### QUAL-3: 重复代码消除
- 后端 `csv_safe` 提取到 `utils/csv.py` 共用
- 前端 `hasPermission` 已在 ARCH-3 中统一

#### QUAL-4: 数据模型修复
- `SnConfig.unique_together` 字段名格式修正

#### QUAL-5: datetime 统一
- `logger.py` — `datetime.utcnow()` → `datetime.now(timezone.utc)`

#### QUAL-6: submitting 竞态修复
- `stores/app.js` — 布尔值改为计数器 writable computed（向后兼容）

#### QUAL-7: window.__erpLoadAll 消除
- 移除全局函数，改用 `router.afterEach` 在登录后自动加载

#### QUAL-8: 未使用 store 清理
- 删除 `stores/orders.js`（无引用）

### 代码质量修改文件汇总

| 文件 | 变更类型 | 对应项 |
|------|---------|--------|
| `backend/app/schemas/stock.py` | 修改 | QUAL-1 Field 校验 |
| `backend/app/schemas/order.py` | 修改 | QUAL-1 Field + Literal |
| `backend/app/schemas/finance.py` | 修改 | QUAL-1 Field 校验 |
| `backend/app/schemas/purchase.py` | 修改 | QUAL-1 Field 校验 |
| `backend/app/routers/payment_methods.py` | 修改 | QUAL-2 Pydantic Schema |
| `backend/app/routers/settings.py` | 修改 | QUAL-2 Pydantic Schema |
| `backend/app/routers/vouchers.py` | 修改 | QUAL-2 Pydantic Schema |
| `backend/app/utils/csv.py` | 新增 | QUAL-3 公共 csv_safe |
| `backend/app/routers/finance.py` | 修改 | QUAL-3 引用公共 csv_safe |
| `backend/app/routers/purchase_orders.py` | 修改 | QUAL-3 引用公共 csv_safe |
| `backend/app/models/sn.py` | 修改 | QUAL-4 unique_together 修正 |
| `backend/app/logger.py` | 修改 | QUAL-5 datetime 统一 |
| `frontend/src/stores/app.js` | 修改 | QUAL-6 submitting 计数器 |
| `frontend/src/App.vue` | 修改 | QUAL-7 移除 loadAll + 改进 afterEach |
| `frontend/src/views/LoginView.vue` | 修改 | QUAL-7 移除 __erpLoadAll |
| `frontend/src/stores/orders.js` | 删除 | QUAL-8 未使用 store |

### 所有优先级已完成

全部 5 个优先级共 34 项修复已完成：
- Phase 1: 8 个功能 BUG
- Phase 2: 6 项安全加固
- Phase 3: 6 项性能优化
- Phase 4: 6 项架构改进
- Phase 5: 8 项代码质量

详见 `CODE_REVIEW.md` 完整审查报告，每项均标记 ✅。

### 遗留事项（非阻塞，建议后续迭代）

详见 `CODE_REVIEW.md` 底部"其他发现（非阻塞）"章节。

---

## v4.4 — 架构重构 & 工程化（2026-02）

### 项目结构重构
- 从单体 `main.py` + 单文件前端重构为 **前后端分离** 的模块化架构
- 后端拆分为 `models/ → schemas/ → services/ → routers/` 四层结构
- 前端从内嵌 HTML 迁移到独立 Vue 3 SPA 项目
- 新增 Docker 多阶段构建 + Docker Compose 一键部署

### 后端变更

#### 数据库迁移
- SQLite → **PostgreSQL 16**，支持并发访问和生产级部署
- ORM 从 raw SQL 迁移到 **Tortoise ORM**，模型定义规范化
- 备份机制从 SQLite 文件复制改为 `pg_dump`

#### 统一日志 & 异常处理（v4.4 新增）
- 新增 `app/logger.py`：统一结构化 JSON 日志输出（替代全项目 `print()` 语句）
- 新增 `app/exceptions.py`：全局 FastAPI 异常处理器
  - `http_exception_handler`：500+ 错误自动记录日志
  - `unhandled_exception_handler`：未捕获异常记录完整堆栈，返回统一 500 响应
- 所有 service/router 中的 `print()`、`traceback.print_exc()` 替换为 `logger.info/warning/error`
- 移除所有 `import traceback` 依赖

#### 认证与权限
- JWT Token 认证，24 小时过期
- 细粒度权限控制（11 个权限标识）
- 登录限流保护（5 次/5 分钟）

#### 核心业务
- **销售订单**: 支持现款、账期、寄售调拨、寄售结算、退货 5 种类型
- **采购流程**: 创建 → 审核 → 付款 → 收货，完整四步流程
- **库存管理**: 加权移动平均成本法，支持入库/调拨/盘点/SN 码管理
- **寄售管理**: 虚拟仓机制，寄售调拨 → 结算/退货完整闭环
- **物流对接**: 快递100 API（订阅推送 + 主动查询 + 回调更新）
- **财务模块**: 收款/退款、对账、记账凭证、返利管理（客户+供应商双向）

### 前端变更

#### 技术栈
- 从 jQuery/原生 JS 迁移到 **Vue 3 Composition API**
- 状态管理采用 **Pinia**（8 个 store）
- 样式框架从手写 CSS 迁移到 **Tailwind CSS v4**
- 构建工具使用 **Vite 7**，支持 HMR 热更新

#### 页面模块
- 11 个独立视图页面，路由懒加载
- 响应式布局，支持移动端（底部导航栏）
- 组件化架构：layout / business / common 三层组件
- API 调用层统一封装（14 个 api 模块）

#### 功能增强
- 仪表盘图表（Chart.js）
- Excel 导入/导出（商品、库存、采购单）
- 操作日志审计追踪
- 空闲超时自动登出

### 部署变更
- 新增 `Dockerfile` 多阶段构建（Node 20 构建前端 + Python 3.12 运行后端）
- 新增 `docker-compose.yml`（PostgreSQL 16 + 应用服务）
- 支持国内镜像加速（阿里云 apt + 清华 PyPI + npm mirror）
- 数据持久化：PostgreSQL 数据卷 + 备份目录卷

---

## v3.x — 早期版本（历史）

> 以下为重构前的单体架构阶段，代码已在 v4.4 中全面重写。

### v3.4
- 单文件 `main.py` 后端（所有路由、模型、业务逻辑在一个文件中）
- SQLite 数据库
- 前端为 FastAPI 内嵌 HTML（Jinja2 模板 + 内联 JS/CSS）
- 基础进销存功能

### v3.0 ~ v3.3
- 逐步添加寄售、采购、物流等模块
- 前端功能持续扩展
- 代码规模增长但架构未变，维护难度逐渐上升

---

## 文件变更汇总（v4.4 日志/异常重构）

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/logger.py` | 新增 | 统一结构化 JSON 日志模块 |
| `backend/app/exceptions.py` | 新增 | 全局 FastAPI 异常处理器 |
| `backend/main.py` | 修改 | 注册全局异常处理器，更新应用标题 |
| `backend/app/config.py` | 修改 | `print("[WARN]...")` → `logger.warning(...)` |
| `backend/app/migrations.py` | 修改 | 4 处 `print("[OK]...")` → `logger.info(...)` |
| `backend/app/services/backup_service.py` | 修改 | 备份成功/失败日志结构化 |
| `backend/app/services/logistics_service.py` | 修改 | 快递查询失败日志结构化 |
| `backend/app/routers/orders.py` | 修改 | `traceback.print_exc()` → `logger.error(...)` |
| `backend/app/routers/stock.py` | 修改 | 3 处 traceback → logger（入库/调拨/导出） |
| `backend/app/routers/consignment.py` | 修改 | 3 行 print+traceback → 1 行 logger |
| `backend/app/routers/logistics.py` | 修改 | 回调处理 print → logger |
| `backend/app/routers/backup.py` | 修改 | 添加备份异常日志 |
| `backend/app/routers/products.py` | 修改 | 移除未使用的 `import traceback` |
| `frontend/index.html` | 修改 | 标题统一为 "ERP系统 v4.4" |
| `backend/static/index.html` | 修改 | 标题统一为 "ERP系统 v4.4" |
