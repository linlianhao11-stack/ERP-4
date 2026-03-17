# 代采代发通知待办机制设计

> 日期：2026-03-17
> 状态：已确认

## 背景

项目已有基于 `todo-counts` 轮询的通知待办机制，但代采代发模块未接入。现有催付款 UI（橙色「催」字 badge）与项目整体风格不符。

## 设计方案：扩展现有 todo-counts

沿用项目现有模式，零新增依赖，改动最小。

### 一、后端：扩展 todo-counts 查询

在 `dashboard.py` 的 `get_todo_counts` 端点新增 3 条查询（均需 `account_set_id` 过滤）：

| 字段名 | SQL 条件 | 含义 |
|--------|---------|------|
| `ds_pending_payment` | `status='pending_payment'` | 待付款 |
| `ds_paid_pending_ship` | `status='paid_pending_ship'` | 已付待发 |
| `ds_urged_unpaid` | `urged_at IS NOT NULL AND status='pending_payment'` | 已催付未处理 |

### 二、前端：仪表盘待办面板

在 `DashboardView.vue` 的 `todoItemDefs` 新增 3 项：

| key | label | 跳转路由 | 权限 |
|-----|-------|---------|------|
| `ds_pending_payment` | 代采代发待付款 | `/dropship` | `dropship` |
| `ds_paid_pending_ship` | 代采代发待发货 | `/dropship` | `dropship` |
| `ds_urged_unpaid` | 代采代发催付未处理 | `/dropship` | `dropship` |

count > 0 且有权限才显示，点击跳转。

### 三、前端：侧边栏 badge

`Sidebar.vue` badge 映射新增：

```
dropship → ds_pending_payment + ds_paid_pending_ship + ds_urged_unpaid
```

三类总和，超过 99 显示 "99+"。

### 四、前端：订单列表 UI 调整

`DropshipOrdersPanel.vue`：

1. **去掉**橙色「催」字 badge
2. **新增** `.todo-dot` 红点在订单号前面
3. 显示条件：`['pending_payment', 'paid_pending_ship'].includes(order.status)`
4. 付款+发货完成后红点自然消失（状态不再匹配）

### 不做的事

- 不新建 Notification 模型（现有 todo-counts 模式够用）
- 不引入 WebSocket（30s 轮询对此场景足够）
- 不改变催付款的后端逻辑（仍然只写 `urged_at` 时间戳）
