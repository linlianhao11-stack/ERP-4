# 每日业务日报邮件

> **目标**: 每天定时生成业务日报，通过邮件发送给指定收件人。HTML 正文含 AI 分析 + 关键指标，Excel 附件含完整数据。

## 约束

- 不新增 Python 依赖（smtplib、email 均为标准库）
- 数据查询用固定 SQL，不走 AI 生成（100% 可靠）
- V3 分析为可选增强，失败不阻塞发送
- SMTP 密码 Fernet 加密存储（复用现有加密机制）

## 整体流程

```
定时触发（用户配置的时间）
  → 检查 last_sent_date 防重复
  → 执行 8 条固定 SQL（今天 vs 昨天环比）
  → 收集数据，生成 Excel 附件（多 sheet）
  → 调 V3 生成分析摘要（best-effort，失败不阻塞）
  → 拼装 HTML 邮件（AI 分析 + 关键指标摘要表）
  → 逐个收件人 SMTP 发送（单个失败不阻塞其他人）
  → 记录 last_sent_date + 操作日志
```

## 固定 SQL 查询（8 条）

| # | 标题 | 视图 | 说明 |
|---|------|------|------|
| 1 | 销售概况（环比） | vw_sales_detail | 今天 vs 昨天：订单数、销售额、毛利、毛利率 |
| 2 | 销售额 TOP5 客户 | vw_sales_detail | 今日按客户汇总 |
| 3 | 销售额 TOP5 商品 | vw_sales_detail | 今日按商品汇总 |
| 4 | 采购概况（环比） | vw_purchase_detail | 今天 vs 昨天：采购单数、金额、状态分布（中文） |
| 5 | 库存周转 TOP10（最慢） | vw_inventory_turnover | 当前库存>0，周转率升序 |
| 6 | 应收账款概况 | vw_receivables | 未收总额、逾期(>30天)金额 |
| 7 | 应付账款概况 | vw_payables | 未付总额、逾期(>30天)金额 |
| 8 | 账龄超30天客户欠款 | vw_receivables | 按账龄降序明细 |

日期条件：今天 = `CURRENT_DATE`，昨天 = `CURRENT_DATE - 1`。

## AI 分析（V3，可选）

- 将 8 张表摘要数据拼接后交给 V3（deepseek-chat）
- max_tokens=2048，timeout=60s
- 失败降级：邮件只发数据，不含分析文字

## 邮件格式

### HTML 正文
- 标题："XXX 业务日报 — 2026-03-18（截至发送时刻）"
- AI 分析摘要段落（如有）
- 关键指标卡片：今日销售额、毛利、采购额、应收余额（带环比）
- 各维度简要数据表格（前 5 行）

### Excel 附件
- 文件名：`业务日报_2026-03-18.xlsx`
- 8 个 sheet，复用现有 openpyxl 逻辑

## 系统设置项

| key | 类型 | 说明 |
|-----|------|------|
| daily_report.enabled | bool | 启用/禁用 |
| daily_report.send_time | string | 发送时间，如 "21:00" |
| daily_report.recipients | JSON array | 收件人邮箱列表 |
| daily_report.smtp_host | string | SMTP 服务器 |
| daily_report.smtp_port | int | SMTP 端口（默认 465） |
| daily_report.smtp_user | string | SMTP 用户名 |
| daily_report.smtp_password | string | SMTP 密码（Fernet 加密） |
| daily_report.from_email | string | 发件人地址 |
| daily_report.from_name | string | 发件人名称 |
| daily_report.last_sent_date | string | 上次发送日期（防重复） |

## 新增文件

| 文件 | 职责 |
|------|------|
| app/services/email_service.py | SMTP 封装（HTML + 附件） |
| app/services/daily_report_service.py | 日报生成：SQL → V3 → HTML → Excel → 发送 |
| app/routers/daily_report.py | 设置 CRUD + 测试发送 + 手动触发 |

## 修改文件

| 文件 | 改动 |
|------|------|
| main.py | lifespan 新增 daily_report_loop 后台任务 |

## 前端

设置页面新增"日报邮件"配置卡片：
- 启用开关、发送时间选择器、收件人列表
- SMTP 配置（host、port、用户名、密码、发件地址、名称）
- 「测试发送」按钮、「立即发送」按钮

## 不做的事

- 不走 R1 生成 SQL
- 不存日报历史快照
- 不做周报/月报
- 不做飞书/钉钉通知
- 不做邮件模板自定义
- 不新增 Python 依赖
