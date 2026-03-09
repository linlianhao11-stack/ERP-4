"""物流管理路由"""
import json
import hashlib
from collections import OrderedDict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from tortoise import transactions
from tortoise.expressions import F

from app.auth.dependencies import get_current_user, require_permission
from app.config import CARRIER_LIST, KD100_KEY, KD100_CUSTOMER
from app.models import (
    User, Order, OrderItem, Shipment, ShipmentItem, SnCode, SnConfig, WarehouseStock, StockLog
)
from app.schemas.logistics import ShipmentUpdate, SNCodeUpdate, ShipRequest
from app.services.logistics_service import (
    subscribe_kd100, refresh_shipment_tracking, parse_kd100_state
)
from app.services.sn_service import validate_and_consume_sn_codes
from app.services.stock_service import get_or_create_consignment_warehouse, update_weighted_entry_date
from app.logger import get_logger

logger = get_logger("logistics")

router = APIRouter(prefix="/api/logistics", tags=["物流管理"])


def _shipment_to_dict(s, tracking_info=None):
    """Shipment 对象转字典"""
    ti = tracking_info
    if ti is None and s.last_tracking_info:
        try:
            ti = json.loads(s.last_tracking_info)
        except Exception:
            ti = []
    ti = ti or []
    return {
        "id": s.id,
        "order_id": s.order_id,
        "carrier_code": s.carrier_code,
        "carrier_name": s.carrier_name,
        "tracking_no": s.tracking_no,
        "phone": s.phone,
        "status": s.status,
        "status_text": s.status_text,
        "kd100_subscribed": s.kd100_subscribed,
        "sn_code": s.sn_code,
        "last_info": ti[0].get("context", "") if ti else None,
        "tracking_info": ti,
        "updated_at": s.updated_at.isoformat()
    }


@router.get("/carriers")
async def get_carriers(user: User = Depends(require_permission("logistics", "sales"))):
    return CARRIER_LIST


@router.get("/pending-orders")
async def list_pending_orders(offset: int = 0, limit: int = 50, user: User = Depends(require_permission("logistics", "sales"))):
    """获取待发货/部分发货的订单列表"""
    limit = min(limit, 500)
    base_query = Order.filter(
        shipping_status__in=["pending", "partial"],
        order_type__in=["CASH", "CREDIT", "CONSIGN_OUT"]
    )
    total = await base_query.count()
    orders = await base_query.order_by("-created_at").offset(offset).limit(limit).select_related("customer", "warehouse")

    if not orders:
        return {"items": [], "total": total}

    # 批量查询所有订单的 OrderItem（消除 N+1）
    order_ids = [o.id for o in orders]
    all_items = await OrderItem.filter(order_id__in=order_ids).select_related("product").all()
    items_by_order = {}
    for i in all_items:
        items_by_order.setdefault(i.order_id, []).append(i)

    result = []
    for o in orders:
        items = items_by_order.get(o.id, [])
        result.append({
            "id": o.id,
            "order_no": o.order_no,
            "order_type": o.order_type,
            "customer_name": o.customer.name if o.customer else None,
            "total_amount": float(o.total_amount),
            "shipping_status": o.shipping_status,
            "remark": o.remark,
            "created_at": o.created_at.isoformat(),
            "items": [{
                "id": i.id,
                "product_id": i.product_id,
                "product_name": i.product.name,
                "product_sku": i.product.sku,
                "quantity": abs(i.quantity),
                "shipped_qty": i.shipped_qty,
                "remaining_qty": abs(i.quantity) - i.shipped_qty,
                "unit_price": float(i.unit_price)
            } for i in items]
        })
    return {"items": result, "total": total}


