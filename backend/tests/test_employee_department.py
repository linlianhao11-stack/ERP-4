import pytest
from app.models.department import Department, Employee


@pytest.mark.anyio
async def test_create_department():
    dept = await Department.create(code="SALES", name="销售部")
    assert dept.id is not None
    assert dept.code == "SALES"
    assert dept.is_active is True


@pytest.mark.anyio
async def test_create_employee_with_department():
    dept = await Department.create(code="SALES", name="销售部")
    emp = await Employee.create(
        code="EMP001", name="张三", phone="13800138000",
        department=dept, is_salesperson=True
    )
    assert emp.id is not None
    assert emp.is_salesperson is True
    loaded = await Employee.get(id=emp.id).prefetch_related("department")
    assert loaded.department.code == "SALES"


@pytest.mark.anyio
async def test_employee_without_department():
    emp = await Employee.create(code="EMP002", name="李四")
    assert emp.department_id is None
    assert emp.is_salesperson is False
