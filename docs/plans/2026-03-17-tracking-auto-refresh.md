# 物流状态自动刷新 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现后端定时轮询快递100 API，自动更新 DropshipOrder 和 Shipment 的物流状态，并联动更新 Order 状态。

**Architecture:** 新增 `tracking_refresh_service.py` 后台 asyncio 循环（与 `auto_backup_loop` 同模式），每 60 秒唤醒，根据发货天数分级刷新。覆盖 DropshipOrder、Shipment 两个模型，Shipment 签收后联动更新 Order.shipping_status 为 `delivered`。

**Tech Stack:** Python 3.9 + FastAPI + Tortoise ORM + asyncio + httpx（快递100 API）

**Design Doc:** `docs/plans/2026-03-17-tracking-auto-refresh-design.md`

---

### Task 1: 数据库迁移 — 新增 last_tracking_refresh 字段

**Files:**
- Modify: `backend/app/models/dropship.py:48` — 新增字段
- Modify: `backend/app/models/shipment.py:17` — 新增字段
- Modify: `backend/app/migrations.py:44` — 注册迁移函数，在 `_run_migrations_inner` 末尾添加调用

**Step 1: 在 DropshipOrder 模型添加字段**

在 `backend/app/models/dropship.py` 的 `shipped_at` 字段后面添加：

```python
    last_tracking_refresh = fields.DatetimeField(null=True)
```

**Step 2: 在 Shipment 模型添加字段**

在 `backend/app/models/shipment.py` 的 `kd100_subscribed` 字段（第15行）后面添加：

```python
    last_tracking_refresh = fields.DatetimeField(null=True)
```

**Step 3: 添加迁移函数**

在 `backend/app/migrations.py` 文件末尾添加：

```python
async def migrate_tracking_refresh_fields():
    """为 dropship_orders 和 shipments 添加 last_tracking_refresh 字段（幂等）"""
    conn = connections.get("default")
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE dropship_orders ADD COLUMN last_tracking_refresh TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE shipments ADD COLUMN last_tracking_refresh TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    logger.info("迁移: last_tracking_refresh 字段已添加")
```

**Step 4: 注册迁移**

在 `_run_migrations_inner()` 函数中，`migrate_stock_last_activity()` 调用之后添加：

```python
    await migrate_tracking_refresh_fields()
```

**Step 5: 提交**

```bash
git add backend/app/models/dropship.py backend/app/models/shipment.py backend/app/migrations.py
git commit -m "feat(物流): 新增 last_tracking_refresh 字段用于分级刷新"
```

---

### Task 2: 创建 tracking_refresh_service.py 核心服务

**Files:**
- Create: `backend/app/services/tracking_refresh_service.py`

**Step 1: 创建服务文件**

创建 `backend/app/services/tracking_refresh_service.py`，完整内容：

