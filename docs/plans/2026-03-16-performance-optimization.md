# 性能优化实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 全面优化数据库索引、查询模式和端点安全，为 50 万+ 订单量级压力测试做准备

**Architecture:** 在 Model Meta 层补充缺失索引，通过 migrations.py 的 `CREATE INDEX IF NOT EXISTS` 幂等创建；优化 N+1 查询改为 select_related；修复无分页/无限制端点

**Tech Stack:** Tortoise ORM, PostgreSQL 16, FastAPI

---

### Task 1: 补充 Model Meta 索引配置

**Files:**
- Modify: `backend/app/models/product.py:19-20`
- Modify: `backend/app/models/customer.py:21-22`
- Modify: `backend/app/models/supplier.py:19-20`
- Modify: `backend/app/models/stock.py:16-18`
- Modify: `backend/app/models/voucher.py:28-29` (Voucher) 和 `48-50` (VoucherEntry)

**Step 1: 给 Product 加索引**

```python
# backend/app/models/product.py:19-21
    class Meta:
        table = "products"
        indexes = (("is_active",),)
```

**Step 2: 给 Customer 加索引**

```python
# backend/app/models/customer.py:21-23
    class Meta:
        table = "customers"
        indexes = (("is_active",),)
```

**Step 3: 给 Supplier 加索引**

```python
# backend/app/models/supplier.py:19-21
    class Meta:
        table = "suppliers"
        indexes = (("is_active",),)
```

**Step 4: 给 WarehouseStock 加复合索引**

```python
# backend/app/models/stock.py:16-19
    class Meta:
        table = "warehouse_stocks"
        unique_together = (("warehouse", "product", "location"),)
        indexes = (("warehouse_id", "product_id"),)
```

**Step 5: 给 Voucher 加索引**

```python
# backend/app/models/voucher.py:28-30
    class Meta:
        table = "vouchers"
        indexes = (("status",),)
```

**Step 6: 给 VoucherEntry 加索引**

```python
# backend/app/models/voucher.py:48-51
    class Meta:
        table = "voucher_entries"
        ordering = ["line_no"]
        indexes = (("voucher_id",), ("account_id",),)
```

**Step 7: 验证**

Run: `cd backend && python -c "from app.models import *; print('Models OK')"`

**Step 8: Commit**

```bash
git add backend/app/models/
git commit -m "perf: 补充 Model Meta 索引配置 — product/customer/supplier/stock/voucher"
```

---

### Task 2: 在 migrations.py 补充缺失的数据库索引

**Files:**
- Modify: `backend/app/migrations.py` — 在 `migrate_add_indexes()` 函数的 `indexes` 列表中追加新条目

**Step 1: 在 migrations.py 的 indexes 列表末尾追加**

在 `migrate_add_indexes()` 函数中，找到 `indexes = [...]` 列表（约第 195 行），在列表末尾追加以下条目：

```python
        # --- 性能优化批次 2026-03-16 ---
        ("idx_products_is_active", "products", "is_active"),
        ("idx_customers_is_active", "customers", "is_active"),
        ("idx_suppliers_is_active", "suppliers", "is_active"),
        ("idx_orders_shipping_status", "orders", "shipping_status"),
        ("idx_warehouse_stocks_wh_product", "warehouse_stocks", "warehouse_id, product_id"),
        ("idx_vouchers_status", "vouchers", "status"),
        ("idx_shipments_status_date", "shipments", "status, created_at"),
        ("idx_operation_logs_operator_date", "operation_logs", "operator_id, created_at"),
```

**Step 2: 验证索引列表语法**

Run: `cd backend && python -c "from app.migrations import migrate_add_indexes; print('OK')"`

**Step 3: Commit**

```bash
git add backend/app/migrations.py
git commit -m "perf: 补充缺失数据库索引 — is_active/shipping_status/warehouse_stock 复合索引"
```

---

### Task 3: 优化应收/应付列表查询 — prefetch_related 改 select_related

**Files:**
- Modify: `backend/app/routers/receivables.py` — 约第 63 行
- Modify: `backend/app/routers/payables.py` — 约第 63 行

**Step 1: 修改 receivables.py**

将 `.prefetch_related("customer", "order")` 改为 `.select_related("customer", "order")`

原因：`customer` 和 `order` 都是 FK 关系，`select_related` 用 JOIN 一次查出，避免 N+1。

**Step 2: 修改 payables.py**

将 `.prefetch_related("supplier", "purchase_order")` 改为 `.select_related("supplier", "purchase_order")`

**Step 3: 验证**

启动后端，请求 `/api/accounting/receivable-bills?account_set_id=1` 确认返回正常。

**Step 4: Commit**

```bash
git add backend/app/routers/receivables.py backend/app/routers/payables.py
git commit -m "perf: 应收/应付列表 prefetch_related 改 select_related 消除 N+1"
```

---

### Task 4: 修复商品导出无 limit 问题

**Files:**
- Modify: `backend/app/routers/products.py` — 约第 124 行

**Step 1: 给商品导出加 limit**

将:
```python
products = await Product.filter(is_active=True)
```
改为:
```python
products = await Product.filter(is_active=True).limit(10000)
```

**Step 2: Commit**

```bash
git add backend/app/routers/products.py
git commit -m "perf: 商品导出加 limit(10000) 防止大数据量 OOM"
```

---

### Task 5: 采购导出改为流式响应

