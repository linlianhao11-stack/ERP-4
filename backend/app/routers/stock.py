import io
import csv
from typing import Optional
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from tortoise import transactions
from tortoise.expressions import F
from urllib.parse import quote

from app.auth.dependencies import get_current_user, require_permission
from app.models import (
    User, Product, Warehouse, Location, WarehouseStock, StockLog, SnCode
)
from app.schemas.stock import RestockRequest, StockAdjustRequest, StockTransferRequest
from app.services.stock_service import update_weighted_entry_date, get_product_weighted_cost
from app.services.sn_service import check_sn_required, validate_and_add_sn_codes
from app.constants import SnCodeStatus
from app.services.operation_log_service import log_operation
from app.utils.response import paginated_response
from app.utils.time import now, to_naive, days_between
from app.logger import get_logger

logger = get_logger("stock")

router = APIRouter(prefix="/api/stock", tags=["库存管理"])


@router.post("/restock")
async def restock(data: RestockRequest, user: User = Depends(require_permission("stock_edit"))):
    async with transactions.in_transaction():
        try:
            product = await Product.filter(id=data.product_id, is_active=True).first()
            if not product:
                raise HTTPException(status_code=404, detail="商品不存在")
            warehouse = await Warehouse.filter(id=data.warehouse_id, is_active=True, is_virtual=False).first()
            if not warehouse:
                raise HTTPException(status_code=404, detail="仓库不存在")
            location = await Location.filter(id=data.location_id, is_active=True).first()
            if not location:
                raise HTTPException(status_code=404, detail="仓位不存在")
            if location.warehouse_id != data.warehouse_id:
                raise HTTPException(status_code=400, detail="仓位不属于所选仓库")

            sn_required = await check_sn_required(data.warehouse_id, data.product_id)
            if sn_required and not data.sn_codes:
                raise HTTPException(status_code=400, detail="该仓库+品牌已启用SN管理，入库时必须填写SN码")

            cost_price = Decimal(str(data.cost_price)) if data.cost_price and data.cost_price > 0 else (product.cost_price or Decimal('0'))

            if sn_required and data.sn_codes:
                await validate_and_add_sn_codes(
                    data.sn_codes, data.warehouse_id, data.product_id, data.location_id,
                    data.quantity, "RESTOCK", cost_price, user
                )

            stock = await WarehouseStock.filter(warehouse_id=data.warehouse_id, product_id=data.product_id, location_id=data.location_id).first()
            before_qty = stock.quantity if stock else 0

            await update_weighted_entry_date(data.warehouse_id, data.product_id, data.quantity, cost_price, data.location_id)

            # 刷新库存记录（update_weighted_entry_date 已更新数量）
            if stock:
                await stock.refresh_from_db()
            stock = stock or await WarehouseStock.filter(warehouse_id=data.warehouse_id, product_id=data.product_id, location_id=data.location_id).first()

            product.cost_price = await get_product_weighted_cost(data.product_id)
            await product.save()

            await StockLog.create(
                product_id=data.product_id, warehouse_id=data.warehouse_id,
                change_type="RESTOCK", quantity=data.quantity,
                before_qty=before_qty, after_qty=stock.quantity,
                remark=f"仓位:{location.code}, 入库成本: ¥{cost_price}" + (f", {data.remark}" if data.remark else ""),
                creator=user
            )

            await log_operation(user, "STOCK_RESTOCK", "STOCK", product.id,
                f"入库 {product.sku} {product.name}，仓位 {location.code}，数量 {data.quantity}，成本 ¥{float(cost_price):.2f}")

            return {"message": "入库成功", "new_quantity": stock.quantity, "weighted_cost": float(stock.weighted_cost)}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("入库失败", exc_info=e)
            raise HTTPException(status_code=500, detail="入库失败，请重试")


