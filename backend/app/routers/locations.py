from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user, require_permission
from app.models import User, Location, Warehouse, WarehouseStock
from app.schemas.warehouse import LocationCreate, LocationUpdate

router = APIRouter(prefix="/api/locations", tags=["仓位管理"])


@router.get("")
async def list_locations(warehouse_id: Optional[int] = None, user: User = Depends(get_current_user)):
    query = Location.filter(is_active=True)
    if warehouse_id:
        query = query.filter(warehouse_id=warehouse_id)
    locations = await query.order_by("code")
    return [{"id": loc.id, "code": loc.code, "name": loc.name, "warehouse_id": loc.warehouse_id} for loc in locations]


@router.post("")
async def create_location(data: LocationCreate, user: User = Depends(require_permission("stock_edit"))):
    warehouse = await Warehouse.filter(id=data.warehouse_id, is_active=True).first()
    if not warehouse:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if await Location.filter(warehouse_id=data.warehouse_id, code=data.code).exists():
        raise HTTPException(status_code=400, detail="该仓库下仓位编号已存在")
    loc = await Location.create(warehouse_id=data.warehouse_id, code=data.code, name=data.name)
    return {"id": loc.id, "message": "创建成功"}


@router.put("/{location_id}")
async def update_location(location_id: int, data: LocationUpdate, user: User = Depends(require_permission("stock_edit"))):
    loc = await Location.filter(id=location_id, is_active=True).first()
    if not loc:
        raise HTTPException(status_code=404, detail="仓位不存在")
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if "code" in update_data:
        if await Location.filter(warehouse_id=loc.warehouse_id, code=update_data["code"]).exclude(id=location_id).exists():
            raise HTTPException(status_code=400, detail="该仓库下仓位编号已存在")
    if update_data:
        await Location.filter(id=location_id).update(**update_data)
    return {"message": "更新成功"}


@router.delete("/{location_id}")
async def delete_location(location_id: int, user: User = Depends(require_permission("stock_edit"))):
    loc = await Location.filter(id=location_id, is_active=True).first()
    if not loc:
        raise HTTPException(status_code=404, detail="仓位不存在")
    has_stock = await WarehouseStock.filter(location_id=location_id, quantity__gt=0).exists()
    if has_stock:
        raise HTTPException(status_code=400, detail="仓位有库存，无法删除")
    loc.is_active = False
    await loc.save()
    return {"message": "删除成功"}
