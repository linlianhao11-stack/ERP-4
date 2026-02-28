# 阶段5：期末处理 + 财务报表 — 设计文档

> 状态：设计完成，待实施
> 日期：2026-02-28
> 依赖：阶段1（科目+凭证）✅ + 阶段2（账簿查询）✅ + 阶段3（应收应付）✅ + 阶段4（发票+出入库）✅

## 概述

实现期末处理流程（损益结转→结账检查→期间锁定→年度结转）和三张财务报表（资产负债表、利润表、现金流量表），支持Excel和PDF双格式导出。

## 关键设计决策

| 决策 | 选择 | 说明 |
|------|------|------|
| 损益结转凭证字 | 转（转账凭证） | 符合会计惯例 |
| 结账预检查 | 严格5项 | 1)凭证已过账 2)试算平衡 3)损益已结转 4)无草稿AR/AP凭证 5)上期已结账 |
| 财务报表 | 三张全套 | 资产负债表 + 利润表 + 现金流量表 |
| 现金流量表 | 简易直接法 | 根据银行存款/库存现金的对手科目自动分类到经营/投资/筹资 |
| 年度结转 | 需要 | 12月结账时 4103本年利润→4104未分配利润 + 初始化下年期间 |
| 报表导出 | Excel + PDF | 复用现有 reportlab + openpyxl |

## 期末处理流程

### 月末流程

```
损益结转（预览→确认）→ 结账检查（5项）→ 结账（锁定期间）
```

### 年末流程（12月）

```
损益结转 → 年度利润结转（4103→4104）→ 结账检查 → 结账 → 初始化下年期间
```

## 功能详细设计

### 1. 期末损益结转

查询所有损益类科目（category="profit_loss"，6xxx系列）的期间已过账发生额：
- 收入类科目（direction=credit）：贷方净额 → 借方转出，贷方转入4103本年利润
- 成本费用类科目（direction=debit）：借方净额 → 贷方转出，借方转入4103本年利润
- 生成一张"转"字凭证，多条分录
- 支持预览（返回将要生成的分录明细）后确认执行
- 幂等：同一期间重复执行时检测是否已有结转凭证

### 2. 期末结账（5项检查）

| 检查项 | 条件 | 说明 |
|--------|------|------|
| 凭证已过账 | 本期无 status != "posted" 的凭证 | 所有凭证必须过账 |
| 试算平衡 | 本期借方合计 == 贷方合计 | 借贷必须平衡 |
| 损益已结转 | 本期损益类科目余额为零 | 必须先执行损益结转 |
| 无草稿AR/AP凭证 | 无已确认但未生成凭证的收款/付款/退款/核销单 | AR/AP凭证必须已生成 |
| 上期已结账 | 上一期间 is_closed=True（首期除外） | 必须按顺序结账 |

检查通过后：
- AccountingPeriod.is_closed = True
- AccountingPeriod.closed_at = now
- AccountingPeriod.closed_by = user

### 3. 年度结转（12月专属）

12月结账时额外步骤：
- 查询4103本年利润的年度累计余额
- 生成"转"字凭证：借 本年利润4103 / 贷 利润分配-未分配利润4104
- 自动初始化下一年度12个会计期间

### 4. 反结账

- 仅admin权限
- 将 is_closed 设为 False
- 如果是12月反结账，需要同时删除年度结转凭证

### 5. 资产负债表

```
左侧（资产）                    右侧（负债+所有者权益）
━━━━━━━━━━━━━━━━━━━━          ━━━━━━━━━━━━━━━━━━━━━━
流动资产                        流动负债
  库存现金      xxx               短期借款        xxx
  银行存款      xxx               应付账款        xxx
  应收账款      xxx               预收账款        xxx
  预付账款      xxx               应付职工薪酬    xxx
  其他应收款    xxx               应交税费        xxx
  原材料        xxx               其他应付款      xxx
  库存商品      xxx             流动负债合计      xxx
  发出商品      xxx
流动资产合计    xxx             所有者权益
                                  实收资本        xxx
非流动资产                        盈余公积        xxx
  固定资产      xxx               本年利润        xxx
  累计折旧     (xxx)              未分配利润      xxx
非流动资产合计  xxx             所有者权益合计    xxx

资产总计        xxx             负债+权益总计     xxx
```

数据来源：查询各科目截至指定期间的累计余额（已过账凭证）。

### 6. 利润表

```
项目                          本期金额    本年累计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
一、营业收入
  主营业务收入(6001)            xxx         xxx
  其他业务收入(6051)            xxx         xxx
二、营业成本
  主营业务成本(6401)            xxx         xxx
  其他业务成本(6402)            xxx         xxx
  税金及附加(6403)              xxx         xxx
三、营业利润
  = 收入 - 成本
四、营业外收支
  营业外收入(6301)              xxx         xxx
  营业外支出(6711)              xxx         xxx
五、利润总额
  = 营业利润 + 营业外收支净额
六、所得税费用(6801)            xxx         xxx
七、净利润
  = 利润总额 - 所得税费用
```

