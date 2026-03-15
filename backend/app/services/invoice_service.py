"""发票服务层"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from typing import Optional
from tortoise import transactions
from app.models.invoice import Invoice, InvoiceItem
from app.models.ar_ap import ReceivableBill, PayableBill
from app.models.delivery import SalesDeliveryBill
from app.models.accounting import AccountSet, ChartOfAccount
from app.models.voucher import Voucher, VoucherEntry
from app.utils.generators import generate_order_no
from app.logger import get_logger
from app.config import UPLOAD_ROOT

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
    receivable_bill_ids: list,
    invoice_type: str,
    items: list,
    creator=None,
    invoice_date: Optional[date] = None,
    tax_rate: Decimal = Decimal("13"),
    remark: str = "",
) -> Invoice:
    """从应收单推送生成销项发票（草稿状态），支持多单合并"""
    if not receivable_bill_ids:
        raise ValueError("请选择至少一张应收单")

    # 查询所有源单据
    rbs = await ReceivableBill.filter(
        id__in=receivable_bill_ids, account_set_id=account_set_id
    ).all()
    if len(rbs) != len(receivable_bill_ids):
        raise ValueError("部分应收单不存在或不属于当前账套")

    # 校验同一客户
    customer_ids = set(rb.customer_id for rb in rbs)
    if len(customer_ids) > 1:
        raise ValueError("多张应收单必须属于同一客户")

    # 防重复：检查 receivable_bill_id FK
    first_id = receivable_bill_ids[0]
    existing = await Invoice.filter(
        receivable_bill_id=first_id, status__not="cancelled"
    ).first()
    if existing:
        raise ValueError(f"应收单已关联发票 {existing.invoice_no}，请勿重复推送")

    if invoice_date is None:
        invoice_date = date.today()

    # 若未传入明细行，按每张应收单汇总生成
    if not items:
        items = []
        for rb in rbs:
            total = rb.total_amount
            rate = tax_rate / Decimal("100")
            without_tax = (total / (1 + rate)).quantize(Decimal("0.01"))
            items.append({
                "product_name": f"应收单 {rb.bill_no} 汇总",
                "quantity": 1,
                "unit_price": str(without_tax),
                "tax_rate": str(tax_rate),
            })

    total_without_tax = Decimal("0")
    total_tax = Decimal("0")
    total_amount = Decimal("0")
    item_data = []
    for it in items:
        unit_price = Decimal(str(it["unit_price"]))
        quantity = int(it["quantity"])
        item_tax_rate = Decimal(str(it.get("tax_rate", "13")))
        without_tax, tax, amount = _calc_item_amounts(unit_price, quantity, item_tax_rate)
        total_without_tax += without_tax
        total_tax += tax
        total_amount += amount
        item_data.append({**it, "amount_without_tax": without_tax, "tax_amount": tax, "amount": amount})

    invoice = await Invoice.create(
        invoice_no=generate_order_no("XS"),
        invoice_type=invoice_type,
        direction="output",
        account_set_id=account_set_id,
        customer_id=rbs[0].customer_id,
        receivable_bill_id=first_id,
        source_receivable_bill_ids=receivable_bill_ids,
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

    logger.info(f"从应收单推送生成销项发票: {invoice.invoice_no}, 源单据: {receivable_bill_ids}")
    return invoice


async def push_invoice_from_payable(
    account_set_id: int,
    payable_bill_ids: list,
    invoice_type: str,
    items: list,
    creator=None,
    invoice_date: Optional[date] = None,
    tax_rate: Decimal = Decimal("13"),
    remark: str = "",
) -> Invoice:
    """从应付单推送生成进项发票（草稿状态），支持多单合并"""
    if not payable_bill_ids:
        raise ValueError("请选择至少一张应付单")

    # 查询所有源单据
    pbs = await PayableBill.filter(
        id__in=payable_bill_ids, account_set_id=account_set_id
    ).all()
    if len(pbs) != len(payable_bill_ids):
        raise ValueError("部分应付单不存在或不属于当前账套")

    # 校验同一供应商
    supplier_ids = set(pb.supplier_id for pb in pbs)
    if len(supplier_ids) > 1:
        raise ValueError("多张应付单必须属于同一供应商")

    # 防重复：检查 payable_bill_id FK
    first_id = payable_bill_ids[0]
    existing = await Invoice.filter(
        payable_bill_id=first_id, status__not="cancelled"
    ).first()
    if existing:
        raise ValueError(f"应付单已关联发票 {existing.invoice_no}，请勿重复推送")

    if invoice_date is None:
        invoice_date = date.today()

    # 若未传入明细行，按每张应付单汇总生成
    if not items:
        items = []
        for pb in pbs:
            total = pb.total_amount
            rate = tax_rate / Decimal("100")
            without_tax = (total / (1 + rate)).quantize(Decimal("0.01"))
            items.append({
                "product_name": f"应付单 {pb.bill_no} 汇总",
                "quantity": 1,
                "unit_price": str(without_tax),
                "tax_rate": str(tax_rate),
            })

    total_without_tax = Decimal("0")
    total_tax = Decimal("0")
    total_amount = Decimal("0")
    item_data = []
    for it in items:
        unit_price = Decimal(str(it["unit_price"]))
        quantity = int(it["quantity"])
        item_tax_rate = Decimal(str(it.get("tax_rate", "13")))
        without_tax, tax, amount = _calc_item_amounts(unit_price, quantity, item_tax_rate)
        total_without_tax += without_tax
        total_tax += tax
        total_amount += amount
        item_data.append({**it, "amount_without_tax": without_tax, "tax_amount": tax, "amount": amount})

    invoice = await Invoice.create(
        invoice_no=generate_order_no("JX"),
        invoice_type=invoice_type,
        direction="input",
        account_set_id=account_set_id,
        supplier_id=pbs[0].supplier_id,
        payable_bill_id=first_id,
        source_payable_bill_ids=payable_bill_ids,
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

    logger.info(f"从应付单推送生成进项发票: {invoice.invoice_no}, 源单据: {payable_bill_ids}")
    return invoice


async def create_input_invoice(
    account_set_id: int,
    supplier_id: int,
    invoice_type: str,
    items: list,
    payable_bill_id: Optional[int] = None,
    creator=None,
    invoice_date: Optional[date] = None,
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
        # 清理 PDF 文件
        for pdf in (inv.pdf_files or []):
            try:
                fpath = os.path.join(UPLOAD_ROOT, pdf["path"])
                # 路径遍历防护
                if not os.path.realpath(fpath).startswith(os.path.realpath(UPLOAD_ROOT)):
                    logger.warning(f"跳过异常路径: {pdf.get('path')}")
                    continue
                if os.path.exists(fpath):
                    os.remove(fpath)
            except Exception as e:
                logger.warning(f"清理发票PDF失败: {pdf.get('path')}, {e}")
        inv.pdf_files = []
        await inv.save()
    logger.info(f"作废发票: {inv.invoice_no}")
    return inv
