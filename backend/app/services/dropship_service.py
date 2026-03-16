"""代采代发服务层"""
from __future__ import annotations

import secrets
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from tortoise import transactions

from app.logger import get_logger
from app.models import Supplier, Product, User
from app.models.ar_ap import PayableBill
from app.models.dropship import DropshipOrder
from app.schemas.dropship import DropshipOrderCreate
from app.utils.generators import generate_sequential_no, generate_order_no
from app.utils.time import now

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
