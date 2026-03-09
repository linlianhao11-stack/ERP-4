"""发票服务层"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from tortoise import transactions
from app.models.invoice import Invoice, InvoiceItem
from app.models.ar_ap import ReceivableBill
from app.models.delivery import SalesDeliveryBill
from app.models.accounting import AccountSet, ChartOfAccount
from app.models.voucher import Voucher, VoucherEntry
from app.utils.generators import generate_order_no
from app.logger import get_logger

logger = get_logger("invoice_service")


from app.utils.voucher_no import next_voucher_no as _next_voucher_no


def _calc_item_amounts(unit_price: Decimal, quantity: int, tax_rate: Decimal) -> tuple:
    """计算明细行金额：返回 (不含税金额, 税额, 价税合计)"""
    without_tax = (unit_price * quantity).quantize(Decimal("0.01"))
    tax = (without_tax * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
    total = without_tax + tax
    return without_tax, tax, total


async def push_invoice_from_receivable(
    account_set_id: int,
    receivable_bill_id: int,
    invoice_type: str,
    items: list[dict],
    creator=None,
    invoice_date: date | None = None,
    remark: str = "",
) -> Invoice:
    """从应收单推送生成销项发票（草稿状态）"""
    rb = await ReceivableBill.filter(id=receivable_bill_id, account_set_id=account_set_id).first()
    if not rb:
        raise ValueError("应收单不存在或不属于当前账套")

    if invoice_date is None:
        invoice_date = date.today()

    total_without_tax = Decimal("0")
    total_tax = Decimal("0")
    total_amount = Decimal("0")
    item_data = []
    for it in items:
        unit_price = Decimal(str(it["unit_price"]))
        quantity = int(it["quantity"])
        tax_rate = Decimal(str(it.get("tax_rate", "13")))
        without_tax, tax, amount = _calc_item_amounts(unit_price, quantity, tax_rate)
        total_without_tax += without_tax
        total_tax += tax
        total_amount += amount
        item_data.append({**it, "amount_without_tax": without_tax, "tax_amount": tax, "amount": amount})

    invoice = await Invoice.create(
        invoice_no=generate_order_no("XS"),
        invoice_type=invoice_type,
        direction="output",
        account_set_id=account_set_id,
        customer_id=rb.customer_id,
        receivable_bill_id=receivable_bill_id,
        invoice_date=invoice_date,
        total_amount=total_amount,
        amount_without_tax=total_without_tax,
        tax_amount=total_tax,
        status="draft",
        remark=remark,
        creator=creator,
    )

    for it in item_data:
        await InvoiceItem.create(
            invoice=invoice,
            product_id=it.get("product_id"),
            product_name=it["product_name"],
            quantity=it["quantity"],
            unit_price=Decimal(str(it["unit_price"])),
            tax_rate=Decimal(str(it.get("tax_rate", "13"))),
            tax_amount=it["tax_amount"],
            amount_without_tax=it["amount_without_tax"],
            amount=it["amount"],
        )

    logger.info(f"从应收单推送生成销项发票: {invoice.invoice_no}")
    return invoice


async def create_input_invoice(
    account_set_id: int,
    supplier_id: int,
    invoice_type: str,
    items: list[dict],
    payable_bill_id: int | None = None,
    creator=None,
    invoice_date: date | None = None,
    remark: str = "",
) -> Invoice:
    """手工创建进项发票"""
    if invoice_date is None:
        invoice_date = date.today()

    total_without_tax = Decimal("0")
    total_tax = Decimal("0")
    total_amount = Decimal("0")
    item_data = []
    for it in items:
        unit_price = Decimal(str(it["unit_price"]))
        quantity = int(it["quantity"])
        tax_rate = Decimal(str(it.get("tax_rate", "13")))
        without_tax, tax, amount = _calc_item_amounts(unit_price, quantity, tax_rate)
        total_without_tax += without_tax
        total_tax += tax
        total_amount += amount
        item_data.append({**it, "amount_without_tax": without_tax, "tax_amount": tax, "amount": amount})

    invoice = await Invoice.create(
        invoice_no=generate_order_no("JX"),
        invoice_type=invoice_type,
        direction="input",
        account_set_id=account_set_id,
        supplier_id=supplier_id,
        payable_bill_id=payable_bill_id,
        invoice_date=invoice_date,
        total_amount=total_amount,
        amount_without_tax=total_without_tax,
        tax_amount=total_tax,
        status="draft",
        remark=remark,
        creator=creator,
    )

    for it in item_data:
        await InvoiceItem.create(
            invoice=invoice,
            product_id=it.get("product_id"),
            product_name=it["product_name"],
            quantity=it["quantity"],
            unit_price=Decimal(str(it["unit_price"])),
            tax_rate=Decimal(str(it.get("tax_rate", "13"))),
            tax_amount=it["tax_amount"],
            amount_without_tax=it["amount_without_tax"],
            amount=it["amount"],
        )

    logger.info(f"创建进项发票: {invoice.invoice_no}")
    return invoice


async def confirm_invoice(invoice_id: int, user) -> Invoice:
    """确认发票。销项发票生成复合凭证（收入确认+成本结转），进项发票不生成凭证。"""
    async with transactions.in_transaction():
        inv = await Invoice.filter(id=invoice_id).select_for_update().first()
        if not inv:
            raise ValueError("发票不存在")
        if inv.status != "draft":
            raise ValueError("只有草稿状态的发票可以确认")

        inv.status = "confirmed"
        await inv.save()

        # 销项发票 → 生成复合凭证
        if inv.direction == "output":
            ar_acct = await ChartOfAccount.filter(
                account_set_id=inv.account_set_id, code="1122", is_active=True
            ).first()
            revenue_acct = await ChartOfAccount.filter(
                account_set_id=inv.account_set_id, code="6001", is_active=True
            ).first()
            output_tax_acct = await ChartOfAccount.filter(
                account_set_id=inv.account_set_id, code="222102", is_active=True
            ).first()
            cogs_acct = await ChartOfAccount.filter(
                account_set_id=inv.account_set_id, code="6401", is_active=True
            ).first()
            shipped_acct = await ChartOfAccount.filter(
                account_set_id=inv.account_set_id, code="1407", is_active=True
            ).first()

            if ar_acct and revenue_acct and output_tax_acct and cogs_acct and shipped_acct:
                # 获取关联的出库单成本
                cost_total = Decimal("0")
                if inv.receivable_bill_id:
                    rb = await ReceivableBill.filter(id=inv.receivable_bill_id).first()
                    if rb and rb.order_id:
                        delivery = await SalesDeliveryBill.filter(
                            order_id=rb.order_id, account_set_id=inv.account_set_id
                        ).first()
                        if delivery:
                            cost_total = delivery.total_cost

                bill_date = inv.invoice_date
                period_name = f"{bill_date.year}-{bill_date.month:02d}"
                total_debit = inv.total_amount + cost_total
                total_credit = inv.amount_without_tax + inv.tax_amount + cost_total

                vno = await _next_voucher_no(inv.account_set_id, "记", period_name)
                v = await Voucher.create(
                    account_set_id=inv.account_set_id,
                    voucher_type="记",
                    voucher_no=vno,
                    period_name=period_name,
                    voucher_date=bill_date,
                    summary=f"销项发票 {inv.invoice_no} 收入确认",
                    total_debit=total_debit,
                    total_credit=total_credit,
                    status="draft",
                    creator=user,
                    source_type="invoice",
                    source_bill_id=inv.id,
                )
                line = 1
                await VoucherEntry.create(
                    voucher=v, line_no=line,
                    account_id=ar_acct.id,
                    summary=f"销项发票 {inv.invoice_no}",
                    debit_amount=inv.total_amount,
                    credit_amount=Decimal("0"),
                    aux_customer_id=inv.customer_id,
                )
                line += 1
                await VoucherEntry.create(
                    voucher=v, line_no=line,
                    account_id=revenue_acct.id,
                    summary=f"销项发票 {inv.invoice_no}",
                    debit_amount=Decimal("0"),
                    credit_amount=inv.amount_without_tax,
                )
                line += 1
                await VoucherEntry.create(
                    voucher=v, line_no=line,
                    account_id=output_tax_acct.id,
                    summary=f"销项发票 {inv.invoice_no} 销项税",
                    debit_amount=Decimal("0"),
                    credit_amount=inv.tax_amount,
                )
                if cost_total > 0:
                    line += 1
                    await VoucherEntry.create(
                        voucher=v, line_no=line,
                        account_id=cogs_acct.id,
                        summary=f"销售成本结转 {inv.invoice_no}",
                        debit_amount=cost_total,
                        credit_amount=Decimal("0"),
                    )
                    line += 1
                    await VoucherEntry.create(
                        voucher=v, line_no=line,
                        account_id=shipped_acct.id,
                        summary=f"销售成本结转 {inv.invoice_no}",
                        debit_amount=Decimal("0"),
                        credit_amount=cost_total,
                    )

                inv.voucher = v
                inv.voucher_no = vno
                await inv.save()

    logger.info(f"确认发票: {inv.invoice_no}, 方向: {inv.direction}")
    return inv


async def cancel_invoice(invoice_id: int) -> Invoice:
    """作废发票，同时清理关联凭证"""
    async with transactions.in_transaction():
        inv = await Invoice.filter(id=invoice_id).select_for_update().first()
        if not inv:
            raise ValueError("发票不存在")
        if inv.status == "cancelled":
            raise ValueError("发票已作废")
        # 清理关联凭证
        if inv.voucher_id:
            await VoucherEntry.filter(voucher_id=inv.voucher_id).delete()
            await Voucher.filter(id=inv.voucher_id).delete()
            inv.voucher_id = None
            inv.voucher_no = None
        inv.status = "cancelled"
        await inv.save()
    logger.info(f"作废发票: {inv.invoice_no}")
    return inv