@router.get("")
async def list_shipments(status: Optional[str] = None, search: Optional[str] = None, shipping_status: Optional[str] = None, offset: int = 0, limit: int = 50, user: User = Depends(require_permission("logistics", "sales"))):
    """物流列表 - 按订单分组"""
    # 数据库级预筛选（减少加载量）
    query = Shipment.all()
    if shipping_status:
        matching_orders = await Order.filter(shipping_status=shipping_status).values_list("id", flat=True)
        if not matching_orders:
            return []
        query = query.filter(order_id__in=matching_orders)
    if status:
        if status == 'pending':
            # "待发货" tab: 查找 shipping_status 为 pending/partial 的订单
            matching_order_ids = list(
                await Order.filter(
                    shipping_status__in=["pending", "partial"],
                    order_type__in=["CASH", "CREDIT", "CONSIGN_OUT"]
                ).values_list("id", flat=True)
            )
            if matching_order_ids:
                query = query.filter(order_id__in=matching_order_ids)
            else:
                query = query.filter(id=-1)  # 无匹配，返回空
        else:
            # 其他物流状态 tab: 按 Shipment.status 过滤
            matching_order_ids = await Shipment.filter(status=status).distinct().values_list("order_id", flat=True)
            if not matching_order_ids:
                return []
            query = query.filter(order_id__in=matching_order_ids)

    all_shipments = await query.order_by("id").select_related("order", "order__customer")

    order_map = OrderedDict()
    for s in all_shipments:
        oid = s.order_id
        if oid not in order_map:
            order_map[oid] = []
        order_map[oid].append(s)

    result = []
    for oid, slist in order_map.items():
        order = slist[0].order
        first = slist[0]

        if status and status != 'pending' and first.status != status:
            continue

        if search:
            keywords = search.lower().split()
            fields = [
                (order.order_no or "").lower(),
                (order.customer.name if order.customer else "").lower(),
            ] + [(s.tracking_no or "").lower() for s in slist] + [(s.carrier_name or "").lower() for s in slist]
            combined = " ".join(fields)
            combined_nospace = combined.replace(" ", "")
            if not all(w in combined or w in combined_nospace for w in keywords):
                continue

        last_info = None
        if first.last_tracking_info:
            try:
                info_list = json.loads(first.last_tracking_info)
                if info_list:
                    last_info = info_list[0].get("context", "") or info_list[0].get("desc", "")
            except Exception:
                pass

        all_tracking = []
        for s in slist:
            if s.tracking_no:
                all_tracking.append({
                    "carrier_name": s.carrier_name or "",
                    "tracking_no": s.tracking_no,
                    "sn_code": s.sn_code or ""
                })

        result.append({
            "order_id": order.id,
            "order_no": order.order_no,
            "order_type": order.order_type,
            "customer_name": order.customer.name if order.customer else None,
            "total_amount": float(order.total_amount),
            "shipping_status": order.shipping_status if hasattr(order, 'shipping_status') else "completed",
            "carrier_name": first.carrier_name,
            "tracking_no": first.tracking_no,
            "status": first.status,
            "status_text": first.status_text,
            "last_info": last_info,
            "shipment_count": len(slist),
            "all_tracking": all_tracking,
            "sn_status": "已添加" if any(s.sn_code for s in slist) else "未添加",
            "created_at": order.created_at.isoformat(),
            "updated_at": first.updated_at.isoformat()
        })

    # 补充没有 Shipment 记录的待发货订单（全部 或 待发货 tab）
    if not status or status == 'pending':
        existing_order_ids = set(order_map.keys())
        pending_query = Order.filter(
            shipping_status__in=["pending", "partial"],
            order_type__in=["CASH", "CREDIT", "CONSIGN_OUT"]
        ).select_related("customer")
        if existing_order_ids:
            pending_query = pending_query.exclude(id__in=list(existing_order_ids))
        pending_orders = await pending_query.order_by("-created_at").limit(200)

        for o in pending_orders:
            if search:
                keywords = search.lower().split()
                fields = [
                    (o.order_no or "").lower(),
                    (o.customer.name if o.customer else "").lower(),
                ]
                combined = " ".join(fields)
                combined_nospace = combined.replace(" ", "")
                if not all(w in combined or w in combined_nospace for w in keywords):
                    continue

            result.append({
                "order_id": o.id,
                "order_no": o.order_no,
                "order_type": o.order_type,
                "customer_name": o.customer.name if o.customer else None,
                "total_amount": float(o.total_amount),
                "shipping_status": o.shipping_status,
                "carrier_name": None,
                "tracking_no": None,
                "status": "pending",
                "status_text": "待发货",
                "last_info": None,
                "shipment_count": 0,
                "all_tracking": [],
                "sn_status": "未添加",
                "created_at": o.created_at.isoformat(),
                "updated_at": o.created_at.isoformat()
            })

    result.sort(key=lambda x: x["updated_at"], reverse=True)
    total = len(result)
    limit = min(limit, 500)
    return {"items": result[offset:offset + limit], "total": total}


