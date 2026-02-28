"""出入库单服务层"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from tortoise import transactions
from app.models.delivery import SalesDeliveryBill, SalesDeliveryItem, PurchaseReceiptBill, PurchaseReceiptItem
from app.models.accounting import AccountSet, ChartOfAccount
from app.models.voucher import Voucher, VoucherEntry
from app.utils.generators import generate_order_no
from app.logger import get_logger

logger = get_logger("delivery_service")


async def _next_voucher_no(account_set_id: int, voucher_type: str, period_name: str) -> str:
    account_set = await AccountSet.filter(id=account_set_id).first()
    prefix = f"{account_set.code}-{voucher_type}-{period_name.replace('-', '')}-"
    last = await Voucher.filter(
        account_set_id=account_set_id, voucher_type=voucher_type, period_name=period_name,
    ).order_by("-voucher_no").first()
    if last and last.voucher_no.startswith(prefix):
        seq = int(last.voucher_no[len(prefix):]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


async def create_sales_delivery(
    account_set_id: int,
    customer_id: int,
    order_id: int | None,
    warehouse_id: int | None,
    items: list[dict],
    creator=None,
    remark: str = "",
    bill_date: date | None = None,
) -> SalesDeliveryBill:
    """创建销售出库单 + 自动生成凭证（借发出商品1407/贷库存商品1405）"""
    if bill_date is None:
        bill_date = date.today()

    total_cost = sum(Decimal(str(it["quantity"])) * Decimal(str(it["cost_price"])) for it in items)
    total_amount = sum(Decimal(str(it["quantity"])) * Decimal(str(it["sale_price"])) for it in items)

    async with transactions.in_transaction():
        bill = await SalesDeliveryBill.create(
            bill_no=generate_order_no("CK"),
            account_set_id=account_set_id,
            customer_id=customer_id,
            order_id=order_id,
            warehouse_id=warehouse_id,
            bill_date=bill_date,
            total_cost=total_cost,
            total_amount=total_amount,
            status="confirmed",
            remark=remark,
            creator=creator,
        )

        for it in items:
            await SalesDeliveryItem.create(
                delivery_bill=bill,
                order_item_id=it.get("order_item_id"),
                product_id=it["product_id"],
                product_name=it["product_name"],
                quantity=it["quantity"],
                cost_price=Decimal(str(it["cost_price"])),
                sale_price=Decimal(str(it["sale_price"])),
            )

        # 自动生成凭证：借 发出商品1407 / 贷 库存商品1405
        shipped_acct = await ChartOfAccount.filter(
            account_set_id=account_set_id, code="1407", is_active=True
        ).first()
        inventory_acct = await ChartOfAccount.filter(
            account_set_id=account_set_id, code="1405", is_active=True
        ).first()

        if shipped_acct and inventory_acct and total_cost > 0:
            period_name = f"{bill_date.year}-{bill_date.month:02d}"
            vno = await _next_voucher_no(account_set_id, "记", period_name)
            v = await Voucher.create(
                account_set_id=account_set_id,
                voucher_type="记",
                voucher_no=vno,
                period_name=period_name,
                voucher_date=bill_date,
                summary=f"销售出库 {bill.bill_no}",
                total_debit=total_cost,
                total_credit=total_cost,
                status="draft",
                creator=creator,
                source_type="sales_delivery",
                source_bill_id=bill.id,
            )
            await VoucherEntry.create(
                voucher=v, line_no=1,
                account_id=shipped_acct.id,
                summary=f"销售出库 {bill.bill_no}",
                debit_amount=total_cost,
                credit_amount=Decimal("0"),
            )
            await VoucherEntry.create(
                voucher=v, line_no=2,
                account_id=inventory_acct.id,
                summary=f"销售出库 {bill.bill_no}",
                debit_amount=Decimal("0"),
                credit_amount=total_cost,
            )
            bill.voucher = v
            bill.voucher_no = vno
            await bill.save()

    logger.info(f"创建销售出库单: {bill.bill_no}, 成本: {total_cost}")
    return bill


async def create_purchase_receipt(
    account_set_id: int,
    supplier_id: int,
    purchase_order_id: int | None,
    warehouse_id: int | None,
    items: list[dict],
    creator=None,
    remark: str = "",
    bill_date: date | None = None,
) -> PurchaseReceiptBill:
    """创建采购入库单 + 自动生成凭证（借库存1405+借进项税222101/贷应付2202）"""
    if bill_date is None:
        bill_date = date.today()

    total_amount = Decimal("0")
    total_without_tax = Decimal("0")
    total_tax = Decimal("0")
    for it in items:
        qty = Decimal(str(it["quantity"]))
        incl = Decimal(str(it["tax_inclusive_price"]))
        excl = Decimal(str(it["tax_exclusive_price"]))
        line_amount = (qty * incl).quantize(Decimal("0.01"))
        line_without = (qty * excl).quantize(Decimal("0.01"))
        total_amount += line_amount
        total_without_tax += line_without
        total_tax += line_amount - line_without

    async with transactions.in_transaction():
        bill = await PurchaseReceiptBill.create(
            bill_no=generate_order_no("RK"),
            account_set_id=account_set_id,
            supplier_id=supplier_id,
            purchase_order_id=purchase_order_id,
            warehouse_id=warehouse_id,
            bill_date=bill_date,
            total_amount=total_amount,
            total_amount_without_tax=total_without_tax,
            total_tax=total_tax,
            status="confirmed",
            remark=remark,
            creator=creator,
        )

        for it in items:
            await PurchaseReceiptItem.create(
                receipt_bill=bill,
                purchase_order_item_id=it.get("purchase_order_item_id"),
                product_id=it["product_id"],
                product_name=it["product_name"],
                quantity=it["quantity"],
                tax_inclusive_price=Decimal(str(it["tax_inclusive_price"])),
                tax_exclusive_price=Decimal(str(it["tax_exclusive_price"])),
                tax_rate=Decimal(str(it.get("tax_rate", "13"))),
            )

        # 自动生成凭证：借库存1405+借进项税222101 / 贷应付2202
        inventory_acct = await ChartOfAccount.filter(
            account_set_id=account_set_id, code="1405", is_active=True
        ).first()
        input_tax_acct = await ChartOfAccount.filter(
            account_set_id=account_set_id, code="222101", is_active=True
        ).first()
        ap_acct = await ChartOfAccount.filter(
            account_set_id=account_set_id, code="2202", is_active=True
        ).first()

        if inventory_acct and input_tax_acct and ap_acct and total_amount > 0:
            period_name = f"{bill_date.year}-{bill_date.month:02d}"
            vno = await _next_voucher_no(account_set_id, "记", period_name)
            v = await Voucher.create(
                account_set_id=account_set_id,
                voucher_type="记",
                voucher_no=vno,
                period_name=period_name,
                voucher_date=bill_date,
                summary=f"采购入库 {bill.bill_no}",
                total_debit=total_amount,
                total_credit=total_amount,
                status="draft",
                creator=creator,
                source_type="purchase_receipt",
                source_bill_id=bill.id,
            )
            await VoucherEntry.create(
                voucher=v, line_no=1,
                account_id=inventory_acct.id,
                summary=f"采购入库 {bill.bill_no}",
                debit_amount=total_without_tax,
                credit_amount=Decimal("0"),
            )
            await VoucherEntry.create(
                voucher=v, line_no=2,
                account_id=input_tax_acct.id,
                summary=f"采购入库 {bill.bill_no} 进项税",
                debit_amount=total_tax,
                credit_amount=Decimal("0"),
            )
            await VoucherEntry.create(
                voucher=v, line_no=3,
                account_id=ap_acct.id,
                summary=f"采购入库 {bill.bill_no}",
                debit_amount=Decimal("0"),
                credit_amount=total_amount,
                aux_supplier_id=supplier_id,
            )
            bill.voucher = v
            bill.voucher_no = vno
            await bill.save()

    logger.info(f"创建采购入库单: {bill.bill_no}, 含税: {total_amount}, 税额: {total_tax}")
    return bill
