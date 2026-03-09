"""业务流程集成测试 — 覆盖采购/销售/库存/财务期末5条核心链路"""
from decimal import Decimal
from datetime import date, datetime, timezone

from tortoise.expressions import F

from app.models import (
    User, Customer, Supplier, Product,
    Warehouse, Location, WarehouseStock, StockLog,
    Order, OrderItem, Payment, PurchaseOrder, PurchaseOrderItem,
)
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.ar_ap import ReceivableBill, ReceiptBill, PayableBill, DisbursementBill
from app.models.voucher import Voucher, VoucherEntry
from app.models.delivery import SalesDeliveryBill, PurchaseReceiptBill
from app.models.invoice import Invoice, InvoiceItem

from app.services.ar_service import (
    create_receivable_bill, create_receipt_bill_for_payment, generate_ar_vouchers,
)
from app.services.ap_service import (
    create_payable_bill, create_disbursement_for_po_payment, generate_ap_vouchers,
)
from app.services.delivery_service import create_sales_delivery, create_purchase_receipt
from app.services.invoice_service import push_invoice_from_receivable, confirm_invoice
from app.services.stock_service import update_weighted_entry_date, get_product_weighted_cost
from app.services.period_end_service import (
    preview_carry_forward, execute_carry_forward, close_check, close_period,
)
from app.services.report_service import get_balance_sheet, get_income_statement
from app.services.ledger_service import get_trial_balance
from app.services.accounting_init import init_chart_of_accounts
from app.utils.generators import generate_order_no


# ─── 辅助函数 ────────────────────────────────────────────────────────────

async def _create_base_data() -> dict:
    """创建完整基础测试数据：账套+32科目+期间+客户+供应商+用户+仓库+仓位+2商品"""
    today = date.today()
    current_period = f"{today.year}-{today.month:02d}"

    # 账套
    account_set = await AccountSet.create(
        code="BIZ", name="集成测试账套", company_name="测试公司",
        start_year=today.year, start_month=1, current_period=current_period,
    )
    # 32个标准科目
    await init_chart_of_accounts(account_set.id)
    # 当月会计期间
    period = await AccountingPeriod.create(
        account_set=account_set, period_name=current_period,
        year=today.year, month=today.month,
    )
    # 基础主数据
    user = await User.create(username="biztest", password_hash="x", display_name="集成测试员")
    customer = await Customer.create(name="测试客户A")
    supplier = await Supplier.create(name="测试供应商B")
    warehouse = await Warehouse.create(name="主仓库", is_default=True, account_set=account_set)
    location = await Location.create(warehouse=warehouse, code="A01", name="A区01号")
    product_a = await Product.create(
        sku="BIZ001", name="集成商品A", brand="测试",
        retail_price=Decimal("100.00"), cost_price=Decimal("60.00"), tax_rate=Decimal("13"),
    )
    product_b = await Product.create(
        sku="BIZ002", name="集成商品B", brand="测试",
        retail_price=Decimal("200.00"), cost_price=Decimal("120.00"), tax_rate=Decimal("13"),
    )
    return {
        "account_set": account_set,
        "period": period,
        "current_period": current_period,
        "user": user,
        "customer": customer,
        "supplier": supplier,
        "warehouse": warehouse,
        "location": location,
        "product_a": product_a,
        "product_b": product_b,
    }


async def _post_voucher(account_set, user, accts, period_name, entries_data):
    """创建并直接过账一张凭证。entries_data: [(科目code, 'debit'/'credit', Decimal金额), ...]"""
    total_debit = sum(e[2] for e in entries_data if e[1] == "debit")
    total_credit = sum(e[2] for e in entries_data if e[1] == "credit")
    assert total_debit == total_credit, f"凭证借贷不平: {total_debit} != {total_credit}"

    seq = await Voucher.filter(account_set_id=account_set.id).count() + 1
    v = await Voucher.create(
        account_set=account_set, voucher_type="记",
        voucher_no=f"记-{period_name.replace('-','')}-{seq:03d}",
        period_name=period_name,
        voucher_date=date(int(period_name[:4]), int(period_name[5:7]), 15),
        summary="测试凭证", total_debit=total_debit, total_credit=total_credit,
        status="posted", creator=user,
        posted_by=user, posted_at=datetime.now(timezone.utc),
    )
    for i, (code, direction, amount) in enumerate(entries_data, 1):
        await VoucherEntry.create(
            voucher=v, line_no=i, account_id=accts[code].id,
            summary=f"测试-{code}",
            debit_amount=amount if direction == "debit" else Decimal("0"),
            credit_amount=amount if direction == "credit" else Decimal("0"),
        )
    return v


