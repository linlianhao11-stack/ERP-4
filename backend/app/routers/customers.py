from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from app.auth.dependencies import get_current_user, require_permission
from app.models import User, Customer, Order, OrderItem
from app.models.customer_balance import CustomerAccountBalance
from app.schemas.customer import CustomerCreate
from app.utils.query_helpers import paginated_query

router = APIRouter(prefix="/api/customers", tags=["客户管理"])


@router.get("")
async def list_customers(keyword: Optional[str] = None, limit: int = 200, offset: int = 0, user: User = Depends(require_permission("customer", "sales", "finance"))):
    customers, total = await paginated_query(
        Customer, filters={"is_active": True}, keyword=keyword,
        keyword_fields=["name", "phone"], order_by="name", offset=offset, limit=limit
    )
    return {"items": [{"id": c.id, "name": c.name, "contact_person": c.contact_person, "phone": c.phone,
             "address": c.address, "tax_id": c.tax_id, "bank_name": c.bank_name, "bank_account": c.bank_account,
             "balance": float(c.balance), "rebate_balance": float(c.rebate_balance)} for c in customers], "total": total}


@router.post("")
async def create_customer(data: CustomerCreate, user: User = Depends(require_permission("customer", "sales"))):
    c = await Customer.create(**data.model_dump())
    return {"id": c.id, "message": "创建成功"}


@router.put("/{customer_id}")
async def update_customer(customer_id: int, data: CustomerCreate, user: User = Depends(require_permission("customer", "sales"))):
    c = await Customer.filter(id=customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="客户不存在")
    await Customer.filter(id=customer_id).update(**data.model_dump())
    return {"message": "更新成功"}


@router.delete("/{customer_id}")
async def delete_customer(customer_id: int, user: User = Depends(require_permission("customer", "sales"))):
    c = await Customer.filter(id=customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="客户不存在")
    has_account_balance = await CustomerAccountBalance.filter(
        customer_id=customer_id, rebate_balance__gt=0
    ).exists()
    if c.balance != 0 or c.rebate_balance != 0 or has_account_balance:
        raise HTTPException(status_code=400, detail="客户有未结清款项或返利余额，无法删除")
    # Check for associated orders before deletion
    order_count = await Order.filter(customer_id=customer_id).count()
    if order_count > 0:
        raise HTTPException(status_code=400, detail=f"该客户有 {order_count} 个关联订单，无法删除")
    c.is_active = False
    await c.save()
    return {"message": "删除成功"}


@router.get("/{customer_id}/transactions")
async def get_customer_transactions(customer_id: int, year: Optional[int] = None, month: Optional[int] = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user: User = Depends(require_permission("customer", "finance"))):
    customer = await Customer.filter(id=customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    query = Order.filter(customer_id=customer_id)
    if year and month:
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        query = query.filter(created_at__gte=start_date, created_at__lt=end_date)

    total = await query.count()
    orders = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size).select_related("warehouse", "creator", "employee")
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])

    stats = {
        "CASH": {"count": 0, "amount": 0, "profit": 0},
        "CREDIT": {"count": 0, "amount": 0, "profit": 0},
        "CONSIGN_OUT": {"count": 0, "amount": 0, "profit": 0},
        "CONSIGN_SETTLE": {"count": 0, "amount": 0, "profit": 0},
        "RETURN": {"count": 0, "amount": 0, "profit": 0}
    }

    transactions_list = []
    for o in orders:
        otype = o.order_type
        if otype in stats:
            stats[otype]["count"] += 1
            stats[otype]["amount"] += float(o.total_amount)
            stats[otype]["profit"] += float(o.total_profit)

        item = {
            "id": o.id, "order_no": o.order_no, "order_type": o.order_type,
            "warehouse_name": o.warehouse.name if o.warehouse else "-",
            "total_amount": float(o.total_amount),
            "paid_amount": float(o.paid_amount),
            "is_cleared": o.is_cleared, "remark": o.remark,
            "employee_name": o.employee.name if o.employee else "-",
            "creator_name": o.creator.display_name if o.creator else "-",
            "created_at": o.created_at.isoformat()
        }
        if has_finance:
            item["total_cost"] = float(o.total_cost)
            item["total_profit"] = float(o.total_profit)
        transactions_list.append(item)

    # 使用数据库聚合获取月份列表（避免拉取全量日期数据）
    from tortoise import connections
    conn = connections.get("default")
    month_rows = await conn.execute_query_dict(
        "SELECT DISTINCT TO_CHAR(created_at, 'YYYY-MM') as month FROM orders WHERE customer_id = $1 ORDER BY month DESC",
        [customer_id]
    )
    available_months = [r["month"] for r in month_rows]

    return {
        "customer": {"id": customer.id, "name": customer.name, "balance": float(customer.balance)},
        "stats": stats if has_finance else None,
        "transactions": transactions_list,
        "available_months": available_months,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
