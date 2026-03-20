"""退款确认逻辑测试

验证销售退款 / 采购退款确认后：
- 正确创建 ReceiptRefundBill / DisbursementRefundBill
- 订单 / 退货单状态正确更新
- 重复确认被拒绝
"""
from __future__ import annotations

import pytest
from decimal import Decimal

from app.models import (
    AccountSet, Customer, Order, User, Supplier,
    ReceiptRefundBill, DisbursementRefundBill,
)
from app.models.purchase import PurchaseReturn, PurchaseOrder


# ---------------------------------------------------------------------------
# 辅助函数：创建测试基础数据
# ---------------------------------------------------------------------------

async def _create_base_data():
    """创建通用的用户和账套"""
    user = await User.create(username="refund_tester", password_hash="x", display_name="退款测试员")
    account_set = await AccountSet.create(
        code="REFUND_TEST", name="退款测试账套",
        start_year=2026, start_month=1, current_period="2026-03",
    )
    return user, account_set


async def _create_sales_return(user, account_set, customer, *, refunded=True, is_cleared=False):
    """创建一个销售退货订单"""
    original = await Order.create(
        order_no="SO-ORIG-001", order_type="CASH",
        customer=customer, total_amount=Decimal("5000"),
        paid_amount=Decimal("5000"), is_cleared=True,
        account_set=account_set, creator=user,
    )
    return_order = await Order.create(
        order_no="SO-RET-001", order_type="RETURN",
        customer=customer, total_amount=Decimal("-5000"),
        related_order=original, refunded=refunded,
        is_cleared=is_cleared, refund_method="银行转账",
        refund_info="退款至工行尾号1234",
        account_set=account_set, creator=user,
    )
    return original, return_order


async def _create_purchase_return(user, account_set, supplier, *, is_refunded=True, refund_status="pending"):
    """创建一个采购退货单"""
    po = await PurchaseOrder.create(
        po_no="PO-ORIG-001", supplier=supplier,
        total_amount=Decimal("8000"), status="completed",
        account_set=account_set, creator=user,
    )
    pr = await PurchaseReturn.create(
        return_no="PR-001", purchase_order=po,
        supplier=supplier, account_set=account_set,
        total_amount=Decimal("3000"),
        is_refunded=is_refunded, refund_status=refund_status,
        refund_method="银行转账", refund_info="退款至建行尾号5678",
        created_by=user,
    )
    return po, pr


# ---------------------------------------------------------------------------
# 销售退款确认测试
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_sales_refund_creates_receipt_refund_bill():
    """确认销售退款后应创建 ReceiptRefundBill，status=confirmed，金额正确"""
    from app.routers.refunds import _confirm_sales_refund

    user, account_set = await _create_base_data()
    customer = await Customer.create(name="销售退款客户A", balance=Decimal("0"))
    _orig, return_order = await _create_sales_return(user, account_set, customer)

    result = await _confirm_sales_refund(return_order.id, user)
    assert result["message"] == "退款确认成功"
    assert result["refund_bill_no"].startswith("SKTK")

    # 验证 ReceiptRefundBill 记录
    bill = await ReceiptRefundBill.filter(bill_no=result["refund_bill_no"]).first()
    assert bill is not None
    assert bill.status == "confirmed"
    assert bill.amount == Decimal("5000")
    assert bill.customer_id == customer.id


@pytest.mark.asyncio
async def test_confirm_sales_refund_clears_order():
    """确认销售退款后退货订单应标记为 is_cleared=True"""
    from app.routers.refunds import _confirm_sales_refund

    user, account_set = await _create_base_data()
    customer = await Customer.create(name="销售退款客户B", balance=Decimal("0"))
    _orig, return_order = await _create_sales_return(user, account_set, customer)

    await _confirm_sales_refund(return_order.id, user)

    updated = await Order.filter(id=return_order.id).first()
    assert updated.is_cleared is True
    assert updated.paid_amount == Decimal("5000")


# ---------------------------------------------------------------------------
# 采购退款确认测试
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_purchase_refund_creates_disbursement_refund_bill():
    """确认采购退款后应创建 DisbursementRefundBill，status=confirmed"""
    from app.routers.refunds import _confirm_purchase_refund

    user, account_set = await _create_base_data()
    supplier = await Supplier.create(name="采购退款供应商A")
    _po, pr = await _create_purchase_return(user, account_set, supplier)

    result = await _confirm_purchase_refund(pr.id, user)
    assert result["message"] == "退款确认成功"
    assert result["refund_bill_no"].startswith("FKTK")

    # 验证 DisbursementRefundBill 记录
    bill = await DisbursementRefundBill.filter(bill_no=result["refund_bill_no"]).first()
    assert bill is not None
    assert bill.status == "confirmed"
    assert bill.amount == Decimal("3000")
    assert bill.supplier_id == supplier.id


@pytest.mark.asyncio
async def test_confirm_purchase_refund_updates_status():
    """确认采购退款后退货单 refund_status 应为 confirmed"""
    from app.routers.refunds import _confirm_purchase_refund

    user, account_set = await _create_base_data()
    supplier = await Supplier.create(name="采购退款供应商B")
    _po, pr = await _create_purchase_return(user, account_set, supplier)

    await _confirm_purchase_refund(pr.id, user)

    updated = await PurchaseReturn.filter(id=pr.id).first()
    assert updated.refund_status == "confirmed"


# ---------------------------------------------------------------------------
# 边界情况测试
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cannot_confirm_already_cleared_sales_refund():
    """已结清的退货订单不能再次确认退款"""
    from fastapi import HTTPException
    from app.routers.refunds import _confirm_sales_refund

    user, account_set = await _create_base_data()
    customer = await Customer.create(name="已结清客户", balance=Decimal("0"))
    _orig, return_order = await _create_sales_return(
        user, account_set, customer, is_cleared=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        await _confirm_sales_refund(return_order.id, user)
    assert exc_info.value.status_code == 400
    assert "不存在或已结清" in exc_info.value.detail
