# 性能优化设计文档

日期：2026-03-16
目标：为 50 万+ 订单量级的压力测试做准备，全面优化数据库索引、查询模式和端点安全

---

## 一、数据库索引优化

### 1.1 新增索引（Model Meta 配置）

| 表 | 新增索引 | 原因 |
|---|---|---|
| `products` | `(is_active,)`, `(category_id,)` | 列表筛选无索引 |
| `customers` | `(is_active,)` | 仪表盘应收聚合过滤 |
| `suppliers` | `(is_active,)` | 采购列表筛选 |
| `orders` | `(order_type, created_at)`, `(shipping_status,)`, `(account_set_id,)` | 类型+日期筛选、物流状态筛选 |
| `warehouse_stocks` | `(warehouse_id, product_id)`, `(product_id,)` | 仪表盘库存聚合 JOIN |
| `vouchers` | `(account_set_id, period_name)`, `(status,)` | 凭证列表筛选 |
| `voucher_entries` | `(voucher_id,)`, `(account_id,)` | 明细查询和科目汇总 |
| `shipments` | `(status, created_at)` | 物流列表状态+时间筛选 |
| `operation_logs` | `(operator_id, created_at)` | 审计日志按操作人筛选 |

### 1.2 实施方式

在各 Model 的 `class Meta:` 中添加 `indexes` 配置，Tortoise ORM 在 `generate_schemas()` 时会自动创建。对于已有数据的表，通过 `migrations.py` 的 `run_raw_sql` 用 `CREATE INDEX IF NOT EXISTS` 确保幂等。

---

## 二、N+1 查询优化

### 2.1 订单详情（orders.py:318-484）

当前问题：加载一个订单详情需要 10-15 条独立 SQL

优化方案：
- 合并 `OrderItem` + `Product` + `Warehouse` 为一次 `select_related` 查询
- `AccountSet` 名称映射改为批量 `IN` 查询（当前已是，保持）
- 发货单 + 发货明细合并为一次查询
- 收款记录 + 收款关联合并为一次查询

预期：从 10-15 条 SQL 降到 4-5 条

### 2.2 应收/应付列表（receivables.py, payables.py）

当前问题：使用 `prefetch_related`（惰性 N+1）
优化方案：改为 `select_related`（FK 关系用 JOIN 一次查出）

---

## 三、无分页/无限制端点修复

### 3.1 商品导出（products.py:124）

当前：`Product.filter(is_active=True)` 无 limit
修复：加 `limit(10000)` 安全上限

### 3.2 采购导出（purchase_orders.py:121）

当前：`limit(10000)` 全量加载到内存
修复：改为 `StreamingResponse` 流式 CSV 输出

### 3.3 客户交易（customers.py:73）

当前：`limit(500)` 硬编码
修复：改为分页参数 `page` + `page_size`，默认 20 条/页

---

## 四、仪表盘聚合查询优化

### 4.1 低库存预警（dashboard.py:159-171）

当前：子查询 + HAVING 全表扫描
优化：加 `WHERE ws.quantity > 0` 预过滤减少聚合行数

### 4.2 库存总值 + Top 10 商品

依赖索引优化即可解决，SQL 结构本身合理

---

## 五、改动范围

- **Model 层**：只加 `indexes` 和 `class Meta`，不改字段定义
- **Router 层**：优化查询方式、加 limit/分页，不改业务逻辑
- **Migration**：通过 `run_raw_sql` 创建索引，幂等执行
- **前端**：无改动

## 六、验证方式

1. 加完索引后生成 50 万条压测数据
2. 用 `EXPLAIN ANALYZE` 验证关键查询走索引
3. 对比优化前后的 API 响应时间
