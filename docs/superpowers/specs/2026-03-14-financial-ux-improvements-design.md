# 财务模块 UX 改进与功能完善设计文档

> 来源：ERP.docx 第 11-25 条财务人员需求
> 日期：2026-03-14
> 状态：待审核

---

## 概述

本设计覆盖 15 条财务人员反馈需求，按依赖关系和功能聚合拆分为 5 个实施计划，执行顺序 E → A → B → C → D。

### 需求总览

| # | 需求摘要 | 归属计划 |
|---|---------|---------|
| 11 | 销项发票：显示货物名称和客户开票信息，多应收单合并推票 | D |
| 12 | 进项发票从应付单下推 | D |
| 13 | 凭证号分开显示（凭证字 + 凭证号） | A |
| 14 | 所有单据界面都要有搜索筛选 | E |
| 15 | 凭证列表页增加列 + 搜索 + 导出明细 | A |
| 16 | 修改凭证日期时凭证号自动跟随变化 | A |
| 17 | 凭证批量提交、审核、过账 | A |
| 18 | 手动勾单汇总生成凭证，同客户/供应商可合并 | B |
| 19 | 制单人 = 审核人 = 过账人（可同一人） | A |
| 20 | 期末结账功能确认/完善 | E |
| 21 | 辅助核算增加商品、银行维度 | B |
| 22 | 应付单付款状态未关联付款单（bug） | E |
| 23 | 录入凭证时显示当前凭证号 + 搜索科目编码 | A |
| 24 | 凭证分录列顺序调整 | A |
| 25 | 凭证批量导出打印 + 标准格式 | C |

---

## 计划 E：Bug 修复与体验优化

**需求来源**：#22、#14、#20
**预估复杂度**：低

### E1: 应付单付款状态未关联付款单 (#22)

**问题**：确认付款单后，应付单仍显示"待付款"状态。

**根因排查方向**：
1. 后端 `confirm_disbursement_bill` 中 PayableBill 状态更新逻辑是否覆盖所有场景（部分付款、退款后再付款）
2. 前端确认操作后是否刷新了应付单列表数据
3. PayableBill 的 `paid_amount` / `unpaid_amount` 计算是否正确

**修复策略**：排查后端状态同步逻辑 + 前端数据刷新时机，确保 `PayableBill.status` 在 `DisbursementBill` 确认后正确更新为 `partial` 或 `completed`。

### E2: 所有单据界面搜索筛选补全 (#14)

**范围检查清单**：
- [ ] VoucherPanel — 凭证管理
- [ ] ReceivableBillsTab — 应收单
- [ ] ReceiptBillsTab — 收款单
- [ ] ReceiptRefundBillsTab — 收款退款
- [ ] WriteOffBillsTab — 应收核销
- [ ] SalesDeliveryTab — 出库单
- [ ] SalesReturnTab — 销售退货
- [ ] PayableBillsTab — 应付单
- [ ] DisbursementBillsTab — 付款单
- [ ] DisbursementRefundBillsTab — 付款退款
- [ ] PurchaseReceiptTab — 入库单
- [ ] PurchaseReturnTab — 采购退货
- [ ] SalesInvoiceTab — 销项发票
- [ ] PurchaseInvoiceTab — 进项发票

**方案**：逐一检查每个 Tab 组件，缺少搜索框的统一补上，遵循现有 `toolbar-search-wrapper` + `toolbar-search` 模式。搜索覆盖：单据号、客户/供应商名称、金额等关键字段。

### E3: 期末结账功能确认 (#20)

**现状**：系统已有完整的 PeriodEndPanel，包含：
- 损益结转（预览 + 执行）
- 结账检查（余额平衡）
- 期间结账 / 开启
- 年度结账

**方案**：确认 UI 入口是否清晰可见。如有导航或可发现性问题则优化。如有具体缺失功能在实施时补充。

---

## 计划 A：凭证管理核心改进

**需求来源**：#13、#15、#16、#17、#19、#23、#24
**预估复杂度**：中-高

### A1: 凭证号分开显示 (#13)

**设计**：在凭证列表和详情页将凭证号拆分为两个独立显示字段：
- 凭证字列：显示 `记` / `收` / `付` / `转`
- 凭证号列：显示纯序号数字 `1`、`2`、`3`...