```python
"""物流状态自动刷新服务 — 智能分级轮询快递100"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

from tortoise.expressions import Q

from app.logger import get_logger
from app.services.logistics_service import query_kd100, parse_kd100_state, _get_kd100_config

logger = get_logger("tracking_refresh")

# 分级刷新策略：(最大天数, 刷新间隔小时数)
REFRESH_TIERS = [
    (1, 2),     # 0-1 天: 每 2 小时
    (5, 4),     # 2-5 天: 每 4 小时
    (15, 8),    # 6-15 天: 每 8 小时
    (30, 24),   # 16-30 天: 每 24 小时
]
MAX_TRACKING_DAYS = 30  # 超过 30 天停止轮询

# 单轮上限
MAX_DROPSHIP_PER_ROUND = 25
MAX_SHIPMENT_PER_ROUND = 25

# 查询间延迟（秒）
QUERY_DELAY = 1.5


def _get_refresh_interval(shipped_at: datetime) -> timedelta | None:
    """根据发货天数返回刷新间隔，超过 MAX_TRACKING_DAYS 返回 None（停止轮询）"""
    days = (datetime.now(shipped_at.tzinfo) - shipped_at).days
    if days > MAX_TRACKING_DAYS:
        return None
    for max_days, hours in REFRESH_TIERS:
        if days <= max_days:
            return timedelta(hours=hours)
    # 16-30 天区间
    return timedelta(hours=24)


def _needs_refresh(shipped_at: datetime, last_refresh: datetime | None) -> bool:
    """判断该订单是否需要刷新"""
    interval = _get_refresh_interval(shipped_at)
    if interval is None:
        return False  # 超期，停止轮询
    if last_refresh is None:
        return True   # 从未刷新过
    now = datetime.now(last_refresh.tzinfo) if last_refresh.tzinfo else datetime.now()
    return (now - last_refresh) >= interval


async def _refresh_dropship_orders() -> dict:
    """刷新代采代发订单物流状态，返回统计"""
    from app.models.dropship import DropshipOrder

    stats = {"total": 0, "success": 0, "signed": 0, "failed": 0}

    orders = await DropshipOrder.filter(
        status="shipped",
        tracking_no__isnull=False,
        carrier_code__isnull=False,
    ).order_by("last_tracking_refresh").limit(MAX_DROPSHIP_PER_ROUND * 2)

    refreshed = 0
    for order in orders:
        if refreshed >= MAX_DROPSHIP_PER_ROUND:
            break
        shipped_at = order.shipped_at or order.created_at
        if not _needs_refresh(shipped_at, order.last_tracking_refresh):
            continue

        stats["total"] += 1
        try:
            resp = await query_kd100(order.carrier_code, order.tracking_no, phone=order.phone)
            now = datetime.now(shipped_at.tzinfo) if shipped_at.tzinfo else datetime.now()
            order.last_tracking_refresh = now

            if resp.get("message") == "ok" and resp.get("data"):
                order.last_tracking_info = json.dumps(resp, ensure_ascii=False)
                if str(resp.get("ischeck")) == "1":
                    if order.status == "shipped":
                        order.status = "completed"
                        stats["signed"] += 1
                        logger.info(f"自动刷新: {order.ds_no} 已签收，状态更新为 completed")
                stats["success"] += 1

            await order.save()
            refreshed += 1
            await asyncio.sleep(QUERY_DELAY)
        except Exception as e:
            stats["failed"] += 1
            logger.warning(f"自动刷新失败: {order.ds_no}, 错误: {e}")

    return stats


async def _refresh_shipments() -> dict:
    """刷新普通物流 Shipment 状态，联动更新 Order，返回统计"""
    from app.models.shipment import Shipment
    from app.models.order import Order

    stats = {"total": 0, "success": 0, "signed": 0, "delivered": 0, "failed": 0}

    shipments = await Shipment.filter(
        ~Q(status__in=["signed", "pending"]),
        tracking_no__isnull=False,
        carrier_code__isnull=False,
    ).order_by("last_tracking_refresh").limit(MAX_SHIPMENT_PER_ROUND * 2)

    refreshed = 0
    for shipment in shipments:
        if refreshed >= MAX_SHIPMENT_PER_ROUND:
            break
        shipped_at = shipment.created_at
        if not _needs_refresh(shipped_at, shipment.last_tracking_refresh):
            continue

        stats["total"] += 1
        try:
            resp = await query_kd100(
                shipment.carrier_code, shipment.tracking_no,
                phone=shipment.phone
            )
            now = datetime.now(shipped_at.tzinfo) if shipped_at.tzinfo else datetime.now()
            shipment.last_tracking_refresh = now

            if resp.get("message") == "ok" and resp.get("data"):
                tracking_data = resp["data"]
                state = str(resp.get("state", ""))
                if str(resp.get("ischeck")) == "1":
                    shipment.status = "signed"
                    shipment.status_text = "已签收"
                    stats["signed"] += 1
                    logger.info(f"自动刷新: Shipment#{shipment.id} 已签收")
                else:
                    status_info = parse_kd100_state(state)
                    shipment.status = status_info[0]
                    shipment.status_text = status_info[1]
                shipment.last_tracking_info = json.dumps(tracking_data, ensure_ascii=False)
                stats["success"] += 1

            await shipment.save()

            # 签收后检查 Order 联动
            if shipment.status == "signed":
                delivered = await _check_order_delivered(shipment.order_id)
                if delivered:
                    stats["delivered"] += 1

            refreshed += 1
            await asyncio.sleep(QUERY_DELAY)
        except Exception as e:
            stats["failed"] += 1
            logger.warning(f"自动刷新失败: Shipment#{shipment.id}, 错误: {e}")

    return stats


async def _check_order_delivered(order_id: int) -> bool:
    """检查 Order 下所有 Shipment 是否全部签收，是则更新 shipping_status 为 delivered"""
    from app.models.shipment import Shipment
    from app.models.order import Order

    order = await Order.filter(id=order_id).first()
    if not order or order.shipping_status != "completed":
        return False

    all_shipments = await Shipment.filter(order_id=order_id).all()
    if not all_shipments:
        return False

    all_signed = all(s.status == "signed" for s in all_shipments)
    if all_signed:
        order.shipping_status = "delivered"
        await order.save()
        logger.info(f"自动刷新: 订单#{order_id} 所有包裹已签收，shipping_status 更新为 delivered")
        return True
    return False


async def tracking_refresh_loop():
    """物流状态自动刷新定时循环。
    每 60 秒唤醒一次，检查是否有需要刷新的订单。
    使用短间隔轮询 + 分级策略，休眠后也能快速恢复。
    """
    logger.info("物流自动刷新循环已启动")
    while True:
        await asyncio.sleep(60)
        try:
            # 检查 KD100 是否配置
            key, customer = await _get_kd100_config()
            if not key or not customer:
                continue  # 未配置，跳过本轮

            ds_stats = await _refresh_dropship_orders()
            ship_stats = await _refresh_shipments()

            total = ds_stats["total"] + ship_stats["total"]
            if total > 0:
                logger.info(
                    f"物流自动刷新完成: "
                    f"代采代发({ds_stats['total']}查/{ds_stats['success']}成功/{ds_stats['signed']}签收/{ds_stats['failed']}失败) "
                    f"普通物流({ship_stats['total']}查/{ship_stats['success']}成功/{ship_stats['signed']}签收/{ship_stats['delivered']}送达/{ship_stats['failed']}失败)"
                )
        except Exception as e:
            logger.error("物流自动刷新循环异常", exc_info=e)
```

