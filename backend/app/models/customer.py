from tortoise import fields, models


class Customer(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=200)
    contact_person = fields.CharField(max_length=100, null=True)
    phone = fields.CharField(max_length=50, null=True)
    address = fields.TextField(null=True)
    tax_id = fields.CharField(max_length=50, null=True)       # 纳税人识别号
    bank_name = fields.CharField(max_length=100, null=True)   # 开户行
    bank_account = fields.CharField(max_length=50, null=True) # 银行账号
    invoice_address = fields.CharField(max_length=200, default="")  # 开票地址
    invoice_phone = fields.CharField(max_length=50, default="")     # 开票电话
    balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    rebate_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "customers"
        indexes = (("is_active",),)
