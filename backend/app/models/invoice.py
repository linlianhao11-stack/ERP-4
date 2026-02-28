"""发票模型"""
from tortoise import fields, models


class Invoice(models.Model):
    """发票"""
    id = fields.IntField(pk=True)
    invoice_no = fields.CharField(max_length=30, unique=True)
    invoice_type = fields.CharField(max_length=20)  # special / normal
    direction = fields.CharField(max_length=10)  # output / input
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="invoices", on_delete=fields.CASCADE)
    customer = fields.ForeignKeyField("models.Customer", related_name="invoices", null=True, on_delete=fields.RESTRICT)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="invoices", null=True, on_delete=fields.RESTRICT)
    receivable_bill = fields.ForeignKeyField("models.ReceivableBill", related_name="invoices", null=True, on_delete=fields.SET_NULL)
    payable_bill = fields.ForeignKeyField("models.PayableBill", related_name="invoices", null=True, on_delete=fields.SET_NULL)
    invoice_date = fields.DateField()
    total_amount = fields.DecimalField(max_digits=18, decimal_places=2)
    amount_without_tax = fields.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = fields.DecimalField(max_digits=18, decimal_places=2)
    status = fields.CharField(max_length=20, default="draft")
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="invoice")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_invoices", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "invoices"
        indexes = (("account_set_id", "direction"), ("account_set_id", "status"),)


class InvoiceItem(models.Model):
    """发票明细行"""
    id = fields.IntField(pk=True)
    invoice = fields.ForeignKeyField("models.Invoice", related_name="items", on_delete=fields.CASCADE)
    product = fields.ForeignKeyField("models.Product", null=True, on_delete=fields.SET_NULL, related_name="invoice_items")
    product_name = fields.CharField(max_length=200)
    quantity = fields.IntField()
    unit_price = fields.DecimalField(max_digits=18, decimal_places=2)
    tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=13)
    tax_amount = fields.DecimalField(max_digits=18, decimal_places=2)
    amount_without_tax = fields.DecimalField(max_digits=18, decimal_places=2)
    amount = fields.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        table = "invoice_items"