@router.get("/{order_id}")
async def get_shipment_detail(order_id: int, user: User = Depends(require_permission("logistics", "sales"))):
    order = await Order.filter(id=order_id).select_related("customer", "warehouse", "creator", "salesperson").first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    items = await OrderItem.filter(order_id=order_id).select_related("product", "warehouse", "location")
    shipment_list = await Shipment.filter(order_id=order_id).order_by("id").all()

    # 批量查询 ShipmentItem（消除 N+1）
    shipment_ids = [s.id for s in shipment_list]
    all_si = await ShipmentItem.filter(shipment_id__in=shipment_ids).select_related("product").all() if shipment_ids else []
    si_by_shipment = {}
    for si in all_si:
        si_by_shipment.setdefault(si.shipment_id, []).append(si)

    # 批量预加载 SN 配置，判断每个商品是否需要 SN 码
    wh_ids = set()
    for i in items:
        wh = i.warehouse if i.warehouse_id else order.warehouse
        if wh:
            wh_ids.add(wh.id)
    sn_configs = await SnConfig.filter(warehouse_id__in=list(wh_ids), is_active=True).all() if wh_ids else []
    sn_config_set = {(sc.warehouse_id, sc.brand) for sc in sn_configs}

    shipments_data = []
    for s in shipment_list:
        sd = _shipment_to_dict(s)
        si_list = si_by_shipment.get(s.id, [])
        sd["items"] = [{
            "product_name": si.product.name,
            "product_sku": si.product.sku,
            "quantity": si.quantity,
            "sn_codes": si.sn_codes
        } for si in si_list]
        shipments_data.append(sd)

    items_data = []
    for i in items:
        wh = i.warehouse if i.warehouse_id else order.warehouse
        product_brand = i.product.brand if i.product else None
        sn_required = bool(product_brand and wh and (wh.id, product_brand) in sn_config_set)
        items_data.append({
            "id": i.id,
            "shipped_qty": i.shipped_qty,
            "remaining_qty": abs(i.quantity) - i.shipped_qty,
            "product_name": i.product.name,
            "product_sku": i.product.sku,
            "product_id": i.product_id,
            "warehouse_id": wh.id if wh else None,
            "quantity": i.quantity,
            "unit_price": float(i.unit_price),
            "amount": float(i.amount),
            "sn_required": sn_required,
        })

    return {
        "order": {
            "id": order.id,
            "order_no": order.order_no,
            "order_type": order.order_type,
            "customer_name": order.customer.name if order.customer else None,
            "total_amount": float(order.total_amount),
            "shipping_status": order.shipping_status,
            "salesperson_name": order.salesperson.name if order.salesperson else None,
            "creator_name": order.creator.display_name if order.creator else None,
            "created_at": order.created_at.isoformat(),
            "remark": order.remark,
            "items": items_data
        },
        "shipments": shipments_data
    }


