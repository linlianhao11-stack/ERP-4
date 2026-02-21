from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user, require_permission
from app.models import User, Salesperson
from app.schemas.salesperson import SalespersonCreate, SalespersonUpdate

router = APIRouter(prefix="/api/salespersons", tags=["销售员管理"])


@router.get("")
async def list_salespersons(user: User = Depends(get_current_user)):
    sps = await Salesperson.filter(is_active=True).order_by("name")
    return [{"id": s.id, "name": s.name, "phone": s.phone} for s in sps]


@router.post("")
async def create_salesperson(data: SalespersonCreate, user: User = Depends(require_permission("admin"))):
    if await Salesperson.filter(name=data.name).exists():
        raise HTTPException(status_code=400, detail="销售员姓名已存在")
    sp = await Salesperson.create(name=data.name, phone=data.phone)
    return {"id": sp.id, "message": "创建成功"}


@router.put("/{sp_id}")
async def update_salesperson(sp_id: int, data: SalespersonUpdate, user: User = Depends(require_permission("admin"))):
    sp = await Salesperson.filter(id=sp_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="销售员不存在")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if "name" in update_data:
        if await Salesperson.filter(name=update_data["name"]).exclude(id=sp_id).exists():
            raise HTTPException(status_code=400, detail="销售员姓名已存在")
    if update_data:
        await Salesperson.filter(id=sp_id).update(**update_data)
    return {"message": "更新成功"}


@router.delete("/{sp_id}")
async def delete_salesperson(sp_id: int, user: User = Depends(require_permission("admin"))):
    sp = await Salesperson.filter(id=sp_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="销售员不存在")
    sp.is_active = False
    await sp.save()
    return {"message": "删除成功"}
