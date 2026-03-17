# 物流状态自动刷新设计文档

> 日期: 2026-03-17
> 状态: 已确认

## 问题

代发代采（DropshipOrder）和普通物流（Shipment）的物流状态只能通过用户手动点击"刷新物流"按钮更新。快递100 Webhook 推送因无公网回调地址而不可用。物流状态影响订单状态流转，手动刷新导致订单状态更新严重滞后。

## 方案：智能分级轮询（方案 B）

### 架构

新增 `backend/app/services/tracking_refresh_service.py`，包含一个 asyncio 后台循环（与 `auto_backup_loop` 同模式），在 `main.py` 的 `lifespan` 中启动。

```
每 60 秒唤醒 → 查询需刷新订单 → 逐个调用快递100 → 更新物流+订单状态 → 休眠
```

### 覆盖模型

| 模型 | 筛选条件 | 状态联动 |
|------|---------|---------|
| DropshipOrder | status=`shipped`，有 tracking_no | 已签收 → status 改为 `completed` |
| Shipment | status 非 `signed`/`pending`，有 tracking_no | 已签收 → status 改为 `signed` |
| Order（通过 Shipment 联动） | 所有 Shipment 已签收 | shipping_status 改为 `delivered` |

### 分级刷新策略

根据发货时间（`shipped_at` / `created_at`）距今天数，控制刷新间隔：

| 发货天数 | 刷新间隔 | 说明 |
|---------|---------|------|
| 0-1 天 | 2 小时 | 揽收确认 |
| 2-5 天 | 4 小时 | 运输中，变化适中 |
| 6-15 天 | 8 小时 | 长途/偏远 |
| 16-30 天 | 24 小时 | 低频检查 |
| 30+ 天 | 停止轮询 | 需人工介入 |

判断逻辑：`now - last_tracking_refresh >= 对应间隔` 时刷新。

### 数据库变更

两个模型各新增一个字段：

```python
# DropshipOrder
last_tracking_refresh = fields.DatetimeField(null=True)

# Shipment
last_tracking_refresh = fields.DatetimeField(null=True)
```

通过 `run_migrations` 自动添加列（ALTER TABLE ADD COLUMN IF NOT EXISTS）。

### Order.shipping_status 新增值

现有值：`pending` → `partial` → `completed`（全部发货）

新增：`delivered`（全部签收）。当 Order 下所有 Shipment.status 均为 `signed` 且 Order.shipping_status 为 `completed` 时，自动更新为 `delivered`。

### 保护措施

- **查询间延迟**：每次快递100查询间隔 1.5 秒，避免限流
- **单轮上限**：最多刷新 50 单（DropshipOrder 25 + Shipment 25）
- **错误隔离**：单个订单查询失败不阻断其他订单
- **KD100 未配置**：`_get_kd100_config` 返回空则跳过整轮
- **日志**：每轮记录刷新数量、成功/失败数、状态变更

### 文件变更清单

| 文件 | 变更 |
|------|------|
| `backend/app/services/tracking_refresh_service.py` | **新增** — 后台刷新循环主逻辑 |
| `backend/app/models/dropship.py` | 新增 `last_tracking_refresh` 字段 |
| `backend/app/models/shipment.py` | 新增 `last_tracking_refresh` 字段 |
| `backend/app/migrations.py` | 新增两个 ALTER TABLE 迁移 |
| `backend/main.py` | lifespan 中启动 tracking_refresh_task |

### 不做的事

- 不修 Webhook 回调（无公网地址，修了也没用）
- 不加前端自动刷新（后端定时已够用）
- 不加管理后台配置界面（通过环境变量或代码常量控制策略）
