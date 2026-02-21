"""采购订单路由"""
import io
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from tortoise import transactions
from tortoise.expressions import F
from tortoise.queryset import Q

from app.auth.dependencies import require_permission
from app.utils.csv import csv_safe
from app.models import (
    User, Product, Warehouse, Location, Supplier,
    PurchaseOrder, PurchaseOrderItem, WarehouseStock, StockLog, RebateLog
)
from app.schemas.purchase import PurchaseOrderCreate, PurchaseReturnRequest, ReceiveRequest, PurchasePayRequest
from app.services.operation_log_service import log_operation
from app.services.stock_service import update_weighted_entry_date, get_product_weighted_cost
from app.services.sn_service import check_sn_required, validate_and_add_sn_codes
from app.utils.generators import generate_order_no
from app.utils.time import now
from app.utils.errors import parse_date

router = APIRouter(prefix="/api/purchase-orders", tags=["采购管理"])


@router.get("")
async def list_purchase_orders(
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_permission("purchase", "purchase_approve", "purchase_pay", "purchase_receive"))
):
    query = PurchaseOrder.all()
    if status:
        query = query.filter(status=status)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))
    if search:
        query = query.filter(Q(po_no__icontains=search) | Q(supplier__name__icontains=search))
    orders = await query.order_by("-created_at").select_related(
        "supplier", "creator", "paid_by", "reviewed_by", "target_warehouse", "target_location")
    return [{
        "id": o.id, "po_no": o.po_no, "supplier_id": o.supplier_id,
        "supplier_name": o.supplier.name if o.supplier else "",
        "status": o.status, "total_amount": float(o.total_amount),
        "return_amount": float(o.return_amount) if o.return_amount else 0,
        "target_warehouse_name": o.target_warehouse.name if o.target_warehouse else None,
        "target_location_code": o.target_location.code if o.target_location else None,
        "remark": o.remark,
        "creator_name": o.creator.display_name if o.creator else None,
        "reviewed_by_name": o.reviewed_by.display_name if o.reviewed_by else None,
        "reviewed_at": o.reviewed_at.isoformat() if o.reviewed_at else None,
        "paid_by_name": o.paid_by.display_name if o.paid_by else None,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "payment_method": o.payment_method,
        "created_at": o.created_at.isoformat(),
    } for o in orders]


@router.get("/export")
async def export_purchase_orders(
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_permission("purchase", "finance"))
):
    """导出采购订单到CSV"""
    query = PurchaseOrder.all()
    if status:
        query = query.filter(status=status)
    if start_date:
        query = query.filter(created_at__gte=parse_date(start_date, "start_date"))
    if end_date:
        query = query.filter(created_at__lte=parse_date(end_date, "end_date") + timedelta(days=1))
    if search:
        query = query.filter(Q(po_no__icontains=search) | Q(supplier__name__icontains=search))
    orders = await query.order_by("-created_at").select_related(
        "supplier", "creator", "paid_by", "reviewed_by", "target_warehouse", "target_location")

    status_names = {
        "pending_review": "待审核", "pending": "待付款", "paid": "在途",
        "partial": "部分到货", "completed": "已完成", "cancelled": "已取消",
        "rejected": "已拒绝", "returned": "已退货"
    }

    output = io.StringIO()
    output.write('\ufeff')
    headers = ["采购单号", "供应商", "状态", "总金额", "目标仓库", "备注", "创建人", "审核人", "审核时间", "付款人", "付款时间", "创建时间",
               "商品SKU", "商品名称", "数量", "含税单价", "税率", "不含税单价", "小计金额", "已收货数量"]
    output.write(','.join(headers) + '\n')

    # 批量查询所有采购明细（避免 N+1）
    po_ids = [o.id for o in orders]
    all_po_items = await PurchaseOrderItem.filter(purchase_order_id__in=po_ids).select_related("product") if po_ids else []
    po_items_by_order = {}
    for item in all_po_items:
        po_items_by_order.setdefault(item.purchase_order_id, []).append(item)

    for o in orders:
        order_base = [
            o.po_no,
            o.supplier.name if o.supplier else "-",
            status_names.get(o.status, o.status),
            f"{float(o.total_amount):.2f}",
            o.target_warehouse.name if o.target_warehouse else "-",
            (o.remark or "").replace('\n', ' '),
            o.creator.display_name if o.creator else "-",
            o.reviewed_by.display_name if o.reviewed_by else "-",
            o.reviewed_at.strftime("%Y-%m-%d %H:%M") if o.reviewed_at else "-",
            o.paid_by.display_name if o.paid_by else "-",
            o.paid_at.strftime("%Y-%m-%d %H:%M") if o.paid_at else "-",
            o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        ]
        items = po_items_by_order.get(o.id, [])
        if items:
            for it in items:
                row = order_base + [
                    it.product.sku if it.product else "-",
                    it.product.name if it.product else "-",
                    str(it.quantity),
                    f"{float(it.tax_inclusive_price):.2f}",
                    f"{float(it.tax_rate * 100):.0f}%",
                    f"{float(it.tax_exclusive_price):.2f}",
                    f"{float(it.amount):.2f}",
                    str(it.received_quantity),
                ]
                output.write(','.join(csv_safe(item) for item in row) + '\n')
        else:
            row = order_base + ["-"] * 8
            output.write(','.join(csv_safe(item) for item in row) + '\n')

    output.seek(0)
    filename = f"采购订单_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    )


