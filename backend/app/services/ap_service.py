"""应付服务层"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from tortoise import transactions
from app.models.ar_ap import PayableBill, DisbursementBill, DisbursementRefundBill
from app.models.purchase import PurchaseReturn, PurchaseReturnItem, PurchaseOrderItem
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.utils.generators import generate_order_no
from app.logger import get_logger

logger = get_logger("ap_service")


async def create_payable_bill(
    account_set_id: int,
    supplier_id: int,
    purchase_order_id: int | None = None,
    total_amount: Decimal = Decimal("0"),
    status: str = "pending",
    creator=None,
    remark: str = "",
    bill_date: date | None = None,
) -> PayableBill:
    if bill_date is None:
        bill_date = date.today()
    paid = total_amount if status == "completed" else Decimal("0")
    unpaid = total_amount - paid
    pb = await PayableBill.create(
        bill_no=generate_order_no("YF"),
        account_set_id=account_set_id,
        supplier_id=supplier_id,
        purchase_order_id=purchase_order_id,
        bill_date=bill_date,
        total_amount=total_amount,
        paid_amount=paid,
        unpaid_amount=unpaid,
        status=status,
        remark=remark,
        creator=creator,
    )
    logger.info(f"创建应付单: {pb.bill_no}, 金额: {total_amount}, 状态: {status}")
    return pb


async def create_disbursement_for_po_payment(
    account_set_id: int,
    supplier_id: int,
    payable_bill: PayableBill | None,
    amount: Decimal,
    disbursement_method: str,
    creator=None,
) -> DisbursementBill:
    async with transactions.in_transaction():
        db = await DisbursementBill.create(
            bill_no=generate_order_no("FK"),
            account_set_id=account_set_id,
            supplier_id=supplier_id,
            payable_bill=payable_bill,
            disbursement_date=date.today(),
            amount=amount,
            disbursement_method=disbursement_method,
            status="confirmed",
            confirmed_by=creator,
            confirmed_at=datetime.now(timezone.utc),
            creator=creator,
        )

        # 更新关联应付单（加锁防止并发）
        if payable_bill:
            pb = await PayableBill.filter(id=payable_bill.id).select_for_update().first()
            pb.paid_amount += amount
            pb.unpaid_amount = pb.total_amount - pb.paid_amount
            pb.status = "completed" if pb.unpaid_amount <= 0 else "partial"
            await pb.save()

    logger.info(f"创建付款单: {db.bill_no}, 金额: {amount}")
    return db


async def confirm_disbursement_bill(disbursement_id: int, user) -> DisbursementBill:
    async with transactions.in_transaction():
        db = await DisbursementBill.filter(id=disbursement_id).select_for_update().first()
        if not db:
            raise ValueError("付款单不存在")
        if db.status != "draft":
            raise ValueError("只有草稿状态的付款单可以确认")
        db.status = "confirmed"
        db.confirmed_by = user
        db.confirmed_at = datetime.now(timezone.utc)
        await db.save()

        if db.payable_bill_id:
            pb = await PayableBill.filter(id=db.payable_bill_id).select_for_update().first()
            if pb:
                pb.paid_amount += db.amount
                pb.unpaid_amount = pb.total_amount - pb.paid_amount
                if pb.unpaid_amount <= 0:
                    pb.status = "completed"
                else:
                    pb.status = "partial"
                await pb.save()

        # 退款付款单确认后，更新采购退货单状态
        if db.bill_type == "return_refund" and db.purchase_return_id:
            try:
                from app.models.purchase import PurchaseReturn
                pr = await PurchaseReturn.filter(id=db.purchase_return_id).select_for_update().first()
                if pr:
                    pr.is_refunded = True
                    pr.refund_status = "completed"
                    await pr.save()
                    logger.info(f"退款确认，采购退货单 {pr.return_no} 已标记退款完成")
            except Exception as e:
                logger.error(f"退款确认更新采购退货单状态失败: {e}")

    logger.info(f"确认付款单: {db.bill_no}")
    return db


async def confirm_disbursement_refund(refund_id: int, user) -> DisbursementRefundBill:
    async with transactions.in_transaction():
        refund = await DisbursementRefundBill.filter(id=refund_id).select_for_update().first()
        if not refund:
            raise ValueError("付款退款单不存在")
        if refund.status != "draft":
            raise ValueError("只有草稿状态的退款单可以确认")
        refund.status = "confirmed"
        refund.confirmed_by = user
        refund.confirmed_at = datetime.now(timezone.utc)
        await refund.save()

        original = await DisbursementBill.filter(id=refund.original_disbursement_id).first()
        if original and original.payable_bill_id:
            pb = await PayableBill.filter(id=original.payable_bill_id).select_for_update().first()
            if pb:
                pb.paid_amount -= refund.amount
                pb.unpaid_amount = pb.total_amount - pb.paid_amount
                if pb.paid_amount <= 0:
                    pb.status = "pending"
                else:
                    pb.status = "partial"
                await pb.save()

    logger.info(f"确认付款退款单: {refund.bill_no}")
    return refund


from app.utils.voucher_no import next_voucher_no as _next_voucher_no


async def generate_ap_vouchers(account_set_id: int, period_names: list[str], user) -> dict:
    # 科目查询只执行一次，放在循环外
    bank_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1002", is_active=True
    ).first()
    ap_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="2202", is_active=True
    ).first()
    if not bank_account or not ap_account:
        raise ValueError("缺少必要科目：银行存款(1002)或应付账款(2202)")

    inventory_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1405", is_active=True
    ).first()
    input_tax_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="222101", is_active=True
    ).first()

    vouchers = []
    summary = {}

    for period_name in period_names:
        period = await AccountingPeriod.filter(
            account_set_id=account_set_id, period_name=period_name
        ).first()
        if not period:
            summary[period_name] = {"count": 0, "skipped": True, "reason": "期间不存在"}
            continue
        if period.is_closed:
            summary[period_name] = {"count": 0, "skipped": True, "reason": "期间已结账"}
            continue

        period_start = date(period.year, period.month, 1)
        _, last_day = calendar.monthrange(period.year, period.month)
        period_end = date(period.year, period.month, last_day)
        month_vouchers = []

        # 付款单 → 借 应付账款2202，贷 银行存款1002
        disbursements = await DisbursementBill.filter(
            account_set_id=account_set_id, status="confirmed", voucher_id=None,
            disbursement_date__gte=period_start, disbursement_date__lte=period_end,
        ).all()
        for d in disbursements:
            async with transactions.in_transaction():
                vno = await _next_voucher_no(account_set_id, "付", period_name)
                v = await Voucher.create(
                    account_set_id=account_set_id,
                    voucher_type="付",
                    voucher_no=vno,
                    period_name=period_name,
                    voucher_date=d.disbursement_date,
                    summary=f"付款单 {d.bill_no}",
                    total_debit=d.amount,
                    total_credit=d.amount,
                    status="draft",
                    creator=user,
                    source_type="disbursement_bill",
                    source_bill_id=d.id,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=1,
                    account_id=ap_account.id,
                    summary=f"付款 {d.bill_no}",
                    debit_amount=d.amount,
                    credit_amount=Decimal("0"),
                    aux_supplier_id=d.supplier_id,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=2,
                    account_id=bank_account.id,
                    summary=f"付款 {d.bill_no}",
                    debit_amount=Decimal("0"),
                    credit_amount=d.amount,
                )
                d.voucher = v
                d.voucher_no = vno
                await d.save()
                month_vouchers.append({"id": v.id, "voucher_no": vno, "source": f"付款单 {d.bill_no}"})

        # 付款退款单 → 借 银行存款1002，贷 应付账款2202
        refunds = await DisbursementRefundBill.filter(
            account_set_id=account_set_id, status="confirmed", voucher_id=None,
            refund_date__gte=period_start, refund_date__lte=period_end,
        ).all()
        for rf in refunds:
            async with transactions.in_transaction():
                vno = await _next_voucher_no(account_set_id, "付", period_name)
                v = await Voucher.create(
                    account_set_id=account_set_id,
                    voucher_type="付",
                    voucher_no=vno,
                    period_name=period_name,
                    voucher_date=rf.refund_date,
                    summary=f"付款退款 {rf.bill_no}",
                    total_debit=rf.amount,
                    total_credit=rf.amount,
                    status="draft",
                    creator=user,
                    source_type="disbursement_refund_bill",
                    source_bill_id=rf.id,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=1,
                    account_id=bank_account.id,
                    summary=f"付款退款 {rf.bill_no}",
                    debit_amount=rf.amount,
                    credit_amount=Decimal("0"),
                )
                await VoucherEntry.create(
                    voucher=v, line_no=2,
                    account_id=ap_account.id,
                    summary=f"付款退款 {rf.bill_no}",
                    debit_amount=Decimal("0"),
                    credit_amount=rf.amount,
                    aux_supplier_id=rf.supplier_id,
                )
                rf.voucher = v
                rf.voucher_no = vno
                await rf.save()
                month_vouchers.append({"id": v.id, "voucher_no": vno, "source": f"付款退款 {rf.bill_no}"})

        # 采购退货单 → 红字冲销入库凭证：借 库存1405（负）+借 进项税222101（负）/ 贷 应付2202（负）
        if inventory_acct and input_tax_acct and ap_account:
            purchase_returns = await PurchaseReturn.filter(
                account_set_id=account_set_id,
                voucher_id=None,
                created_at__gte=datetime(period_start.year, period_start.month, period_start.day, 0, 0, 0, tzinfo=timezone.utc),
                created_at__lte=datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc),
            ).all()
            for pr in purchase_returns:
                if pr.total_amount <= 0:
                    continue
                # 逐行计算不含税金额和税额
                pr_items = await PurchaseReturnItem.filter(purchase_return_id=pr.id).all()
                total_excl_tax = Decimal("0")
                total_tax = Decimal("0")
                for pri in pr_items:
                    poi = await PurchaseOrderItem.filter(id=pri.purchase_item_id).first() if pri.purchase_item_id else None
                    tax_rate = poi.tax_rate if poi else Decimal("0.13")
                    item_excl = (pri.amount / (1 + tax_rate)).quantize(Decimal("0.01"))
                    item_tax = pri.amount - item_excl
                    total_excl_tax += item_excl
                    total_tax += item_tax
                total_amount = total_excl_tax + total_tax

                async with transactions.in_transaction():
                    vno = await _next_voucher_no(account_set_id, "记", period_name)
                    v = await Voucher.create(
                        account_set_id=account_set_id,
                        voucher_type="记",
                        voucher_no=vno,
                        period_name=period_name,
                        voucher_date=pr.created_at.date() if hasattr(pr.created_at, 'date') else pr.created_at,
                        summary=f"采购退货冲回 {pr.return_no}",
                        total_debit=-total_amount,
                        total_credit=-total_amount,
                        status="draft",
                        creator=user,
                        source_type="purchase_return",
                        source_bill_id=pr.id,
                    )
                    await VoucherEntry.create(
                        voucher=v, line_no=1,
                        account_id=inventory_acct.id,
                        summary=f"采购退货冲回 {pr.return_no}",
                        debit_amount=-total_excl_tax,
                        credit_amount=Decimal("0"),
                    )
                    await VoucherEntry.create(
                        voucher=v, line_no=2,
                        account_id=input_tax_acct.id,
                        summary=f"采购退货冲回 {pr.return_no} 进项税",
                        debit_amount=-total_tax,
                        credit_amount=Decimal("0"),
                    )
                    await VoucherEntry.create(
                        voucher=v, line_no=3,
                        account_id=ap_account.id,
                        summary=f"采购退货冲回 {pr.return_no}",
                        debit_amount=Decimal("0"),
                        credit_amount=-total_amount,
                        aux_supplier_id=pr.supplier_id,
                    )
                    pr.voucher = v
                    pr.voucher_no = vno
                    await pr.save()
                    month_vouchers.append({"id": v.id, "voucher_no": vno, "source": f"采购退货 {pr.return_no}"})

        summary[period_name] = {"count": len(month_vouchers), "skipped": False}
        vouchers.extend(month_vouchers)

    logger.info(f"AP凭证生成完成: {len(vouchers)} 张")
    return {"vouchers": vouchers, "summary": summary}


async def create_rebate_payment_voucher(
    account_set_id: int,
    po,
    disbursement_bill,
    creator,
):
    """采购付款时生成含返利分录的凭证

    凭证分录：
    借：应付账款           total_amount + rebate_used（原始应付）
    借：主营业务成本        -(rebate_used / 1.13)（负数红冲）
    借：应交税费           -(rebate_used - rebate_used / 1.13)（负数红冲）
    贷：银行存款           total_amount（实付金额）
    """
    if not po.rebate_used or po.rebate_used <= 0:
        return None

    rebate = po.rebate_used
    total_with_rebate = po.total_amount + rebate
    actual_paid = po.total_amount

    rebate_excl_tax = (rebate / Decimal("1.13")).quantize(Decimal("0.01"))
    rebate_tax = rebate - rebate_excl_tax

    ap_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="2202", is_active=True
    ).first()
    bank_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1002", is_active=True
    ).first()
    cost_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="5401", is_active=True
    ).first()
    tax_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="2221", is_active=True
    ).first()

    if not all([ap_account, bank_account, cost_account, tax_account]):
        logger.warning("缺少凭证科目(2202/1002/5401/2221)，跳过返利凭证生成")
        return None

    today = date.today()
    period_name = f"{today.year}-{today.month:02d}"

    async with transactions.in_transaction():
        vno = await _next_voucher_no(account_set_id, "付", period_name)
        v = await Voucher.create(
            account_set_id=account_set_id,
            voucher_type="付",
            voucher_no=vno,
            period_name=period_name,
            voucher_date=today,
            summary=f"采购付款(含返利) {po.po_no}",
            total_debit=actual_paid,
            total_credit=actual_paid,
            status="draft",
            creator=creator,
            source_type="purchase_payment",
            source_bill_id=po.id,
        )
        await VoucherEntry.create(
            voucher=v, line_no=1,
            account_id=ap_account.id,
            summary=f"采购付款 {po.po_no}",
            debit_amount=total_with_rebate,
            credit_amount=Decimal("0"),
            aux_supplier_id=po.supplier_id,
        )
        await VoucherEntry.create(
            voucher=v, line_no=2,
            account_id=cost_account.id,
            summary=f"采购返利红冲 {po.po_no}",
            debit_amount=-rebate_excl_tax,
            credit_amount=Decimal("0"),
        )
        await VoucherEntry.create(
            voucher=v, line_no=3,
            account_id=tax_account.id,
            summary=f"采购返利税金红冲 {po.po_no}",
            debit_amount=-rebate_tax,
            credit_amount=Decimal("0"),
        )
        await VoucherEntry.create(
            voucher=v, line_no=4,
            account_id=bank_account.id,
            summary=f"采购付款 {po.po_no}",
            debit_amount=Decimal("0"),
            credit_amount=actual_paid,
        )

        if disbursement_bill:
            disbursement_bill.voucher = v
            disbursement_bill.voucher_no = vno
            await disbursement_bill.save()

    logger.info(f"生成采购付款凭证(含返利): {vno}, 应付={total_with_rebate}, 返利={rebate}, 实付={actual_paid}")
    return v
