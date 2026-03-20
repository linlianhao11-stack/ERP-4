"""样机管理服务层"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from tortoise import transactions

from app.models import (
    DemoUnit, DemoLoan, DemoDisposal,
    Product, Warehouse, Location, WarehouseStock, StockLog,
    SnCode, Customer, Employee, Order, OrderItem,
)
from app.services.stock_service import update_weighted_entry_date
from app.services.ar_service import create_receivable_bill
from app.utils.generators import generate_sequential_no, generate_order_no
from app.utils.time import now
from app.logger import get_logger

logger = get_logger("demo")


# ── 辅助函数 ──

def _require_status(unit: DemoUnit, *allowed: str):
    """检查样机状态，不在允许列表则抛出 400"""
    if unit.status not in allowed:
        labels = {
            "in_stock": "在库", "lent_out": "借出中", "repairing": "维修中",
            "sold": "已转销售", "scrapped": "已报废", "lost": "已丢失", "converted": "已转良品",
        }
        current = labels.get(unit.status, unit.status)
        expected = "、".join(labels.get(s, s) for s in allowed)
        raise HTTPException(status_code=400, detail=f"当前状态为「{current}」，仅「{expected}」状态可执行此操作")


async def _get_unit(unit_id: int) -> DemoUnit:
    """获取样机并预加载关联，不存在则 404"""
    unit = await DemoUnit.filter(id=unit_id).select_related("product", "warehouse", "sn_code").first()
    if not unit:
        raise HTTPException(status_code=404, detail="样机不存在")
    return unit


async def _resolve_sn(
    sn_code_str: str,
    product_id: int,
    warehouse_id: int,
    source_warehouse_id: Optional[int],
    user,
) -> SnCode:
    """查找或创建 SN 码记录。

    如果是库存调拨（source_warehouse_id 有值），优先在源仓库查找匹配的 SN 码并迁移；
    否则新建一条 SN 码记录。
    """
    if source_warehouse_id:
        existing = await SnCode.filter(
            sn_code=sn_code_str,
            warehouse_id=source_warehouse_id,
            product_id=product_id,
            status="in_stock",
        ).first()
        if existing:
            existing.warehouse_id = warehouse_id
            existing.location = None
            existing.status = "in_stock"
            await existing.save()
            return existing

    # 检查 SN 码是否已存在（全局唯一）
    existing_any = await SnCode.filter(sn_code=sn_code_str).first()
    if existing_any:
        raise HTTPException(status_code=400, detail=f"SN 码 {sn_code_str} 已存在")

    sn = await SnCode.create(
        sn_code=sn_code_str,
        warehouse_id=warehouse_id,
        product_id=product_id,
        status="in_stock",
        entry_type="DEMO_IN",
        entry_date=now(),
        entry_user=user,
    )
    return sn


# ── 样机 CRUD ──

@transactions.atomic()
async def create_demo_unit(data, user) -> DemoUnit:
    """新增样机

    两种来源：
    - stock_transfer: 从源仓库扣减库存，加到样机仓
    - new_purchase: 直接以采购成本入样机仓
    """
    product = await Product.filter(id=data.product_id, is_active=True).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    warehouse = await Warehouse.filter(id=data.warehouse_id, is_active=True).first()
    if not warehouse:
        raise HTTPException(status_code=404, detail="目标仓库不存在")

    # 验证目标仓位
    target_location = None
    if data.location_id:
        target_location = await Location.filter(id=data.location_id, warehouse_id=data.warehouse_id).first()
        if not target_location:
            raise HTTPException(status_code=400, detail="目标仓位不存在或不属于该仓库")

    # 确定成本
    cost_price = Decimal("0")

    if data.source == "stock_transfer":
        if not data.source_warehouse_id:
            raise HTTPException(status_code=400, detail="库存调拨需指定源仓库")
        src_wh = await Warehouse.filter(id=data.source_warehouse_id, is_active=True).first()
        if not src_wh:
            raise HTTPException(status_code=404, detail="源仓库不存在")

        # 查找源仓库库存（优先按仓位精确匹配）
        src_stock_query = {"warehouse_id": data.source_warehouse_id, "product_id": data.product_id}
        if data.source_location_id:
            src_stock_query["location_id"] = data.source_location_id
        src_stock = await WarehouseStock.filter(**src_stock_query).first()
        if not src_stock or src_stock.quantity < 1:
            raise HTTPException(status_code=400, detail="源仓库库存不足")

        cost_price = src_stock.weighted_cost or product.cost_price or Decimal("0")

        # 扣减源仓库库存
        before_qty = src_stock.quantity
        await update_weighted_entry_date(
            data.source_warehouse_id, data.product_id, -1, cost_price,
            data.source_location_id,
        )
        await StockLog.create(
            product_id=data.product_id, warehouse_id=data.source_warehouse_id,
            change_type="TRANSFER_OUT", quantity=-1,
            before_qty=before_qty, after_qty=before_qty - 1,
            remark=f"调拨至样机仓 {warehouse.name}", creator=user,
        )
    else:
        # new_purchase
        cost_price = data.cost_price or product.cost_price or Decimal("0")

    # 增加样机仓库存
    demo_stock = await WarehouseStock.filter(
        warehouse_id=data.warehouse_id,
        product_id=data.product_id,
    ).first()
    before_demo = demo_stock.quantity if demo_stock else 0
    await update_weighted_entry_date(
        data.warehouse_id, data.product_id, 1, cost_price,
        data.location_id,
    )

    await StockLog.create(
        product_id=data.product_id, warehouse_id=data.warehouse_id,
        change_type="RESTOCK", quantity=1,
        before_qty=before_demo, after_qty=before_demo + 1,
        remark=f"样机入库（{('库存调拨' if data.source == 'stock_transfer' else '新采购')}）",
        creator=user,
    )

    # SN 码处理
    sn = await _resolve_sn(
        data.sn_code, data.product_id, data.warehouse_id,
        data.source_warehouse_id if data.source == "stock_transfer" else None,
        user,
    )

    code = await generate_sequential_no("DM", "demo_units", "code")

    unit = await DemoUnit.create(
        code=code,
        product_id=data.product_id,
        sn_code=sn,
        warehouse_id=data.warehouse_id,
        location_id=data.location_id,
        status="in_stock",
        condition=data.condition,
        cost_price=cost_price,
        notes=data.notes,
        created_by=user,
    )
    logger.info(f"创建样机: {code}, 商品: {product.name}, SN: {data.sn_code}")
    return unit


# ── 借还流程 ──

@transactions.atomic()
async def create_demo_loan(data, user) -> DemoLoan:
    """创建借出申请"""
    unit = await _get_unit(data.demo_unit_id)
    _require_status(unit, "in_stock")

    # 一机一借：检查是否已有进行中的借出记录
    existing = await DemoLoan.filter(
        demo_unit_id=data.demo_unit_id,
        status__in=["pending_approval", "approved", "lent_out"],
    ).count()
    if existing > 0:
        raise HTTPException(status_code=400, detail="该样机已有进行中的借出记录")

    # 验证借用人
    if data.borrower_type == "customer":
        borrower = await Customer.filter(id=data.borrower_id, is_active=True).first()
        if not borrower:
            raise HTTPException(status_code=404, detail="客户不存在")
    else:
        borrower = await Employee.filter(id=data.borrower_id, is_active=True).first()
        if not borrower:
            raise HTTPException(status_code=404, detail="员工不存在")

    loan_no = await generate_sequential_no("DL", "demo_loans", "loan_no")

    loan = await DemoLoan.create(
        loan_no=loan_no,
        demo_unit_id=data.demo_unit_id,
        loan_type=data.loan_type,
        borrower_type=data.borrower_type,
        borrower_id=data.borrower_id,
        handler_id=data.handler_id,
        expected_return_date=data.expected_return_date,
        condition_on_loan=unit.condition,
        purpose=data.purpose,
        status="pending_approval",
        created_by=user,
    )
    logger.info(f"创建借出申请: {loan_no}, 样机: {unit.code}")
    return loan


@transactions.atomic()
async def approve_demo_loan(loan_id: int, user) -> DemoLoan:
    """审批通过"""
    loan = await DemoLoan.filter(id=loan_id).select_for_update().first()
    if not loan:
        raise HTTPException(status_code=404, detail="借出记录不存在")
    if loan.status != "pending_approval":
        raise HTTPException(status_code=400, detail="仅待审批状态可审批")

    loan.status = "approved"
    loan.approved_by = user
    loan.approved_at = now()
    await loan.save()
    logger.info(f"审批通过: {loan.loan_no}")
    return loan


@transactions.atomic()
async def reject_demo_loan(loan_id: int, user) -> DemoLoan:
    """审批拒绝"""
    loan = await DemoLoan.filter(id=loan_id).select_for_update().first()
    if not loan:
        raise HTTPException(status_code=404, detail="借出记录不存在")
    if loan.status != "pending_approval":
        raise HTTPException(status_code=400, detail="仅待审批状态可拒绝")

    loan.status = "rejected"
    # 复用 approved_by/approved_at 记录拒绝人和时间
    loan.approved_by = user
    loan.approved_at = now()
    await loan.save()
    logger.info(f"审批拒绝: {loan.loan_no}")
    return loan


@transactions.atomic()
async def lend_demo_unit(loan_id: int, user) -> DemoLoan:
    """确认借出"""
    loan = await DemoLoan.filter(id=loan_id).select_related("demo_unit").first()
    if not loan:
        raise HTTPException(status_code=404, detail="借出记录不存在")
    if loan.status != "approved":
        raise HTTPException(status_code=400, detail="仅已审批状态可执行借出")

    unit = loan.demo_unit
    _require_status(unit, "in_stock")

    # 更新借出记录
    loan.status = "lent_out"
    loan.loan_date = date.today()
    await loan.save()

    # 更新样机状态
    unit.status = "lent_out"
    unit.current_holder_type = loan.borrower_type
    unit.current_holder_id = loan.borrower_id
    await unit.save()

    # 扣减样机仓库存
    demo_stock = await WarehouseStock.filter(
        warehouse_id=unit.warehouse_id, product_id=unit.product_id,
        location_id=unit.location_id,
    ).first()
    before_qty = demo_stock.quantity if demo_stock else 0
    await update_weighted_entry_date(
        unit.warehouse_id, unit.product_id, -1, unit.cost_price,
        unit.location_id,
    )
    await StockLog.create(
        product_id=unit.product_id, warehouse_id=unit.warehouse_id,
        change_type="TRANSFER_OUT", quantity=-1,
        before_qty=before_qty, after_qty=before_qty - 1,
        remark=f"样机借出 {loan.loan_no}", creator=user,
    )

    # 更新 SN 码状态
    if unit.sn_code_id:
        await SnCode.filter(id=unit.sn_code_id).update(status="shipped")

    logger.info(f"确认借出: {loan.loan_no}, 样机: {unit.code}")
    return loan


@transactions.atomic()
async def return_demo_unit(loan_id: int, data, user) -> DemoLoan:
    """归还样机"""
    loan = await DemoLoan.filter(id=loan_id).select_related("demo_unit").first()
    if not loan:
        raise HTTPException(status_code=404, detail="借出记录不存在")
    if loan.status != "lent_out":
        raise HTTPException(status_code=400, detail="仅借出中状态可归还")

    unit = loan.demo_unit

    # 计算借出天数
    loan_days = 0
    if loan.loan_date:
        loan_days = (date.today() - loan.loan_date).days

    # 更新借出记录
    loan.status = "returned"
    loan.actual_return_date = date.today()
    loan.condition_on_return = data.condition_on_return
    loan.return_notes = data.return_notes
    await loan.save()

    # 更新样机统计
    unit.status = "in_stock"
    unit.condition = data.condition_on_return
    unit.current_holder_type = None
    unit.current_holder_id = None
    unit.total_loan_count += 1
    unit.total_loan_days += loan_days
    await unit.save()

    # 归还入库：样机仓库存 +1
    demo_stock = await WarehouseStock.filter(
        warehouse_id=unit.warehouse_id, product_id=unit.product_id,
        location_id=unit.location_id,
    ).first()
    before_qty = demo_stock.quantity if demo_stock else 0
    await update_weighted_entry_date(
        unit.warehouse_id, unit.product_id, 1, unit.cost_price,
        unit.location_id,
    )
    await StockLog.create(
        product_id=unit.product_id, warehouse_id=unit.warehouse_id,
        change_type="RESTOCK", quantity=1,
        before_qty=before_qty, after_qty=before_qty + 1,
        remark=f"样机归还入库 {loan.loan_no}", creator=user,
    )

    # 恢复 SN 码状态
    if unit.sn_code_id:
        await SnCode.filter(id=unit.sn_code_id).update(status="in_stock")

    logger.info(f"样机归还: {loan.loan_no}, 借出天数: {loan_days}")
    return loan


# ── 处置操作 ──

@transactions.atomic()
async def sell_demo_unit(unit_id: int, data, user) -> DemoDisposal:
    """样机转销售"""
    unit = await _get_unit(unit_id)
    _require_status(unit, "in_stock", "lent_out")

    customer = await Customer.filter(id=data.customer_id, is_active=True).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    # 如果借出中，自动关闭活跃借出
    if unit.status == "lent_out":
        active_loan = await DemoLoan.filter(
            demo_unit_id=unit_id, status="lent_out",
        ).first()
        if active_loan:
            active_loan.status = "closed"
            active_loan.actual_return_date = date.today()
            active_loan.return_notes = "样机转销售，自动关闭借出"
            await active_loan.save()

    # 创建销售订单
    order_no = generate_order_no("ORD")
    profit = data.sale_price - unit.cost_price
    order = await Order.create(
        order_no=order_no,
        order_type="CASH",
        customer_id=data.customer_id,
        warehouse_id=unit.warehouse_id,
        total_amount=data.sale_price,
        total_cost=unit.cost_price,
        total_profit=profit,
        remark=data.remark or f"样机转销售 {unit.code}",
        employee_id=data.employee_id,
        creator=user,
        account_set_id=data.account_set_id,
    )
    await OrderItem.create(
        order=order,
        product_id=unit.product_id,
        warehouse_id=unit.warehouse_id,
        quantity=1,
        unit_price=data.sale_price,
        cost_price=unit.cost_price,
        amount=data.sale_price,
        profit=profit,
    )

    # 创建应收单
    rb = await create_receivable_bill(
        account_set_id=data.account_set_id,
        customer_id=data.customer_id,
        order_id=order.id,
        total_amount=data.sale_price,
        status="pending",
        creator=user,
        remark=f"样机转销售 {unit.code}",
    )

    # 仅 in_stock 状态才扣减库存（lent_out 时借出已经扣过了）
    if unit.status == "in_stock":
        demo_stock = await WarehouseStock.filter(
            warehouse_id=unit.warehouse_id, product_id=unit.product_id,
            location_id=unit.location_id,
        ).first()
        before_qty = demo_stock.quantity if demo_stock else 0
        await update_weighted_entry_date(
            unit.warehouse_id, unit.product_id, -1, unit.cost_price,
            unit.location_id,
        )
        await StockLog.create(
            product_id=unit.product_id, warehouse_id=unit.warehouse_id,
            change_type="SALE", quantity=-1,
            before_qty=before_qty, after_qty=max(before_qty - 1, 0),
            remark=f"样机转销售 {unit.code}", creator=user,
        )
    else:
        # lent_out → sold：库存已在借出时扣减，仅记日志
        await StockLog.create(
            product_id=unit.product_id, warehouse_id=unit.warehouse_id,
            change_type="SALE", quantity=0,
            before_qty=0, after_qty=0,
            remark=f"样机转销售（借出中） {unit.code}", creator=user,
        )

    # 更新 SN 码状态
    if unit.sn_code_id:
        await SnCode.filter(id=unit.sn_code_id).update(status="shipped")

    # 更新样机状态
    unit.status = "sold"
    unit.current_holder_type = None
    unit.current_holder_id = None
    await unit.save()

    # 记录处置
    disposal = await DemoDisposal.create(
        demo_unit_id=unit_id,
        disposal_type="sale",
        amount=data.sale_price,
        order_id=order.id,
        receivable_bill_id=rb.id,
        reason=data.remark,
        created_by=user,
    )
    logger.info(f"样机转销售: {unit.code}, 订单: {order_no}, 金额: {data.sale_price}")
    return disposal


@transactions.atomic()
async def convert_demo_unit(unit_id: int, data, user) -> DemoDisposal:
    """样机翻新转良品"""
    unit = await _get_unit(unit_id)
    _require_status(unit, "in_stock")

    target_wh = await Warehouse.filter(id=data.target_warehouse_id, is_active=True).first()
    if not target_wh:
        raise HTTPException(status_code=404, detail="目标仓库不存在")

    refurbish_cost = data.refurbish_cost or Decimal("0")
    new_cost = unit.cost_price + refurbish_cost

    # 扣减样机仓库存
    demo_stock = await WarehouseStock.filter(
        warehouse_id=unit.warehouse_id, product_id=unit.product_id,
        location_id=unit.location_id,
    ).first()
    before_demo = demo_stock.quantity if demo_stock else 0
    await update_weighted_entry_date(
        unit.warehouse_id, unit.product_id, -1, unit.cost_price,
        unit.location_id,
    )
    await StockLog.create(
        product_id=unit.product_id, warehouse_id=unit.warehouse_id,
        change_type="TRANSFER_OUT", quantity=-1,
        before_qty=before_demo, after_qty=max(before_demo - 1, 0),
        remark=f"样机转良品 {unit.code} → {target_wh.name}", creator=user,
    )

    # 增加目标仓库库存
    target_stock = await WarehouseStock.filter(
        warehouse_id=data.target_warehouse_id, product_id=unit.product_id,
    ).first()
    before_target = target_stock.quantity if target_stock else 0
    await update_weighted_entry_date(
        data.target_warehouse_id, unit.product_id, 1, new_cost,
        data.target_location_id,
    )
    await StockLog.create(
        product_id=unit.product_id, warehouse_id=data.target_warehouse_id,
        change_type="TRANSFER_IN", quantity=1,
        before_qty=before_target, after_qty=before_target + 1,
        remark=f"样机翻新入库 {unit.code}, 翻新成本: ¥{refurbish_cost}", creator=user,
    )

    # 迁移 SN 码到目标仓库
    if unit.sn_code_id:
        await SnCode.filter(id=unit.sn_code_id).update(
            warehouse_id=data.target_warehouse_id,
            location_id=data.target_location_id,
            status="in_stock",
        )

    # 更新样机状态
    unit.status = "converted"
    await unit.save()

    disposal = await DemoDisposal.create(
        demo_unit_id=unit_id,
        disposal_type="conversion",
        refurbish_cost=refurbish_cost,
        target_warehouse_id=data.target_warehouse_id,
        target_location_id=data.target_location_id,
        reason=f"翻新成本: ¥{refurbish_cost}, 新成本: ¥{new_cost}",
        created_by=user,
    )
    logger.info(f"样机转良品: {unit.code} → {target_wh.name}, 翻新成本: {refurbish_cost}")
    return disposal


@transactions.atomic()
async def scrap_demo_unit(unit_id: int, data, user) -> DemoDisposal:
    """样机报废"""
    unit = await _get_unit(unit_id)
    _require_status(unit, "in_stock", "repairing")

    # 扣减样机仓库存
    demo_stock = await WarehouseStock.filter(
        warehouse_id=unit.warehouse_id, product_id=unit.product_id,
        location_id=unit.location_id,
    ).first()
    before_qty = demo_stock.quantity if demo_stock else 0
    await update_weighted_entry_date(
        unit.warehouse_id, unit.product_id, -1, unit.cost_price,
        unit.location_id,
    )
    await StockLog.create(
        product_id=unit.product_id, warehouse_id=unit.warehouse_id,
        change_type="ADJUST", quantity=-1,
        before_qty=before_qty, after_qty=max(before_qty - 1, 0),
        remark=f"样机报废 {unit.code}: {data.reason}", creator=user,
    )

    # SN 码标记为 shipped（已出库），当前 SN 体系无 disposed 状态
    if unit.sn_code_id:
        await SnCode.filter(id=unit.sn_code_id).update(status="shipped")

    unit.status = "scrapped"
    await unit.save()

    disposal = await DemoDisposal.create(
        demo_unit_id=unit_id,
        disposal_type="scrap",
        amount=data.residual_value,
        reason=data.reason,
        created_by=user,
    )
    logger.info(f"样机报废: {unit.code}, 原因: {data.reason}")
    return disposal


@transactions.atomic()
async def report_loss_demo_unit(unit_id: int, data, user) -> DemoDisposal:
    """样机丢失"""
    unit = await _get_unit(unit_id)
    _require_status(unit, "lent_out")

    # 自动关闭活跃借出
    active_loan = await DemoLoan.filter(
        demo_unit_id=unit_id, status="lent_out",
    ).first()
    if active_loan:
        active_loan.status = "closed"
        active_loan.actual_return_date = date.today()
        active_loan.return_notes = f"样机丢失: {data.description}"
        await active_loan.save()

    # 如果借用人是客户，创建赔偿应收
    rb_id = None
    if active_loan and active_loan.borrower_type == "customer":
        rb = await create_receivable_bill(
            account_set_id=data.account_set_id,
            customer_id=active_loan.borrower_id,
            total_amount=data.compensation_amount,
            status="pending",
            creator=user,
            remark=f"样机丢失赔偿 {unit.code}",
        )
        rb_id = rb.id

    # 注意：不扣减库存 — 借出时已经扣过（lend_demo_unit 中 -1），丢失只是最终状态变更
    # 仅记录一条日志便于追溯
    await StockLog.create(
        product_id=unit.product_id, warehouse_id=unit.warehouse_id,
        change_type="ADJUST", quantity=0,
        before_qty=0, after_qty=0,
        remark=f"样机丢失（借出中） {unit.code}: {data.description}", creator=user,
    )

    # SN 码标记为 shipped（已出库），当前 SN 体系无 disposed 状态
    if unit.sn_code_id:
        await SnCode.filter(id=unit.sn_code_id).update(status="shipped")

    unit.status = "lost"
    unit.current_holder_type = None
    unit.current_holder_id = None
    await unit.save()

    disposal = await DemoDisposal.create(
        demo_unit_id=unit_id,
        disposal_type="loss_compensation",
        amount=data.compensation_amount,
        receivable_bill_id=rb_id,
        reason=data.description,
        created_by=user,
    )
    logger.info(f"样机丢失: {unit.code}, 赔偿金额: {data.compensation_amount}")
    return disposal


# ── 删除样机 ──

@transactions.atomic()
async def delete_demo_unit(unit_id: int, user):
    """删除样机（仅在库且无借还记录）"""
    unit = await DemoUnit.filter(id=unit_id).select_for_update().first()
    if not unit:
        raise HTTPException(status_code=404, detail="样机不存在")
    if unit.status != "in_stock":
        raise HTTPException(status_code=400, detail="只能删除在库样机")
    if await DemoLoan.filter(demo_unit_id=unit.id).exists():
        raise HTTPException(status_code=400, detail="该样机有借还记录，不能删除")

    # 反转库存操作
    stock = await WarehouseStock.filter(
        warehouse_id=unit.warehouse_id, product_id=unit.product_id,
        location_id=unit.location_id,
    ).select_for_update().first()
    if stock and stock.quantity > 0:
        before = stock.quantity
        stock.quantity -= 1
        await stock.save()
        await StockLog.create(
            product_id=unit.product_id, warehouse_id=unit.warehouse_id,
            change_type="DEMO_DELETE", quantity=-1,
            before_qty=before, after_qty=stock.quantity,
            reference_type="DEMO_UNIT", remark=f"删除样机 {unit.code}",
            creator=user,
        )

    # 删除关联 SN 码（如果是样机模块创建的）
    if unit.sn_code_id:
        sn = await SnCode.filter(id=unit.sn_code_id).first()
        if sn and sn.entry_type == "DEMO_IN":
            await sn.delete()

    await unit.delete()


# ── 统计 ──

async def get_demo_stats(warehouse_id: Optional[int] = None) -> dict:
    """样机统计"""
    query = DemoUnit.all()
    if warehouse_id:
        query = query.filter(warehouse_id=warehouse_id)

    units = await query.all()
    total = len(units)
    in_stock = sum(1 for u in units if u.status == "in_stock")
    lent_out = sum(1 for u in units if u.status == "lent_out")
    total_value = sum(u.cost_price for u in units if u.status in ("in_stock", "lent_out", "repairing"))

    # 逾期数量：借出中且超过预期归还日期
    overdue_count = 0
    lent_unit_ids = [u.id for u in units if u.status == "lent_out"]
    if lent_unit_ids:
        overdue_count = await DemoLoan.filter(
            demo_unit_id__in=lent_unit_ids,
            status="lent_out",
            expected_return_date__lt=date.today(),
        ).count()

    return {
        "total": total,
        "in_stock": in_stock,
        "lent_out": lent_out,
        "overdue": overdue_count,
        "total_value": float(total_value),
    }
