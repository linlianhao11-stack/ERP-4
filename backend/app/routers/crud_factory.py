"""通用 CRUD 路由工厂"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.auth.dependencies import get_current_user, require_permission
from app.models import User


class MethodCreate(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    account_set_id: Optional[int] = None

class MethodUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1)
    name: Optional[str] = Field(default=None, min_length=1)


def create_method_router(prefix: str, tag: str, model_class, entity_name: str):
    """创建通用的收款/付款方式 CRUD 路由"""
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("")
    async def list_methods(
        account_set_id: Optional[int] = Query(default=None),
        user: User = Depends(get_current_user),
    ):
        filters = {"is_active": True}
        if account_set_id is not None:
            filters["account_set_id"] = account_set_id
        methods = await model_class.filter(**filters).order_by("sort_order", "id")
        return [
            {
                "id": m.id,
                "code": m.code,
                "name": m.name,
                "sort_order": m.sort_order,
                "account_set_id": m.account_set_id,
            }
            for m in methods
        ]

    @router.post("")
    async def create_method(data: MethodCreate, user: User = Depends(require_permission("finance"))):
        code = data.code.strip()
        name = data.name.strip()
        if not code or not name:
            raise HTTPException(status_code=400, detail="编码和名称不能为空")
        # 唯一性检查：在同一账套内不允许重复编码
        duplicate_filter = {"code": code}
        if data.account_set_id is not None:
            duplicate_filter["account_set_id"] = data.account_set_id
        else:
            duplicate_filter["account_set_id__isnull"] = True
        if await model_class.filter(**duplicate_filter).exists():
            raise HTTPException(status_code=400, detail="编码已存在")
        max_sort = await model_class.all().order_by("-sort_order").first()
        sort_order = (max_sort.sort_order + 1) if max_sort else 1
        create_kwargs = {"code": code, "name": name, "sort_order": sort_order}
        if data.account_set_id is not None:
            create_kwargs["account_set_id"] = data.account_set_id
        m = await model_class.create(**create_kwargs)
        return {"id": m.id, "message": "添加成功"}

    @router.put("/{method_id}")
    async def update_method(method_id: int, data: MethodUpdate, user: User = Depends(require_permission("finance"))):
        m = await model_class.filter(id=method_id).first()
        if not m:
            raise HTTPException(status_code=404, detail=f"{entity_name}不存在")
        if data.name and data.name.strip():
            m.name = data.name.strip()
        if data.code and data.code.strip():
            # 在同一账套内检查编码唯一性
            if data.code != m.code:
                dup_filter = {"code": data.code}
                if m.account_set_id is not None:
                    dup_filter["account_set_id"] = m.account_set_id
                else:
                    dup_filter["account_set_id__isnull"] = True
                if await model_class.filter(**dup_filter).exists():
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
