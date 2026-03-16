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
from app.models.ar_ap import PayableBill, DisbursementBill, ReceivableBill
from app.models.stock import WarehouseStock, StockLog
from app.models.warehouse import Warehouse
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


async def ship_dropship_order(
    order_id: int,
    carrier_code: str,
    carrier_name: str,
    tracking_no: str,
    user: User,
) -> DropshipOrder:
    """
    确认发货：更新物流信息、创建应收单、处理过手转发出入库、订阅快递100。

    流程:
    1. 校验订单状态为 paid_pending_ship
    2. 更新物流信息 (carrier_code, carrier_name, tracking_no)
    3. 创建应收单 (ReceivableBill)
    4. 若 shipping_mode == 'transit'，通过虚拟中转仓创建入库+出库记录
    5. 订阅快递100 (失败不阻断主流程)
    6. 状态 → shipped
    """

    async with transactions.in_transaction():
        # 1. 加锁查询订单
        order = await DropshipOrder.filter(id=order_id).select_for_update().first()
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        if order.status != "paid_pending_ship":
            raise HTTPException(
                status_code=400,
                detail=f"只有已付待发状态可以发货，当前状态: {order.status}",
            )

        # 2. 更新物流信息
        order.carrier_code = carrier_code
        order.carrier_name = carrier_name
        order.tracking_no = tracking_no

        # 3. 创建应收单
        bill_no = generate_order_no("YS-DS")
        receivable = await ReceivableBill.create(
            bill_no=bill_no,
            account_set_id=order.account_set_id,
            customer_id=order.customer_id,
            bill_date=date.today(),
            total_amount=order.sale_total,
            received_amount=Decimal("0"),
            unreceived_amount=order.sale_total,
            status="pending",
            platform_order_no=order.platform_order_no,
            dropship_order_id=order.id,
            remark=f"代采代发订单 {order.ds_no}",
            creator=user,
        )
        logger.info(f"创建应收单: {bill_no}, 金额: {order.sale_total}")

        # 4. 过手转发：通过虚拟中转仓记录出入库
        if order.shipping_mode == "transit":
            # 查找或创建虚拟中转仓
            transit_wh, _ = await Warehouse.get_or_create(
                name="代采代发中转仓",
                defaults={"is_virtual": True, "is_active": True},
            )

            # 入库记录
            await StockLog.create(
                product_id=order.product_id,
                warehouse=transit_wh,
                change_type="PURCHASE_IN",
                quantity=order.quantity,
                before_qty=0,
                after_qty=order.quantity,
                reference_type="DROPSHIP",
                reference_id=order.id,
                remark=f"代采代发入库 {order.ds_no}",
                creator=user,
            )

            # 出库记录
            await StockLog.create(
                product_id=order.product_id,
                warehouse=transit_wh,
                change_type="SALE",
                quantity=-order.quantity,
                before_qty=order.quantity,
                after_qty=0,
                reference_type="DROPSHIP",
                reference_id=order.id,
                remark=f"代采代发出库 {order.ds_no}",
                creator=user,
            )

            # 更新库存记录（净库存为0）
            ws, _ = await WarehouseStock.get_or_create(
                warehouse=transit_wh,
                product_id=order.product_id,
                location=None,
                defaults={"quantity": 0, "reserved_qty": 0},
            )
            ws.quantity = 0
            ws.last_activity_at = now()
            await ws.save()

            logger.info(f"过手转发出入库: {order.ds_no}, 中转仓={transit_wh.name}")

        # 5. 关联应收单并更新状态
        order.receivable_bill_id = receivable.id
        order.status = "shipped"
        await order.save()

    # 6. 订阅快递100（事务外，失败不阻断）
    try:
        from app.services.logistics_service import subscribe_kd100
        await subscribe_kd100(carrier_code, tracking_no, order.id)
        order.kd100_subscribed = True
        await order.save()
        logger.info(f"快递100订阅成功: {order.ds_no}, 快递={carrier_code}, 单号={tracking_no}")
    except Exception as e:
        logger.warning(f"快递100订阅失败（不影响发货）: {order.ds_no}, 错误: {e}")

    logger.info(f"代采代发发货: {order.ds_no} → shipped, 应收单={bill_no}")
    return order


