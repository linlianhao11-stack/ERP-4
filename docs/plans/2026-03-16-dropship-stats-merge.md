# 代采代发数据合并到 Dashboard + AI Chat 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将代采代发业务数据合并到 Dashboard 整体统计（KPI、趋势图、最近订单、畅销商品），并为 AI Chat 新增代采代发语义视图和预设查询。

**Architecture:** Dashboard 端修改 4 个 SQL 查询（UNION dropship_orders），前端最近订单区域适配 DROPSHIP 类型。AI Chat 端新增 2 个 PostgreSQL 视图 + schema 注册 + 权限 + 预设 + 业务词典。

**Tech Stack:** FastAPI + Tortoise ORM (raw SQL) + PostgreSQL 16 + Vue 3 + Chart.js

---

### Task 1: 后端 — Dashboard KPI 合并代采代发

**Files:**
- Modify: `backend/app/routers/dashboard.py:25-31` (今日销售额 SQL)
- Modify: `backend/app/routers/dashboard.py:37-42` (今日毛利 SQL)

**Step 1: 修改今日销售额查询**

将原 SQL 改为 UNION ALL 代采代发的 sale_total。在 `backend/app/routers/dashboard.py` 第 25-30 行，将整个 `sales_agg` 查询替换为：

```python
    # 今日销售额 + 毛利（常规订单 + 代采代发 UNION 聚合）
    sales_agg = await conn.execute_query_dict("""
        SELECT COALESCE(SUM(total_sales), 0) as total_sales,
               COALESCE(SUM(total_profit), 0) as total_profit
        FROM (
            SELECT SUM(total_amount) as total_sales, SUM(total_profit) as total_profit
            FROM orders WHERE created_at >= $1
              AND order_type IN ('CASH', 'CREDIT', 'CONSIGN_SETTLE')
            UNION ALL
            SELECT SUM(sale_total), SUM(gross_profit)
            FROM dropship_orders WHERE created_at >= $1
              AND status NOT IN ('draft', 'cancelled')
        ) combined
    """, [today])
```

**Step 2: 修改退货利润查询**

退货利润部分（第 37-42 行）保持不变 — 代采代发没有退货概念。无需改动。

**Step 3: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

---

### Task 2: 后端 — 销售趋势图合并代采代发

**Files:**
- Modify: `backend/app/routers/dashboard.py:192-200` (sales-trend SQL)

**Step 1: 修改趋势查询**

将 `get_sales_trend` 函数的 SQL（第 192-200 行）替换为：

```python
    rows = await conn.execute_query_dict("""
        SELECT date, COALESCE(SUM(amount), 0) as amount
        FROM (
            SELECT DATE(created_at) as date, total_amount as amount
            FROM orders
            WHERE created_at >= $1
              AND order_type IN ('CASH', 'CREDIT', 'CONSIGN_SETTLE')
            UNION ALL
            SELECT DATE(created_at) as date, sale_total as amount
            FROM dropship_orders
            WHERE created_at >= $1
              AND status NOT IN ('draft', 'cancelled')
        ) combined
        GROUP BY date
        ORDER BY date
    """, [start_date])
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

---

### Task 3: 后端 — 最近订单合并代采代发

**Files:**
- Modify: `backend/app/routers/dashboard.py:222-244` (recent-orders SQL + 返回格式)

**Step 1: 修改最近订单查询**

将 `get_recent_orders` 函数整个查询和返回部分替换为：

```python
    rows = await conn.execute_query_dict("""
        SELECT * FROM (
            SELECT o.id, o.order_no, o.order_type, o.total_amount,
                   o.shipping_status, o.is_cleared, o.created_at,
                   c.name as customer_name,
                   'order' as source
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.id
            UNION ALL
            SELECT d.id, d.ds_no as order_no, 'DROPSHIP' as order_type, d.sale_total as total_amount,
                   d.status as shipping_status, false as is_cleared, d.created_at,
                   d.customer_name,
                   'dropship' as source
            FROM dropship_orders d
            WHERE d.status NOT IN ('draft', 'cancelled')
        ) combined
        ORDER BY created_at DESC
        LIMIT $1
    """, [limit])

    return [
        {
            "id": r["id"],
            "order_no": r["order_no"],
            "order_type": r["order_type"],
            "total_amount": float(r["total_amount"]),
            "shipping_status": r["shipping_status"],
            "is_cleared": r["is_cleared"],
            "customer_name": r["customer_name"] or "-",
            "created_at": str(r["created_at"])[:19].replace("T", " ") if r["created_at"] else "",
            "source": r["source"],
        }
        for r in rows
    ]
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