# ─── 流程1：采购全流程 ────────────────────────────────────────────────────

async def test_purchase_full_flow():
    """采购全流程：PO创建→审核→收货(应付单+入库单+凭证)→付款→库存验证→期末AP凭证"""
    d = await _create_base_data()

    # === 步骤1：创建采购订单 ===
    po = await PurchaseOrder.create(
        po_no=generate_order_no("PO"), supplier=d["supplier"],
        status="pending_review", total_amount=Decimal("2260.00"),
        target_warehouse=d["warehouse"], target_location=d["location"],
        creator=d["user"], account_set=d["account_set"],
    )
    poi_a = await PurchaseOrderItem.create(
        purchase_order=po, product=d["product_a"], quantity=10,
        tax_inclusive_price=Decimal("113.00"), tax_rate=Decimal("13"),
        tax_exclusive_price=Decimal("100.00"), amount=Decimal("1130.00"),
    )
    poi_b = await PurchaseOrderItem.create(
        purchase_order=po, product=d["product_b"], quantity=5,
        tax_inclusive_price=Decimal("226.00"), tax_rate=Decimal("13"),
        tax_exclusive_price=Decimal("200.00"), amount=Decimal("1130.00"),
    )
    assert po.status == "pending_review"
    assert po.total_amount == Decimal("2260.00")

    # === 步骤2：审核 ===
    po.status = "pending"
    po.reviewed_by = d["user"]
    po.reviewed_at = datetime.now(timezone.utc)
    await po.save()
    assert po.status == "pending"

    # === 步骤3：收货 — 模拟路由钩子 ===
    poi_a.received_quantity = 10
    await poi_a.save()
    poi_b.received_quantity = 5
    await poi_b.save()
    po.status = "completed"
    await po.save()

    # 3a: 创建应付单
    payable = await create_payable_bill(
        account_set_id=d["account_set"].id, supplier_id=d["supplier"].id,
        purchase_order_id=po.id, total_amount=Decimal("2260.00"),
        status="pending", creator=d["user"],
    )
    assert payable.bill_no.startswith("YF")
    assert payable.unpaid_amount == Decimal("2260.00")

    # 3b: 创建入库单 + 自动生成凭证
    receipt_bill = await create_purchase_receipt(
        account_set_id=d["account_set"].id, supplier_id=d["supplier"].id,
        purchase_order_id=po.id, warehouse_id=d["warehouse"].id,
        items=[
            {"product_id": d["product_a"].id, "product_name": "集成商品A",
             "quantity": 10, "tax_inclusive_price": "113.00",
             "tax_exclusive_price": "100.00", "tax_rate": "13"},
            {"product_id": d["product_b"].id, "product_name": "集成商品B",
             "quantity": 5, "tax_inclusive_price": "226.00",
             "tax_exclusive_price": "200.00", "tax_rate": "13"},
        ],
        creator=d["user"],
    )
    assert receipt_bill.bill_no.startswith("RK")
    assert receipt_bill.voucher_no is not None

    # 验证入库凭证分录（借1405+借222101 / 贷2202）
    v = await Voucher.filter(id=receipt_bill.voucher_id).first()
    entries = await VoucherEntry.filter(voucher=v).order_by("line_no").all()
    assert len(entries) == 3
    total_d = sum(e.debit_amount for e in entries)
    total_c = sum(e.credit_amount for e in entries)
    assert total_d == total_c  # 借贷平衡
    assert total_d == Decimal("2260.00")

    # 3c: 更新库存
    await update_weighted_entry_date(
        d["warehouse"].id, d["product_a"].id, 10,
        cost_price=Decimal("100.00"), location_id=d["location"].id,
    )
    await update_weighted_entry_date(
        d["warehouse"].id, d["product_b"].id, 5,
        cost_price=Decimal("200.00"), location_id=d["location"].id,
    )

    # === 步骤4：付款 ===
    disbursement = await create_disbursement_for_po_payment(
        account_set_id=d["account_set"].id, supplier_id=d["supplier"].id,
        payable_bill=payable, amount=Decimal("2260.00"),
        disbursement_method="对公转账", creator=d["user"],
    )
    assert disbursement.bill_no.startswith("FK")
    assert disbursement.status == "confirmed"

    # 应付单应已结清
    await payable.refresh_from_db()
    assert payable.paid_amount == Decimal("2260.00")
    assert payable.status == "completed"

    # === 步骤5：验证库存 ===
    stock_a = await WarehouseStock.filter(
        warehouse_id=d["warehouse"].id, product_id=d["product_a"].id,
        location_id=d["location"].id,
    ).first()
    assert stock_a.quantity == 10
    assert stock_a.weighted_cost == Decimal("100.00")

    stock_b = await WarehouseStock.filter(
        warehouse_id=d["warehouse"].id, product_id=d["product_b"].id,
        location_id=d["location"].id,
    ).first()
    assert stock_b.quantity == 5
    assert stock_b.weighted_cost == Decimal("200.00")

    # === 步骤6：期末生成AP凭证 ===
    ap_vouchers = await generate_ap_vouchers(
        d["account_set"].id, d["current_period"], d["user"],
    )
    assert len(ap_vouchers) == 1
    assert ap_vouchers[0]["source"].startswith("付款单")

    # 验证AP凭证分录（借应付2202 / 贷银行1002）
    v_ap = await Voucher.filter(id=ap_vouchers[0]["id"]).first()
    entries_ap = await VoucherEntry.filter(voucher=v_ap).order_by("line_no").all()
    assert len(entries_ap) == 2
    assert sum(e.debit_amount for e in entries_ap) == sum(e.credit_amount for e in entries_ap)