@router.post("/{order_id}/ship")
async def ship_order_items(order_id: int, data: ShipRequest, user: User = Depends(require_permission("logistics", "sales"))):
    """发货操作：选择商品和数量，创建物流单并扣减库存"""
    order = await Order.filter(id=order_id).select_related("customer", "warehouse").first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.shipping_status not in ("pending", "partial"):
        raise HTTPException(status_code=400, detail="该订单不在待发货状态")
    if order.order_type not in ("CASH", "CREDIT", "CONSIGN_OUT"):
        raise HTTPException(status_code=400, detail="该订单类型不支持发货操作")
    if not data.items:
        raise HTTPException(status_code=400, detail="请选择要发货的商品")

    is_self_pickup = data.is_self_pickup or data.carrier_code == "self_pickup"
    if not is_self_pickup and not data.tracking_no:
        raise HTTPException(status_code=400, detail="请填写快递单号")

    async with transactions.in_transaction():
        shipment = await Shipment.create(
            order=order,
            carrier_code=data.carrier_code,
            carrier_name=data.carrier_name,
            tracking_no=data.tracking_no or None,
            phone=data.phone or None,
            status="signed" if is_self_pickup else "shipped",
            status_text="已自提" if is_self_pickup else "已发货"
        )

        consignment_wh = None
        if order.order_type == "CONSIGN_OUT" and order.customer_id:
            consignment_wh = await get_or_create_consignment_warehouse(order.customer_id)

        all_sn_display = []

        # --- 批量预加载只读数据，消除 N+1 ---
        oi_ids = [si.order_item_id for si in data.items]
        ois = await OrderItem.filter(id__in=oi_ids, order_id=order_id).select_related("product", "warehouse", "location").all()
        oi_map = {o.id: o for o in ois}

        # 批量预加载 SN 配置
        wh_ids = set()
        for si in data.items:
            oi = oi_map.get(si.order_item_id)
            if oi:
                wh = oi.warehouse if oi.warehouse_id else order.warehouse
                if wh:
                    wh_ids.add(wh.id)
        sn_configs = await SnConfig.filter(warehouse_id__in=list(wh_ids), is_active=True).all() if wh_ids else []
        sn_config_set = {(sc.warehouse_id, sc.brand) for sc in sn_configs}
        # --- 预加载结束 ---

        for ship_item in data.items:
            oi = oi_map.get(ship_item.order_item_id)
            if not oi:
                raise HTTPException(status_code=404, detail=f"订单项不存在: {ship_item.order_item_id}")

            remaining = abs(oi.quantity) - oi.shipped_qty
            if ship_item.quantity <= 0:
                raise HTTPException(status_code=400, detail=f"商品 {oi.product.name} 发货数量必须大于0")
            if ship_item.quantity > remaining:
                raise HTTPException(status_code=400, detail=f"商品 {oi.product.name} 剩余未发 {remaining}，不能发 {ship_item.quantity}")

            wh = oi.warehouse if oi.warehouse_id else order.warehouse
            loc = oi.location
            if not wh or not loc:
                raise HTTPException(status_code=400, detail=f"商品 {oi.product.name} 没有仓库/仓位信息")

            # SN 检查：用预加载的 sn_config_set 替代逐条查询
            product_brand = oi.product.brand if oi.product else None
            sn_required = bool(product_brand and (wh.id, product_brand) in sn_config_set)
            if sn_required and (not ship_item.sn_codes or len(ship_item.sn_codes) != ship_item.quantity):
                raise HTTPException(status_code=400, detail=f"商品 {oi.product.name} 需要提供 {ship_item.quantity} 个SN码")

            stock = await WarehouseStock.filter(
                warehouse_id=wh.id, product_id=oi.product_id, location_id=loc.id
            ).select_for_update().first()
            if not stock or stock.quantity < ship_item.quantity:
                raise HTTPException(status_code=400, detail=f"商品 {oi.product.name} 库存不足")

            before_qty = stock.quantity
            await WarehouseStock.filter(id=stock.id).update(
                quantity=F('quantity') - ship_item.quantity,
                reserved_qty=F('reserved_qty') - ship_item.quantity
            )

            change_type = "CONSIGN_OUT" if order.order_type == "CONSIGN_OUT" else "SALE"
            await StockLog.create(
                product_id=oi.product_id, warehouse=wh, change_type=change_type,
                quantity=-ship_item.quantity,
                before_qty=before_qty, after_qty=before_qty - ship_item.quantity,
                reference_type="ORDER", reference_id=order.id, creator=user
            )

            if order.order_type == "CONSIGN_OUT" and consignment_wh:
                await update_weighted_entry_date(consignment_wh.id, oi.product_id, ship_item.quantity)
                v_stock = await WarehouseStock.filter(warehouse_id=consignment_wh.id, product_id=oi.product_id).first()
                await StockLog.create(
                    product_id=oi.product_id, warehouse=consignment_wh, change_type="CONSIGN_OUT",
                    quantity=ship_item.quantity,
                    before_qty=v_stock.quantity - ship_item.quantity, after_qty=v_stock.quantity,
                    reference_type="ORDER", reference_id=order.id, creator=user
                )

            await OrderItem.filter(id=oi.id).update(shipped_qty=F('shipped_qty') + ship_item.quantity)

            sn_codes_json = json.dumps(ship_item.sn_codes) if ship_item.sn_codes else None
            await ShipmentItem.create(
                shipment=shipment, order_item_id=oi.id,
                product_id=oi.product_id, quantity=ship_item.quantity,
                sn_codes=sn_codes_json
            )

            if ship_item.sn_codes:
                await validate_and_consume_sn_codes(ship_item.sn_codes, shipment, user)
                all_sn_display.extend(ship_item.sn_codes)

        if all_sn_display:
            shipment.sn_code = ", ".join(all_sn_display)
            await shipment.save()

        all_items = await OrderItem.filter(order_id=order_id).all()
        all_shipped = all(abs(item.quantity) <= item.shipped_qty for item in all_items)
        order.shipping_status = "completed" if all_shipped else "partial"
        await order.save()

    # 钩子放在事务外部：钩子失败不会回滚核心发货操作
    if order.shipping_status == "completed" and getattr(order, "account_set_id", None):
        # 钩子：发货完成 → 自动生成应收单
        try:
            from app.services.ar_service import create_receivable_bill, create_receipt_bill_for_payment
            from app.models import Payment

            if order.order_type in ("CASH", "CREDIT", "CONSIGN_SETTLE"):
                total = abs(order.total_amount)
                if order.order_type == "CASH":
                    rb = await create_receivable_bill(
                        account_set_id=order.account_set_id,
                        customer_id=order.customer_id,
                        order_id=order.id,
                        total_amount=total,
                        status="completed",
                        creator=user,
                    )
                    payment = await Payment.filter(order_id=order.id).first()
                    if payment:
                        await create_receipt_bill_for_payment(
                            account_set_id=order.account_set_id,
                            customer_id=order.customer_id,
                            receivable_bill=rb,
                            payment_id=payment.id,
                            amount=total,
                            payment_method=payment.payment_method or "现金",
                            creator=user,
                        )
                else:  # CREDIT / CONSIGN_SETTLE
                    await create_receivable_bill(
                        account_set_id=order.account_set_id,
                        customer_id=order.customer_id,
                        order_id=order.id,
                        total_amount=total,
                        status="pending",
                        creator=user,
                    )
        except Exception as e:
            logger.warning(f"自动生成应收单失败: {e}")

        # 钩子：发货完成 → 自动生成出库单
        try:
            from app.services.delivery_service import create_sales_delivery
            from app.models import Product
            # 重新查询 all_items（事务已提交，需要最新数据）
            all_items = await OrderItem.filter(order_id=order_id).all()
            prod_ids = {oi.product_id for oi in all_items if oi.shipped_qty > 0}
            products_map = {p.id: p for p in await Product.filter(id__in=list(prod_ids)).all()} if prod_ids else {}
            shipped_items = []
            for oi in all_items:
                if oi.shipped_qty > 0:
                    product = products_map.get(oi.product_id)
                    shipped_items.append({
                        "order_item_id": oi.id,
                        "product_id": oi.product_id,
                        "product_name": product.name if product else str(oi.product_id),
                        "quantity": oi.shipped_qty,
                        "cost_price": str(oi.cost_price),
                        "sale_price": str(oi.unit_price),
                    })
            if shipped_items:
                await create_sales_delivery(
                    account_set_id=order.account_set_id,
                    customer_id=order.customer_id,
                    order_id=order.id,
                    warehouse_id=order.warehouse_id,
                    items=shipped_items,
                    creator=user,
                )
        except Exception as e:
            logger.warning(f"自动生成出库单失败: {e}")

    if not is_self_pickup and data.tracking_no:
        try:
            await refresh_shipment_tracking(shipment)
        except Exception as e:
            logger.warning("刷新物流跟踪失败", extra={"data": {"shipment_id": shipment.id, "error": str(e)}})
        try:
            resp = await subscribe_kd100(data.carrier_code, data.tracking_no, order_id, shipment.id, phone=shipment.phone)
            if resp.get("returnCode") == "200" or resp.get("result") is True:
                shipment.kd100_subscribed = True
                await shipment.save()
        except Exception as e:
            logger.warning("订阅快递100失败", extra={"data": {"shipment_id": shipment.id, "error": str(e)}})

    return {
        "message": "已标记自提完成" if is_self_pickup else "发货成功",
        "shipment": _shipment_to_dict(shipment),
        "shipping_status": order.shipping_status
    }


