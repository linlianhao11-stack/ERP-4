# 代采代发数据合并到整体统计 + AI Chat 可查询

## 目标

将代采代发（dropship）业务数据合并到 Dashboard 整体统计中，并让 AI Chat 能够查询代采代发数据。

## 决策记录

| 决策项 | 选择 | 原因 |
|--------|------|------|
| 销售趋势图 | 合并为一条线 | 简洁直观，用户只关心总收入 |
| 最近订单 | 混合显示 + 类型标签 | 按时间排序，代采代发加「代发」标签区分 |
| AI 权限 | 新增 ai_dropship | 精细控制，与其他 AI 权限体系一致 |

## 一、Dashboard 改动

### 1.1 KPI 卡片

**今日销售额**：原 SQL 只查 `orders` 表，改为 UNION `dropship_orders.sale_total`（排除 draft/cancelled 状态）。

**今日毛利**：同上，UNION `dropship_orders.gross_profit`。

### 1.2 销售趋势图

`GET /api/dashboard/sales-trend` 的 SQL 改为 UNION 两个渠道的每日金额，合并为一条线。

### 1.3 最近订单

`GET /api/dashboard/recent-orders` 改为 UNION 代采代发订单，统一字段格式：
- `order_no` → `ds_no`
- `total_amount` → `sale_total`
- `order_type` → 固定 `'DROPSHIP'`
- `shipping_status` → 映射 dropship status
- `customer_name` → 同字段名

前端根据 `order_type === 'DROPSHIP'` 显示「代发」标签，点击打开代采代发详情。

### 1.4 畅销商品 TOP10

UNION 代采代发的商品销量（`product_name` + `quantity`），按总量排序。

### 1.5 不改的部分

- **库存总值** — 代采代发不涉及库存
- **应收账款** — 代采代发用独立的应收体系
- **今日发货** — 代采代发的物流是外部快递，不走内部发货流程
- **待办计数** — 代采代发有独立待办

## 二、AI Chat 改动

### 2.1 新建 PostgreSQL 视图

**`vw_dropship_detail`** — 代采代发订单明细：
- ds_no (单号), order_date (日期), status (状态)
- supplier_name (供应商), customer_name (客户)
- product_name (商品), quantity (数量)
- purchase_price (采购单价), purchase_total (采购总额)
- sale_price (销售单价), sale_total (销售总额)
- gross_profit (毛利), gross_margin (毛利率)
- carrier_name (快递公司), tracking_no (快递单号), tracking_status (物流状态)
- settlement_type (结算方式), note (备注)

**`vw_dropship_summary`** — 代采代发月度汇总：
- year_month (月份), order_count (订单数)
- total_purchase (采购总额), total_sales (销售总额)
- total_profit (毛利), profit_rate (毛利率)
- customer_count (客户数), supplier_count (供应商数)

### 2.2 Schema 注册

在 `schema_registry.py` 中注册两个新视图，包含字段名、中文注释、数据类型。

### 2.3 权限

- 新增 `ai_dropship` 权限
- 映射：`ai_dropship` → `vw_dropship_detail`, `vw_dropship_summary`

### 2.4 预设查询

新增 3 个高频预设：
- "本月代采代发概况" → 查 vw_dropship_summary
- "代采代发毛利分析" → 按客户/供应商维度的毛利
- "代采代发客户排名" → 按客户的销售额排名

### 2.5 业务词典

补充术语：代采代发、代发、直发、supply chain、dropship、物流状态（待查询/运输中/已签收/待揽收）

### 2.6 数据库授权

给 `erp_ai_readonly` 用户 GRANT SELECT 新视图。

## 三、影响范围

| 文件 | 改动类型 |
|------|----------|
| `backend/app/routers/dashboard.py` | 修改 SQL |
| `frontend/src/views/DashboardView.vue` | 最近订单显示代发标签 + 点击跳转 |
| `backend/app/migrations.py` | 新增视图迁移 + 授权 |
| `backend/app/ai/schema_registry.py` | 注册新视图 |
| `backend/app/ai/view_permissions.py` | 新增 ai_dropship 映射 |
| `backend/app/ai/preset_queries.py` | 新增预设查询 |
| `backend/app/ai/prompt_builder.py` | 补充业务词典 |