---

### Task 4: 后端 — 畅销商品合并代采代发

**Files:**
- Modify: `backend/app/routers/dashboard.py:74-90` (top_products SQL)

**Step 1: 修改畅销商品查询**

将 `top_products` 查询（第 74-90 行）替换为：

```python
    # Top 10 畅销商品（常规订单 + 代采代发 UNION 聚合）
    top_products = await conn.execute_query_dict("""
        SELECT name, sku, SUM(quantity) as quantity, SUM(amount) as amount
        FROM (
            SELECT p.name, p.sku, oi.quantity, oi.amount
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            WHERE o.created_at >= $1
              AND o.order_type IN ('CASH', 'CREDIT', 'CONSIGN_SETTLE')
            UNION ALL
            SELECT d.product_name as name, '' as sku, d.quantity, d.sale_total as amount
            FROM dropship_orders d
            WHERE d.created_at >= $1
              AND d.status NOT IN ('draft', 'cancelled')
        ) combined
        GROUP BY name, sku
        ORDER BY quantity DESC
        LIMIT 10
    """, [thirty_days_ago])
    top_products = [
        {"name": r["name"], "sku": r["sku"], "quantity": int(r["quantity"]), "amount": float(r["amount"])}
        for r in top_products
    ]
```

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

---

### Task 5: 前端 — 最近订单适配 DROPSHIP 类型 + 点击跳转

**Files:**
- Modify: `frontend/src/utils/constants.js:124-134` (新增 DROPSHIP 类型映射)
- Modify: `frontend/src/views/DashboardView.vue:99-137` (最近订单模板)
- Modify: `frontend/src/views/DashboardView.vue:419-434` (goToOrder 函数)

**Step 1: 新增 DROPSHIP 类型到常量**

在 `frontend/src/utils/constants.js` 的 `orderTypeNames` 中添加:

```javascript
export const orderTypeNames = {
  CASH: '现款', CREDIT: '账期',
  CONSIGN_OUT: '寄售调拨', CONSIGN_SETTLE: '寄售结算',
  CONSIGN_RETURN: '寄售退货', RETURN: '退货',
  DROPSHIP: '代发',
}

export const orderTypeBadges = {
  CASH: 'badge badge-green', CREDIT: 'badge badge-yellow',
  CONSIGN_OUT: 'badge badge-purple', CONSIGN_SETTLE: 'badge badge-blue',
  CONSIGN_RETURN: 'badge badge-orange', RETURN: 'badge badge-red',
  DROPSHIP: 'badge badge-cyan',
}
```

**Step 2: 修改 DashboardView 的 goToOrder 函数**

在 `DashboardView.vue` 的 `goToOrder` 函数中（约第 419 行），添加代采代发订单的处理逻辑。需要判断 source 字段：

将 `goToOrder` 函数替换为：

```javascript
const goToOrder = async (order) => {
  // 代采代发订单：跳转到代采代发页面
  if (order.source === 'dropship') {
    router.push({ path: '/dropship', query: { orderId: order.id } })
    return
  }
  // 常规订单：打开详情弹窗
  orderDetailLoading.value = true
  showOrderDetail.value = true
  lockScroll(true)
  try {
    const { data } = await getOrder(order.id)
    Object.keys(orderDetail).forEach(k => delete orderDetail[k])
    Object.assign(orderDetail, data)
  } catch (e) {
    appStore.showToast('加载订单详情失败', 'error')
    showOrderDetail.value = false
    lockScroll(false)
  } finally {
    orderDetailLoading.value = false
  }
}
```