async def _create_reverse_voucher(original_voucher_id: int, user: User) -> Optional[Voucher]:
    """基于原凭证创建红冲凭证（所有金额取反）"""

    original = await Voucher.filter(id=original_voucher_id).first()
    if not original:
        return None

    entries = await VoucherEntry.filter(voucher_id=original.id).all()

    period_name = f"{date.today().year}-{date.today().month:02d}"
    vno = await next_voucher_no(original.account_set_id, original.voucher_type, period_name)

    reverse_v = await Voucher.create(
        account_set_id=original.account_set_id,
        voucher_type=original.voucher_type,
        voucher_no=vno,
        period_name=period_name,
        voucher_date=date.today(),
        summary=f"【红冲】{original.summary}",
        total_debit=-original.total_debit,
        total_credit=-original.total_credit,
        status="draft",
        creator=user,
        source_type="dropship_cancel",
        source_bill_id=original.source_bill_id,
    )

    for entry in entries:
        await VoucherEntry.create(
            voucher=reverse_v,
            line_no=entry.line_no,
            account_id=entry.account_id,
            summary=f"【红冲】{entry.summary}",
            debit_amount=-entry.debit_amount,
            credit_amount=-entry.credit_amount,
            aux_customer_id=entry.aux_customer_id,
            aux_supplier_id=entry.aux_supplier_id,
            aux_employee_id=entry.aux_employee_id,
        )

    logger.info(f"创建红冲凭证: {vno}, 原凭证={original.voucher_no}")
    return reverse_v


async def cancel_dropship_order(order_id: int, reason: str, user: User) -> DropshipOrder:
    """
    取消代采代发订单

    按取消时的状态分别处理：
    - 草稿(draft): 直接取消
    - 待付款(pending_payment): 冲销应付单
    - 已付待发(paid_pending_ship): 冲销应付单 + 付款单 + 红冲凭证
    - 已发货及之后: 不允许取消
    """

    async with transactions.in_transaction():
        # 加锁查询订单
        order = await DropshipOrder.filter(id=order_id).select_for_update().first()
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")

        # 已发货及之后不允许取消
        if order.status in ("shipped", "completed", "cancelled"):
            raise HTTPException(
                status_code=400,
                detail=f"当前状态({order.status})不允许取消",
            )

        # 1. 草稿 → 直接取消
        if order.status == "draft":
            order.status = "cancelled"
            order.cancel_reason = reason
            await order.save()
            logger.info(f"代采代发取消(草稿): {order.ds_no}, 原因: {reason}")
            return order

        # 2. 待付款 → 冲销应付单
        if order.status == "pending_payment":
            if order.payable_bill_id:
                pb = await PayableBill.filter(id=order.payable_bill_id).select_for_update().first()
                if pb:
                    pb.status = "cancelled"
                    await pb.save()
                    logger.info(f"冲销应付单: {pb.bill_no}")

            order.status = "cancelled"
            order.cancel_reason = reason
            await order.save()
            logger.info(f"代采代发取消(待付款): {order.ds_no}, 原因: {reason}")
            return order

        # 3. 已付待发 → 冲销应付单 + 付款单 + 红冲凭证
        if order.status == "paid_pending_ship":
            # 冲销应付单
            if order.payable_bill_id:
                pb = await PayableBill.filter(id=order.payable_bill_id).select_for_update().first()
                if pb:
                    pb.status = "cancelled"
                    await pb.save()
                    logger.info(f"冲销应付单: {pb.bill_no}")

            # 冲销付款单 + 红冲凭证
            if order.disbursement_bill_id:
                disb = await DisbursementBill.filter(id=order.disbursement_bill_id).select_for_update().first()
                if disb:
                    disb.status = "cancelled"
                    await disb.save()
                    logger.info(f"冲销付款单: {disb.bill_no}")

                    # 红冲关联凭证
                    if disb.voucher_id:
                        reverse_v = await _create_reverse_voucher(disb.voucher_id, user)
                        if reverse_v:
                            logger.info(f"红冲凭证已生成: {reverse_v.voucher_no}")

            order.status = "cancelled"
            order.cancel_reason = reason
            await order.save()
            logger.info(f"代采代发取消(已付待发): {order.ds_no}, 原因: {reason}")
            return order

    # 兜底（理论上不会走到这里）
    raise HTTPException(status_code=400, detail=f"无法取消，当前状态: {order.status}")