@router.post("")
async def create_purchase_order(data: PurchaseOrderCreate, user: User = Depends(require_permission("purchase"))):
    if not data.items:
        raise HTTPException(status_code=400, detail="请添加采购明细")
    supplier = await Supplier.filter(id=data.supplier_id, is_active=True).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    po_no = generate_order_no("PO")
    async with transactions.in_transaction():
        po = await PurchaseOrder.create(
            po_no=po_no, supplier=supplier, status="pending_review",
            target_warehouse_id=data.target_warehouse_id,
            target_location_id=data.target_location_id,
            remark=data.remark, creator=user
        )
        total = Decimal("0")
        total_rebate = Decimal("0")
        for item in data.items:
            product = await Product.filter(id=item.product_id, is_active=True).first()
            if not product:
                raise HTTPException(status_code=404, detail=f"商品ID {item.product_id} 不存在")
            item_rebate = Decimal(str(item.rebate_amount)) if item.rebate_amount else Decimal("0")
            raw_amount = Decimal(str(item.tax_inclusive_price * item.quantity)).quantize(Decimal("0.01"))
            if item_rebate > 0:
                if item_rebate > raw_amount:
                    raise HTTPException(status_code=400, detail=f"商品 {product.name} 返利金额不能超过行金额")
                amount = raw_amount - item_rebate
                total_rebate += item_rebate
            else:
                amount = raw_amount
            if item.quantity == 0:
                raise HTTPException(status_code=400, detail=f"商品 {product.name} 数量不能为0")
            tax_exclusive = (Decimal(str(amount)) / item.quantity / (1 + Decimal(str(item.tax_rate)))).quantize(Decimal("0.01"))
            await PurchaseOrderItem.create(
                purchase_order=po, product=product,
                quantity=item.quantity, tax_inclusive_price=item.tax_inclusive_price,
                tax_rate=item.tax_rate, tax_exclusive_price=tax_exclusive,
                amount=amount, rebate_amount=item_rebate,
                target_warehouse_id=item.target_warehouse_id,
                target_location_id=item.target_location_id
            )
            total += amount
        if total_rebate > 0:
            # Use select_for_update to prevent TOCTOU on supplier rebate balance
            supplier = await Supplier.filter(id=supplier.id).select_for_update().first()
            if supplier.rebate_balance < total_rebate:
                raise HTTPException(status_code=400, detail=f"供应商返利余额不足，可用 ¥{float(supplier.rebate_balance):.2f}，需要 ¥{float(total_rebate):.2f}")
            await Supplier.filter(id=supplier.id).update(rebate_balance=F('rebate_balance') - total_rebate)
            await supplier.refresh_from_db()
            po.rebate_used = total_rebate
            rebate_remark = f"[返利抵扣] 使用返利 ¥{float(total_rebate):.2f}"
            po.remark = f"{po.remark}\n{rebate_remark}" if po.remark else rebate_remark
            await RebateLog.create(
                target_type="supplier", target_id=supplier.id,
                type="use", amount=total_rebate,
                balance_after=supplier.rebate_balance,
                reference_type="PURCHASE_ORDER", reference_id=po.id,
                remark=f"采购单 {po_no} 使用返利", creator=user
            )
        # 在账资金抵扣
        credit_amount = Decimal(str(data.credit_amount)) if data.credit_amount else Decimal("0")
        if credit_amount > 0:
            # Use select_for_update to prevent TOCTOU on supplier credit balance
            supplier = await Supplier.filter(id=supplier.id).select_for_update().first()
            if supplier.credit_balance < credit_amount:
                raise HTTPException(status_code=400, detail=f"供应商在账资金不足，可用 ¥{float(supplier.credit_balance):.2f}，需要 ¥{float(credit_amount):.2f}")
            await Supplier.filter(id=supplier.id).update(credit_balance=F('credit_balance') - credit_amount)
            await supplier.refresh_from_db()
            po.credit_used = credit_amount
            credit_remark = f"[在账资金抵扣] 使用在账资金 ¥{float(credit_amount):.2f}"
            po.remark = f"{po.remark}\n{credit_remark}" if po.remark else credit_remark
            await RebateLog.create(
                target_type="supplier", target_id=supplier.id,
                type="credit_use", amount=-credit_amount,
                balance_after=supplier.credit_balance,
                reference_type="PURCHASE_ORDER", reference_id=po.id,
                remark=f"采购单 {po_no} 使用在账资金", creator=user
            )
        po.total_amount = total
        await po.save()
        await log_operation(user, "PURCHASE_CREATE", "PURCHASE_ORDER", po.id,
            f"创建采购单 {po_no}，供应商 {supplier.name}，金额 ¥{float(total):.2f}" +
            (f"，在账资金抵扣 ¥{float(credit_amount):.2f}" if credit_amount > 0 else ""))
    return {"id": po.id, "po_no": po_no, "message": "采购订单创建成功"}