**Step 2: 提交**

```bash
git add backend/app/services/tracking_refresh_service.py
git commit -m "feat(物流): 新增 tracking_refresh_service 智能分级轮询服务"
```

---

### Task 3: 在 main.py 中注册后台任务

**Files:**
- Modify: `backend/main.py:16-17` — 新增 import
- Modify: `backend/main.py:92-116` — lifespan 中启动和停止任务

**Step 1: 添加 import**

在 `backend/main.py` 第 16 行 `from app.services.backup_service import auto_backup_loop` 后面添加：

```python
from app.services.tracking_refresh_service import tracking_refresh_loop
```

**Step 2: 在 lifespan 中启动任务**

在 `lifespan` 函数中，第 100 行 `backup_task = asyncio.create_task(auto_backup_loop())` 后面添加：

```python
    tracking_task = asyncio.create_task(tracking_refresh_loop())
```

**Step 3: 在 lifespan 关闭时取消任务**

在第 103 行 `backup_task.cancel()` 后面添加：

```python
    tracking_task.cancel()
```

在第 107 行 `except asyncio.CancelledError: pass` 后面添加：

```python
    try:
        await tracking_task
    except asyncio.CancelledError:
        pass
```

最终 lifespan 函数应变为：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    await init_db()
    await run_migrations()
    await _migrate_ai_permissions()
    await _migrate_dropship_permissions()
    # 启动后台任务
    backup_task = asyncio.create_task(auto_backup_loop())
    tracking_task = asyncio.create_task(tracking_refresh_loop())
    yield
    # 关闭
    backup_task.cancel()
    tracking_task.cancel()
    try:
        await backup_task
    except asyncio.CancelledError:
        pass
    try:
        await tracking_task
    except asyncio.CancelledError:
        pass
    # 关闭 AI 资源
    try:
        from app.services.ai_chat_service import close_ai_pool
        from app.ai.deepseek_client import close_client
        await close_ai_pool()
        await close_client()
    except Exception:
        pass
    await close_db()
```

**Step 4: 提交**

```bash
git add backend/main.py
git commit -m "feat(物流): 在 lifespan 中注册物流自动刷新后台任务"
```

---

### Task 4: 验证

**Step 1: 确认 Python 语法无误**

```bash
cd backend && python -c "from app.services.tracking_refresh_service import tracking_refresh_loop; print('import OK')"
```

Expected: `import OK`

**Step 2: 确认前端构建通过（无前端变更，快速确认）**

```bash
cd frontend && npm run build
```

Expected: 构建成功

**Step 3: 启动服务确认日志**

启动后端服务，观察日志中出现 `物流自动刷新循环已启动`。

```bash
cd backend && timeout 10 python -c "
import asyncio
from app.services.tracking_refresh_service import _get_refresh_interval, _needs_refresh
from datetime import datetime, timedelta

# 测试分级策略
now = datetime.now()
assert _get_refresh_interval(now) == timedelta(hours=2), '0天应为2小时'
assert _get_refresh_interval(now - timedelta(days=3)) == timedelta(hours=4), '3天应为4小时'
assert _get_refresh_interval(now - timedelta(days=10)) == timedelta(hours=8), '10天应为8小时'
assert _get_refresh_interval(now - timedelta(days=20)) == timedelta(hours=24), '20天应为24小时'
assert _get_refresh_interval(now - timedelta(days=35)) is None, '35天应停止'

# 测试 needs_refresh
assert _needs_refresh(now, None) == True, '从未刷新应返回True'
assert _needs_refresh(now, now) == False, '刚刷新应返回False'
assert _needs_refresh(now, now - timedelta(hours=3)) == True, '超过间隔应返回True'

print('所有分级策略测试通过')
" 2>/dev/null
```

Expected: `所有分级策略测试通过`

**Step 4: 最终提交（如有修复）**

如果验证中发现问题，修复后提交。