# ─── 流程2：现金销售全流程 ──────────────────────────────────────────────

async def test_sales_cash_flow():
    """现金销售全流程：库存→CASH订单→预留→发货→收款→应收+收款单→发票→期末AR凭证"""
    d = await _create_base_data()

    # === 步骤1：预置库存 ===
    await update_weighted_entry_date(
        d["warehouse"].id, d["product_a"].id, 20,
        cost_price=Decimal("60.00"), location_id=d["location"].id,
    )
    stock = await WarehouseStock.filter(
        warehouse_id=d["warehouse"].id, product_id=d["product_a"].id,
    ).first()
    assert stock.quantity == 20
    assert stock.weighted_cost == Decimal("60.00")

    # === 步骤2：创建CASH订单 ===
    order = await Order.create(
        order_no=generate_order_no("SO"), order_type="CASH",
        customer=d["customer"], warehouse=d["warehouse"],
        total_amount=Decimal("1000.00"), total_cost=Decimal("600.00"),
        total_profit=Decimal("400.00"), account_set=d["account_set"],
        creator=d["user"], shipping_status="pending",
    )
    oi = await OrderItem.create(
        order=order, product=d["product_a"],
        warehouse=d["warehouse"], location=d["location"],
        quantity=10, unit_price=Decimal("100.00"),
        cost_price=Decimal("60.00"), amount=Decimal("1000.00"),
        profit=Decimal("400.00"),
    )

    # === 步骤3：库存预留 ===
    await WarehouseStock.filter(id=stock.id).update(reserved_qty=F('reserved_qty') + 10)
    await stock.refresh_from_db()
    assert stock.reserved_qty == 10
    assert stock.quantity - stock.reserved_qty == 10  # 可用库存

    # === 步骤4：发货 ===
    # 4a: 扣减库存
    await update_weighted_entry_date(
        d["warehouse"].id, d["product_a"].id, -10,
        location_id=d["location"].id,
    )
    await WarehouseStock.filter(id=stock.id).update(reserved_qty=F('reserved_qty') - 10)
    await stock.refresh_from_db()
    assert stock.quantity == 10
    assert stock.reserved_qty == 0

    # 4b: 更新发货状态
    oi.shipped_qty = 10
    await oi.save()
    order.shipping_status = "completed"
    await order.save()

    # 4c: 生成出库单 + 凭证
    delivery = await create_sales_delivery(
        account_set_id=d["account_set"].id,
        customer_id=d["customer"].id,
        order_id=order.id,
        warehouse_id=d["warehouse"].id,
        items=[{
            "product_id": d["product_a"].id,
            "product_name": "集成商品A",
            "quantity": 10,
            "cost_price": "60.00",
            "sale_price": "100.00",
        }],
        creator=d["user"],
    )
    assert delivery.bill_no.startswith("CK")
    assert delivery.total_cost == Decimal("600.00")
    assert delivery.total_amount == Decimal("1000.00")
    assert delivery.voucher_no is not None

    # 验证出库凭证（借1407发出商品 / 贷1405库存商品）
    v_ck = await Voucher.filter(id=delivery.voucher_id).first()
    entries_ck = await VoucherEntry.filter(voucher=v_ck).order_by("line_no").all()
    assert len(entries_ck) == 2
    assert entries_ck[0].debit_amount == Decimal("600.00")
    assert entries_ck[1].credit_amount == Decimal("600.00")

    # === 步骤5：CASH收款 ===
    payment = await Payment.create(
        payment_no=generate_order_no("PAY"),
        customer=d["customer"], order=order,
        amount=Decimal("1000.00"), payment_method="cash",
        source="CASH", is_confirmed=False,
        account_set=d["account_set"], creator=d["user"],
    )
    order.paid_amount = Decimal("1000.00")
    order.is_cleared = True
    await order.save()

    # === 步骤6：应收单 + 收款单 ===
    receivable = await create_receivable_bill(
        account_set_id=d["account_set"].id,
        customer_id=d["customer"].id,
        order_id=order.id,
        total_amount=Decimal("1000.00"),
        status="pending",
        creator=d["user"],
    )
    assert receivable.bill_no.startswith("YS")
    assert receivable.unreceived_amount == Decimal("1000.00")

    receipt = await create_receipt_bill_for_payment(
        account_set_id=d["account_set"].id,
        customer_id=d["customer"].id,
        receivable_bill=receivable,
        payment_id=payment.id,
        amount=Decimal("1000.00"),
        payment_method="cash",
        creator=d["user"],
    )
    assert receipt.bill_no.startswith("SK")
    assert receipt.status == "confirmed"

    # === 步骤7：推送发票 ===
    invoice = await push_invoice_from_receivable(
        account_set_id=d["account_set"].id,
        receivable_bill_id=receivable.id,
        invoice_type="special",
        items=[{
            "product_id": d["product_a"].id,
            "product_name": "集成商品A",
            "quantity": 10,
            "unit_price": "100.00",
            "tax_rate": "13",
        }],
        creator=d["user"],
    )
    assert invoice.direction == "output"
    assert invoice.status == "draft"
    assert invoice.amount_without_tax == Decimal("1000.00")
    assert invoice.tax_amount == Decimal("130.00")
    assert invoice.total_amount == Decimal("1130.00")

    # === 步骤8：确认发票（生成复合凭证）===
    confirmed_inv = await confirm_invoice(invoice.id, d["user"])
    assert confirmed_inv.status == "confirmed"
    assert confirmed_inv.voucher_no is not None

    # 验证发票凭证（借1122/贷6001+222102+借6401/贷1407）
    v_inv = await Voucher.filter(id=confirmed_inv.voucher_id).first()
    entries_inv = await VoucherEntry.filter(voucher=v_inv).order_by("line_no").all()
    total_d = sum(e.debit_amount for e in entries_inv)
    total_c = sum(e.credit_amount for e in entries_inv)
    assert total_d == total_c  # 借贷平衡

    # === 步骤9：期末AR凭证 ===
    ar_vouchers = await generate_ar_vouchers(
        d["account_set"].id, d["current_period"], d["user"],
    )
    assert len(ar_vouchers) == 1
    assert ar_vouchers[0]["source"].startswith("收款单")

    # 幂等性验证
    ar_vouchers_2 = await generate_ar_vouchers(
        d["account_set"].id, d["current_period"], d["user"],
    )
    assert len(ar_vouchers_2) == 0  # 不重复生成


