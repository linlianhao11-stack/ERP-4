from tortoise import fields, models


class Payment(models.Model):
    id = fields.IntField(pk=True)
    payment_no = fields.CharField(max_length=50, unique=True)
    customer = fields.ForeignKeyField("models.Customer", related_name="payments", on_delete=fields.RESTRICT)
    order = fields.ForeignKeyField("models.Order", related_name="cash_payments", null=True, on_delete=fields.SET_NULL)
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    payment_method = fields.CharField(max_length=50, default="cash")
    source = fields.CharField(max_length=20, default="CREDIT")
    is_confirmed = fields.BooleanField(default=False)
    confirmed_by = fields.ForeignKeyField("models.User", related_name="confirmed_payments", null=True, on_delete=fields.SET_NULL)
    confirmed_at = fields.DatetimeField(null=True)
    remark = fields.TextField(null=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="payments", null=True, on_delete=fields.SET_NULL)
    creator = fields.ForeignKeyField("models.User", related_name="payments", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "payments"
        indexes = (("customer_id",), ("order_id",),)


class PaymentOrder(models.Model):
    id = fields.IntField(pk=True)
    payment = fields.ForeignKeyField("models.Payment", related_name="order_links", on_delete=fields.CASCADE)
    order = fields.ForeignKeyField("models.Order", related_name="payment_links", on_delete=fields.RESTRICT)
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "payment_orders"
        indexes = (("payment_id",), ("order_id",),)


class PaymentMethod(models.Model):
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=50, unique=True)
    name = fields.CharField(max_length=100)
    sort_order = fields.IntField(default=0)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "payment_methods"


class DisbursementMethod(models.Model):
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=50, unique=True)
    name = fields.CharField(max_length=100)
    sort_order = fields.IntField(default=0)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "disbursement_methods"
