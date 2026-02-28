"""应付服务层"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from tortoise import transactions
from app.models.ar_ap import PayableBill, DisbursementBill, DisbursementRefundBill
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

    # 更新关联应付单
    if payable_bill:
        payable_bill.paid_amount += amount
        payable_bill.unpaid_amount = payable_bill.total_amount - payable_bill.paid_amount
        if payable_bill.unpaid_amount <= 0:
            payable_bill.status = "completed"
        else:
            payable_bill.status = "partial"
        await payable_bill.save()

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


async def _next_voucher_no(account_set_id: int, voucher_type: str, period_name: str) -> str:
    account_set = await AccountSet.filter(id=account_set_id).first()
    prefix = f"{account_set.code}-{voucher_type}-{period_name.replace('-', '')}-"
    last = await Voucher.filter(
        account_set_id=account_set_id,
        voucher_type=voucher_type,
        period_name=period_name,
    ).order_by("-voucher_no").first()
    if last and last.voucher_no.startswith(prefix):
        seq = int(last.voucher_no[len(prefix):]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


async def generate_ap_vouchers(account_set_id: int, period_name: str, user) -> list:
    period = await AccountingPeriod.filter(
        account_set_id=account_set_id, period_name=period_name
    ).first()
    if not period:
        raise ValueError(f"会计期间 {period_name} 不存在")

    bank_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1002", is_active=True
    ).first()
    ap_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="2202", is_active=True
    ).first()
    if not bank_account or not ap_account:
        raise ValueError("缺少必要科目：银行存款(1002)或应付账款(2202)")

    vouchers = []

    # 付款单 → 借 应付账款2202，贷 银行存款1002
    disbursements = await DisbursementBill.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None
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
            vouchers.append({"id": v.id, "voucher_no": vno, "source": f"付款单 {d.bill_no}"})

    # 付款退款单 → 借 银行存款1002，贷 应付账款2202
    refunds = await DisbursementRefundBill.filter(
        account_set_id=account_set_id, status="confirmed", voucher_id=None
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
            vouchers.append({"id": v.id, "voucher_no": vno, "source": f"付款退款 {rf.bill_no}"})

    logger.info(f"AP凭证生成完成: {len(vouchers)} 张")
    return vouchers