@router.get("/receivable")
async def list_receivable_orders(user: User = Depends(require_permission("purchase_receive"))):
    orders = await PurchaseOrder.filter(status__in=["paid", "partial"]).order_by("-created_at") \
        .select_related("supplier", "target_warehouse", "target_location")

    # 批量查询所有待收货明细（避免 N+1）
    po_ids = [o.id for o in orders]
    all_items = await PurchaseOrderItem.filter(purchase_order_id__in=po_ids).select_related(
        "product", "target_warehouse", "target_location") if po_ids else []
    items_by_po = {}
    for it in all_items:
        items_by_po.setdefault(it.purchase_order_id, []).append(it)

    result = []
    for o in orders:
        items = items_by_po.get(o.id, [])
        item_list = [{
            "id": it.id, "product_id": it.product_id,
            "product_name": f"{it.product.sku} - {it.product.name}" if it.product else "",
            "quantity": it.quantity, "received_quantity": it.received_quantity,
            "pending_quantity": it.quantity - it.received_quantity,
            "tax_inclusive_price": float(it.tax_inclusive_price),
            "target_warehouse_id": it.target_warehouse_id or o.target_warehouse_id,
            "target_warehouse_name": (it.target_warehouse.name if it.target_warehouse else
                                       o.target_warehouse.name if o.target_warehouse else None),
            "target_location_id": it.target_location_id or o.target_location_id,
            "target_location_code": (it.target_location.code if it.target_location else
                                      o.target_location.code if o.target_location else None),
        } for it in items if it.received_quantity < it.quantity]
        if item_list:
            result.append({
                "id": o.id, "po_no": o.po_no,
                "supplier_name": o.supplier.name if o.supplier else "",
                "status": o.status, "total_amount": float(o.total_amount),
                "items": item_list
            })
    return result


