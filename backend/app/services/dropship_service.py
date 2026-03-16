"""代采代发服务层"""
from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List

from fastapi import HTTPException
from tortoise import transactions

from app.logger import get_logger
from app.models import Supplier, Product, User, Employee
from app.models.accounting import ChartOfAccount
from app.models.ar_ap import PayableBill, DisbursementBill
from app.models.dropship import DropshipOrder
from app.models.voucher import Voucher, VoucherEntry
from app.schemas.dropship import DropshipOrderCreate
from app.utils.generators import generate_sequential_no, generate_order_no
from app.utils.time import now
from app.utils.voucher_no import next_voucher_no

logger = get_logger("dropship_service")


async def calculate_gross_profit(
    purchase_total: Decimal,
    sale_total: Decimal,
    purchase_tax_rate: Decimal,
    sale_tax_rate: Decimal,
    invoice_type: str,
) -> tuple:
    """
    计算毛利和毛利率

    - 不含税售价 = sale_total / (1 + sale_tax_rate/100)
    - 专票: 不含税成本 = purchase_total / (1 + purchase_tax_rate/100)
    - 普票: 不含税成本 = purchase_total (含税全额入成本)
    - gross_profit = 不含税售价 - 不含税成本
    - gross_margin = gross_profit / 不含税售价 × 100
    """
    sale_excl_tax = (sale_total / (1 + sale_tax_rate / 100)).quantize(Decimal("0.01"))

    if invoice_type == "special":
        purchase_excl_tax = (purchase_total / (1 + purchase_tax_rate / 100)).quantize(Decimal("0.01"))
    else:
        # 普票：含税全额入成本
        purchase_excl_tax = purchase_total

    gross_profit = (sale_excl_tax - purchase_excl_tax).quantize(Decimal("0.01"))

    if sale_excl_tax > 0:
        gross_margin = (gross_profit / sale_excl_tax * 100).quantize(Decimal("0.01"))
    else:
        gross_margin = Decimal("0.00")

    return gross_profit, gross_margin


async def create_dropship_order(
    data: DropshipOrderCreate,
    user: User,
    submit: bool = False,
) -> DropshipOrder:
    """创建代采代发订单，可选自动提交"""

    # 1. 处理供应商
    if data.supplier_id:
        supplier = await Supplier.filter(id=data.supplier_id).first()
        if not supplier:
            raise HTTPException(status_code=400, detail="供应商不存在")
        supplier_id = supplier.id
    elif data.supplier_name:
        # 快速新建供应商
        supplier = await Supplier.create(name=data.supplier_name)
        supplier_id = supplier.id
        logger.info(f"快速新建供应商: {supplier.name} (id={supplier.id})")
    else:
        raise HTTPException(status_code=400, detail="必须提供供应商ID或供应商名称")

    # 2. 处理商品
    product_id = None
    if data.product_id:
        product = await Product.filter(id=data.product_id).first()
        if not product:
            raise HTTPException(status_code=400, detail="商品不存在")
        product_id = product.id
    else:
        # 快速新建商品
        sku = f"DS-{secrets.token_hex(4).upper()}"
        product = await Product.create(
            sku=sku,
            name=data.product_name,
            category="代采代发",
            cost_price=data.purchase_price,
            retail_price=data.sale_price,
        )
        product_id = product.id
        logger.info(f"快速新建商品: {product.name} (sku={sku})")

    # 3. 计算金额
    purchase_total = data.purchase_price * data.quantity
    sale_total = data.sale_price * data.quantity

    # 4. 计算毛利
    gross_profit, gross_margin = await calculate_gross_profit(
        purchase_total, sale_total,
        data.purchase_tax_rate, data.sale_tax_rate,
        data.invoice_type,
    )

    # 5. 生成编号
    ds_no = await generate_sequential_no("DS", "dropship_orders", "ds_no")

    # 6. 创建订单
    order = await DropshipOrder.create(
        ds_no=ds_no,
        account_set_id=data.account_set_id,
        supplier_id=supplier_id,
        product_id=product_id,
        product_name=data.product_name,
        purchase_price=data.purchase_price,
        quantity=data.quantity,
        purchase_total=purchase_total,
        invoice_type=data.invoice_type,
        purchase_tax_rate=data.purchase_tax_rate,
        customer_id=data.customer_id,
        platform_order_no=data.platform_order_no,
        sale_price=data.sale_price,
        sale_total=sale_total,
        sale_tax_rate=data.sale_tax_rate,
        settlement_type=data.settlement_type,
        advance_receipt_id=data.advance_receipt_id,
        gross_profit=gross_profit,
        gross_margin=gross_margin,
        shipping_mode=data.shipping_mode,
        note=data.note,
        creator=user,
        status="draft",
    )

    logger.info(f"创建代采代发订单: {ds_no}, 采购={purchase_total}, 销售={sale_total}, 毛利={gross_profit}")

    # 7. 可选自动提交
    if submit:
        order = await submit_dropship_order(order.id, user)

    return order


