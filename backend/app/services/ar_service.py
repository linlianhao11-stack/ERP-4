"""应收服务层"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from tortoise import transactions
from app.models.ar_ap import ReceivableBill, ReceiptBill, ReceiptRefundBill, ReceivableWriteOff
from app.models.accounting import AccountSet, ChartOfAccount, AccountingPeriod
from app.models.voucher import Voucher, VoucherEntry
from app.models.order import Order
from app.utils.generators import generate_order_no
from app.logger import get_logger

logger = get_logger("ar_service")


async def create_receivable_bill(
    account_set_id: int,
    customer_id: int,
    order_id: Optional[int] = None,
    total_amount: Decimal = Decimal("0"),
    status: str = "pending",
    creator=None,
    remark: str = "",
    bill_date: Optional[date] = None,
) -> ReceivableBill:
    if bill_date is None:
        bill_date = date.today()
    received = total_amount if status == "completed" else Decimal("0")
    unreceived = total_amount - received
    rb = await ReceivableBill.create(
        bill_no=generate_order_no("YS"),
        account_set_id=account_set_id,
        customer_id=customer_id,
        order_id=order_id,
        bill_date=bill_date,
        total_amount=total_amount,
        received_amount=received,
        unreceived_amount=unreceived,
        status=status,
        remark=remark,
        creator=creator,
    )
    logger.info(f"创建应收单: {rb.bill_no}, 金额: {total_amount}, 状态: {status}")
    return rb


async def create_receipt_bill_for_payment(
    account_set_id: int,
    customer_id: int,
    receivable_bill: Optional[ReceivableBill],
    payment_id: Optional[int],
    amount: Decimal,
    payment_method: str,
    creator=None,
) -> ReceiptBill:
    receipt = await ReceiptBill.create(
        bill_no=generate_order_no("SK"),
        account_set_id=account_set_id,
        customer_id=customer_id,
        receivable_bill=receivable_bill,
        payment_id=payment_id,
        receipt_date=date.today(),
        amount=amount,
        payment_method=payment_method,
        status="confirmed",
        confirmed_by=creator,
        confirmed_at=datetime.now(timezone.utc),
        creator=creator,
    )
    logger.info(f"创建收款单: {receipt.bill_no}, 金额: {amount}")
    return receipt


async def confirm_receipt_bill(receipt_id: int, user) -> ReceiptBill:
    async with transactions.in_transaction():
        receipt = await ReceiptBill.filter(id=receipt_id).select_for_update().first()
        if not receipt:
            raise ValueError("收款单不存在")
        if receipt.status != "draft":
            raise ValueError("只有草稿状态的收款单可以确认")
        receipt.status = "confirmed"
        receipt.confirmed_by = user
        receipt.confirmed_at = datetime.now(timezone.utc)
        await receipt.save()

        if receipt.receivable_bill_id:
            rb = await ReceivableBill.filter(id=receipt.receivable_bill_id).select_for_update().first()
            if rb:
                rb.received_amount += receipt.amount
                rb.unreceived_amount = rb.total_amount - rb.received_amount
                if rb.unreceived_amount <= 0:
                    rb.status = "completed"
                else:
                    rb.status = "partial"
                await rb.save()

    logger.info(f"确认收款单: {receipt.bill_no}")
    return receipt


async def confirm_receipt_refund(refund_id: int, user) -> ReceiptRefundBill:
    async with transactions.in_transaction():
        refund = await ReceiptRefundBill.filter(id=refund_id).select_for_update().first()
        if not refund:
            raise ValueError("收款退款单不存在")
        if refund.status != "draft":
            raise ValueError("只有草稿状态的退款单可以确认")
        refund.status = "confirmed"
        refund.confirmed_by = user
        refund.confirmed_at = datetime.now(timezone.utc)
        await refund.save()

        original = await ReceiptBill.filter(id=refund.original_receipt_id).first()
        if original and original.receivable_bill_id:
            rb = await ReceivableBill.filter(id=original.receivable_bill_id).select_for_update().first()
            if rb:
                rb.received_amount -= refund.amount
                rb.unreceived_amount = rb.total_amount - rb.received_amount
                if rb.received_amount <= 0:
                    rb.status = "pending"
                else:
                    rb.status = "partial"
                await rb.save()

    logger.info(f"确认收款退款单: {refund.bill_no}")
    return refund


async def confirm_write_off(write_off_id: int, user) -> ReceivableWriteOff:
    async with transactions.in_transaction():
        wo = await ReceivableWriteOff.filter(id=write_off_id).select_for_update().first()
        if not wo:
            raise ValueError("核销单不存在")
        if wo.status != "draft":
            raise ValueError("只有草稿状态的核销单可以确认")
        wo.status = "confirmed"
        wo.confirmed_by = user
        wo.confirmed_at = datetime.now(timezone.utc)
        await wo.save()

        rb = await ReceivableBill.filter(id=wo.receivable_bill_id).select_for_update().first()
        if rb:
            rb.received_amount += wo.amount
            rb.unreceived_amount = rb.total_amount - rb.received_amount
            if rb.unreceived_amount <= 0:
                rb.status = "completed"
            else:
                rb.status = "partial"
            await rb.save()

    logger.info(f"确认核销单: {wo.bill_no}")
    return wo


from app.utils.voucher_no import next_voucher_no as _next_voucher_no


async def _get_employee_department_from_receivable(receivable_bill_id: Optional[int]):
    """从应收单关联的订单中获取员工和部门"""
    if not receivable_bill_id:
        return None, None
    rb = await ReceivableBill.filter(id=receivable_bill_id).first()
    if not rb or not rb.order_id:
        return None, None
    order = await Order.filter(id=rb.order_id).prefetch_related("employee__department").first()
    if not order or not order.employee:
        return None, None
    employee = order.employee
    department = employee.department if hasattr(employee, "department") else None
    return employee, department


async def generate_ar_vouchers(account_set_id: int, period_names: list, user, bills: list = None, merge_by_partner: bool = False) -> dict:
    # 科目查询只执行一次，放在循环外
    bank_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1002", is_active=True
    ).first()
    ar_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1122", is_active=True
    ).first()
    advance_account = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="2203", is_active=True
    ).first()
    if not bank_account or not ar_account:
        raise ValueError("缺少必要科目：银行存款(1002)或应收账款(1122)")

    shipped_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1407", is_active=True
    ).first()
    inventory_acct = await ChartOfAccount.filter(
        account_set_id=account_set_id, code="1405", is_active=True
    ).first()

    vouchers = []
    summary = {}

    # ── bills 模式：按勾选单据生成凭证 ──
    if bills:
        from collections import defaultdict
        # 按 type 分组
        grouped = defaultdict(list)
        for b in bills:
            grouped[b["type"]].append(b["id"])

        # 查询各类单据对象
        receipt_objs = await ReceiptBill.filter(id__in=grouped.get("receipt", [])).select_related("customer").all() if "receipt" in grouped else []
        refund_objs = await ReceiptRefundBill.filter(id__in=grouped.get("refund", [])).select_related("customer").all() if "refund" in grouped else []
        write_off_objs = await ReceivableWriteOff.filter(id__in=grouped.get("write_off", [])).select_related("customer").all() if "write_off" in grouped else []
        sales_return_objs = await Order.filter(id__in=grouped.get("sales_return", [])).select_related("customer").all() if "sales_return" in grouped else []

        # 统一放入列表，标记类型
        all_bill_objs = []
        for r in receipt_objs:
            all_bill_objs.append(("receipt", r))
        for rf in refund_objs:
            all_bill_objs.append(("refund", rf))
        for wo in write_off_objs:
            all_bill_objs.append(("write_off", wo))
        for ro in sales_return_objs:
            all_bill_objs.append(("sales_return", ro))

        if merge_by_partner:
            # 按 customer_id 分组
            partner_groups = defaultdict(list)
            for bill_type, obj in all_bill_objs:
                cid = obj.customer_id if hasattr(obj, 'customer_id') else None
                partner_groups[cid].append((bill_type, obj))

            for cid, group_bills in partner_groups.items():
                # 确定客户名称
                customer_name = ""
                for _, obj in group_bills:
                    if hasattr(obj, 'customer') and obj.customer:
                        customer_name = obj.customer.name
                        break

                # 从第一个关联单据获取员工/部门信息
                emp_id = None
                dept_id = None
                for bt, obj in group_bills:
                    receivable_id = None
                    if bt == "receipt":
                        receivable_id = getattr(obj, 'receivable_bill_id', None)
                    elif bt == "write_off":
                        receivable_id = getattr(obj, 'receivable_bill_id', None)
                    elif bt == "refund":
                        original_receipt = await ReceiptBill.filter(id=obj.original_receipt_id).first()
                        receivable_id = original_receipt.receivable_bill_id if original_receipt else None
                    if receivable_id:
                        emp, dept = await _get_employee_department_from_receivable(receivable_id)
                        if emp:
                            emp_id = emp.id
                            dept_id = dept.id if dept else None
                            break

                # 按类型分别生成合并凭证
                # 收款单合并
                receipts_in_group = [(t, o) for t, o in group_bills if t == "receipt"]
                if receipts_in_group:
                    total_amount = sum(o.amount for _, o in receipts_in_group)
                    bill_nos = ", ".join(o.bill_no for _, o in receipts_in_group)
                    latest_date = max(o.receipt_date for _, o in receipts_in_group)
                    period_name = f"{latest_date.year}-{latest_date.month:02d}"
                    async with transactions.in_transaction():
                        vno = await _next_voucher_no(account_set_id, "收", period_name)
                        v = await Voucher.create(
                            account_set_id=account_set_id,
                            voucher_type="收",
                            voucher_no=vno,
                            period_name=period_name,
                            voucher_date=latest_date,
                            summary=f"收货款-{customer_name}（{bill_nos}）",
                            total_debit=total_amount,
                            total_credit=total_amount,
                            status="draft",
                            creator=user,
                            source_type="receipt_bill",
                            source_bill_id=receipts_in_group[0][1].id,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=1,
                            account_id=bank_account.id,
                            summary=f"收货款-{customer_name}（{bill_nos}）",
                            debit_amount=total_amount,
                            credit_amount=Decimal("0"),
                            aux_employee_id=emp_id,
                            aux_department_id=dept_id,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=2,
                            account_id=ar_account.id,
                            summary=f"收货款-{customer_name}（{bill_nos}）",
                            debit_amount=Decimal("0"),
                            credit_amount=total_amount,
                            aux_customer_id=cid,
                            aux_employee_id=emp_id,
                            aux_department_id=dept_id,
                        )
                        for _, o in receipts_in_group:
                            o.voucher = v
                            o.voucher_no = vno
                            await o.save()
                        vouchers.append({"id": v.id, "voucher_no": vno, "source": f"收货款-{customer_name}（{bill_nos}）"})

                # 收款退款单合并
                refunds_in_group = [(t, o) for t, o in group_bills if t == "refund"]
                if refunds_in_group:
                    total_amount = sum(o.amount for _, o in refunds_in_group)
                    bill_nos = ", ".join(o.bill_no for _, o in refunds_in_group)
                    latest_date = max(o.refund_date for _, o in refunds_in_group)
                    period_name = f"{latest_date.year}-{latest_date.month:02d}"
                    async with transactions.in_transaction():
                        vno = await _next_voucher_no(account_set_id, "收", period_name)
                        v = await Voucher.create(
                            account_set_id=account_set_id,
                            voucher_type="收",
                            voucher_no=vno,
                            period_name=period_name,
                            voucher_date=latest_date,
                            summary=f"收款退款-{customer_name}（{bill_nos}）",
                            total_debit=total_amount,
                            total_credit=total_amount,
                            status="draft",
                            creator=user,
                            source_type="receipt_refund_bill",
                            source_bill_id=refunds_in_group[0][1].id,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=1,
                            account_id=ar_account.id,
                            summary=f"收款退款-{customer_name}（{bill_nos}）",
                            debit_amount=total_amount,
                            credit_amount=Decimal("0"),
                            aux_customer_id=cid,
                            aux_employee_id=emp_id,
                            aux_department_id=dept_id,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=2,
                            account_id=bank_account.id,
                            summary=f"收款退款-{customer_name}（{bill_nos}）",
                            debit_amount=Decimal("0"),
                            credit_amount=total_amount,
                            aux_employee_id=emp_id,
                            aux_department_id=dept_id,
                        )
                        for _, o in refunds_in_group:
                            o.voucher = v
                            o.voucher_no = vno
                            await o.save()
                        vouchers.append({"id": v.id, "voucher_no": vno, "source": f"收款退款-{customer_name}（{bill_nos}）"})

                # 核销单合并
                writeoffs_in_group = [(t, o) for t, o in group_bills if t == "write_off"]
                if writeoffs_in_group and advance_account:
                    total_amount = sum(o.amount for _, o in writeoffs_in_group)
                    bill_nos = ", ".join(o.bill_no for _, o in writeoffs_in_group)
                    latest_date = max(o.write_off_date for _, o in writeoffs_in_group)
                    period_name = f"{latest_date.year}-{latest_date.month:02d}"
                    async with transactions.in_transaction():
                        vno = await _next_voucher_no(account_set_id, "记", period_name)
                        v = await Voucher.create(
                            account_set_id=account_set_id,
                            voucher_type="记",
                            voucher_no=vno,
                            period_name=period_name,
                            voucher_date=latest_date,
                            summary=f"核销-{customer_name}（{bill_nos}）",
                            total_debit=total_amount,
                            total_credit=total_amount,
                            status="draft",
                            creator=user,
                            source_type="receivable_write_off",
                            source_bill_id=writeoffs_in_group[0][1].id,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=1,
                            account_id=advance_account.id,
                            summary=f"核销-{customer_name}（{bill_nos}）",
                            debit_amount=total_amount,
                            credit_amount=Decimal("0"),
                            aux_customer_id=cid,
                            aux_employee_id=emp_id,
                            aux_department_id=dept_id,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=2,
                            account_id=ar_account.id,
                            summary=f"核销-{customer_name}（{bill_nos}）",
                            debit_amount=Decimal("0"),
                            credit_amount=total_amount,
                            aux_customer_id=cid,
                            aux_employee_id=emp_id,
                            aux_department_id=dept_id,
                        )
                        for _, o in writeoffs_in_group:
                            o.voucher = v
                            o.voucher_no = vno
                            await o.save()
                        vouchers.append({"id": v.id, "voucher_no": vno, "source": f"核销-{customer_name}（{bill_nos}）"})

                # 销售退货单合并
                returns_in_group = [(t, o) for t, o in group_bills if t == "sales_return"]
                if returns_in_group and shipped_acct and inventory_acct:
                    valid_returns = [(t, o) for t, o in returns_in_group if abs(float(o.total_cost)) > 0]
                    if valid_returns:
                        total_cost = sum(abs(o.total_cost) for _, o in valid_returns)
                        bill_nos = ", ".join(o.order_no for _, o in valid_returns)
                        latest_date = max(o.created_at for _, o in valid_returns)
                        voucher_date = latest_date.date() if hasattr(latest_date, 'date') else latest_date
                        period_name = f"{voucher_date.year}-{voucher_date.month:02d}"
                        async with transactions.in_transaction():
                            vno = await _next_voucher_no(account_set_id, "记", period_name)
                            v = await Voucher.create(
                                account_set_id=account_set_id,
                                voucher_type="记",
                                voucher_no=vno,
                                period_name=period_name,
                                voucher_date=voucher_date,
                                summary=f"销售退货冲回-{customer_name}（{bill_nos}）",
                                total_debit=-total_cost,
                                total_credit=-total_cost,
                                status="draft",
                                creator=user,
                                source_type="sales_return",
                                source_bill_id=valid_returns[0][1].id,
                            )
                            await VoucherEntry.create(
                                voucher=v, line_no=1,
                                account_id=shipped_acct.id,
                                summary=f"销售退货冲回-{customer_name}（{bill_nos}）",
                                debit_amount=-total_cost,
                                credit_amount=Decimal("0"),
                                aux_employee_id=emp_id,
                                aux_department_id=dept_id,
                            )
                            await VoucherEntry.create(
                                voucher=v, line_no=2,
                                account_id=inventory_acct.id,
                                summary=f"销售退货冲回-{customer_name}（{bill_nos}）",
                                debit_amount=Decimal("0"),
                                credit_amount=-total_cost,
                                aux_employee_id=emp_id,
                                aux_department_id=dept_id,
                            )
                            for _, o in valid_returns:
                                o.voucher = v
                                o.voucher_no = vno
                                await o.save()
                            vouchers.append({"id": v.id, "voucher_no": vno, "source": f"销售退货冲回-{customer_name}（{bill_nos}）"})

            summary["bills_mode"] = {"count": len(vouchers), "skipped": False}
        else:
            # 不合并，逐单生成
            for bill_type, obj in all_bill_objs:
                if bill_type == "receipt":
                    employee, department = await _get_employee_department_from_receivable(obj.receivable_bill_id)
                    period_name = f"{obj.receipt_date.year}-{obj.receipt_date.month:02d}"
                    async with transactions.in_transaction():
                        vno = await _next_voucher_no(account_set_id, "收", period_name)
                        v = await Voucher.create(
                            account_set_id=account_set_id, voucher_type="收", voucher_no=vno,
                            period_name=period_name, voucher_date=obj.receipt_date,
                            summary=f"收款单 {obj.bill_no}", total_debit=obj.amount, total_credit=obj.amount,
                            status="draft", creator=user, source_type="receipt_bill", source_bill_id=obj.id,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=1, account_id=bank_account.id,
                            summary=f"收款 {obj.bill_no}", debit_amount=obj.amount, credit_amount=Decimal("0"),
                            aux_employee=employee if bank_account.aux_employee else None,
                            aux_department=department if bank_account.aux_department else None,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=2, account_id=ar_account.id,
                            summary=f"收款 {obj.bill_no}", debit_amount=Decimal("0"), credit_amount=obj.amount,
                            aux_customer_id=obj.customer_id,
                            aux_employee=employee if ar_account.aux_employee else None,
                            aux_department=department if ar_account.aux_department else None,
                        )
                        obj.voucher = v
                        obj.voucher_no = vno
                        await obj.save()
                        vouchers.append({"id": v.id, "voucher_no": vno, "source": f"收款单 {obj.bill_no}"})

                elif bill_type == "refund":
                    original_receipt = await ReceiptBill.filter(id=obj.original_receipt_id).first()
                    receivable_id = original_receipt.receivable_bill_id if original_receipt else None
                    employee, department = await _get_employee_department_from_receivable(receivable_id)
                    period_name = f"{obj.refund_date.year}-{obj.refund_date.month:02d}"
                    async with transactions.in_transaction():
                        vno = await _next_voucher_no(account_set_id, "收", period_name)
                        v = await Voucher.create(
                            account_set_id=account_set_id, voucher_type="收", voucher_no=vno,
                            period_name=period_name, voucher_date=obj.refund_date,
                            summary=f"收款退款 {obj.bill_no}", total_debit=obj.amount, total_credit=obj.amount,
                            status="draft", creator=user, source_type="receipt_refund_bill", source_bill_id=obj.id,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=1, account_id=ar_account.id,
                            summary=f"收款退款 {obj.bill_no}", debit_amount=obj.amount, credit_amount=Decimal("0"),
                            aux_customer_id=obj.customer_id,
                            aux_employee=employee if ar_account.aux_employee else None,
                            aux_department=department if ar_account.aux_department else None,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=2, account_id=bank_account.id,
                            summary=f"收款退款 {obj.bill_no}", debit_amount=Decimal("0"), credit_amount=obj.amount,
                            aux_employee=employee if bank_account.aux_employee else None,
                            aux_department=department if bank_account.aux_department else None,
                        )
                        obj.voucher = v
                        obj.voucher_no = vno
                        await obj.save()
                        vouchers.append({"id": v.id, "voucher_no": vno, "source": f"收款退款 {obj.bill_no}"})

                elif bill_type == "write_off" and advance_account:
                    employee, department = await _get_employee_department_from_receivable(obj.receivable_bill_id)
                    period_name = f"{obj.write_off_date.year}-{obj.write_off_date.month:02d}"
                    async with transactions.in_transaction():
                        vno = await _next_voucher_no(account_set_id, "记", period_name)
                        v = await Voucher.create(
                            account_set_id=account_set_id, voucher_type="记", voucher_no=vno,
                            period_name=period_name, voucher_date=obj.write_off_date,
                            summary=f"核销 {obj.bill_no}", total_debit=obj.amount, total_credit=obj.amount,
                            status="draft", creator=user, source_type="receivable_write_off", source_bill_id=obj.id,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=1, account_id=advance_account.id,
                            summary=f"核销 {obj.bill_no}", debit_amount=obj.amount, credit_amount=Decimal("0"),
                            aux_customer_id=obj.customer_id,
                            aux_employee=employee if advance_account.aux_employee else None,
                            aux_department=department if advance_account.aux_department else None,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=2, account_id=ar_account.id,
                            summary=f"核销 {obj.bill_no}", debit_amount=Decimal("0"), credit_amount=obj.amount,
                            aux_customer_id=obj.customer_id,
                            aux_employee=employee if ar_account.aux_employee else None,
                            aux_department=department if ar_account.aux_department else None,
                        )
                        obj.voucher = v
                        obj.voucher_no = vno
                        await obj.save()
                        vouchers.append({"id": v.id, "voucher_no": vno, "source": f"核销 {obj.bill_no}"})

                elif bill_type == "sales_return" and shipped_acct and inventory_acct:
                    cost = abs(obj.total_cost)
                    if cost <= 0:
                        continue
                    voucher_date = obj.created_at.date() if hasattr(obj.created_at, 'date') else obj.created_at
                    period_name = f"{voucher_date.year}-{voucher_date.month:02d}"
                    async with transactions.in_transaction():
                        vno = await _next_voucher_no(account_set_id, "记", period_name)
                        v = await Voucher.create(
                            account_set_id=account_set_id, voucher_type="记", voucher_no=vno,
                            period_name=period_name, voucher_date=voucher_date,
                            summary=f"销售退货冲回 {obj.order_no}", total_debit=-cost, total_credit=-cost,
                            status="draft", creator=user, source_type="sales_return", source_bill_id=obj.id,
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=1, account_id=shipped_acct.id,
                            summary=f"销售退货冲回 {obj.order_no}", debit_amount=-cost, credit_amount=Decimal("0"),
                        )
                        await VoucherEntry.create(
                            voucher=v, line_no=2, account_id=inventory_acct.id,
                            summary=f"销售退货冲回 {obj.order_no}", debit_amount=Decimal("0"), credit_amount=-cost,
                        )
                        obj.voucher = v
                        obj.voucher_no = vno
                        await obj.save()
                        vouchers.append({"id": v.id, "voucher_no": vno, "source": f"销售退货 {obj.order_no}"})

            summary["bills_mode"] = {"count": len(vouchers), "skipped": False}

        logger.info(f"AR凭证生成完成(bills模式): {len(vouchers)} 张")
        return {"vouchers": vouchers, "summary": summary}

    # ── period_names 模式（原有逻辑） ──
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

        # 收款单 → 借 银行存款1002，贷 应收账款1122
        receipts = await ReceiptBill.filter(
            account_set_id=account_set_id, status="confirmed", voucher_id=None,
            receipt_date__gte=period_start, receipt_date__lte=period_end,
        ).all()
        for r in receipts:
            employee, department = await _get_employee_department_from_receivable(r.receivable_bill_id)
            async with transactions.in_transaction():
                vno = await _next_voucher_no(account_set_id, "收", period_name)
                v = await Voucher.create(
                    account_set_id=account_set_id,
                    voucher_type="收",
                    voucher_no=vno,
                    period_name=period_name,
                    voucher_date=r.receipt_date,
                    summary=f"收款单 {r.bill_no}",
                    total_debit=r.amount,
                    total_credit=r.amount,
                    status="draft",
                    creator=user,
                    source_type="receipt_bill",
                    source_bill_id=r.id,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=1,
                    account_id=bank_account.id,
                    summary=f"收款 {r.bill_no}",
                    debit_amount=r.amount,
                    credit_amount=Decimal("0"),
                    aux_employee=employee if bank_account.aux_employee else None,
                    aux_department=department if bank_account.aux_department else None,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=2,
                    account_id=ar_account.id,
                    summary=f"收款 {r.bill_no}",
                    debit_amount=Decimal("0"),
                    credit_amount=r.amount,
                    aux_customer_id=r.customer_id,
                    aux_employee=employee if ar_account.aux_employee else None,
                    aux_department=department if ar_account.aux_department else None,
                )
                r.voucher = v
                r.voucher_no = vno
                await r.save()
                month_vouchers.append({"id": v.id, "voucher_no": vno, "source": f"收款单 {r.bill_no}"})

        # 收款退款单 → 借 应收账款1122，贷 银行存款1002
        refunds = await ReceiptRefundBill.filter(
            account_set_id=account_set_id, status="confirmed", voucher_id=None,
            refund_date__gte=period_start, refund_date__lte=period_end,
        ).all()
        for rf in refunds:
            # 通过原始收款单的应收单获取员工/部门
            original_receipt = await ReceiptBill.filter(id=rf.original_receipt_id).first()
            receivable_id = original_receipt.receivable_bill_id if original_receipt else None
            employee, department = await _get_employee_department_from_receivable(receivable_id)
            async with transactions.in_transaction():
                vno = await _next_voucher_no(account_set_id, "收", period_name)
                v = await Voucher.create(
                    account_set_id=account_set_id,
                    voucher_type="收",
                    voucher_no=vno,
                    period_name=period_name,
                    voucher_date=rf.refund_date,
                    summary=f"收款退款 {rf.bill_no}",
                    total_debit=rf.amount,
                    total_credit=rf.amount,
                    status="draft",
                    creator=user,
                    source_type="receipt_refund_bill",
                    source_bill_id=rf.id,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=1,
                    account_id=ar_account.id,
                    summary=f"收款退款 {rf.bill_no}",
                    debit_amount=rf.amount,
                    credit_amount=Decimal("0"),
                    aux_customer_id=rf.customer_id,
                    aux_employee=employee if ar_account.aux_employee else None,
                    aux_department=department if ar_account.aux_department else None,
                )
                await VoucherEntry.create(
                    voucher=v, line_no=2,
                    account_id=bank_account.id,
                    summary=f"收款退款 {rf.bill_no}",
                    debit_amount=Decimal("0"),
                    credit_amount=rf.amount,
                    aux_employee=employee if bank_account.aux_employee else None,
                    aux_department=department if bank_account.aux_department else None,
                )
                rf.voucher = v
                rf.voucher_no = vno
                await rf.save()
                month_vouchers.append({"id": v.id, "voucher_no": vno, "source": f"收款退款 {rf.bill_no}"})

        # 核销单 → 借 预收账款2203，贷 应收账款1122
        if advance_account:
            write_offs = await ReceivableWriteOff.filter(
                account_set_id=account_set_id, status="confirmed", voucher_id=None,
                write_off_date__gte=period_start, write_off_date__lte=period_end,
            ).all()
            for wo in write_offs:
                employee, department = await _get_employee_department_from_receivable(wo.receivable_bill_id)
                async with transactions.in_transaction():
                    vno = await _next_voucher_no(account_set_id, "记", period_name)
                    v = await Voucher.create(
                        account_set_id=account_set_id,
                        voucher_type="记",
                        voucher_no=vno,
                        period_name=period_name,
                        voucher_date=wo.write_off_date,
                        summary=f"核销 {wo.bill_no}",
                        total_debit=wo.amount,
                        total_credit=wo.amount,
                        status="draft",
                        creator=user,
                        source_type="receivable_write_off",
                        source_bill_id=wo.id,
                    )
                    await VoucherEntry.create(
                        voucher=v, line_no=1,
                        account_id=advance_account.id,
                        summary=f"核销 {wo.bill_no}",
                        debit_amount=wo.amount,
                        credit_amount=Decimal("0"),
                        aux_customer_id=wo.customer_id,
                        aux_employee=employee if advance_account.aux_employee else None,
                        aux_department=department if advance_account.aux_department else None,
                    )
                    await VoucherEntry.create(
                        voucher=v, line_no=2,
                        account_id=ar_account.id,
                        summary=f"核销 {wo.bill_no}",
                        debit_amount=Decimal("0"),
                        credit_amount=wo.amount,
                        aux_customer_id=wo.customer_id,
                        aux_employee=employee if ar_account.aux_employee else None,
                        aux_department=department if ar_account.aux_department else None,
                    )
                    wo.voucher = v
                    wo.voucher_no = vno
                    await wo.save()
                    month_vouchers.append({"id": v.id, "voucher_no": vno, "source": f"核销 {wo.bill_no}"})

        # 销售退货单 → 红字冲销出库凭证：借 发出商品1407（负数），贷 库存商品1405（负数）
        if shipped_acct and inventory_acct:
            return_orders = await Order.filter(
                account_set_id=account_set_id,
                order_type="RETURN",
                voucher_id=None,
                created_at__gte=period_start,
                created_at__lte=datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc),
            ).all()
            for ro in return_orders:
                cost = abs(ro.total_cost)
                if cost <= 0:
                    continue
                async with transactions.in_transaction():
                    vno = await _next_voucher_no(account_set_id, "记", period_name)
                    v = await Voucher.create(
                        account_set_id=account_set_id,
                        voucher_type="记",
                        voucher_no=vno,
                        period_name=period_name,
                        voucher_date=ro.created_at.date() if hasattr(ro.created_at, 'date') else ro.created_at,
                        summary=f"销售退货冲回 {ro.order_no}",
                        total_debit=-cost,
                        total_credit=-cost,
                        status="draft",
                        creator=user,
                        source_type="sales_return",
                        source_bill_id=ro.id,
                    )
                    await VoucherEntry.create(
                        voucher=v, line_no=1,
                        account_id=shipped_acct.id,
                        summary=f"销售退货冲回 {ro.order_no}",
                        debit_amount=-cost,
                        credit_amount=Decimal("0"),
                    )
                    await VoucherEntry.create(
                        voucher=v, line_no=2,
                        account_id=inventory_acct.id,
                        summary=f"销售退货冲回 {ro.order_no}",
                        debit_amount=Decimal("0"),
                        credit_amount=-cost,
                    )
                    ro.voucher = v
                    ro.voucher_no = vno
                    await ro.save()
                    month_vouchers.append({"id": v.id, "voucher_no": vno, "source": f"销售退货 {ro.order_no}"})

        summary[period_name] = {"count": len(month_vouchers), "skipped": False}
        vouchers.extend(month_vouchers)

    logger.info(f"AR凭证生成完成: {len(vouchers)} 张")
    return {"vouchers": vouchers, "summary": summary}
