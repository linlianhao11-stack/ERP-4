# 迁移系统版本化改造设计

> **目标**: 将 1201 行单文件 `migrations.py` 改造为版本化迁移系统，提升可维护性、可扩展性和启动性能。

## 现状问题

- `app/migrations.py` 包含 28 个迁移函数，1201 行全塞一个文件
- 每次启动全量检查所有迁移（检查列是否存在、表是否存在），启动越来越慢
- 新增迁移需要在大文件里找位置、写幂等检查、改调用顺序
- 无法追踪某个迁移何时执行过

## 方案选型

| 方案 | 可维护性 | 可扩展性 | 稳定性 | 选择 |
|------|---------|---------|--------|------|
| A: 纯拆文件 | 中 | 低 | 高 | ❌ |
| B: Aerich | 高 | 高 | 低（成熟度不够） | ❌ |
| **C: 自研版本化迁移** | **高** | **高** | **高** | ✅ |

## 架构设计

### 目录结构

```
app/migrations/
  __init__.py              # 导出 run_migrations()
  runner.py                # 迁移运行器（~80行）
  v001_init_seeds.py       # 种子数据（管理员/收付款方式/仓库）
  v002_location_warehouse.py
  v003_user_fields.py
  v004_order_fields.py
  v005_order_item_warehouse.py
  v006_purchase_order_fields.py
  v007_purchase_return_fields.py
  v008_timestamp_columns.py
  v009_shipping_flow.py
  v010_performance_indexes.py
  v011_accounting_phase1.py
  v012_accounting_phase3.py
  v013_accounting_phase4.py
  v014_accounting_phase5.py
  v015_supplier_account_balance.py
  v016_customer_account_balance.py
  v017_purchase_returns_table.py
  v018_invoice_pdf_files.py
  v019_shipment_no.py
  v020_ai_readonly_user.py
  v021_stock_last_activity.py
  v022_dropship_module.py
  v023_dropship_phone.py
  v024_tracking_refresh.py
  v025_warehouse_color.py
  v026_permission_migrations.py
  v027_missing_indexes.py
  v028_check_constraints.py
  README.md
```

### 核心组件：runner.py

```python
"""版本化迁移运行器

启动时：
1. 确保 migration_history 表存在
2. 扫描 migrations/ 目录下所有 v*.py 文件
3. 对比 migration_history，只执行未运行的迁移
4. 用 pg_advisory_lock 防止多 worker 并发
"""

# migration_history 表结构：
# id SERIAL PRIMARY KEY
# version VARCHAR(10) NOT NULL UNIQUE  -- "v001", "v002", ...
# name VARCHAR(200) NOT NULL           -- 文件名（不含 .py）
# applied_at TIMESTAMPTZ DEFAULT NOW()
```

### 迁移文件格式

每个文件导出一个 `up(conn)` 函数：

```python
"""v002: 仓位关联仓库"""

async def up(conn):
    await conn.execute_query(
        "ALTER TABLE locations ADD COLUMN IF NOT EXISTS warehouse_id INT ..."
    )
```

- 不需要 `down()` — 本项目不需要回滚能力（回滚靠数据库备份）
- 不需要手写幂等检查 — runner 保证每个迁移只执行一次
- 但对 DDL 操作仍建议用 `IF NOT EXISTS` 作为防御性编程

### 已有数据库兼容

对于已运行的数据库（生产/开发），首次启动时：
1. runner 检测到 `migration_history` 表不存在 → 创建
2. 发现 v001-v028 都未记录，但数据库已有这些变更
3. **解决方案**：runner 检查一个"基线标志"（如 `users` 表的 `password_changed_at` 列是否存在）
   - 存在 → 这是已有数据库，批量插入 v001-v028 为"已执行"
   - 不存在 → 这是全新数据库，从 v001 开始按顺序执行

### 全新部署兼容

全新数据库启动时，v001-v028 按顺序执行，效果等同于当前 `migrations.py` 的全量执行。

## 入口变更

```python
# main.py (改前)
from app.migrations import run_migrations

# main.py (改后) — 导入路径不变
from app.migrations import run_migrations
```

`app/migrations/__init__.py` 导出 `run_migrations()`，对 `main.py` 完全透明。

## 开发者指南（README.md 内容）

```
# 如何添加新迁移

1. 创建文件：v029_描述.py（编号递增）
2. 写 up() 函数：

   async def up(conn):
       await conn.execute_query("ALTER TABLE ...")

3. 完成。启动时自动执行。
```

## 不做的事

- 不引入 Aerich 或任何外部依赖
- 不实现 `down()` 回滚（靠数据库备份恢复）
- 不改变 Tortoise ORM 的 `generate_schemas()` 逻辑（仍由 `database.py` 负责）
- 不改变现有迁移的业务逻辑，只做物理拆分