@router.get("/{po_id}")
async def get_purchase_order(po_id: int, user: User = Depends(require_permission("purchase", "purchase_approve", "purchase_pay", "purchase_receive"))):
    po = await PurchaseOrder.filter(id=po_id).select_related(
        "supplier", "creator", "paid_by", "reviewed_by", "returned_by", "target_warehouse", "target_location").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    items = await PurchaseOrderItem.filter(purchase_order_id=po.id).select_related(
        "product", "target_warehouse", "target_location")
    return {
        "id": po.id, "po_no": po.po_no,
        "supplier_id": po.supplier_id,
        "supplier_name": po.supplier.name if po.supplier else "",
        "status": po.status, "total_amount": float(po.total_amount),
        "rebate_used": float(po.rebate_used),
        "return_amount": float(po.return_amount) if po.return_amount else 0,
        "return_tracking_no": po.return_tracking_no,
        "is_refunded": po.is_refunded,
        "returned_by_name": po.returned_by.display_name if po.returned_by else None,
        "returned_at": po.returned_at.isoformat() if po.returned_at else None,
        "credit_used": float(po.credit_used) if po.credit_used else 0,
        "target_warehouse_id": po.target_warehouse_id,
        "target_warehouse_name": po.target_warehouse.name if po.target_warehouse else None,
        "target_location_id": po.target_location_id,
        "target_location_code": po.target_location.code if po.target_location else None,
        "remark": po.remark,
        "creator_name": po.creator.display_name if po.creator else None,
        "reviewed_by_name": po.reviewed_by.display_name if po.reviewed_by else None,
        "reviewed_at": po.reviewed_at.isoformat() if po.reviewed_at else None,
        "paid_by_name": po.paid_by.display_name if po.paid_by else None,
        "paid_at": po.paid_at.isoformat() if po.paid_at else None,
        "created_at": po.created_at.isoformat(),
        "items": [{
            "id": it.id, "product_id": it.product_id,
            "product_sku": it.product.sku if it.product else "",
            "product_name": it.product.name if it.product else "",
            "quantity": it.quantity,
            "tax_inclusive_price": float(it.tax_inclusive_price),
            "tax_rate": float(it.tax_rate),
            "tax_exclusive_price": float(it.tax_exclusive_price),
            "amount": float(it.amount),
            "rebate_amount": float(it.rebate_amount) if it.rebate_amount else 0,
            "received_quantity": it.received_quantity,
            "returned_quantity": it.returned_quantity,
            "returnable_quantity": it.received_quantity - it.returned_quantity,
            "target_warehouse_name": (it.target_warehouse.name if it.target_warehouse else
                                       po.target_warehouse.name if po.target_warehouse else None),
            "target_location_code": (it.target_location.code if it.target_location else
                                      po.target_location.code if po.target_location else None),
        } for it in items]
    }


@router.post("/{po_id}/pay")
async def confirm_purchase_payment(po_id: int, data: PurchasePayRequest = PurchasePayRequest(), user: User = Depends(require_permission("purchase_pay"))):
    po = await PurchaseOrder.filter(id=po_id).select_related("supplier").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    if po.status != "pending":
        raise HTTPException(status_code=400, detail="该采购单不是待付款状态")
    po.status = "paid"
    po.payment_method = data.payment_method
    po.paid_by = user
    po.paid_at = now()
    await po.save()
    await log_operation(user, "PURCHASE_PAY", "PURCHASE_ORDER", po.id,
        f"确认付款 {po.po_no}，供应商 {po.supplier.name}，金额 ¥{float(po.total_amount):.2f}")
    return {"message": "付款确认成功"}


@router.post("/{po_id}/approve")
async def approve_purchase_order(po_id: int, user: User = Depends(require_permission("purchase_approve"))):
    po = await PurchaseOrder.filter(id=po_id).select_related("supplier").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    if po.status != "pending_review":
        raise HTTPException(status_code=400, detail="该采购单不是待审核状态")
    po.status = "pending"
    po.reviewed_by = user
    po.reviewed_at = now()
    await po.save()
    await log_operation(user, "PURCHASE_APPROVE", "PURCHASE_ORDER", po.id,
        f"审核通过采购单 {po.po_no}，供应商 {po.supplier.name}，金额 ¥{float(po.total_amount):.2f}")
    return {"message": "审核通过"}