**数据结构说明**：后端 `voucher_no` 是 `CharField(max_length=30)`，存储格式为复合字符串（如 `A01-记-202603-007`），包含账套编码、凭证类型、期间和序号。`voucher_type` 是独立的凭证字字段。

**后端改动**：API 响应中新增 `sequence_no` 字段（从 `voucher_no` 中提取序号部分），供前端直接使用。前端显示"凭证字"取 `voucher_type`，"凭证号"取 `sequence_no`。

### A2: 凭证列表页双视图 + 搜索筛选 + 导出 (#15)

**参考**：ERP.docx 第 3 张截图（金蝶凭证列表页）。

#### 双视图切换

提供视图切换按钮（类似图标按钮组），用户可在两种视图间切换：

**凭证视图**（当前默认）：
- 每行一张凭证，显示凭证级汇总
- 列：日期 | 期间 | 凭证字 | 凭证号 | 摘要 | 借方合计 | 贷方合计 | 制单人 | 审核人 | 过账人 | 状态

**分录视图**（新增）：
- 每行一条 VoucherEntry
- 列：日期 | 会计年度 | 期间 | 凭证字 | 凭证号 | 摘要 | 科目编码 | 科目名称 | 核算维度 | 借方金额 | 贷方金额 | 制单 | 审核 | 过账 | 审核状态
- 同一张凭证的多条分录通过凭证号视觉分组

#### 搜索筛选

在工具栏增加搜索框，支持：
- 按凭证号精确搜索
- 按科目名称模糊搜索
- 按摘要关键字搜索
- 现有的期间、凭证类型、状态筛选保持

#### 导出明细

新增"导出"按钮：
- 导出当前筛选条件下的所有分录级数据为 Excel
- 列与分录视图一致

#### 后端改动

- 新增 API `GET /api/vouchers/entries`：返回分录级平铺数据（支持分页、排序、筛选）
- 查询参数：`account_set_id`、`period`、`voucher_type`、`status`、`search`（模糊搜索摘要/科目名称）
- 新增导出 API `GET /api/vouchers/entries/export`：导出 Excel

### A3: 修改凭证日期时凭证号自动变化 (#16)

**后端**：
- 新增 `GET /api/vouchers/next-number`
- 参数：`account_set_id`、`period`（YYYY-MM）、`voucher_type`（记/收/付/转）
- 返回：`{ "sequence_no": 8, "voucher_no": "A01-记-202601-008" }`
- 逻辑：调用现有 `next_voucher_no()` 工具函数（`backend/app/utils/voucher_no.py`）获取完整凭证号，同时提取序号部分返回

**前端**：
- 凭证录入/编辑界面，日期或凭证类型变更时自动调用此 API
- 显示 `sequence_no` 给用户（用户仍可手动修改序号部分）
- 保存时后端校验 `voucher_no` 全局唯一性（`voucher_no` 字段有 `unique=True` 约束）

**并发安全**：`next-number` 仅用于前端预览，实际凭证号分配在保存时由后端在事务中完成（使用 `select_for_update` 锁定），避免并发冲突。如果预览号与实际分配号不同，后端返回最终分配的凭证号供前端更新。

### A4: 批量提交、审核、过账 (#17)

**前端**：
- 凭证列表增加行首复选框（全选 + 逐行选）
- 工具栏增加三个批量操作按钮：
  - "批量提交"（当列表中有 `draft` 状态凭证时启用）
  - "批量审核"（当有 `pending` 状态时启用）
  - "批量过账"（当有 `approved` 状态时启用）
- 操作完成后弹出结果摘要：成功 N 条，失败 M 条（附失败原因）

**后端**：
- `POST /api/vouchers/batch-submit`
  - body: `{ "voucher_ids": [1, 2, 3] }`
  - 校验：每张凭证状态必须是 `draft`
- `POST /api/vouchers/batch-approve`
  - body: `{ "voucher_ids": [1, 2, 3] }`
  - 校验：每张凭证状态必须是 `pending`
- `POST /api/vouchers/batch-post`
  - body: `{ "voucher_ids": [1, 2, 3] }`
  - 校验：每张凭证状态必须是 `approved`，期间未关闭
