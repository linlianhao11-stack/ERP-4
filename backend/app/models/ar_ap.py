"""应收应付模型"""
from tortoise import fields, models


class ReceivableBill(models.Model):
    """应收单"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="receivable_bills", on_delete=fields.CASCADE)
    customer = fields.ForeignKeyField("models.Customer", related_name="receivable_bills", on_delete=fields.RESTRICT)
    order = fields.ForeignKeyField("models.Order", related_name="receivable_bills", null=True, on_delete=fields.SET_NULL)
    bill_date = fields.DateField()
    total_amount = fields.DecimalField(max_digits=18, decimal_places=2)
    received_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    unreceived_amount = fields.DecimalField(max_digits=18, decimal_places=2)
    status = fields.CharField(max_length=20, default="pending")  # pending/partial/completed/cancelled
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="receivable_bill")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_receivables", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "receivable_bills"
        indexes = (("account_set_id", "customer_id"), ("account_set_id", "status"),)


class ReceiptBill(models.Model):
    """收款单"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="receipt_bills", on_delete=fields.CASCADE)
    customer = fields.ForeignKeyField("models.Customer", related_name="receipt_bills", on_delete=fields.RESTRICT)
    receivable_bill = fields.ForeignKeyField("models.ReceivableBill", null=True, on_delete=fields.SET_NULL, related_name="receipt_bills")
    payment = fields.ForeignKeyField("models.Payment", null=True, on_delete=fields.SET_NULL, related_name="receipt_bill_link")
    receipt_date = fields.DateField()
    amount = fields.DecimalField(max_digits=18, decimal_places=2)
    payment_method = fields.CharField(max_length=50)
    is_advance = fields.BooleanField(default=False)
    status = fields.CharField(max_length=20, default="draft")  # draft/confirmed
    confirmed_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL, related_name="confirmed_receipts")
    confirmed_at = fields.DatetimeField(null=True)
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="receipt_bill")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_receipts", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "receipt_bills"


class ReceiptRefundBill(models.Model):
    """收款退款单"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="receipt_refund_bills", on_delete=fields.CASCADE)
    customer = fields.ForeignKeyField("models.Customer", related_name="receipt_refund_bills", on_delete=fields.RESTRICT)
    original_receipt = fields.ForeignKeyField("models.ReceiptBill", on_delete=fields.RESTRICT, related_name="refund_bills")
    refund_date = fields.DateField()
    amount = fields.DecimalField(max_digits=18, decimal_places=2)
    reason = fields.TextField(default="")
    status = fields.CharField(max_length=20, default="draft")
    confirmed_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL, related_name="confirmed_receipt_refunds")
    confirmed_at = fields.DatetimeField(null=True)
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="receipt_refund_bill")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_receipt_refunds", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "receipt_refund_bills"


class ReceivableWriteOff(models.Model):
    """应收核销单（预收冲应收）"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="receivable_write_offs", on_delete=fields.CASCADE)
    customer = fields.ForeignKeyField("models.Customer", related_name="receivable_write_offs", on_delete=fields.RESTRICT)
    advance_receipt = fields.ForeignKeyField("models.ReceiptBill", on_delete=fields.RESTRICT, related_name="write_off_usages")
    receivable_bill = fields.ForeignKeyField("models.ReceivableBill", on_delete=fields.RESTRICT, related_name="write_offs")
    write_off_date = fields.DateField()
    amount = fields.DecimalField(max_digits=18, decimal_places=2)
    status = fields.CharField(max_length=20, default="draft")
    confirmed_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL, related_name="confirmed_write_offs")
    confirmed_at = fields.DatetimeField(null=True)
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="receivable_write_off")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_write_offs", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "receivable_write_offs"


class PayableBill(models.Model):
    """应付单"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="payable_bills", on_delete=fields.CASCADE)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="payable_bills", on_delete=fields.RESTRICT)
    purchase_order = fields.ForeignKeyField("models.PurchaseOrder", related_name="payable_bills", null=True, on_delete=fields.SET_NULL)
    bill_date = fields.DateField()
    total_amount = fields.DecimalField(max_digits=18, decimal_places=2)
    paid_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    unpaid_amount = fields.DecimalField(max_digits=18, decimal_places=2)
    status = fields.CharField(max_length=20, default="pending")
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="payable_bill")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_payables", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "payable_bills"
        indexes = (("account_set_id", "supplier_id"), ("account_set_id", "status"),)


class DisbursementBill(models.Model):
    """付款单"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="disbursement_bills", on_delete=fields.CASCADE)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="disbursement_bills", on_delete=fields.RESTRICT)
    payable_bill = fields.ForeignKeyField("models.PayableBill", null=True, on_delete=fields.SET_NULL, related_name="disbursement_bills")
    disbursement_date = fields.DateField()
    amount = fields.DecimalField(max_digits=18, decimal_places=2)
    disbursement_method = fields.CharField(max_length=50)
    status = fields.CharField(max_length=20, default="draft")
    confirmed_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL, related_name="confirmed_disbursements")
    confirmed_at = fields.DatetimeField(null=True)
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="disbursement_bill")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_disbursements", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "disbursement_bills"


class DisbursementRefundBill(models.Model):
    """付款退款单"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="disbursement_refund_bills", on_delete=fields.CASCADE)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="disbursement_refund_bills", on_delete=fields.RESTRICT)
    original_disbursement = fields.ForeignKeyField("models.DisbursementBill", on_delete=fields.RESTRICT, related_name="refund_bills")
    refund_date = fields.DateField()
    amount = fields.DecimalField(max_digits=18, decimal_places=2)
    reason = fields.TextField(default="")
    status = fields.CharField(max_length=20, default="draft")
    confirmed_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL, related_name="confirmed_disb_refunds")
    confirmed_at = fields.DatetimeField(null=True)
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="disbursement_refund_bill")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_disb_refunds", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "disbursement_refund_bills"
