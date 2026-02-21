"""通用 CRUD 路由工厂"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.auth.dependencies import get_current_user, require_permission
from app.models import User


class MethodCreate(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)

class MethodUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1)
    name: Optional[str] = Field(default=None, min_length=1)


def create_method_router(prefix: str, tag: str, model_class, entity_name: str):
    """创建通用的收款/付款方式 CRUD 路由"""
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("")
    async def list_methods(user: User = Depends(get_current_user)):
        methods = await model_class.filter(is_active=True).order_by("sort_order", "id")
        return [{"id": m.id, "code": m.code, "name": m.name, "sort_order": m.sort_order} for m in methods]

    @router.post("")
    async def create_method(data: MethodCreate, user: User = Depends(require_permission("finance"))):
        code = data.code.strip()
        name = data.name.strip()
        if not code or not name:
            raise HTTPException(status_code=400, detail="编码和名称不能为空")
        if await model_class.filter(code=code).exists():
            raise HTTPException(status_code=400, detail="编码已存在")
        max_sort = await model_class.all().order_by("-sort_order").first()
        sort_order = (max_sort.sort_order + 1) if max_sort else 1
        m = await model_class.create(code=code, name=name, sort_order=sort_order)
        return {"id": m.id, "message": "添加成功"}

    @router.put("/{method_id}")
    async def update_method(method_id: int, data: MethodUpdate, user: User = Depends(require_permission("finance"))):
        m = await model_class.filter(id=method_id).first()
        if not m:
            raise HTTPException(status_code=404, detail=f"{entity_name}不存在")
        if data.name and data.name.strip():
            m.name = data.name.strip()
        if data.code and data.code.strip():
            if data.code != m.code and await model_class.filter(code=data.code).exists():
                raise HTTPException(status_code=400, detail="编码已存在")
            m.code = data.code.strip()
        await m.save()
        return {"message": "更新成功"}

    @router.delete("/{method_id}")
    async def delete_method(method_id: int, user: User = Depends(require_permission("finance"))):
        m = await model_class.filter(id=method_id).first()
        if not m:
            raise HTTPException(status_code=404, detail=f"{entity_name}不存在")
        m.is_active = False
        await m.save()
        return {"message": "删除成功"}

    return router