- 返回格式：`{ "success": [1, 2], "failed": [{ "id": 3, "reason": "期间已关闭" }] }`
- **事务策略**：采用 best-effort（部分成功）模式，逐条处理，成功的立即生效，失败的跳过并记录原因。不使用全局事务（避免一条失败导致全部回滚）。
- **安全校验**：所有传入的 `voucher_ids` 必须属于同一个 `account_set_id`，后端需验证。

### A5: 制单人 = 审核人 = 过账人 (#19)

**现状**：后端 `approve_voucher` 已通过 `SystemSetting(key="voucher_maker_checker")` 控制是否强制制单人与审核人不同。当设置值为 `"false"` 时不做校验。

**改动**：将 `voucher_maker_checker` 的默认值改为 `"false"`（允许同一人），并在前端设置页面增加此开关供管理员配置。如果当前系统没有在设置页面暴露此选项，需要补上。

**影响**：默认允许同一用户创建凭证后自行审核和过账，简化小型企业的操作流程。企业可在设置中重新开启 maker-checker 规则。

### A6: 录入时显示凭证号 + 科目搜索 (#23)

**凭证号预填**：
- 新建凭证时，根据默认日期（当天）和凭证类型（记）调用 A3 的 `next-number` API
- 预填凭证号到表单中

**科目搜索**：
- 科目选择器从普通下拉改为可搜索 combobox
- 支持按编码或名称模糊匹配（如输入 `1002` 或 `银行` 都能找到"银行存款"）
- 前端已有 `chartOfAccounts` 数据在 store 中，可直接前端过滤，无需后端改动

### A7: 分录列顺序调整 (#24)

**参考**：ERP.docx 第 2 张截图（金蝶凭证录入界面）。

**目标列顺序**：序号 → 摘要 → 科目编码 → 科目全名 → 核算维度 → 借方金额 → 贷方金额

**改动**：纯前端，重排凭证录入/编辑界面中分录表格的 `<th>` 和 `<td>` 顺序。

---

## 计划 B：辅助核算增强 + 凭证生成流程

**需求来源**：#21、#18
**预估复杂度**：高

### B1: 增加商品、银行辅助核算维度 (#21)

**现有维度**：客户(customer)、供应商(supplier)、员工(employee)、部门(department) — 共 4 个。

**新增维度**：
- **商品(product)**：用于入库/出库/成本类凭证分录，记录具体商品
- **银行(bank)**：用于银行存款科目(1002)，记录具体银行账户

#### 新建 BankAccount 模型

```python
class BankAccount(models.Model):
    id = fields.IntField(pk=True)
    account_set = fields.ForeignKeyField(
        "models.AccountSet", related_name="bank_accounts", on_delete=fields.RESTRICT
    )
    bank_name = fields.CharField(max_length=100)       # 银行名称，如"工商银行粤秀支行"
    account_number = fields.CharField(max_length=50)    # 银行账号
    short_name = fields.CharField(max_length=50, default="")  # 简称，如"工行粤秀"
    sort_order = fields.IntField(default=0)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "bank_accounts"
        unique_together = (("account_set", "account_number"),)
```

#### ChartOfAccount 模型变更

新增字段：
- `aux_product: BooleanField(default=False)`
- `aux_bank: BooleanField(default=False)`

#### VoucherEntry 模型变更

新增字段：
- `aux_product: ForeignKeyField("models.Product", null=True, on_delete=SET_NULL)`
- `aux_bank: ForeignKeyField("models.BankAccount", null=True, on_delete=SET_NULL)`

#### 初始化脚本更新（accounting_init.py）

为预设科目设置辅助核算标记：
- 库存商品(1405)：`aux_product=True`
- 原材料(1403)：`aux_product=True`
- 银行存款(1002)：`aux_bank=True`
- 在途物资(1407)：`aux_product=True`

#### ReceiptBill / DisbursementBill 模型变更

为支持银行维度自动填充，收付款单需记录使用的银行账户：
- `ReceiptBill` 新增：`bank_account: ForeignKeyField("models.BankAccount", null=True, on_delete=SET_NULL)` — 收款使用的银行账户
- `DisbursementBill` 新增：`bank_account: ForeignKeyField("models.BankAccount", null=True, on_delete=SET_NULL)` — 付款使用的银行账户

前端收款/付款确认时，如果选择的收付款方式对应银行转账，需同时选择银行账户。

#### 凭证生成逻辑更新