@router.post("/{po_id}/reject")
async def reject_purchase_order(po_id: int, user: User = Depends(require_permission("purchase_approve"))):
    po = await PurchaseOrder.filter(id=po_id).select_related("supplier").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    if po.status != "pending_review":
        raise HTTPException(status_code=400, detail="该采购单不是待审核状态")
    po.status = "rejected"
    po.reviewed_by = user
    po.reviewed_at = now()
    await po.save()
    await log_operation(user, "PURCHASE_REJECT", "PURCHASE_ORDER", po.id,
        f"拒绝采购单 {po.po_no}，供应商 {po.supplier.name}，金额 ¥{float(po.total_amount):.2f}")
    return {"message": "已拒绝"}


@router.post("/{po_id}/cancel")
async def cancel_purchase_order(po_id: int, user: User = Depends(require_permission("purchase_pay"))):
    async with transactions.in_transaction():
        po = await PurchaseOrder.filter(id=po_id).select_for_update().first()
        if not po:
            raise HTTPException(status_code=404, detail="采购订单不存在")
        if po.status not in ("pending_review", "pending"):
            raise HTTPException(status_code=400, detail="只有待审核或待付款状态的采购单才能取消")
        # Load supplier relation
        await po.fetch_related("supplier")
        # 退还返利
        if po.rebate_used and po.rebate_used > 0:
            await Supplier.filter(id=po.supplier_id).update(rebate_balance=F('rebate_balance') + po.rebate_used)
            supplier = await Supplier.filter(id=po.supplier_id).first()
            await RebateLog.create(
                target_type="supplier", target_id=po.supplier_id,
                type="refund", amount=po.rebate_used,
                balance_after=supplier.rebate_balance,
                reference_type="PURCHASE_ORDER", reference_id=po.id,
                remark=f"取消采购单 {po.po_no} 退还返利", creator=user
            )
        # 退还在账资金
        if po.credit_used and po.credit_used > 0:
            await Supplier.filter(id=po.supplier_id).update(credit_balance=F('credit_balance') + po.credit_used)
            supplier = await Supplier.filter(id=po.supplier_id).first()
            await RebateLog.create(
                target_type="supplier", target_id=po.supplier_id,
                type="credit_refund", amount=po.credit_used,
                balance_after=supplier.credit_balance,
                reference_type="PURCHASE_ORDER", reference_id=po.id,
                remark=f"取消采购单 {po.po_no} 退还在账资金", creator=user
            )
        po.status = "cancelled"
        await po.save()

    await log_operation(user, "PURCHASE_CANCEL", "PURCHASE_ORDER", po.id,
        f"取消采购单 {po.po_no}，供应商 {po.supplier.name}，金额 ¥{float(po.total_amount):.2f}")
    return {"message": "采购单已取消"}