# ─── 流程3：挂账销售全流程 ──────────────────────────────────────────────

async def test_sales_credit_flow():
    """挂账销售全流程：CREDIT订单→发货→挂账→应收单→发票→无AR凭证"""
    d = await _create_base_data()

    # 预置库存（商品B 20件@120）
    await update_weighted_entry_date(
        d["warehouse"].id, d["product_b"].id, 20,
        cost_price=Decimal("120.00"), location_id=d["location"].id,
    )

    # 创建CREDIT订单
    order = await Order.create(
        order_no=generate_order_no("SO"), order_type="CREDIT",
        customer=d["customer"], warehouse=d["warehouse"],
        total_amount=Decimal("2000.00"), total_cost=Decimal("1200.00"),
        total_profit=Decimal("800.00"), account_set=d["account_set"],
        creator=d["user"], shipping_status="pending",
    )
    oi = await OrderItem.create(
        order=order, product=d["product_b"],
        warehouse=d["warehouse"], location=d["location"],
        quantity=10, unit_price=Decimal("200.00"),
        cost_price=Decimal("120.00"), amount=Decimal("2000.00"),
        profit=Decimal("800.00"),
    )

    # 库存预留 + 发货
    stock = await WarehouseStock.filter(
        warehouse_id=d["warehouse"].id, product_id=d["product_b"].id,
    ).first()
    await WarehouseStock.filter(id=stock.id).update(reserved_qty=F('reserved_qty') + 10)
    await update_weighted_entry_date(
        d["warehouse"].id, d["product_b"].id, -10,
        location_id=d["location"].id,
    )
    await WarehouseStock.filter(id=stock.id).update(reserved_qty=F('reserved_qty') - 10)
    await stock.refresh_from_db()
    assert stock.quantity == 10  # 20 - 10
    assert stock.reserved_qty == 0

    oi.shipped_qty = 10
    await oi.save()
    order.shipping_status = "completed"
    await order.save()

    # 出库单
    delivery = await create_sales_delivery(
        account_set_id=d["account_set"].id,
        customer_id=d["customer"].id,
        order_id=order.id,
        warehouse_id=d["warehouse"].id,
        items=[{
            "product_id": d["product_b"].id,
            "product_name": "集成商品B",
            "quantity": 10,
            "cost_price": "120.00",
            "sale_price": "200.00",
        }],
        creator=d["user"],
    )
    assert delivery.voucher_no is not None
    assert delivery.total_cost == Decimal("1200.00")

    # 挂账：客户余额增加
    await Customer.filter(id=d["customer"].id).update(
        balance=F('balance') + Decimal("2000.00"),
    )
    await d["customer"].refresh_from_db()
    assert d["customer"].balance == Decimal("2000.00")

    # 应收单（无收款单）
    receivable = await create_receivable_bill(
        account_set_id=d["account_set"].id,
        customer_id=d["customer"].id,
        order_id=order.id,
        total_amount=Decimal("2000.00"),
        status="pending",
        creator=d["user"],
    )
    assert receivable.status == "pending"
    assert receivable.unreceived_amount == Decimal("2000.00")

    # 推送+确认发票
    invoice = await push_invoice_from_receivable(
        account_set_id=d["account_set"].id,
        receivable_bill_id=receivable.id,
        invoice_type="special",
        items=[{
            "product_id": d["product_b"].id,
            "product_name": "集成商品B",
            "quantity": 10,
            "unit_price": "200.00",
            "tax_rate": "13",
        }],
        creator=d["user"],
    )
    confirmed_inv = await confirm_invoice(invoice.id, d["user"])
    assert confirmed_inv.status == "confirmed"

    # CREDIT订单没有收款单 → 不应生成AR凭证
    payment_count = await Payment.filter(order=order).count()
    assert payment_count == 0

    ar_vouchers = await generate_ar_vouchers(
        d["account_set"].id, d["current_period"], d["user"],
    )
    assert len(ar_vouchers) == 0

    # 客户挂账余额不变
    await d["customer"].refresh_from_db()
    assert d["customer"].balance == Decimal("2000.00")


