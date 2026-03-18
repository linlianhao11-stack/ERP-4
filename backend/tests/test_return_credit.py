"""退货未退款 → 客户在账资金 测试

验证所有类型退货（CASH/CREDIT 原单）在未勾选"已退款"时，
退货金额都能正确转为客户在账资金（balance 减少 = 预付增加）。
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from types import SimpleNamespace

from app.models import Customer, Order, User
from app.constants import OrderType
from app.services.order_service import process_order_settlement


def _make_data(order_type, refunded=False, related_order_id=None, **kw):
    """构造模拟的 order data 对象"""
    return SimpleNamespace(
        order_type=order_type,
        refunded=refunded,
        related_order_id=related_order_id,
        use_credit=False,
        payment_method=None,
        refund_method=None,
        **kw,
    )


@pytest.mark.asyncio
async def test_cash_return_no_refund_creates_credit():
    """CASH 原单退货 + 未退款 → 客户余额减少（形成在账资金）"""
    user = await User.create(username="t_ret1", password_hash="x", display_name="T")
    customer = await Customer.create(name="测试客户-现款退货", balance=Decimal("0"))
    original = await Order.create(
        order_no="SO-TEST-CASH-001", order_type=OrderType.CASH,
        customer=customer, total_amount=Decimal("5000"),
        paid_amount=Decimal("5000"), is_cleared=True, creator=user,
    )
    return_order = await Order.create(
        order_no="SO-TEST-RET-001", order_type=OrderType.RETURN,
        customer=customer, total_amount=Decimal("-5000"),
        related_order_id=original.id, creator=user,
    )

    data = _make_data(OrderType.RETURN, refunded=False, related_order_id=original.id)
    await process_order_settlement(
        data, customer, return_order, Decimal("-5000"), user, return_order.order_no
    )

    updated = await Customer.filter(id=customer.id).first()
    # balance 应为 -5000（负数 = 客户有在账资金 5000）
    assert updated.balance == Decimal("-5000"), (
        f"CASH 退货未退款应产生在账资金，期望 balance=-5000，实际 {updated.balance}"
    )


@pytest.mark.asyncio
async def test_credit_return_no_refund_creates_credit():
    """CREDIT 原单退货 + 未退款 → 客户余额减少（形成在账资金）"""
    user = await User.create(username="t_ret2", password_hash="x", display_name="T")
    customer = await Customer.create(name="测试客户-账期退货", balance=Decimal("3000"))
    original = await Order.create(
        order_no="SO-TEST-CRED-001", order_type=OrderType.CREDIT,
        customer=customer, total_amount=Decimal("3000"),
        creator=user,
    )
    return_order = await Order.create(
        order_no="SO-TEST-RET-002", order_type=OrderType.RETURN,
        customer=customer, total_amount=Decimal("-3000"),
        related_order_id=original.id, creator=user,
    )

    data = _make_data(OrderType.RETURN, refunded=False, related_order_id=original.id)
    await process_order_settlement(
        data, customer, return_order, Decimal("-3000"), user, return_order.order_no
    )

    updated = await Customer.filter(id=customer.id).first()
    # 原 balance=3000（欠款），退货 -3000 → balance=0（两清）
    assert updated.balance == Decimal("0"), (
        f"CREDIT 退货未退款应冲减欠款，期望 balance=0，实际 {updated.balance}"
    )


@pytest.mark.asyncio
async def test_return_with_refund_no_balance_change():
    """退货 + 已退款 → 客户余额不变（钱已退给客户）"""
    user = await User.create(username="t_ret3", password_hash="x", display_name="T")
    customer = await Customer.create(name="测试客户-已退款", balance=Decimal("0"))
    original = await Order.create(
        order_no="SO-TEST-CASH-002", order_type=OrderType.CASH,
        customer=customer, total_amount=Decimal("2000"),
        paid_amount=Decimal("2000"), is_cleared=True, creator=user,
    )
    return_order = await Order.create(
        order_no="SO-TEST-RET-003", order_type=OrderType.RETURN,
        customer=customer, total_amount=Decimal("-2000"),
        related_order_id=original.id, refunded=True, creator=user,
    )

    data = _make_data(OrderType.RETURN, refunded=True, related_order_id=original.id)
    await process_order_settlement(
        data, customer, return_order, Decimal("-2000"), user, return_order.order_no
    )

    updated = await Customer.filter(id=customer.id).first()
    # 已退款给客户，余额不应变动
    assert updated.balance == Decimal("0"), (
        f"已退款退货不应改变余额，期望 balance=0，实际 {updated.balance}"
    )


@pytest.mark.asyncio
async def test_partial_return_credit():
    """部分退货 → 只产生退货金额的在账资金"""
    user = await User.create(username="t_ret4", password_hash="x", display_name="T")
    customer = await Customer.create(name="测试客户-部分退货", balance=Decimal("0"))
    original = await Order.create(
        order_no="SO-TEST-CASH-003", order_type=OrderType.CASH,
        customer=customer, total_amount=Decimal("10000"),
        paid_amount=Decimal("10000"), is_cleared=True, creator=user,
    )
    return_order = await Order.create(
        order_no="SO-TEST-RET-004", order_type=OrderType.RETURN,
        customer=customer, total_amount=Decimal("-3000"),
        related_order_id=original.id, creator=user,
    )

    data = _make_data(OrderType.RETURN, refunded=False, related_order_id=original.id)
    await process_order_settlement(
        data, customer, return_order, Decimal("-3000"), user, return_order.order_no
    )

    updated = await Customer.filter(id=customer.id).first()
    assert updated.balance == Decimal("-3000"), (
        f"部分退货应产生对应金额在账资金，期望 balance=-3000，实际 {updated.balance}"
    )
