from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.auth.dependencies import get_current_user, require_permission
from app.models import User
from app.models.department import Department, Employee
from app.utils.response import paginated_response

router = APIRouter(prefix="/api/employees", tags=["员工管理"])


class EmployeeCreate(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    phone: str = ""
    department_id: Optional[int] = None
    is_salesperson: bool = False


class EmployeeUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1)
    name: Optional[str] = Field(default=None, min_length=1)
    phone: Optional[str] = None
    department_id: Optional[int] = None
    is_salesperson: Optional[bool] = None


@router.get("")
async def list_employees(
    is_salesperson: Optional[bool] = None,
    department_id: Optional[int] = None,
    user: User = Depends(get_current_user),
):
    qs = Employee.filter(is_active=True)
    if is_salesperson is not None:
        qs = qs.filter(is_salesperson=is_salesperson)
    if department_id is not None:
        qs = qs.filter(department_id=department_id)
    employees = await qs.order_by("id").prefetch_related("department")
    return paginated_response([
        {
            "id": e.id, "code": e.code, "name": e.name,
            "phone": e.phone,
            "department_id": e.department_id,
            "department_name": e.department.name if e.department else None,
            "is_salesperson": e.is_salesperson,
        }
        for e in employees
    ])


@router.post("")
async def create_employee(data: EmployeeCreate, user: User = Depends(require_permission("settings"))):
    code = data.code.strip()
    if await Employee.filter(code=code).exists():
        raise HTTPException(status_code=400, detail="员工编码已存在")
    if data.department_id:
        dept = await Department.filter(id=data.department_id, is_active=True).first()
        if not dept:
            raise HTTPException(status_code=400, detail="部门不存在")
    emp = await Employee.create(
        code=code, name=data.name.strip(), phone=data.phone or "",
        department_id=data.department_id, is_salesperson=data.is_salesperson
    )
    return {"id": emp.id, "message": "添加成功"}


@router.put("/{emp_id}")
async def update_employee(emp_id: int, data: EmployeeUpdate, user: User = Depends(require_permission("settings"))):
    emp = await Employee.filter(id=emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="员工不存在")
    if data.name:
        emp.name = data.name.strip()
    if data.code:
        if data.code != emp.code and await Employee.filter(code=data.code).exists():
            raise HTTPException(status_code=400, detail="员工编码已存在")
        emp.code = data.code.strip()
    if data.phone is not None:
        emp.phone = data.phone
    if data.department_id is not None:
        emp.department_id = data.department_id if data.department_id > 0 else None
    if data.is_salesperson is not None:
        emp.is_salesperson = data.is_salesperson
    await emp.save()
    return {"message": "更新成功"}


@router.delete("/{emp_id}")
async def delete_employee(emp_id: int, user: User = Depends(require_permission("settings"))):
    emp = await Employee.filter(id=emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="员工不存在")
    emp.is_active = False
    await emp.save()
    return {"message": "删除成功"}