**Step 3: 修改模板中 goToOrder 的调用**

在移动端卡片（约第 99 行）和桌面端表格行（约第 126 行），将 `@click="goToOrder(o.id)"` 改为 `@click="goToOrder(o)"`（传整个对象而不是 id）。

移动端（约第 99 行）:
```html
        <div v-for="o in recentOrders" :key="o.order_no" class="px-4 py-3 cursor-pointer active:bg-elevated" @click="goToOrder(o)">
```

桌面端（约第 126 行）:
```html
              <tr v-for="o in recentOrders" :key="o.order_no" class="hover:bg-elevated cursor-pointer" @click="goToOrder(o)">
```

**Step 4: 代采代发订单的物流状态列显示**

桌面端表格的状态列（约第 131 行），对代采代发订单用 `dropshipStatus` 类型：

```html
              <td class="px-4 py-2.5 text-center">
                <StatusBadge v-if="o.order_type === 'DROPSHIP'" type="dropshipStatus" :status="o.shipping_status" />
                <StatusBadge v-else type="shippingStatus" :status="o.shipping_status" />
              </td>
```

**Step 5: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

---

### Task 6: AI Chat — 新建代采代发 PostgreSQL 视图

**Files:**
- Modify: `backend/app/ai/views.sql` (末尾添加 2 个视图 + GRANT)

**Step 1: 添加 vw_dropship_detail 视图**

在 `backend/app/ai/views.sql` 末尾（第 228 行 GRANT 语句之后）追加：

```sql

-- ============================================================
-- 10. 代采代发订单明细
-- ============================================================
CREATE OR REPLACE VIEW vw_dropship_detail AS
SELECT
    d.ds_no,
    d.created_at::date AS order_date,
    d.status,
    sup.name AS supplier_name,
    d.customer_name,
    d.product_name,
    d.quantity,
    ROUND(d.purchase_price::numeric, 2) AS purchase_price,
    ROUND(d.purchase_total::numeric, 2) AS purchase_total,
    ROUND(d.sale_price::numeric, 2) AS sale_price,
    ROUND(d.sale_total::numeric, 2) AS sale_total,
    ROUND(d.gross_profit::numeric, 2) AS gross_profit,
    ROUND(d.gross_margin::numeric, 2) AS gross_margin,
    d.carrier_name,
    d.tracking_no,
    d.settlement_type,
    d.note,
    u.name AS creator_name
FROM dropship_orders d
LEFT JOIN suppliers sup ON sup.id = d.supplier_id
LEFT JOIN users u ON u.id = d.creator_id;

-- 11. 代采代发按月汇总
CREATE OR REPLACE VIEW vw_dropship_summary AS
SELECT
    TO_CHAR(d.created_at, 'YYYY-MM') AS year_month,
    COUNT(*) AS order_count,
    ROUND(SUM(d.purchase_total)::numeric, 2) AS total_purchase,
    ROUND(SUM(d.sale_total)::numeric, 2) AS total_sales,
    ROUND(SUM(d.gross_profit)::numeric, 2) AS total_profit,
    ROUND(
        CASE WHEN SUM(d.sale_total) > 0
             THEN (SUM(d.gross_profit) / NULLIF(SUM(d.sale_total), 0) * 100)::numeric
             ELSE 0 END,
        2
    ) AS profit_rate,
    COUNT(DISTINCT d.customer_name) AS customer_count,
    COUNT(DISTINCT d.supplier_id) AS supplier_count
FROM dropship_orders d
WHERE d.status NOT IN ('draft', 'cancelled')
GROUP BY TO_CHAR(d.created_at, 'YYYY-MM');

-- 授权只读用户 — 代采代发视图
GRANT SELECT ON vw_dropship_detail TO erp_ai_readonly;
GRANT SELECT ON vw_dropship_summary TO erp_ai_readonly;
```