@router.post("/{po_id}/receive")
async def receive_purchase_order(po_id: int, data: ReceiveRequest, user: User = Depends(require_permission("purchase_receive"))):
    po = await PurchaseOrder.filter(id=po_id).select_related("supplier").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    if po.status not in ("paid", "partial"):
        raise HTTPException(status_code=400, detail="该采购单不可收货（需为已付款或部分到货状态）")

    async with transactions.in_transaction():
        received_details = []
        for recv_item in data.items:
            if recv_item.receive_quantity <= 0:
                continue
            poi = await PurchaseOrderItem.filter(id=recv_item.item_id, purchase_order_id=po.id).select_related("product").first()
            if not poi:
                raise HTTPException(status_code=404, detail=f"采购明细 {recv_item.item_id} 不存在")
            pending = poi.quantity - poi.received_quantity
            if recv_item.receive_quantity > pending:
                raise HTTPException(status_code=400, detail=f"{poi.product.name} 本次收货数量({recv_item.receive_quantity})超过待收数量({pending})")

            wh_id = recv_item.warehouse_id or poi.target_warehouse_id or po.target_warehouse_id
            loc_id = recv_item.location_id or poi.target_location_id or po.target_location_id
            if not wh_id or not loc_id:
                raise HTTPException(status_code=400, detail=f"{poi.product.name} 缺少目标仓库或仓位")

            warehouse = await Warehouse.filter(id=wh_id, is_active=True, is_virtual=False).first()
            if not warehouse:
                raise HTTPException(status_code=404, detail="目标仓库不存在")
            location = await Location.filter(id=loc_id, is_active=True).first()
            if not location:
                raise HTTPException(status_code=404, detail="目标仓位不存在")
            if location.warehouse_id != wh_id:
                raise HTTPException(status_code=400, detail=f"{poi.product.name} 的仓位不属于所选仓库")

            # 成本价 = 实际付款金额(已扣返利) / 数量，反映真实资金成本
            cost_price = poi.amount / poi.quantity if poi.quantity > 0 else poi.tax_inclusive_price

            sn_required = await check_sn_required(wh_id, poi.product_id)
            if sn_required and not recv_item.sn_codes:
                raise HTTPException(status_code=400, detail=f"{poi.product.name} 已启用SN管理，收货时必须填写SN码")
            if sn_required and recv_item.sn_codes:
                await validate_and_add_sn_codes(
                    recv_item.sn_codes, wh_id, poi.product_id, loc_id,
                    recv_item.receive_quantity, "PURCHASE_IN", cost_price, user, po.id
                )

            stock = await WarehouseStock.filter(warehouse_id=wh_id, product_id=poi.product_id, location_id=loc_id).first()
            before_qty = stock.quantity if stock else 0

            await update_weighted_entry_date(wh_id, poi.product_id, recv_item.receive_quantity, cost_price, loc_id)

            stock = await WarehouseStock.filter(warehouse_id=wh_id, product_id=poi.product_id, location_id=loc_id).first()

            product = await Product.filter(id=poi.product_id).first()
            if product:
                product.cost_price = await get_product_weighted_cost(poi.product_id)
                await product.save()

            await StockLog.create(
                product_id=poi.product_id, warehouse_id=wh_id,
                change_type="PURCHASE_IN", quantity=recv_item.receive_quantity,
                before_qty=before_qty, after_qty=stock.quantity if stock else recv_item.receive_quantity,
                reference_type="PURCHASE_ORDER", reference_id=po.id,
                remark=f"采购收货 {po.po_no}，仓位:{location.code}，成本:¥{float(cost_price)}",
                creator=user
            )

            poi.received_quantity += recv_item.receive_quantity
            await poi.save()
            received_details.append(f"{poi.product.name}×{recv_item.receive_quantity}")

        all_items = await PurchaseOrderItem.filter(purchase_order_id=po.id).all()
        all_received = all(it.received_quantity >= it.quantity for it in all_items)
        any_received = any(it.received_quantity > 0 for it in all_items)

        if all_received:
            po.status = "completed"
        elif any_received:
            po.status = "partial"
        await po.save()

        await log_operation(user, "PURCHASE_RECEIVE", "PURCHASE_ORDER", po.id,
            f"采购收货 {po.po_no}，{', '.join(received_details)}，状态→{po.status}")

    return {"message": "收货成功", "status": po.status}


