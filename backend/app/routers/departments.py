from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.models.department import Department
from app.utils.response import paginated_response

router = APIRouter(prefix="/api/departments", tags=["部门管理"])


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)


class DepartmentUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1)
    name: Optional[str] = Field(default=None, min_length=1)


@router.get("")
async def list_departments(user: User = Depends(get_current_user)):
    depts = await Department.filter(is_active=True).order_by("sort_order", "id")
    return paginated_response([{"id": d.id, "code": d.code, "name": d.name, "sort_order": d.sort_order} for d in depts])


@router.post("")
async def create_department(data: DepartmentCreate, user: User = Depends(require_permission("settings"))):
    code = data.code.strip()
    if await Department.filter(code=code).exists():
        raise HTTPException(status_code=400, detail="部门编码已存在")
    max_sort = await Department.all().order_by("-sort_order").first()
    sort_order = (max_sort.sort_order + 1) if max_sort else 1
    d = await Department.create(code=code, name=data.name.strip(), sort_order=sort_order)
    return {"id": d.id, "message": "添加成功"}


@router.put("/{dept_id}")
async def update_department(dept_id: int, data: DepartmentUpdate, user: User = Depends(require_permission("settings"))):
    d = await Department.filter(id=dept_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="部门不存在")
    if data.name:
        d.name = data.name.strip()
    if data.code:
        if data.code != d.code and await Department.filter(code=data.code).exists():
            raise HTTPException(status_code=400, detail="部门编码已存在")
        d.code = data.code.strip()
    await d.save()
    return {"message": "更新成功"}


@router.delete("/{dept_id}")
async def delete_department(dept_id: int, user: User = Depends(require_permission("settings"))):
    from app.models.department import Employee
    d = await Department.filter(id=dept_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="部门不存在")
    active_employees = await Employee.filter(department=d, is_active=True).count()
    if active_employees > 0:
        raise HTTPException(status_code=400, detail=f"该部门下有 {active_employees} 名在职员工，无法删除")
    d.is_active = False
    await d.save()
    return {"message": "删除成功"}
