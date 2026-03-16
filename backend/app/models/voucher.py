"""凭证模型"""
from tortoise import fields, models


class Voucher(models.Model):
    """记账凭证"""
    id = fields.IntField(pk=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="vouchers", on_delete=fields.CASCADE)
    voucher_type = fields.CharField(max_length=4)  # 记/收/付/转
    voucher_no = fields.CharField(max_length=30, unique=True)
    period_name = fields.CharField(max_length=7)
    voucher_date = fields.DateField()
    summary = fields.CharField(max_length=200, default="")
    total_debit = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_credit = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = fields.CharField(max_length=20, default="draft")  # draft/pending/approved/posted
    attachment_count = fields.IntField(default=0)
    creator = fields.ForeignKeyField("models.User", related_name="created_vouchers", null=True, on_delete=fields.SET_NULL)
    approved_by = fields.ForeignKeyField("models.User", related_name="approved_vouchers", null=True, on_delete=fields.SET_NULL)
    approved_at = fields.DatetimeField(null=True)
    posted_by = fields.ForeignKeyField("models.User", related_name="posted_vouchers", null=True, on_delete=fields.SET_NULL)
    posted_at = fields.DatetimeField(null=True)
    source_type = fields.CharField(max_length=30, null=True)
    source_bill_id = fields.IntField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "vouchers"
        indexes = (("status",),)


class VoucherEntry(models.Model):
    """凭证分录"""
    id = fields.IntField(pk=True)
    voucher = fields.ForeignKeyField("models.Voucher", related_name="entries", on_delete=fields.CASCADE)
    line_no = fields.IntField()
    account = fields.ForeignKeyField("models.ChartOfAccount", related_name="voucher_entries", on_delete=fields.RESTRICT)
    summary = fields.CharField(max_length=200, default="")
    debit_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    credit_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    aux_customer = fields.ForeignKeyField("models.Customer", null=True, on_delete=fields.SET_NULL, related_name="voucher_entries")
    aux_supplier = fields.ForeignKeyField("models.Supplier", null=True, on_delete=fields.SET_NULL, related_name="voucher_entries")
    aux_employee = fields.ForeignKeyField("models.Employee", null=True, on_delete=fields.SET_NULL, related_name="voucher_entries")
    aux_department = fields.ForeignKeyField("models.Department", null=True, on_delete=fields.SET_NULL, related_name="voucher_entries")
    aux_product = fields.ForeignKeyField("models.Product", null=True, on_delete=fields.SET_NULL, related_name="voucher_entries_product")
    aux_bank_account = fields.ForeignKeyField("models.BankAccount", null=True, on_delete=fields.SET_NULL, related_name="voucher_entries_bank")

    class Meta:
        table = "voucher_entries"
        ordering = ["line_no"]
        indexes = (("voucher_id",), ("account_id",),)
