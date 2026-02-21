from tortoise import fields, models


class Supplier(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    contact_person = fields.CharField(max_length=50, null=True)
    phone = fields.CharField(max_length=30, null=True)
    tax_id = fields.CharField(max_length=50, null=True)
    bank_account = fields.CharField(max_length=50, null=True)
    bank_name = fields.CharField(max_length=100, null=True)
    address = fields.TextField(null=True)
    rebate_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "suppliers"