# ─── 流程4：库存管理全流程 ──────────────────────────────────────────────

async def test_stock_management_flow():
    """库存管理全流程：入库→二次入库(不同成本)→调拨→调整→加权成本验证"""
    d = await _create_base_data()

    # 创建第二仓库
    warehouse_b = await Warehouse.create(name="分仓库", is_default=False)
    location_b = await Location.create(warehouse=warehouse_b, code="B01", name="B区01号")

    # === 步骤1：首次入库 20件@60 ===
    stock_a = await update_weighted_entry_date(
        d["warehouse"].id, d["product_a"].id, 20,
        cost_price=Decimal("60.00"), location_id=d["location"].id,
    )
    assert stock_a.quantity == 20
    assert stock_a.weighted_cost == Decimal("60.00")

    # === 步骤2：追加入库 10件@90（验证加权平均） ===
    stock_a = await update_weighted_entry_date(
        d["warehouse"].id, d["product_a"].id, 10,
        cost_price=Decimal("90.00"), location_id=d["location"].id,
    )
    assert stock_a.quantity == 30
    # 加权成本 = (20*60 + 10*90) / 30 = 2100/30 = 70.00
    assert stock_a.weighted_cost == Decimal("70.00")

    # === 步骤3：调拨 10件到分仓 ===
    # 源仓库扣减
    stock_a = await update_weighted_entry_date(
        d["warehouse"].id, d["product_a"].id, -10,
        location_id=d["location"].id,
    )
    assert stock_a.quantity == 20

    # 目标仓库增加（继承源仓库成本）
    stock_b = await update_weighted_entry_date(
        warehouse_b.id, d["product_a"].id, 10,
        cost_price=Decimal("70.00"), location_id=location_b.id,
    )
    assert stock_b.quantity == 10
    assert stock_b.weighted_cost == Decimal("70.00")

    # === 步骤4：库存调整 主仓-5 ===
    stock_a = await update_weighted_entry_date(
        d["warehouse"].id, d["product_a"].id, -5,
        location_id=d["location"].id,
    )
    assert stock_a.quantity == 15

    # === 步骤5：全局加权成本验证 ===
    # 主仓15件@70 + 分仓10件@70 → 加权成本=70
    weighted_cost = await get_product_weighted_cost(d["product_a"].id)
    assert weighted_cost == Decimal("70.00")


