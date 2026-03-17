from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user, require_permission
from app.models import User, Warehouse, Location, WarehouseStock, AccountSet
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from app.utils.response import paginated_response

router = APIRouter(prefix="/api/warehouses", tags=["仓库管理"])


@router.get("")
async def list_warehouses(include_virtual: bool = False, user: User = Depends(get_current_user)):
    query = Warehouse.filter(is_active=True)
    if not include_virtual:
        query = query.filter(is_virtual=False)
    warehouses = await query.order_by("-is_default", "name")

    # 批量查询所有仓位（避免 N+1）
    wh_ids = [w.id for w in warehouses]
    all_locs = await Location.filter(warehouse_id__in=wh_ids, is_active=True).order_by("code") if wh_ids else []
    locs_by_wh = {}
    for loc in all_locs:
        locs_by_wh.setdefault(loc.warehouse_id, []).append(loc)

    # 批量查询账套名称（避免 N+1）
    as_ids = list(set(w.account_set_id for w in warehouses if w.account_set_id))
    as_map = {}
    if as_ids:
        for a in await AccountSet.filter(id__in=as_ids):
            as_map[a.id] = a.name

    items = []
    for w in warehouses:
        locs = locs_by_wh.get(w.id, [])
        items.append({
            "id": w.id, "name": w.name, "is_default": w.is_default,
            "is_virtual": w.is_virtual, "customer_id": w.customer_id,
            "account_set_id": w.account_set_id,
            "account_set_name": as_map.get(w.account_set_id) if w.account_set_id else None,
            "locations": [{"id": loc.id, "code": loc.code, "name": loc.name, "color": loc.color or "blue"} for loc in locs]
        })
    return paginated_response(items)


@router.post("")
async def create_warehouse(data: WarehouseCreate, user: User = Depends(require_permission("stock_edit"))):
    if await Warehouse.filter(name=data.name).exists():
        raise HTTPException(status_code=400, detail="仓库名已存在")
    from tortoise import transactions
    async with transactions.in_transaction():
        if data.is_default:
            await Warehouse.filter(is_default=True).update(is_default=False)
        create_kwargs = dict(name=data.name, is_default=data.is_default)
        if data.account_set_id is not None:
            create_kwargs["account_set_id"] = data.account_set_id
        wh = await Warehouse.create(**create_kwargs)
    return {"id": wh.id, "message": "创建成功"}


@router.put("/{warehouse_id}")
async def update_warehouse(warehouse_id: int, data: WarehouseUpdate, user: User = Depends(require_permission("stock_edit"))):
    wh = await Warehouse.filter(id=warehouse_id).first()
    if not wh:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if wh.is_virtual:
        raise HTTPException(status_code=400, detail="不能修改系统仓库")
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if "name" in update_data:
        if await Warehouse.filter(name=update_data["name"]).exclude(id=warehouse_id).exists():
            raise HTTPException(status_code=400, detail="仓库名已存在")
    from tortoise import transactions
    async with transactions.in_transaction():
        if update_data.get("is_default"):
            await Warehouse.filter(is_default=True).update(is_default=False)
        if update_data:
            await Warehouse.filter(id=warehouse_id).update(**update_data)
    return {"message": "更新成功"}


@router.delete("/{warehouse_id}")
async def delete_warehouse(warehouse_id: int, user: User = Depends(require_permission("stock_edit"))):
    wh = await Warehouse.filter(id=warehouse_id).first()
    if not wh:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if wh.is_default:
        raise HTTPException(status_code=400, detail="不能删除默认仓库")
    if wh.is_virtual:
        raise HTTPException(status_code=400, detail="不能删除系统仓库")
    has_stock = await WarehouseStock.filter(warehouse_id=warehouse_id, quantity__gt=0).exists()
    if has_stock:
        raise HTTPException(status_code=400, detail="仓库有库存，无法删除")
    has_locations = await Location.filter(warehouse_id=warehouse_id, is_active=True).exists()
    if has_locations:
        raise HTTPException(status_code=400, detail="仓库下有仓位，请先删除仓位")
    wh.is_active = False
    await wh.save()
    return {"message": "删除成功"}
