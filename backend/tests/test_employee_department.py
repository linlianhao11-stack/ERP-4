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


@pytest.mark.anyio
async def test_voucher_entry_with_aux_employee_department():
    from app.models.accounting import AccountSet, ChartOfAccount
    from app.models.voucher import Voucher, VoucherEntry
    from datetime import date

    dept = await Department.create(code="SALES", name="销售部")
    emp = await Employee.create(code="EMP001", name="张三", department=dept, is_salesperson=True)
    acct_set = await AccountSet.create(code="QL", name="启领", start_year=2026, start_month=1, current_period="2026-03")
    coa = await ChartOfAccount.create(
        account_set=acct_set, code="6001", name="主营业务收入",
        level=1, category="profit_loss", direction="credit",
        is_leaf=True, aux_employee=True, aux_department=True
    )
    voucher = await Voucher.create(
        account_set=acct_set, voucher_type="记", voucher_no="JZ-202603-001",
        period_name="2026-03", voucher_date=date(2026, 3, 14),
        total_debit=1000, total_credit=1000
    )
    entry = await VoucherEntry.create(
        voucher=voucher, line_no=1, account=coa,
        debit_amount=0, credit_amount=1000,
        aux_employee=emp, aux_department=dept
    )
    loaded = await VoucherEntry.get(id=entry.id).prefetch_related("aux_employee", "aux_department")
    assert loaded.aux_employee.name == "张三"
    assert loaded.aux_department.name == "销售部"