AR/AP service 的批量凭证生成中：
- 银行存款分录：从 `ReceiptBill.bank_account` / `DisbursementBill.bank_account` 获取银行维度填入 `VoucherEntry.aux_bank`
- 库存/成本分录：从关联订单行项的 `Product` 填入 `VoucherEntry.aux_product`

**所有创建 VoucherEntry 的代码位置**（均需更新以支持新字段）：
1. `backend/app/routers/vouchers.py` — 手动录入凭证
2. `backend/app/services/ar_service.py` — AR 凭证生成
3. `backend/app/services/ap_service.py` — AP 凭证生成
4. `backend/app/services/invoice_service.py` — 发票确认凭证
5. `backend/app/services/period_end_service.py` — 期末结转凭证（无需商品/银行维度，传 None 即可）

#### 前端改动

1. 科目管理界面增加"商品核算"和"银行核算"开关
2. 凭证录入界面：选中设有 `aux_product=true` 的科目时，核算维度区自动出现商品选择器；`aux_bank=true` 同理出现银行选择器
3. 凭证列表核算维度列展示商品和银行信息
4. 新增银行账户管理页面（设置模块中，简单 CRUD，按账套隔离）

#### 新增 API

- `GET/POST/PUT/DELETE /api/bank-accounts` — 银行账户 CRUD
- 支持 `account_set_id` 过滤

### B2: 手动勾单汇总 + 合并生成凭证 (#18)

**当前流程**：选月份 → 自动处理该月所有已确认且无凭证的单据 → 每张单据一张凭证。

**目标流程**：选月份 → 展示待处理单据列表 → 用户勾选 → 可选合并 → 确认生成。

#### 后端改动

**新增查询 API**：
- `GET /api/receivables/pending-voucher-bills`
  - 参数：`account_set_id`、`period`（YYYY-MM）
  - 返回四类单据（与现有 `generate_ar_vouchers` 处理范围一致）：
    1. 收款单（ReceiptBill, `status=confirmed`, `voucher_id=None`）
    2. 收款退款单（ReceiptRefundBill, `status=confirmed`, `voucher_id=None`）
    3. 核销单（ReceivableWriteOff, `status=confirmed`, `voucher_id=None`）
    4. 销售退货单（Order, `order_type=RETURN`, 该期间内, 未生成凭证）
  - 每条记录包含：id、单据号、类型标签、客户名称、金额、日期

- `GET /api/payables/pending-voucher-bills`
  - 返回三类单据：
    1. 付款单（DisbursementBill, `status=confirmed`, `voucher_id=None`）
    2. 付款退款单（DisbursementRefundBill, `status=confirmed`, `voucher_id=None`）
    3. 采购退货单（PurchaseReturn, 该期间内, 未生成凭证）
  - 每条记录包含：id、单据号、类型标签、供应商名称、金额、日期

**修改生成 API**：
- `POST /api/receivables/generate-ar-vouchers`
  ```json
  {
    "account_set_id": 1,
    "bills": [
      { "id": 1, "type": "receipt" },
      { "id": 2, "type": "receipt" },
      { "id": 3, "type": "refund" },
      { "id": 4, "type": "write_off" },
      { "id": 5, "type": "sales_return" }
    ],
    "merge_by_partner": true
  }
  ```
  - `type` 区分单据类型，支持混合选择不同类型的单据
  - 保留向后兼容：如果传入 `period_names` 而不是 `bills`，则走旧的全量处理逻辑

- `POST /api/payables/generate-ap-vouchers`
  ```json
  {
    "account_set_id": 1,
    "bills": [
      { "id": 1, "type": "disbursement" },
      { "id": 2, "type": "refund" },
      { "id": 3, "type": "purchase_return" }
    ],
    "merge_by_partner": true
  }
  ```

**合并逻辑**：
- `merge_by_partner=true` 时，按 `customer_id` / `supplier_id` 分组
- 同组同类型的多张单据合并到一张凭证的多条分录中
- 凭证摘要汇总：如"收货款-客户A（SK-001, SK-002, SK-003）"
- 借贷方分别合计
- **合并凭证日期**：使用该组中最晚的单据日期作为凭证日期

#### 前端改动

