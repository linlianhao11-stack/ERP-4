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