@router.post("/adjust")
async def adjust_stock(data: StockAdjustRequest, user: User = Depends(require_permission("stock_edit"))):
    async with transactions.in_transaction():
        location = await Location.filter(id=data.location_id, is_active=True).first()
        if not location:
            raise HTTPException(status_code=404, detail="仓位不存在")
        if location.warehouse_id != data.warehouse_id:
            raise HTTPException(status_code=400, detail="仓位不属于所选仓库")

        stock = await WarehouseStock.filter(
            warehouse_id=data.warehouse_id, product_id=data.product_id, location_id=data.location_id
        ).select_for_update().first()
        before_qty = stock.quantity if stock else 0

        # Check that new quantity does not go below reserved quantity
        if stock and data.new_quantity < stock.reserved_qty:
            raise HTTPException(status_code=400, detail=f"库存不能低于预留数量({stock.reserved_qty})")

        if not stock:
            stock = await WarehouseStock.create(
                warehouse_id=data.warehouse_id, product_id=data.product_id,
                location_id=data.location_id,
                quantity=data.new_quantity, weighted_entry_date=now()
            )
        else:
            stock.quantity = data.new_quantity
            await stock.save()

        await StockLog.create(
            product_id=data.product_id, warehouse_id=data.warehouse_id,
            change_type="ADJUST", quantity=data.new_quantity - before_qty,
            before_qty=before_qty, after_qty=data.new_quantity,
            remark=f"仓位:{location.code}" + (f", {data.remark}" if data.remark else ""),
            creator=user
        )

        product = await Product.filter(id=data.product_id).first()
        await log_operation(user, "STOCK_ADJUST", "STOCK", data.product_id,
            f"库存调整 {product.sku if product else data.product_id}，仓位 {location.code}，{before_qty} → {data.new_quantity}")

        return {"message": "调整成功"}


@router.post("/transfer")
async def transfer_stock(data: StockTransferRequest, user: User = Depends(require_permission("stock_edit"))):
    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="调拨数量必须大于0")
    if data.from_warehouse_id == data.to_warehouse_id and data.from_location_id == data.to_location_id:
        raise HTTPException(status_code=400, detail="源和目标位置不能相同")

    async with transactions.in_transaction():
        try:
            product = await Product.filter(id=data.product_id, is_active=True).first()
            if not product:
                raise HTTPException(status_code=404, detail="商品不存在")
            from_wh = await Warehouse.filter(id=data.from_warehouse_id, is_active=True).first()
            to_wh = await Warehouse.filter(id=data.to_warehouse_id, is_active=True).first()
            if not from_wh or not to_wh:
                raise HTTPException(status_code=404, detail="仓库不存在")
            from_loc = await Location.filter(id=data.from_location_id, is_active=True).first()
            to_loc = await Location.filter(id=data.to_location_id, is_active=True).first()
            if not from_loc or not to_loc:
                raise HTTPException(status_code=404, detail="仓位不存在")
            if from_loc.warehouse_id != data.from_warehouse_id:
                raise HTTPException(status_code=400, detail="源仓位不属于源仓库")
            if to_loc.warehouse_id != data.to_warehouse_id:
                raise HTTPException(status_code=400, detail="目标仓位不属于目标仓库")

            from_stock = await WarehouseStock.filter(
                warehouse_id=data.from_warehouse_id, product_id=data.product_id,
                location_id=data.from_location_id
            ).select_for_update().first()
            if not from_stock or from_stock.quantity < data.quantity:
                raise HTTPException(status_code=400, detail="源库存不足")

            # Check that source stock has enough available (non-reserved) quantity
            available = from_stock.quantity - from_stock.reserved_qty
            if data.quantity > available:
                raise HTTPException(status_code=400, detail=f"可用库存不足，当前可用: {available}")

            from_before = from_stock.quantity

            to_stock = await WarehouseStock.filter(
                warehouse_id=data.to_warehouse_id, product_id=data.product_id,
                location_id=data.to_location_id
            ).first()
            if not to_stock:
                to_stock = await WarehouseStock.create(
                    warehouse_id=data.to_warehouse_id, product_id=data.product_id,
                    location_id=data.to_location_id, quantity=0,
                    weighted_cost=from_stock.weighted_cost,
                    weighted_entry_date=from_stock.weighted_entry_date
                )

            to_before = to_stock.quantity

            updated = await WarehouseStock.filter(id=from_stock.id, quantity__gte=data.quantity).update(quantity=F('quantity') - data.quantity)
            if not updated:
                raise HTTPException(status_code=400, detail="源库存不足，调拨失败")
            await WarehouseStock.filter(id=to_stock.id).update(quantity=F('quantity') + data.quantity)
            await from_stock.refresh_from_db()
            await to_stock.refresh_from_db()

            remark_out = f"调拨至 {to_wh.name}/{to_loc.code}"
            if data.remark:
                remark_out += f", {data.remark}"
            await StockLog.create(
                product_id=data.product_id, warehouse_id=data.from_warehouse_id,
                change_type="TRANSFER_OUT", quantity=-data.quantity,
                before_qty=from_before, after_qty=from_stock.quantity,
                remark=remark_out, creator=user
            )

            remark_in = f"从 {from_wh.name}/{from_loc.code} 调入"
            if data.remark:
                remark_in += f", {data.remark}"
            await StockLog.create(
                product_id=data.product_id, warehouse_id=data.to_warehouse_id,
                change_type="TRANSFER_IN", quantity=data.quantity,
                before_qty=to_before, after_qty=to_stock.quantity,
                remark=remark_in, creator=user
            )

            await log_operation(user, "STOCK_TRANSFER", "STOCK", data.product_id,
                f"库存调拨 {product.sku}，{from_wh.name}/{from_loc.code} → {to_wh.name}/{to_loc.code}，数量 {data.quantity}")

            return {"message": "调拨成功", "from_qty": from_stock.quantity, "to_qty": to_stock.quantity}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("调拨失败", exc_info=e)
            raise HTTPException(status_code=500, detail="调拨失败，请重试")