**Files:**
- Modify: `backend/app/routers/purchase_orders.py` — 约第 100-159 行

**Step 1: 将导出改为 StreamingResponse**

在文件顶部确认已有 `from starlette.responses import StreamingResponse` 导入（或添加）。

将当前的 `output = io.StringIO()` + 循环写入 + `return StreamingResponse(...)` 模式保持不变，但将内存中一次性构建改为生成器模式：

```python
import io
from starlette.responses import StreamingResponse

# 在 export 函数内，将 for 循环改为生成器
def generate_csv():
    output = io.StringIO()
    output.write('\ufeff')
    output.write(','.join(headers) + '\n')
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    for o in orders:
        # ... 构建行数据（保持现有逻辑不变）
        # 每 100 行 flush 一次
        if line_count % 100 == 0:
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    remaining = output.getvalue()
    if remaining:
        yield remaining

return StreamingResponse(generate_csv(), media_type="text/csv", ...)
```

注意：这个改动比较大，需要仔细保持现有的 CSV 行构建逻辑不变，只是包裹成生成器。如果改动风险太高，可以只将 `limit(10000)` 降为 `limit(5000)` 作为替代方案。

**Step 2: 验证**

请求 `/api/purchase/export` 确认 CSV 下载正常。

**Step 3: Commit**

```bash
git add backend/app/routers/purchase_orders.py
git commit -m "perf: 采购导出改流式响应，降低大数据量内存压力"
```

---

### Task 6: 客户交易端点改为分页

**Files:**
- Modify: `backend/app/routers/customers.py` — 约第 57-125 行

**Step 1: 将 limit(500) 改为分页参数**

修改函数签名，增加分页参数：
```python
@router.get("/{customer_id}/transactions")
async def get_customer_transactions(
    customer_id: int,
    year: Optional[int] = None,
    month: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("customer", "finance"))
):
```

将:
```python
orders = await query.order_by("-created_at").limit(500).select_related("warehouse", "creator", "employee")
```
改为:
```python
total = await query.count()
orders = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).select_related("warehouse", "creator", "employee")
```

在返回值中增加分页信息：
```python
return {
    "customer": {...},
    "stats": stats if has_finance else None,
    "transactions": transactions_list,
    "available_months": available_months,
    "total": total,
    "page": page,
    "page_size": page_size,
}
```

注意：stats 统计目前是在 Python 循环中累加当前页的数据。改为分页后，stats 只反映当前页。如果需要全量 stats，需要用数据库聚合 SQL 替代。鉴于改动范围，先保持现状（stats 仅反映当前页），后续可优化。

**Step 2: 修改前端对应的 API 调用**

检查 `frontend/src/api/customers.js` 和使用该接口的组件，确认传入 page/page_size 参数，并处理返回的 total 字段。

**Step 3: Commit**

```bash
git add backend/app/routers/customers.py
git commit -m "perf: 客户交易端点改分页 — 默认 20 条/页替代 limit(500)"
```

---

### Task 7: 优化仪表盘低库存预警查询

**Files:**
- Modify: `backend/app/routers/dashboard.py` — 约第 159-172 行

**Step 1: 在子查询中加 WHERE 预过滤**

将:
```sql
SELECT COUNT(*) as c FROM (
    SELECT ws.product_id
    FROM warehouse_stocks ws
    JOIN warehouses w ON ws.warehouse_id = w.id
    JOIN products p ON ws.product_id = p.id
    WHERE NOT w.is_virtual AND p.is_active = true
    GROUP BY ws.product_id
    HAVING SUM(ws.quantity) < 10
) sub
```
改为:
```sql
SELECT COUNT(*) as c FROM (
    SELECT ws.product_id
    FROM warehouse_stocks ws
    JOIN warehouses w ON ws.warehouse_id = w.id
    JOIN products p ON ws.product_id = p.id
    WHERE NOT w.is_virtual AND p.is_active = true AND ws.quantity >= 0
    GROUP BY ws.product_id
    HAVING SUM(ws.quantity) < 10
) sub
```

增加 `AND ws.quantity >= 0` 排除负数记录（如果有的话），主要目的是让查询优化器更好地利用索引。

**Step 2: Commit**

```bash
git add backend/app/routers/dashboard.py
git commit -m "perf: 低库存预警查询加 WHERE 预过滤优化"
```

---

### Task 8: 重构 Docker 并验证

**Step 1: 构建前端**

```bash
cd frontend && npm run build
```

**Step 2: 重构 Docker**

```bash
docker compose up -d --build erp
```

**Step 3: 验证索引已创建**

```bash
docker exec erp-4-erp-1 python -c "
import asyncio
from tortoise import Tortoise, connections
async def check():
    await Tortoise.init(db_url='postgres://...', modules={'models': ['app.models']})
    conn = connections.get('default')
    rows = await conn.execute_query_dict(\"SELECT indexname FROM pg_indexes WHERE tablename IN ('products','customers','suppliers','warehouse_stocks','vouchers','shipments','operation_logs') ORDER BY tablename, indexname\")
    for r in rows:
        print(r['indexname'])
asyncio.run(check())
"
```

或者直接进 psql 查看：
```bash
docker exec -it erp-4-db-1 psql -U erp -d erp -c "\di"
```

**Step 4: Commit**

```bash
git add -A
git commit -m "perf: 全面性能优化完成 — 索引/查询/分页/流式导出"
```
