# 数据库迁移

## 如何添加新迁移

1. 创建文件 `vNNN_描述.py`（编号递增，如 `v029_add_xxx.py`）
2. 实现 `up(conn)` 函数：

```python
"""v029: 描述"""

async def up(conn):
    await conn.execute_query("ALTER TABLE ...")
```

3. 完成。下次启动时自动执行。

## 工作原理

- `runner.py` 启动时扫描所有 `v*.py` 文件
- 对比 `migration_history` 表，只执行未运行的迁移
- 用 `pg_advisory_lock` 防止多 worker 并发执行
- 已有数据库首次升级时，v001-v028 自动标记为已执行（通过检测 `users.password_changed_at` 列判断）

## 注意事项

- 文件编号必须递增且唯一
- 已提交的迁移文件不要修改（已在生产执行过）
- DDL 操作建议用 `IF NOT EXISTS` 作为防御性编程
- 迁移失败会阻止应用启动（fail-fast）
- `up(conn)` 中可以直接使用 ORM 模型（如 `await User.filter(...)`），也可以用 `conn.execute_query()` 执行原始 SQL
- 版本号最大支持 v999（3 位零填充，确保字符串排序正确）
