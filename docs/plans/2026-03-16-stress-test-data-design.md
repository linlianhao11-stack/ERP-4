# 压力测试数据生成设计

## 目标

向 ERP 系统注入 ~120 万条测试数据，验证百万级数据下各模块性能表现。

## 数据分布

| 层级 | 表 | 目标量 | 说明 |
|------|-----|--------|------|
| 基础数据 | products | 5,000 | 商品 SKU |
| | customers | 2,000 | 客户 |
| | suppliers | 500 | 供应商 |
| 交易核心 | orders | 100,000 | 2年跨度 |
| | order_items | 300,000 | 平均每单3项 |
| | purchase_orders | 20,000 | 采购单 |
| | purchase_order_items | 60,000 | 平均每单3项 |
| 库存 | warehouse_stocks | 20,000 | 仓库×商品 |
| | stock_logs | 200,000 | 库存变动 |
| 物流 | shipments | 80,000 | 物流记录 |
| | shipment_items | 120,000 | 物流明细 |
| 财务 | vouchers | 50,000 | 凭证 |
| | voucher_entries | 100,000 | 凭证分录 |
| | receivable_bills | 30,000 | 应收单 |
| | payable_bills | 15,000 | 应付单 |
| 日志 | operation_logs | 100,000 | 操作日志 |
| **合计** | | **~1,200,000** | |

## 生成策略

### 方式：Python 脚本 + PostgreSQL COPY

- 用 Python 生成 CSV 文件，通过 `COPY FROM` 批量导入
- 比 ORM 逐条插入快 100x+
- 脚本位置：`backend/scripts/generate_stress_data.py`

### 数据标记

所有测试数据通过以下方式标记，便于清除：
- 有 `remark` 字段的表：填入 `[STRESS_TEST]`
- 无 remark 但有 `description` 字段：填入 `[STRESS_TEST]`
- 商品 SKU 前缀：`ST-`
- 客户名前缀：`压测客户-`
- 供应商名前缀：`压测供应商-`
- 订单号前缀：`ST-SO-`
- 采购单号前缀：`ST-PO-`
- 凭证号前缀：`ST-V-`
- 应收单号前缀：`ST-AR-`
- 应付单号前缀：`ST-AP-`

### ID 范围

- 所有测试数据 ID 从 100,000 开始
- 避免与现有真实数据冲突
- 清除时按 `id >= 100000` 批量删除

### 时间跨度

- 订单日期：2024-01-01 ~ 2026-03-15（约2年）
- 均匀分布，模拟真实业务增长

### FK 依赖顺序

生成顺序必须遵循 FK 依赖：
1. products, customers, suppliers（无 FK 依赖）
2. warehouse_stocks（依赖 warehouse + product）
3. orders（依赖 customer + warehouse）
4. order_items（依赖 order + product）
5. purchase_orders（依赖 supplier + warehouse）
6. purchase_order_items（依赖 purchase_order + product）
7. shipments（依赖 order）
8. shipment_items（依赖 shipment + order_item + product）
9. stock_logs（依赖 product + warehouse）
10. vouchers（依赖 account_set）
11. voucher_entries（依赖 voucher + chart_of_account）
12. receivable_bills（依赖 account_set + customer + order）
13. payable_bills（依赖 account_set + supplier + purchase_order）
14. operation_logs（依赖 user）

## 清除策略

清除脚本：`backend/scripts/cleanup_stress_data.py`

按 FK 依赖逆序删除（子表先删）：
1. operation_logs, voucher_entries, shipment_items, stock_logs
2. receivable_bills, payable_bills, shipments, vouchers
3. order_items, purchase_order_items
4. orders, purchase_orders
5. warehouse_stocks
6. products, customers, suppliers

删除条件：`id >= 100000`

清除后重置序列：`SELECT setval(pg_get_serial_sequence(table, 'id'), max(id)) FROM table`

## 脚本交付

- `backend/scripts/generate_stress_data.py` — 在 Docker 容器内执行
- `backend/scripts/cleanup_stress_data.py` — 在 Docker 容器内执行
- 两个脚本都通过 `docker exec` 运行，直连数据库
