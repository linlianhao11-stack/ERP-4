from tortoise import fields, models


class Order(models.Model):
    id = fields.IntField(pk=True)
    order_no = fields.CharField(max_length=50, unique=True)
    order_type = fields.CharField(max_length=20)
    customer = fields.ForeignKeyField("models.Customer", related_name="orders", null=True, on_delete=fields.RESTRICT)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="orders", null=True, on_delete=fields.SET_NULL)
    related_order = fields.ForeignKeyField("models.Order", related_name="return_orders", null=True, on_delete=fields.SET_NULL)
    total_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_profit = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    rebate_used = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_cleared = fields.BooleanField(default=False)
    refunded = fields.BooleanField(default=False)
    refund_method = fields.CharField(max_length=50, null=True)
    refund_amount = fields.DecimalField(max_digits=18, decimal_places=2, null=True)
    remark = fields.TextField(null=True)
    refund_info = fields.TextField(default="")  # 退款备注信息（业务员填写）
    employee = fields.ForeignKeyField("models.Employee", related_name="orders", null=True, on_delete=fields.SET_NULL)
    creator = fields.ForeignKeyField("models.User", related_name="orders", null=True, on_delete=fields.SET_NULL)
    shipping_status = fields.CharField(max_length=20, default="pending")
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="orders", null=True, on_delete=fields.SET_NULL)
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="return_order_vouchers")
    voucher_no = fields.CharField(max_length=30, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "orders"
        indexes = (("customer_id", "created_at"),)


class OrderItem(models.Model):
    id = fields.IntField(pk=True)
    order = fields.ForeignKeyField("models.Order", related_name="items", on_delete=fields.CASCADE)
    product = fields.ForeignKeyField("models.Product", related_name="order_items", on_delete=fields.RESTRICT)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="order_items", null=True, on_delete=fields.SET_NULL)
    location = fields.ForeignKeyField("models.Location", related_name="order_items", null=True, on_delete=fields.SET_NULL)
    quantity = fields.IntField()
    unit_price = fields.DecimalField(max_digits=12, decimal_places=2)
    cost_price = fields.DecimalField(max_digits=12, decimal_places=2)
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    profit = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    rebate_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipped_qty = fields.IntField(default=0)

    class Meta:
        table = "order_items"
        indexes = (("order_id", "product_id"), ("warehouse_id", "location_id"),)