async def submit_dropship_order(order_id: int, user: User) -> DropshipOrder:
    """提交代采代发订单：draft → pending_payment，并创建应付单"""

    async with transactions.in_transaction():
        order = await DropshipOrder.filter(id=order_id).select_for_update().first()
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        if order.status != "draft":
            raise HTTPException(status_code=400, detail=f"只有草稿状态可以提交，当前状态: {order.status}")

        # 创建应付单
        bill_no = generate_order_no("YF-DS")
        payable = await PayableBill.create(
            bill_no=bill_no,
            account_set_id=order.account_set_id,
            supplier_id=order.supplier_id,
            bill_date=date.today(),
            total_amount=order.purchase_total,
            paid_amount=Decimal("0"),
            unpaid_amount=order.purchase_total,
            status="pending",
            remark=f"代采代发订单 {order.ds_no}",
            creator=user,
        )
        logger.info(f"创建应付单: {bill_no}, 金额: {order.purchase_total}")

        # 更新订单状态
        order.payable_bill_id = payable.id
        order.status = "pending_payment"
        await order.save()

    logger.info(f"代采代发订单提交: {order.ds_no} → pending_payment")
    return order


async def batch_pay_dropship(
    order_ids: List[int],
    payment_method: str,
    employee_id: Optional[int],
    user: User,
) -> dict:
    """批量付款：创建付款单、更新应付单、更新订单状态、按供应商合并生成凭证A"""

    # 校验 employee_advance 必须有 employee_id
    if payment_method == "employee_advance" and not employee_id:
        raise HTTPException(status_code=400, detail="员工垫付方式必须指定员工")

    # 校验员工存在
    if employee_id:
        employee = await Employee.filter(id=employee_id).first()
        if not employee:
            raise HTTPException(status_code=400, detail="指定的员工不存在")

    async with transactions.in_transaction():
        # 1. 加锁查询所有订单
        orders = await DropshipOrder.filter(id__in=order_ids).select_for_update().all()
        if len(orders) != len(order_ids):
            found_ids = {o.id for o in orders}
            missing = [oid for oid in order_ids if oid not in found_ids]
            raise HTTPException(status_code=400, detail=f"订单不存在: {missing}")

        # 校验全部处于 pending_payment 状态
        for order in orders:
            if order.status != "pending_payment":
                raise HTTPException(
                    status_code=400,
                    detail=f"订单 {order.ds_no} 不是待付款状态，当前状态: {order.status}",
                )

        # 2. 按供应商分组（用于后续合并凭证）
        supplier_groups: dict[int, list] = defaultdict(list)
        disbursement_bills = []

        for order in orders:
            # 2a. 创建付款单
            bill_no = generate_order_no("FK-DS")
            disb = await DisbursementBill.create(
                bill_no=bill_no,
                account_set_id=order.account_set_id,
                supplier_id=order.supplier_id,
                payable_bill_id=order.payable_bill_id,
                disbursement_date=date.today(),
                amount=order.purchase_total,
                disbursement_method=payment_method,
                status="confirmed",
                confirmed_by=user,
                confirmed_at=datetime.now(timezone.utc),
                remark=f"代采代发批量付款 {order.ds_no}",
                creator=user,
            )
            disbursement_bills.append(disb)

            # 2b. 更新应付单
            if order.payable_bill_id:
                pb = await PayableBill.filter(id=order.payable_bill_id).select_for_update().first()
                if pb:
                    pb.paid_amount += order.purchase_total
                    pb.unpaid_amount = pb.total_amount - pb.paid_amount
                    pb.status = "completed" if pb.unpaid_amount <= 0 else "partial"
                    await pb.save()

            # 2c. 更新订单
            order.status = "paid_pending_ship"
            order.payment_method = payment_method
            order.disbursement_bill_id = disb.id
            if employee_id:
                order.payment_employee_id = employee_id
            await order.save()

            supplier_groups[order.supplier_id].append((order, disb))

        logger.info(f"批量付款: {len(orders)} 笔订单, 方式={payment_method}")

        # 3. 按供应商合并生成凭证A
        vouchers_created = []

        for supplier_id, group in supplier_groups.items():
            group_orders = [item[0] for item in group]
            group_disbs = [item[1] for item in group]

            # 获取供应商名称
            supplier = await Supplier.filter(id=supplier_id).first()
            supplier_name = supplier.name if supplier else f"供应商{supplier_id}"

            # 计算合计金额
            total_amount = sum(o.purchase_total for o in group_orders)
            ds_nos = "/".join(o.ds_no for o in group_orders)
            account_set_id = group_orders[0].account_set_id

            # 查找科目
            prepaid_account = await ChartOfAccount.filter(
                account_set_id=account_set_id, code="1123", is_active=True
            ).first()
            bank_account = await ChartOfAccount.filter(
                account_set_id=account_set_id, code="1002", is_active=True
            ).first()
            other_receivable_account = await ChartOfAccount.filter(
                account_set_id=account_set_id, code="1221", is_active=True
            ).first()

            if not prepaid_account:
                raise HTTPException(status_code=400, detail="缺少必要科目：预付账款(1123)")

            if payment_method == "employee_advance" and not other_receivable_account:
                raise HTTPException(status_code=400, detail="缺少必要科目：其他应收款(1221)")

            if payment_method != "employee_advance" and not bank_account:
                raise HTTPException(status_code=400, detail="缺少必要科目：银行存款(1002)")

            # 生成凭证
            today = date.today()
            period_name = f"{today.year}-{today.month:02d}"
            summary_text = f"代采代发付款 {supplier_name} {ds_nos}"

            vno = await next_voucher_no(account_set_id, "付", period_name)
            v = await Voucher.create(
                account_set_id=account_set_id,
                voucher_type="付",
                voucher_no=vno,
                period_name=period_name,
                voucher_date=today,
                summary=summary_text,
                total_debit=total_amount,
                total_credit=total_amount,
                status="draft",
                creator=user,
                source_type="dropship_payment",
                source_bill_id=group_disbs[0].id,
            )

            # 借方：预付账款
            await VoucherEntry.create(
                voucher=v,
                line_no=1,
                account_id=prepaid_account.id,
                summary=summary_text,
                debit_amount=total_amount,
                credit_amount=Decimal("0"),
                aux_supplier_id=supplier_id,
            )

            # 贷方：根据付款方式决定科目
            if payment_method == "employee_advance":
                await VoucherEntry.create(
                    voucher=v,
                    line_no=2,
                    account_id=other_receivable_account.id,
                    summary=summary_text,
                    debit_amount=Decimal("0"),
                    credit_amount=total_amount,
                    aux_employee_id=employee_id,
                )
            else:
                await VoucherEntry.create(
                    voucher=v,
                    line_no=2,
                    account_id=bank_account.id,
                    summary=summary_text,
                    debit_amount=Decimal("0"),
                    credit_amount=total_amount,
                )

            # 将凭证关联到付款单
            for disb in group_disbs:
                disb.voucher = v
                disb.voucher_no = vno
                await disb.save()

            vouchers_created.append({
                "id": v.id,
                "voucher_no": vno,
                "supplier_name": supplier_name,
                "amount": float(total_amount),
                "order_count": len(group_orders),
            })

            logger.info(f"生成代采代发付款凭证: {vno}, 供应商={supplier_name}, 金额={total_amount}")

    return {
        "paid_count": len(orders),
        "total_amount": float(sum(o.purchase_total for o in orders)),
        "vouchers": vouchers_created,
    }