**Step 2: 验证**

SQL 文件不需要编译验证，将在应用启动时自动执行。确认文件语法无误即可。

---

### Task 7: AI Chat — Schema 注册 + 权限映射

**Files:**
- Modify: `backend/app/ai/schema_registry.py:157` (VIEW_SCHEMAS 末尾添加 2 个视图)
- Modify: `backend/app/ai/view_permissions.py:4-26` (添加映射 + 权限 key)

**Step 1: 在 schema_registry.py 注册视图**

在 `VIEW_SCHEMAS` 字典的最后一个条目 `vw_accounting_voucher_summary` 之后（第 157 行 `}` 之前），添加：

```python
    "vw_dropship_detail": {
        "description": "代采代发订单明细 — 每行一个代采代发订单",
        "columns": [
            ("ds_no", "VARCHAR", "代采代发单号"),
            ("order_date", "DATE", "订单日期"),
            ("status", "VARCHAR", "状态: draft/pending_payment/paid_pending_ship/shipped/completed/cancelled"),
            ("supplier_name", "VARCHAR", "供应商名称"),
            ("customer_name", "VARCHAR", "客户名称"),
            ("product_name", "VARCHAR", "商品名称"),
            ("quantity", "INT", "数量"),
            ("purchase_price", "DECIMAL", "采购单价"),
            ("purchase_total", "DECIMAL", "采购总额"),
            ("sale_price", "DECIMAL", "销售单价"),
            ("sale_total", "DECIMAL", "销售总额"),
            ("gross_profit", "DECIMAL", "毛利"),
            ("gross_margin", "DECIMAL", "毛利率(%)"),
            ("carrier_name", "VARCHAR", "快递公司"),
            ("tracking_no", "VARCHAR", "快递单号"),
            ("settlement_type", "VARCHAR", "结算方式: prepaid/postpaid"),
            ("note", "VARCHAR", "备注"),
            ("creator_name", "VARCHAR", "创建人"),
        ],
    },
    "vw_dropship_summary": {
        "description": "代采代发按月汇总",
        "columns": [
            ("year_month", "VARCHAR", "年月 如 2024-03"),
            ("order_count", "INT", "订单数"),
            ("total_purchase", "DECIMAL", "采购总额"),
            ("total_sales", "DECIMAL", "销售总额"),
            ("total_profit", "DECIMAL", "毛利"),
            ("profit_rate", "DECIMAL", "毛利率(%)"),
            ("customer_count", "INT", "客户数"),
            ("supplier_count", "INT", "供应商数"),
        ],
    },
```

**Step 2: 在 view_permissions.py 添加映射**

在 `AI_VIEW_PERMISSIONS` 字典中，`vw_accounting_voucher_summary` 之后添加：

```python
    "vw_dropship_detail": "ai_dropship",
    "vw_dropship_summary": "ai_dropship",
```

在 `AI_PERMISSION_KEYS` 列表末尾添加 `"ai_dropship"`:

```python
AI_PERMISSION_KEYS = [
    "ai_chat", "ai_sales", "ai_purchase", "ai_stock",
    "ai_customer", "ai_finance", "ai_accounting", "ai_dropship",
]
```

**Step 3: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

---

### Task 8: AI Chat — 预设查询 + 业务词典

**Files:**
- Modify: `backend/app/ai/preset_queries.py:77` (末尾添加预设)
- Modify: `backend/app/ai/business_dict.py:22` (末尾添加术语)

**Step 1: 添加预设查询**

在 `DEFAULT_PRESET_QUERIES` 列表末尾（第 77 行 `]` 之前）添加：