### 7. 现金流量表（简易直接法）

查询银行存款(1002)+库存现金(1001)的所有已过账分录，按对手科目自动分类：

| 对手科目 | 现金流分类 |
|---------|-----------|
| 1122 应收账款 | 经营活动 — 销售商品收到的现金 |
| 2202 应付账款 | 经营活动 — 购买商品支付的现金 |
| 2211 应付职工薪酬 | 经营活动 — 支付给职工的现金 |
| 2221/222101/222102 应交税费 | 经营活动 — 支付的各项税费 |
| 6xxx 损益类 | 经营活动 — 其他经营现金流 |
| 2203 预收账款 | 经营活动 — 收到的其他经营现金 |
| 1123 预付账款 | 经营活动 — 支付的其他经营现金 |
| 1601 固定资产 | 投资活动 |
| 1403 原材料 | 投资活动 |
| 2001 短期借款 | 筹资活动 — 借款收到/偿还 |
| 4001 实收资本 | 筹资活动 — 吸收投资收到的现金 |
| 其他 | 经营活动（默认） |

报表结构：
```
一、经营活动现金流量
  销售商品、提供劳务收到的现金          xxx
  购买商品、接受劳务支付的现金         (xxx)
  支付给职工以及为职工支付的现金       (xxx)
  支付的各项税费                       (xxx)
  其他经营活动现金流入/流出             xxx
  经营活动现金流量净额                  xxx

二、投资活动现金流量
  购建固定资产支付的现金               (xxx)
  投资活动现金流量净额                  xxx

三、筹资活动现金流量
  借款收到的现金                        xxx
  偿还借款支付的现金                   (xxx)
  吸收投资收到的现金                    xxx
  筹资活动现金流量净额                  xxx

四、现金及现金等价物净增加额            xxx
  期初现金余额                          xxx
  期末现金余额                          xxx
```

## API 端点

### /api/period-end（~6个端点）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | /carry-forward/preview | period_end | 损益结转预览（返回将生成的分录） |
| POST | /carry-forward | period_end | 执行损益结转 |
| POST | /close-check | period_end | 结账5项检查 |
| POST | /close | period_end | 执行结账（锁定期间） |
| POST | /reopen | admin | 反结账 |
| POST | /year-close | period_end | 年度结转（12月专用） |

### /api/financial-reports（~6个端点）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /balance-sheet | accounting_view | 资产负债表数据 |
| GET | /income-statement | accounting_view | 利润表数据 |
| GET | /cash-flow | accounting_view | 现金流量表数据 |
| GET | /balance-sheet/export | accounting_view | Excel+PDF导出 |
| GET | /income-statement/export | accounting_view | Excel+PDF导出 |
| GET | /cash-flow/export | accounting_view | Excel+PDF导出 |

## 前端

### AccountingView 新增Tab

- **期末处理** — PeriodEndPanel
- **财务报表** — FinancialReportPanel（3个子Tab：资产负债表/利润表/现金流量表）

### PeriodEndPanel

- 当前期间状态卡片
- 损益结转区域：预览按钮 → 显示结转分录预览 → 确认执行
- 结账检查区域：5项检查清单（绿色✓/红色✗）→ 全部通过后显示结账按钮
- 年度结转区域（12月显示）
- 反结账按钮（admin）
- 期间历史列表

### FinancialReportPanel

- 期间选择器
- 资产负债表子Tab：左右两栏结构
- 利润表子Tab：本期 + 本年累计双列
- 现金流量表子Tab：三大活动分类
- 导出按钮（Excel/PDF）

## 新建/修改文件预估

### 新建文件（~14个）

| 文件 | 用途 |
|------|------|
| backend/app/services/period_end_service.py | 损益结转 + 结账检查 + 结账 + 年度结转 |
| backend/app/services/report_service.py | 三张报表查询 |
| backend/app/services/report_export.py | Excel + PDF 导出 |
| backend/app/routers/period_end.py | 期末处理路由 |
| backend/app/routers/financial_reports.py | 财务报表路由 |
| backend/tests/test_period_end.py | 期末处理测试 |
| backend/tests/test_reports.py | 报表测试 |
| frontend/src/components/business/PeriodEndPanel.vue | 期末处理面板 |
| frontend/src/components/business/FinancialReportPanel.vue | 报表容器 |
| frontend/src/components/business/BalanceSheetTab.vue | 资产负债表 |
| frontend/src/components/business/IncomeStatementTab.vue | 利润表 |
| frontend/src/components/business/CashFlowTab.vue | 现金流量表 |

### 修改文件（~4个）

| 文件 | 变更 |
|------|------|
| backend/main.py | 注册2个新路由 |
| frontend/src/api/accounting.js | 新增API函数 |
| frontend/src/views/AccountingView.vue | 新增2个Tab |
| backend/requirements.txt | 追加 openpyxl（如未安装） |