将现有的"批量生成凭证"按钮流程改为：
1. 点击 → 弹出勾选面板（modal）
2. 面板顶部：月份选择器
3. 中部：待处理单据表格（复选框 + 单据号 + 类型 + 客户/供应商 + 金额 + 日期）
4. 底部：
   - "合并同客户/供应商"开关
   - 预览文本："将生成 N 张凭证"
   - 确认按钮

---

## 计划 C：凭证打印与导出

**需求来源**：#25
**预估复杂度**：中

### 标准记账凭证 PDF 格式

**参考**：ERP.docx 第 1 张截图——传统中式记账凭证。

#### PDF 布局

```
┌──────────────────────────────────────────────────┐
│                    记 账 凭 证                     │
│                                                  │
│  日期: 2025-12-31              编号: 付  26       │
│  核算单位: 广州启领信息科技有限公司    页号: 第1/1页   │
├─────────────┬──────────────────┬────────┬────────┤
│    摘  要    │     科   目      │  借 方  │  贷 方  │
│ Description │      A/C         │  Debit │ Credit │
├─────────────┼──────────────────┼────────┼────────┤
│ 付货款-XXX  │ 应付账款_明细... │14360.00│        │
│ ...         │ ...              │        │ ...    │
├─────────────┼──────────────────┼────────┼────────┤
│   合 计     │ 大写金额          │ 合计   │  合计   │
│   Total     │                  │        │        │
├─────────────┴──────────────────┴────────┴────────┤
│  过账:XXX    出纳:          制单:XXX    审核:XXX   │
└──────────────────────────────────────────────────┘
```

#### 技术方案

**PDF 生成**（后端）：
- 使用 ReportLab 绘制表格布局
- 支持中文字体（宋体/黑体）
- 中文大写金额转换（如 `9137.00` → `玖仟壹佰叁拾柒元整`）
- 签名区填入实际的制单人、审核人、过账人姓名

**批量导出**（后端）：
- 复用已有的 `POST /api/vouchers/batch-pdf` 端点
- 用新模板生成 PDF，多张凭证合并为一个 PDF 文件

**前端**：
- 凭证列表增加"批量导出 PDF"按钮
- 两种导出模式：
  - 勾选模式：勾选凭证后点导出
  - 筛选模式：按当前筛选条件导出全部

---

## 计划 D：发票下推流程

**需求来源**：#11、#12
**预估复杂度**：中

### D1: 销项发票从应收单多单合并下推 (#11)

**目标**：在应收单列表勾选多张应收单 → 合并推送为一张销项发票 → 显示货物名称和客户开票信息。

#### 后端改动

**修改 `push_invoice_from_receivable`**：
- 接受 `receivable_bill_ids: list[int]`（替代单个 id）
- 校验所有应收单属于同一客户
- **防重复校验**：检查每张应收单是否已有关联发票，已有则排除并提示
- 从关联订单的 OrderItem 提取货物明细生成 InvoiceItem
- 汇总金额、税额

**Invoice 模型多源关联**：
- 当前 Invoice 模型的 `receivable_bill` / `payable_bill` 是单个 FK，不支持多单合并
- 新增 `InvoiceSourceBill` 关联表（或 `source_bill_ids: JSONField`）记录发票关联的所有源单据
- 推荐方案：使用 JSONField 存储 `source_receivable_bill_ids: list[int]`（简单，无需新表）
- 保留原有的 `receivable_bill` FK 指向第一张应收单（兼容现有逻辑）

**Customer 模型检查**：
- Customer 已有字段：`tax_id`、`bank_name`、`bank_account`
- 仅需新增：`invoice_address`（开票地址）、`invoice_phone`（开票电话）

#### 前端改动

1. ReceivableBillsTab 增加复选框 + "推送发票"按钮
2. 推送弹窗：
   - 上半部：客户开票信息（自动从 Customer 读取，可编辑）
   - 下半部：货物明细表格（自动从订单行项提取，含商品名、数量、单价、税率）
3. 确认生成发票

### D2: 进项发票从应付单下推 (#12)

#### 后端改动

**新增 service 方法**：
- `push_invoice_from_payable(payable_bill_ids: list[int])`
- 校验所有应付单属于同一供应商
- **防重复校验**：检查每张应付单是否已有关联发票
- 从关联采购订单提取商品明细
- 生成进项发票（`direction=input`）
- 使用 JSONField `source_payable_bill_ids` 记录所有源应付单（与 D1 对称）

