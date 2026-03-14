"""应收服务层"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from tortoise import transactions
from app.models.ar_ap import ReceivableBill, ReceiptBill, ReceiptRefundBill, ReceivableWriteOff
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.models.order import Order
from app.utils.generators import generate_order_no
from app.logger import get_logger

logger = get_logger("ar_service")


async def create_receivable_bill(
    account_set_id: int,
    customer_id: int,
    order_id: int | None = None,
    total_amount: Decimal = Decimal("0"),
    status: str = "pending",
    creator=None,
    remark: str = "",
    bill_date: date | None = None,
) -> ReceivableBill:
    if bill_date is None:
        bill_date = date.today()
    received = total_amount if status == "completed" else Decimal("0")
    unreceived = total_amount - received
    rb = await ReceivableBill.create(
        bill_no=generate_order_no("YS"),
        account_set_id=account_set_id,
        customer_id=customer_id,
        order_id=order_id,
        bill_date=bill_date,
        total_amount=total_amount,
        received_amount=received,
        unreceived_amount=unreceived,
        status=status,
        remark=remark,
        creator=creator,
    )
    logger.info(f"创建应收单: {rb.bill_no}, 金额: {total_amount}, 状态: {status}")
    return rb


async def create_receipt_bill_for_payment(
    account_set_id: int,
    customer_id: int,
    receivable_bill: ReceivableBill | None,
    payment_id: int | None,
    amount: Decimal,
    payment_method: str,
    creator=None,
) -> ReceiptBill:
    receipt = await ReceiptBill.create(
        bill_no=generate_order_no("SK"),
        account_set_id=account_set_id,
        customer_id=customer_id,
        receivable_bill=receivable_bill,
        payment_id=payment_id,
        receipt_date=date.today(),
        amount=amount,
        payment_method=payment_method,
        status="confirmed",
        confirmed_by=creator,
        confirmed_at=datetime.now(timezone.utc),
        creator=creator,
    )
    logger.info(f"创建收款单: {receipt.bill_no}, 金额: {amount}")
    return receipt


async def confirm_receipt_bill(receipt_id: int, user) -> ReceiptBill:
    async with transactions.in_transaction():
        receipt = await ReceiptBill.filter(id=receipt_id).select_for_update().first()
        if not receipt:
            raise ValueError("收款单不存在")
        if receipt.status != "draft":
            raise ValueError("只有草稿状态的收款单可以确认")
        receipt.status = "confirmed"
        receipt.confirmed_by = user
        receipt.confirmed_at = datetime.now(timezone.utc)
        await receipt.save()

        if receipt.receivable_bill_id:
            rb = await ReceivableBill.filter(id=receipt.receivable_bill_id).select_for_update().first()
            if rb:
                rb.received_amount += receipt.amount
                rb.unreceived_amount = rb.total_amount - rb.received_amount
                if rb.unreceived_amount <= 0:
                    rb.status = "completed"
                else:
                    rb.status = "partial"
                await rb.save()

        # 退款收款单确认后，更新退货订单状态
        if receipt.bill_type == "return_refund" and receipt.return_order_id:
            try:
                return_order = await Order.filter(id=receipt.return_order_id).select_for_update().first()
                if return_order:
                    return_order.is_cleared = True
                    await return_order.save()
                    logger.info(f"退款确认，订单 {return_order.order_no} 已结清")
            except Exception as e:
                logger.error(f"退款确认更新订单状态失败: {e}")

    logger.info(f"确认收款单: {receipt.bill_no}")
    return receipt


async def confirm_receipt_refund(refund_id: int, user) -> ReceiptRefundBill:
    async with transactions.in_transaction():
        refund = await ReceiptRefundBill.filter(id=refund_id).select_for_update().first()
        if not refund:
            raise ValueError("收款退款单不存在")
        if refund.status != "draft":
            raise ValueError("只有草稿状态的退款单可以确认")
        refund.status = "confirmed"
        refund.confirmed_by = user
        refund.confirmed_at = datetime.now(timezone.utc)
        await refund.save()

        original = await ReceiptBill.filter(id=refund.original_receipt_id).first()
        if original and original.receivable_bill_id:
            rb = await ReceivableBill.filter(id=original.receivable_bill_id).select_for_update().first()
            if rb:
                rb.received_amount -= refund.amount
                rb.unreceived_amount = rb.total_amount - rb.received_amount
                if rb.received_amount <= 0:
                    rb.status = "pending"
                else:
                    rb.status = "partial"
                await rb.save()

    logger.info(f"确认收款退款单: {refund.bill_no}")
    return refund


async def confirm_write_off(write_off_id: int, user) -> ReceivableWriteOff:
    async with transactions.in_transaction():
        wo = await ReceivableWriteOff.filter(id=write_off_id).select_for_update().first()
        if not wo:
            raise ValueError("核销单不存在")
        if wo.status != "draft":
            raise ValueError("只有草稿状态的核销单可以确认")
        wo.status = "confirmed"
        wo.confirmed_by = user
        wo.confirmed_at = datetime.now(timezone.utc)
        await wo.save()

        rb = await ReceivableBill.filter(id=wo.receivable_bill_id).select_for_update().first()
        if rb:
            rb.received_amount += wo.amount
            rb.unreceived_amount = rb.total_amount - rb.received_amount
            if rb.unreceived_amount <= 0:
                rb.status = "completed"
            else:
                rb.status = "partial"
            await rb.save()

    logger.info(f"确认核销单: {wo.bill_no}")
    return wo


from app.utils.voucher_no import next_voucher_no as _next_voucher_no


async def _get_employee_department_from_receivable(receivable_bill_id: int | None):
    """从应收单关联的订单中获取员工和部门"""
    if not receivable_bill_id:
        return None, None
    rb = await ReceivableBill.filter(id=receivable_bill_id).first()
    if not rb or not rb.order_id:
        return None, None
    order = await Order.filter(id=rb.order_id).prefetch_related("employee__department").first()
    if not order or not order.employee:
        return None, None
    employee = order.employee
    department = employee.department if hasattr(employee, "department") else None
    return employee, department


async def generate_ar_vouchers(account_set_id: int, period_name: str, user) -> list:
    period = await AccountingPeriod.filter(
        account_set_id=account_set_id, period_name=period_name
    ).first()
    if not period:
        raise ValueError(f"会计期间 {period_name} 不存在")

    # 根据年月计算期间起止日期
    period_start = date(period.year, period.month, 1)
    _, last_day = calendar.monthrange(period.year, period.month)
    period_end = date(period.year, period.month, last_day)

    bank_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1002", is_active=True
    ).first()
    ar_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1122", is_active=True
    ).first()
    advance_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="2203", is_active=True
    ).first()
    if not bank_account or not ar_account:
        raise ValueError("缺少必要科目：银行存款(1002)或应收账款(1122)")

    vouchers = []

    # 收款单 → 借 银行存款1002，贷 应收账款1122（仅处理当前期间）
    receipts = await ReceiptBill.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None,
        receipt_date__gte=period_start, receipt_date__lte=period_end,
    ).all()
    for r in receipts:
        employee, department = await _get_employee_department_from_receivable(r.receivable_bill_id)
        async with transactions.in_transaction():
            vno = await _next_voucher_no(account_set_id, "收", period_name)
            v = await Voucher.create(
                account_set_id=account_set_id,
                voucher_type="收",
                voucher_no=vno,
                period_name=period_name,
                voucher_date=r.receipt_date,
                summary=f"收款单 {r.bill_no}",
                total_debit=r.amount,
                total_credit=r.amount,
                status="draft",
                creator=user,
                source_type="receipt_bill",
                source_bill_id=r.id,
            )
            await VoucherEntry.create(
                voucher=v, line_no=1,
                account_id=bank_account.id,
                summary=f"收款 {r.bill_no}",
                debit_amount=r.amount,
                credit_amount=Decimal("0"),
                aux_employee=employee if bank_account.aux_employee else None,
                aux_department=department if bank_account.aux_department else None,
            )
            await VoucherEntry.create(
                voucher=v, line_no=2,
                account_id=ar_account.id,
                summary=f"收款 {r.bill_no}",
                debit_amount=Decimal("0"),
                credit_amount=r.amount,
                aux_customer_id=r.customer_id,
                aux_employee=employee if ar_account.aux_employee else None,
                aux_department=department if ar_account.aux_department else None,
            )
            r.voucher = v
            r.voucher_no = vno
            await r.save()
            vouchers.append({"id": v.id, "voucher_no": vno, "source": f"收款单 {r.bill_no}"})

    # 收款退款单 → 借 应收账款1122，贷 银行存款1002（仅处理当前期间）
    refunds = await ReceiptRefundBill.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None,
        refund_date__gte=period_start, refund_date__lte=period_end,
    ).all()
    for rf in refunds:
        # 通过原始收款单的应收单获取员工/部门
        original_receipt = await ReceiptBill.filter(id=rf.original_receipt_id).first()
        receivable_id = original_receipt.receivable_bill_id if original_receipt else None
        employee, department = await _get_employee_department_from_receivable(receivable_id)
        async with transactions.in_transaction():
            vno = await _next_voucher_no(account_set_id, "收", period_name)
            v = await Voucher.create(
                account_set_id=account_set_id,
                voucher_type="收",
                voucher_no=vno,
                period_name=period_name,
                voucher_date=rf.refund_date,
                summary=f"收款退款 {rf.bill_no}",
                total_debit=rf.amount,
                total_credit=rf.amount,
                status="draft",
                creator=user,
                source_type="receipt_refund_bill",
                source_bill_id=rf.id,
            )
            await VoucherEntry.create(
                voucher=v, line_no=1,
                account_id=ar_account.id,
                summary=f"收款退款 {rf.bill_no}",
                debit_amount=rf.amount,
                credit_amount=Decimal("0"),
                aux_customer_id=rf.customer_id,
                aux_employee=employee if ar_account.aux_employee else None,
                aux_department=department if ar_account.aux_department else None,
            )
            await VoucherEntry.create(
                voucher=v, line_no=2,
                account_id=bank_account.id,
                summary=f"收款退款 {rf.bill_no}",
                debit_amount=Decimal("0"),
                credit_amount=rf.amount,
                aux_employee=employee if bank_account.aux_employee else None,
                aux_department=department if bank_account.aux_department else None,
            )
            rf.voucher = v
            rf.voucher_no = vno
            await rf.save()
            vouchers.append({"id": v.id, "voucher_no": vno, "source": f"收款退款 {rf.bill_no}"})

    # 核销单 → 借 预收账款2203，贷 应收账款1122（仅处理当前期间）
    if advance_account:
        write_offs = await ReceivableWriteOff.filter(
            account_set_id=account_set_id, status="confirmed", voucher_id=None,
            write_off_date__gte=period_start, write_off_date__lte=period_end,
        ).all()
        for wo in write_offs:
            employee, department = await _get_employee_department_from_receivable(wo.receivable_bill_id)
            async with transactions.in_transaction():
                vno = await _next_voucher_no(account_set_id, "记", period_name)
                v = await Voucher.create(
                    account_set_id=account_set_id,
                    voucher_type="记",
                    voucher_no=vno,
                    period_name=period_name,
                    voucher_date=wo.write_off_date,
                    summary=f"核销 {wo.bill_no}",
                    total_debit=wo.amount,
                    total_credit=wo.amount,
                    status="draft",
                    creator=user,
                    source_type="receivable_write_off",
                    source_bill_id=wo.id,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=1,
                    account_id=advance_account.id,
                    summary=f"核销 {wo.bill_no}",
                    debit_amount=wo.amount,
                    credit_amount=Decimal("0"),
                    aux_customer_id=wo.customer_id,
                    aux_employee=employee if advance_account.aux_employee else None,
                    aux_department=department if advance_account.aux_department else None,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=2,
                    account_id=ar_account.id,
                    summary=f"核销 {wo.bill_no}",
                    debit_amount=Decimal("0"),
                    credit_amount=wo.amount,
                    aux_customer_id=wo.customer_id,
                    aux_employee=employee if ar_account.aux_employee else None,
                    aux_department=department if ar_account.aux_department else None,
                )
                wo.voucher = v
                wo.voucher_no = vno
                await wo.save()
                vouchers.append({"id": v.id, "voucher_no": vno, "source": f"核销 {wo.bill_no}"})

    # 销售退货单 → 红字冲销出库凭证：借 发出商品1407（负数），贷 库存商品1405（负数）
    shipped_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1407", is_active=True
    ).first()
    inventory_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1405", is_active=True
    ).first()

    if shipped_acct and inventory_acct:
        return_orders = await Order.filter(
            account_set_id=account_set_id,
            order_type="RETURN",
            voucher_id=None,
            created_at__gte=period_start,
            created_at__lte=datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc),
        ).all()
        for ro in return_orders:
            cost = abs(ro.total_cost)
            if cost <= 0:
                continue
            async with transactions.in_transaction():
                p_name = f"{ro.created_at.year}-{ro.created_at.month:02d}"
                vno = await _next_voucher_no(account_set_id, "记", p_name)
                v = await Voucher.create(
                    account_set_id=account_set_id,
                    voucher_type="记",
                    voucher_no=vno,
                    period_name=p_name,
                    voucher_date=ro.created_at.date() if hasattr(ro.created_at, 'date') else ro.created_at,
                    summary=f"销售退货冲回 {ro.order_no}",
                    total_debit=-cost,
                    total_credit=-cost,
                    status="draft",
                    creator=user,
                    source_type="sales_return",
                    source_bill_id=ro.id,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=1,
                    account_id=shipped_acct.id,
                    summary=f"销售退货冲回 {ro.order_no}",
                    debit_amount=-cost,
                    credit_amount=Decimal("0"),
                )
                await VoucherEntry.create(
                    voucher=v, line_no=2,
                    account_id=inventory_acct.id,
                    summary=f"销售退货冲回 {ro.order_no}",
                    debit_amount=Decimal("0"),
                    credit_amount=-cost,
                )
                ro.voucher = v
                ro.voucher_no = vno
                await ro.save()
                vouchers.append({"id": v.id, "voucher_no": vno, "source": f"销售退货 {ro.order_no}"})

    logger.info(f"AR凭证生成完成: {len(vouchers)} 张")
    return vouchers