# ─── 流程5：财务期末全流程 ──────────────────────────────────────────────

async def test_period_end_flow():
    """财务期末全流程：凭证→试算→损益结转→结账→资产负债表→利润表"""
    d = await _create_base_data()

    # 构建科目字典
    accts = {}
    for coa in await ChartOfAccount.filter(account_set_id=d["account_set"].id).all():
        accts[coa.code] = coa

    # === 步骤1：创建4张凭证模拟一个月业务 ===

    # 凭证1：投入资本 — 借 银行存款 100,000 / 贷 实收资本 100,000
    await _post_voucher(d["account_set"], d["user"], accts, d["current_period"], [
        ("1002", "debit", Decimal("100000")),
        ("4001", "credit", Decimal("100000")),
    ])
    # 凭证2：销售收入 — 借 银行存款 11,300 / 贷 收入 10,000 + 贷 销项税 1,300
    await _post_voucher(d["account_set"], d["user"], accts, d["current_period"], [
        ("1002", "debit", Decimal("11300")),
        ("6001", "credit", Decimal("10000")),
        ("222102", "credit", Decimal("1300")),
    ])
    # 凭证3：成本 — 借 主营业务成本 6,000 / 贷 库存商品 6,000
    await _post_voucher(d["account_set"], d["user"], accts, d["current_period"], [
        ("6401", "debit", Decimal("6000")),
        ("1405", "credit", Decimal("6000")),
    ])
    # 凭证4：管理费用 — 借 管理费用 2,000 / 贷 银行存款 2,000
    await _post_voucher(d["account_set"], d["user"], accts, d["current_period"], [
        ("6602", "debit", Decimal("2000")),
        ("1002", "credit", Decimal("2000")),
    ])

    all_v = await Voucher.filter(account_set_id=d["account_set"].id).all()
    assert len(all_v) == 4
    assert all(v.status == "posted" for v in all_v)

    # === 步骤2：试算平衡（结转前）===
    trial = await get_trial_balance(d["account_set"].id, d["current_period"])
    assert trial["is_balanced"] is True

    # === 步骤3：验证利润表（结转前，损益科目有余额）===
    stmt = await get_income_statement(d["account_set"].id, d["current_period"])
    rows = {r["name"]: r for r in stmt["rows"]}
    assert rows["  主营业务收入"]["current"] == "10000"
    assert rows["  主营业务成本"]["current"] == "6000"
    assert rows["  管理费用"]["current"] == "2000"
    assert rows["三、营业利润"]["current"] == "2000"
    assert rows["五、净利润"]["current"] == "2000"

    # === 步骤4：损益结转预览 ===
    preview = await preview_carry_forward(d["account_set"].id, d["current_period"])
    assert preview.get("already_exists") is not True
    # 利润 = 收入10000 - 成本6000 - 管理费2000 = 2000
    assert preview["total_profit"] == "2000"

    # === 步骤5：执行损益结转 ===
    result = await execute_carry_forward(d["account_set"].id, d["current_period"], d["user"])
    assert result["voucher_no"] is not None
    assert result["total_profit"] == "2000"

    # 验证结转凭证
    carry_v = await Voucher.filter(id=result["voucher_id"]).first()
    assert carry_v.voucher_type == "转"
    assert carry_v.status == "posted"

    carry_entries = await VoucherEntry.filter(voucher=carry_v).order_by("line_no").all()
    # 3个损益科目(6001/6401/6602) + 1个本年利润(4103) = 4行分录
    assert len(carry_entries) == 4
    carry_d = sum(e.debit_amount for e in carry_entries)
    carry_c = sum(e.credit_amount for e in carry_entries)
    assert carry_d == carry_c  # 结转凭证借贷平衡

    # === 步骤6：结账检查 ===
    checks = await close_check(d["account_set"].id, d["current_period"])
    assert all(c["passed"] for c in checks)

    # === 步骤7：结账 ===
    close_result = await close_period(d["account_set"].id, d["current_period"], d["user"])
    assert close_result.get("already_closed") is not True

    await d["period"].refresh_from_db()
    assert d["period"].is_closed is True

    # === 步骤8：验证资产负债表 ===
    bs = await get_balance_sheet(d["account_set"].id, d["current_period"])
    assert bs["is_balanced"] is True
    # 银行存款 = 100000 + 11300 - 2000 = 109300
    assert bs["assets"]["current"]["bank"] == "109300"
    # 实收资本 = 100000
    assert bs["equity"]["paid_capital"] == "100000"
    # 本年利润 = 2000
    assert bs["equity"]["current_profit"] == "2000"
    # 总资产 = 总负债+权益
    assert Decimal(bs["assets"]["total"]) == Decimal(bs["total_liabilities_equity"])

    # === 步骤9：验证结转后试算仍平衡 ===
    trial_after = await get_trial_balance(d["account_set"].id, d["current_period"])
    assert trial_after["is_balanced"] is True