```python
    {
        "display": "本月代采代发概况",
        "keywords": ["代采代发", "代发"],
        "permission": "ai_dropship",
        "sql": "SELECT COUNT(*) AS 订单数, ROUND(SUM(sale_total),2) AS 销售额, ROUND(SUM(purchase_total),2) AS 采购额, ROUND(SUM(gross_profit),2) AS 毛利, ROUND(SUM(gross_profit)/NULLIF(SUM(sale_total),0)*100,2) AS 毛利率 FROM vw_dropship_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) AND status NOT IN ('draft', 'cancelled')",
    },
    {
        "display": "代采代发客户排名",
        "keywords": ["代采代发", "客户", "排名"],
        "permission": "ai_dropship",
        "sql": "SELECT customer_name AS 客户, COUNT(*) AS 订单数, ROUND(SUM(sale_total),2) AS 销售额, ROUND(SUM(gross_profit),2) AS 毛利 FROM vw_dropship_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) AND status NOT IN ('draft', 'cancelled') GROUP BY customer_name ORDER BY SUM(sale_total) DESC LIMIT 20",
    },
    {
        "display": "代采代发毛利分析",
        "keywords": ["代采代发", "毛利"],
        "permission": "ai_dropship",
        "sql": "SELECT supplier_name AS 供应商, COUNT(*) AS 订单数, ROUND(SUM(purchase_total),2) AS 采购额, ROUND(SUM(sale_total),2) AS 销售额, ROUND(SUM(gross_profit),2) AS 毛利, ROUND(SUM(gross_profit)/NULLIF(SUM(sale_total),0)*100,2) AS 毛利率 FROM vw_dropship_detail WHERE order_date >= date_trunc('month', CURRENT_DATE) AND status NOT IN ('draft', 'cancelled') GROUP BY supplier_name ORDER BY SUM(gross_profit) DESC",
    },
```

**Step 2: 添加业务词典**

在 `DEFAULT_BUSINESS_DICT` 列表末尾（第 23 行 `]` 之前）添加：

```python
    {"term": "代采代发/代发/直发", "meaning": "从供应商直接发货给客户，不经过自己仓库的业务模式", "field_hint": "vw_dropship_detail, vw_dropship_summary"},
    {"term": "代采代发毛利", "meaning": "销售额 - 采购额，代采代发的利润", "field_hint": "gross_profit, gross_margin"},
    {"term": "代采代发状态", "meaning": "草稿→待付款→已付待发→已发货→已完成/已取消", "field_hint": "status: draft/pending_payment/paid_pending_ship/shipped/completed/cancelled"},
```

**Step 3: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

---

### Task 9: 前端权限配置 — 新增 ai_dropship

**Files:**
- Modify: `frontend/src/utils/constants.js` (AI 权限分组中添加 ai_dropship)

**Step 1: 添加 ai_dropship 权限选项**

在 `frontend/src/utils/constants.js` 的权限分组中找到 AI 数据查询部分（含 `ai_sales`, `ai_purchase` 等），添加:

```javascript
    { key: 'ai_dropship', name: '代采代发数据' },
```

放在 `ai_finance` 之后。

**Step 2: 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

---

### Task 10: 端到端验证 + 提交

**Step 1: Build 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`
Expected: 编译成功，无错误

**Step 2: 功能验证（preview）**

- 启动开发服务器
- 访问首页 Dashboard
- 验证: 今日销售额是否包含代采代发数据
- 验证: 销售趋势图数据是否合并
- 验证: 最近订单列表是否包含代采代发订单（带「代发」标签）
- 验证: 点击代采代发订单是否跳转到代采代发页面

**Step 3: 提交**

```bash
git add \
  backend/app/routers/dashboard.py \
  backend/app/ai/views.sql \
  backend/app/ai/schema_registry.py \
  backend/app/ai/view_permissions.py \
  backend/app/ai/preset_queries.py \
  backend/app/ai/business_dict.py \
  frontend/src/utils/constants.js \
  frontend/src/views/DashboardView.vue
git commit -m "feat: 代采代发数据合并到 Dashboard 统计 + AI Chat 可查询"
```