@router.get("/logs")
async def get_stock_logs(product_id: Optional[int] = None, warehouse_id: Optional[int] = None,
                         limit: int = 100, user: User = Depends(require_permission("logs"))):
    limit = min(limit, 1000)
    query = StockLog.all()
    if product_id:
        query = query.filter(product_id=product_id)
    if warehouse_id:
        query = query.filter(warehouse_id=warehouse_id)
    logs = await query.order_by("-created_at").limit(limit).select_related("product", "warehouse", "creator")
    return paginated_response([{
        "id": l.id, "product_name": l.product.name, "product_sku": l.product.sku,
        "warehouse_name": l.warehouse.name, "change_type": l.change_type,
        "quantity": l.quantity, "before_qty": l.before_qty, "after_qty": l.after_qty,
        "remark": l.remark,
        "creator_name": l.creator.display_name if l.creator else None,
        "created_at": l.created_at.isoformat()
    } for l in logs])


@router.get("/export")
async def export_stock(warehouse_id: Optional[int] = None, user: User = Depends(require_permission("stock_view"))):
    try:
        products = await Product.filter(is_active=True).order_by("sku")
        stock_query = WarehouseStock.all()
        if warehouse_id:
            stock_query = stock_query.filter(warehouse_id=warehouse_id)
        stocks = await stock_query.select_related("product", "warehouse", "location")

        stock_by_product = {}
        for s in stocks:
            if s.product_id not in stock_by_product:
                stock_by_product[s.product_id] = []
            stock_by_product[s.product_id].append(s)

        # 批量统计 SN 码数量（避免 N+1）
        # 仅查询当前导出范围内的 SN 码
        sn_query = SnCode.filter(status=SnCodeStatus.IN_STOCK.value)
        if warehouse_id:
            sn_query = sn_query.filter(warehouse_id=warehouse_id)
        product_ids_for_sn = [p.id for p in products]
        if product_ids_for_sn:
            sn_query = sn_query.filter(product_id__in=product_ids_for_sn)
        all_sn = await sn_query.values_list("warehouse_id", "product_id", "location_id")
        sn_count_map = {}
        for wid, pid, lid in all_sn:
            key = (wid, pid, lid)
            sn_count_map[key] = sn_count_map.get(key, 0) + 1

        output = io.StringIO()
        output.write('\ufeff')
        headers = ["SKU", "商品名称", "品牌", "分类", "仓库", "仓位", "库存数量", "SN码数量", "加权成本", "库存金额", "零售价", "库龄(天)", "入库时间"]
        writer = csv.writer(output)
        writer.writerow(headers)

        for p in products:
            product_stocks = stock_by_product.get(p.id, [])
            if not product_stocks:
                if not warehouse_id:
                    row = [p.sku, p.name, p.brand or "-", p.category or "-", "-", "-", "0", "0",
                           f"{float(p.cost_price or 0):.2f}", "0.00", f"{float(p.retail_price or 0):.2f}", "-", "-"]
                    writer.writerow(row)
            else:
                for s in product_stocks:
                    age_days = "-"
                    entry_date_str = "-"
                    entry_date = to_naive(s.weighted_entry_date) if s.weighted_entry_date else None
                    if entry_date:
                        age_days = str(days_between(now(), entry_date))
                        entry_date_str = entry_date.strftime("%Y-%m-%d")
                    stock_value = float(s.quantity) * float(s.weighted_cost or p.cost_price or 0)
                    sn_count = sn_count_map.get((s.warehouse_id, s.product_id, s.location_id), 0)
                    row = [p.sku, p.name, p.brand or "-", p.category or "-",
                           s.warehouse.name if s.warehouse else "-",
                           s.location.code if s.location else "-",
                           str(s.quantity), str(sn_count),
                           f"{float(s.weighted_cost or 0):.2f}", f"{stock_value:.2f}",
                           f"{float(p.retail_price or 0):.2f}", age_days, entry_date_str]
                    writer.writerow(row)

        output.seek(0)
        filename = f"库存表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8')]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
        )
    except Exception as e:
        logger.error("库存导出失败", exc_info=e)
        raise HTTPException(status_code=500, detail="导出失败，请重试")