**新增 API**：
- `POST /api/invoices/from-payable`
- body: `{ "payable_bill_ids": [1, 2, 3] }`

**Supplier 模型检查**：
- Supplier 已有字段：`tax_id`、`bank_name`、`bank_account`、`address`、`phone`
- 已有的 `address` 和 `phone` 可直接用作开票信息，无需新增字段

#### 前端改动

1. PayableBillsTab 增加复选框 + "推送发票"按钮
2. 推送弹窗：供应商信息 + 商品明细（与 D1 对称）
3. 确认生成

---

## 执行顺序与依赖

```
E (Bug修复/体验优化)        ← 无依赖，先修复现有问题
  ↓
A (凭证管理核心改进)         ← E 完成后，凭证是核心
  ↓
B (辅助核算 + 凭证生成流程)  ← 依赖 A 的凭证结构改动
  ↓
C (凭证打印与导出)           ← 依赖 A 的列结构 + B 的辅助核算数据
  ↓
D (发票下推流程)             ← 相对独立，放最后
```

---

## 涉及的关键文件

### 后端

| 文件 | 计划 | 改动 |
|------|------|------|
| `backend/app/models/voucher.py` | B | VoucherEntry 增加 aux_product, aux_bank |
| `backend/app/models/accounting.py` | B | ChartOfAccount 增加 aux_product, aux_bank |
| `backend/app/models/ar_ap.py` | E | 排查 PayableBill 状态更新逻辑 |
| `backend/app/routers/vouchers.py` | A | 批量操作 API、next-number、entries 列表、导出 |
| `backend/app/routers/receivables.py` | B, D | pending-voucher-bills 查询、生成 API 参数改造 |
| `backend/app/routers/payables.py` | B, D | 同上 |
| `backend/app/routers/invoices.py` | D | from-payable API |
| `backend/app/services/ar_service.py` | B | 勾单合并生成逻辑 |
| `backend/app/services/ap_service.py` | B | 勾单合并生成逻辑 |
| `backend/app/services/invoice_service.py` | D | 多单合并推送、进项下推 |
| `backend/app/services/accounting_init.py` | B | 初始化商品/银行维度标记 |
| `backend/app/utils/pdf_print.py` | C | 重写标准记账凭证 PDF 模板（现有 PDF 生成工具） |

### 前端

| 文件 | 计划 | 改动 |
|------|------|------|
| `frontend/src/components/business/VoucherPanel.vue` | A | 双视图、列调整、批量操作、搜索、导出 |
| `frontend/src/components/business/ReceivablePanel.vue` | B, D | 勾单生成面板、发票下推 |
| `frontend/src/components/business/PayablePanel.vue` | B, D | 勾单生成面板、发票下推 |
| `frontend/src/components/business/InvoicePanel.vue` | D | 发票详情展示（货物名称、开票信息） |
| `frontend/src/components/business/*Tab.vue`（多个） | E | 搜索筛选补全 |
| `frontend/src/api/accounting.js` | A, B, C | 新增 API 调用 |
| `frontend/src/stores/accounting.js` | B | 银行账户数据管理 |

### 新增文件

| 文件 | 计划 | 说明 |
|------|------|------|
| `backend/app/models/bank_account.py` | B | BankAccount 模型 |
| `backend/app/routers/bank_accounts.py` | B | 银行账户 CRUD API |

---

## 计划内部依赖与并行说明

### 计划 A 内部

```
A1 (凭证号分开显示) ← 独立
A3 (next-number API) ← 独立
A6 (预填凭证号 + 科目搜索) ← 依赖 A3
A5 (maker-checker 设置) ← 独立
A4 (批量操作) ← 需要先确认 A5（批量审核会触发 maker-checker 检查）
A7 (分录列顺序) ← 独立
A2 (双视图 + 搜索 + 导出) ← 独立，但工作量最大，建议最后做
```

可并行：A1 + A3 + A5 + A7 → 然后 A6 + A4 → 最后 A2

### 计划 B 内部

B1（辅助核算）必须先于 B2（凭证生成流程），因为 B2 的凭证生成需要填充新的辅助核算维度。

### 计划 D 与计划 B 的隐性耦合

D1/D2 中发票确认后如果会生成凭证，该凭证需要填充 B1 新增的 `aux_product` 维度。因此 D 放在 B 之后是正确的。
