"""SN码管理路由"""
from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user, require_permission
from app.models import User, Warehouse, SnConfig, SnCode
from app.schemas.sn import SnConfigCreate
from app.services.sn_service import check_sn_required

router = APIRouter(prefix="/api", tags=["SN码管理"])


@router.get("/sn-configs")
async def list_sn_configs(user: User = Depends(require_permission("settings", "admin"))):
    """获取SN配置列表"""
    configs = await SnConfig.filter(is_active=True).select_related("warehouse").order_by("-created_at")
    return [{"id": c.id, "warehouse_id": c.warehouse_id, "warehouse_name": c.warehouse.name if c.warehouse else "", "brand": c.brand} for c in configs]


@router.post("/sn-configs")
async def create_sn_config(data: SnConfigCreate, user: User = Depends(require_permission("settings", "admin"))):
    """创建SN配置"""
    warehouse = await Warehouse.filter(id=data.warehouse_id, is_active=True, is_virtual=False).first()
    if not warehouse:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if not data.brand or not data.brand.strip():
        raise HTTPException(status_code=400, detail="品牌不能为空")
    existing = await SnConfig.filter(warehouse_id=data.warehouse_id, brand=data.brand.strip()).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="该仓库+品牌配置已存在")
        existing.is_active = True
        await existing.save()
        return {"id": existing.id, "message": "配置已恢复"}
    config = await SnConfig.create(warehouse_id=data.warehouse_id, brand=data.brand.strip())
    return {"id": config.id, "message": "配置已创建"}


@router.delete("/sn-configs/{config_id}")
async def delete_sn_config(config_id: int, user: User = Depends(require_permission("settings", "admin"))):
    """删除SN配置（软删除）"""
    config = await SnConfig.filter(id=config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    config.is_active = False
    await config.save()
    return {"message": "配置已删除"}


@router.get("/sn-codes/check-required")
async def check_sn_required_api(warehouse_id: int, product_id: int, user: User = Depends(get_current_user)):
    """检查是否需要SN码"""
    required = await check_sn_required(warehouse_id, product_id)
    return {"required": required}


@router.get("/sn-codes/available")
async def list_available_sn_codes(warehouse_id: int, product_id: int, user: User = Depends(require_permission("stock_view", "logistics", "sales"))):
    """查询可用SN码"""
    codes = await SnCode.filter(warehouse_id=warehouse_id, product_id=product_id, status="in_stock").order_by("entry_date")
    return [{"id": c.id, "sn_code": c.sn_code, "entry_date": c.entry_date.isoformat() if c.entry_date else None} for c in codes]