@router.post("/{order_id}/add")
async def add_shipment(order_id: int, data: ShipmentUpdate, user: User = Depends(require_permission("logistics", "sales"))):
    """为订单添加新物流单"""
    order = await Order.filter(id=order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.order_type not in ("CASH", "CREDIT", "CONSIGN_OUT"):
        raise HTTPException(status_code=400, detail="该订单类型不支持添加物流单")

    is_self_pickup = data.carrier_code == "self_pickup"
    shipment = await Shipment.create(
        order=order,
        carrier_code=data.carrier_code,
        carrier_name=data.carrier_name,
        tracking_no=data.tracking_no or None,
        phone=data.phone or None,
        sn_code=data.sn_code or None,
        status="signed" if is_self_pickup else "shipped",
        status_text="已自提" if is_self_pickup else "已发货"
    )

    if data.sn_codes:
        await validate_and_consume_sn_codes(data.sn_codes, shipment, user, strict=False)

    tracking_info = []
    if not is_self_pickup and data.tracking_no:
        result = await refresh_shipment_tracking(shipment)
        if result:
            tracking_info = result.get("tracking_info", [])

        try:
            resp = await subscribe_kd100(data.carrier_code, data.tracking_no, order_id, shipment.id, phone=shipment.phone)
            if resp.get("returnCode") == "200" or resp.get("result") is True:
                shipment.kd100_subscribed = True
                await shipment.save()
        except Exception:
            pass

    return {"message": "已标记自提完成" if is_self_pickup else "物流单已添加", "shipment": _shipment_to_dict(shipment, tracking_info)}


@router.put("/shipment/{shipment_id}/ship")
async def ship_order(shipment_id: int, data: ShipmentUpdate, user: User = Depends(require_permission("logistics", "sales"))):
    shipment = await Shipment.filter(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="物流记录不存在")

    is_self_pickup = data.carrier_code == "self_pickup"
    tracking_changed = (shipment.tracking_no != data.tracking_no) or (shipment.carrier_code != data.carrier_code)

    shipment.carrier_code = data.carrier_code
    shipment.carrier_name = data.carrier_name
    shipment.tracking_no = data.tracking_no or None
    shipment.phone = data.phone or shipment.phone
    shipment.sn_code = data.sn_code if data.sn_code is not None else shipment.sn_code
    shipment.status = "signed" if is_self_pickup else "shipped"
    shipment.status_text = "已自提" if is_self_pickup else "已发货"

    if tracking_changed:
        shipment.last_tracking_info = None
        shipment.kd100_subscribed = False

    await shipment.save()

    tracking_info = []
    if not is_self_pickup and data.tracking_no and tracking_changed:
        result = await refresh_shipment_tracking(shipment)
        if result:
            tracking_info = result.get("tracking_info", [])

        try:
            resp = await subscribe_kd100(data.carrier_code, data.tracking_no, shipment.order_id, shipment.id, phone=shipment.phone)
            if resp.get("returnCode") == "200" or resp.get("result") is True:
                shipment.kd100_subscribed = True
                await shipment.save()
        except Exception:
            pass

    return {"message": "已标记自提完成" if is_self_pickup else "发货信息已保存", "shipment": _shipment_to_dict(shipment, tracking_info)}


@router.post("/shipment/{shipment_id}/update-sn")
async def update_shipment_sn(shipment_id: int, data: SNCodeUpdate, user: User = Depends(require_permission("logistics", "sales"))):
    """独立更新物流单SN码"""
    shipment = await Shipment.filter(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="物流记录不存在")

    async with transactions.in_transaction():
        old_sn_objs = await SnCode.filter(shipment_id=shipment_id, status="shipped").select_for_update().all()
        for sn_obj in old_sn_objs:
            sn_obj.status = "in_stock"
            sn_obj.shipment = None
            sn_obj.ship_date = None
            sn_obj.ship_user = None
            await sn_obj.save()

        if data.sn_codes:
            await validate_and_consume_sn_codes(data.sn_codes, shipment, user, strict=False)

        shipment.sn_code = data.sn_code or None
        await shipment.save()

    return {"message": "SN码已保存", "shipment": _shipment_to_dict(shipment)}


@router.delete("/shipment/{shipment_id}")
async def delete_shipment(shipment_id: int, user: User = Depends(require_permission("logistics", "sales"))):
    shipment = await Shipment.filter(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="物流记录不存在")

    order = await Order.filter(id=shipment.order_id).select_related("customer", "warehouse").first()

    async with transactions.in_transaction():
        # 回滚已发货数量和库存
        ship_items = await ShipmentItem.filter(shipment_id=shipment_id).all()

        consignment_wh = None
        if order and order.order_type == "CONSIGN_OUT" and order.customer_id:
            consignment_wh = await get_or_create_consignment_warehouse(order.customer_id)

        for si in ship_items:
            # 获取关联的 OrderItem 以找到仓库和仓位信息
            oi = await OrderItem.filter(id=si.order_item_id).select_related("warehouse", "location").first()
            if oi:
                wh = oi.warehouse if oi.warehouse_id else (order.warehouse if order else None)
                loc = oi.location

                if wh and loc:
                    # 恢复源仓库库存
                    stock = await WarehouseStock.filter(
                        warehouse_id=wh.id, product_id=si.product_id, location_id=loc.id
                    ).select_for_update().first()
                    before_qty = stock.quantity if stock else 0

                    if stock:
                        # When deleting a shipment we restore stock to "reserved" state because the
                        # parent order still exists and expects the items to be fulfilled. Therefore
                        # reserved_qty += si.quantity is the intended behaviour.  However, if the
                        # reservation was already released (e.g. order cancelled between ship and
                        # delete), blindly adding could push reserved_qty above quantity. Clamp
                        # the addition so reserved_qty never exceeds the new quantity.
                        new_quantity = stock.quantity + si.quantity
                        safe_reserved_add = min(si.quantity, max(0, new_quantity - stock.reserved_qty))
                        await WarehouseStock.filter(id=stock.id).update(
                            quantity=F('quantity') + si.quantity,
                            reserved_qty=F('reserved_qty') + safe_reserved_add
                        )
                    else:
                        await WarehouseStock.create(
                            warehouse_id=wh.id, product_id=si.product_id,
                            location_id=loc.id, quantity=si.quantity
                        )

                    # 创建库存恢复日志
                    await StockLog.create(
                        product_id=si.product_id, warehouse=wh,
                        change_type="ADJUST",
                        quantity=si.quantity,
                        before_qty=before_qty, after_qty=before_qty + si.quantity,
                        reference_type="ORDER", reference_id=shipment.order_id,
                        remark=f"删除物流单恢复库存",
                        creator=user
                    )

                    # 对于寄售调拨订单，扣减寄售（虚拟）仓库库存
                    if order and order.order_type == "CONSIGN_OUT" and consignment_wh:
                        try:
                            v_stock = await WarehouseStock.filter(
                                warehouse_id=consignment_wh.id, product_id=si.product_id
                            ).select_for_update().first()
                            v_before_qty = v_stock.quantity if v_stock else 0
                            if v_stock and v_stock.quantity >= si.quantity:
                                await WarehouseStock.filter(
                                    id=v_stock.id
                                ).update(quantity=F('quantity') - si.quantity)
                                await StockLog.create(
                                    product_id=si.product_id, warehouse=consignment_wh,
                                    change_type="ADJUST",
                                    quantity=-si.quantity,
                                    before_qty=v_before_qty, after_qty=v_before_qty - si.quantity,
                                    reference_type="ORDER", reference_id=shipment.order_id,
                                    remark=f"删除物流单扣减寄售仓库库存",
                                    creator=user
                                )
                            elif v_stock:
                                logger.warning(
                                    f"寄售库存不足以恢复扣减: product_id={si.product_id}, ",
                                    extra={"data": {"v_qty": v_before_qty, "si_qty": si.quantity}}
                                )
                        except Exception as e:
                            logger.error(
                                f"删除物流单恢复寄售库存失败: product_id={si.product_id}",
                                exc_info=e
                            )

            # 恢复 OrderItem.shipped_qty (CAS-style guard to prevent underflow)
            updated = await OrderItem.filter(
                id=si.order_item_id,
                shipped_qty__gte=si.quantity
            ).update(
                shipped_qty=F('shipped_qty') - si.quantity
            )
            if not updated:
                # Log warning but don't fail - shipped_qty was already 0 or lower
                logger.warning("shipped_qty underflow prevented", extra={"data": {"order_item_id": si.order_item_id}})
            # 恢复 SN 码状态
            sn_objs = await SnCode.filter(shipment_id=shipment_id, product_id=si.product_id, status="shipped").all()
            for sn_obj in sn_objs:
                sn_obj.status = "in_stock"
                sn_obj.shipment = None
                sn_obj.ship_date = None
                sn_obj.ship_user = None
                await sn_obj.save()

        await ShipmentItem.filter(shipment_id=shipment_id).delete()
        await shipment.delete()

        # 更新订单发货状态
        if order:
            all_items = await OrderItem.filter(order_id=order.id).all()
            if all_items:
                all_shipped = all(abs(item.quantity) <= item.shipped_qty for item in all_items)
                any_shipped = any(item.shipped_qty > 0 for item in all_items)
                if all_shipped:
                    order.shipping_status = "completed"
                elif any_shipped:
                    order.shipping_status = "partial"
                else:
                    order.shipping_status = "pending"
                await order.save()

    return {"message": "物流单已删除"}


@router.post("/shipment/{shipment_id}/refresh")
async def refresh_shipment(shipment_id: int, user: User = Depends(require_permission("logistics", "sales"))):
    """实时查询快递100获取最新物流信息"""
    shipment = await Shipment.filter(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="物流记录不存在")
    if not shipment.carrier_code or not shipment.tracking_no:
        raise HTTPException(status_code=400, detail="请先填写快递信息")

    result = await refresh_shipment_tracking(shipment)
    if result:
        return {"message": "物流信息已更新", "shipment": _shipment_to_dict(shipment)}
    raise HTTPException(status_code=400, detail="未查询到物流信息，请检查快递公司和单号是否正确")


@router.post("/kd100/callback")
async def kd100_callback(request: Request, order_id: Optional[int] = None, shipment_id: Optional[int] = None):
    """快递100回调接口"""
    form = await request.form()
    param_str = form.get("param", "")
    sign_received = form.get("sign", "")

    if not KD100_KEY:
        return {"result": False, "returnCode": "500", "message": "快递100未配置"}
    expected_sign = hashlib.md5((param_str + KD100_KEY).encode()).hexdigest().upper()
    if sign_received != expected_sign:
        return {"result": False, "returnCode": "500", "message": "签名验证失败"}

    try:
        param = json.loads(param_str)
        state = str(param.get("state", ""))
        tracking_no = param.get("lastResult", {}).get("nu", "")
        tracking_data = param.get("lastResult", {}).get("data", [])

        shipment = None
        if shipment_id:
            shipment = await Shipment.filter(id=shipment_id).first()
        elif tracking_no:
            shipment = await Shipment.filter(tracking_no=tracking_no).first()
        elif order_id:
            shipment = await Shipment.filter(order_id=order_id).first()

        if shipment:
            # 校验回调的快递单号与 shipment 匹配（防止参数篡改）
            if tracking_no and shipment.tracking_no and tracking_no != shipment.tracking_no:
                logger.warning(f"快递100回调单号不匹配: callback={tracking_no}, shipment={shipment.tracking_no}")
                return {"result": True, "returnCode": "200", "message": "成功"}
            if str(param.get("lastResult", {}).get("ischeck")) == "1":
                shipment.status = "signed"
                shipment.status_text = "已签收"
            else:
                status_info = parse_kd100_state(state)
                shipment.status = status_info[0]
                shipment.status_text = status_info[1]
            shipment.last_tracking_info = json.dumps(tracking_data, ensure_ascii=False)
            await shipment.save()
    except Exception as e:
        logger.warning("快递100回调处理错误", exc_info=e)

    return {"result": True, "returnCode": "200", "message": "成功"}