@router.post("/{po_id}/return")
async def return_purchase_order(po_id: int, data: PurchaseReturnRequest, user: User = Depends(require_permission("purchase"))):
    po = await PurchaseOrder.filter(id=po_id).select_related("supplier").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    if po.status not in ("completed", ):
        raise HTTPException(status_code=400, detail="只有已完成的采购单才能退货")
    if not data.items:
        raise HTTPException(status_code=400, detail="请选择退货商品")

    async with transactions.in_transaction():
        total_return_amount = Decimal("0")
        return_details = []

        for ret_item in data.items:
            poi = await PurchaseOrderItem.filter(id=ret_item.item_id, purchase_order_id=po.id).select_related("product").first()
            if not poi:
                raise HTTPException(status_code=404, detail=f"采购明细 {ret_item.item_id} 不存在")
            returnable = poi.received_quantity - poi.returned_quantity
            if ret_item.return_quantity > returnable:
                raise HTTPException(status_code=400, detail=f"{poi.product.name} 退货数量({ret_item.return_quantity})超过可退数量({returnable})")

            # 计算退货金额（按比例）
            unit_amount = poi.amount / poi.quantity if poi.quantity > 0 else Decimal("0")
            item_return_amount = round(unit_amount * ret_item.return_quantity, 2)
            total_return_amount += item_return_amount

            # 从仓库扣减库存（汇总该仓库所有仓位的库存）
            wh_id = poi.target_warehouse_id or po.target_warehouse_id
            if not wh_id:
                raise HTTPException(status_code=400, detail=f"{poi.product.name} 缺少仓库信息，无法退货扣减库存")

            stocks = await WarehouseStock.filter(warehouse_id=wh_id, product_id=poi.product_id).select_for_update().all()
            total_stock = sum(s.quantity - s.reserved_qty for s in stocks)
            if total_stock < ret_item.return_quantity:
                raise HTTPException(status_code=400, detail=f"{poi.product.name} 库存不足（当前:{total_stock}，需退:{ret_item.return_quantity}）")

            # 从各仓位逐条原子扣减
            remaining = ret_item.return_quantity
            for s in stocks:
                if remaining <= 0:
                    break
                deduct = min(s.quantity - s.reserved_qty, remaining)
                if deduct > 0:
                    updated = await WarehouseStock.filter(id=s.id, quantity__gte=deduct).update(quantity=F('quantity') - deduct)
                    if not updated:
                        raise HTTPException(status_code=400, detail="库存已变更，请重试")
                    remaining -= deduct

            await StockLog.create(
                product_id=poi.product_id, warehouse_id=wh_id,
                change_type="PURCHASE_RETURN", quantity=-ret_item.return_quantity,
                before_qty=total_stock, after_qty=total_stock - ret_item.return_quantity,
                reference_type="PURCHASE_ORDER", reference_id=po.id,
                remark=f"采购退货 {po.po_no}，退回{ret_item.return_quantity}件",
                creator=user
            )

            poi.returned_quantity += ret_item.return_quantity
            await poi.save()
            return_details.append(f"{poi.product.name}×{ret_item.return_quantity}")

        # 更新 PO
        po.return_amount = (po.return_amount or Decimal("0")) + total_return_amount
        po.return_tracking_no = data.tracking_no
        po.is_refunded = data.is_refunded
        po.returned_by = user
        po.returned_at = now()

        # 判断是否全部退货
        all_items = await PurchaseOrderItem.filter(purchase_order_id=po.id).all()
        all_returned = all(it.returned_quantity >= it.received_quantity for it in all_items)
        if all_returned:
            po.status = "returned"
        await po.save()

        # 未退款时增加供应商在账资金
        if not data.is_refunded:
            supplier = po.supplier
            await Supplier.filter(id=supplier.id).update(credit_balance=F('credit_balance') + total_return_amount)
            await supplier.refresh_from_db()
            await RebateLog.create(
                target_type="supplier", target_id=supplier.id,
                type="credit_charge", amount=total_return_amount,
                balance_after=supplier.credit_balance,
                reference_type="PURCHASE_ORDER", reference_id=po.id,
                remark=f"采购退货 {po.po_no}，退货金额 ¥{float(total_return_amount):.2f} 转为在账资金",
                creator=user
            )

        await log_operation(user, "PURCHASE_RETURN", "PURCHASE_ORDER", po.id,
            f"采购退货 {po.po_no}，{', '.join(return_details)}，退货金额 ¥{float(total_return_amount):.2f}，{'已退款' if data.is_refunded else '转为在账资金'}，状态→{po.status}")

    return {"message": "退货成功", "status": po.status, "return_amount": float(total_return_amount)}
