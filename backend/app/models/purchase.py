from decimal import Decimal
from tortoise import fields, models


class PurchaseOrder(models.Model):
    id = fields.IntField(pk=True)
    po_no = fields.CharField(max_length=30, unique=True)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="purchase_orders", on_delete=fields.RESTRICT)
    status = fields.CharField(max_length=20, default="pending_review")
    total_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    rebate_used = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    target_warehouse = fields.ForeignKeyField("models.Warehouse", related_name="purchase_orders", null=True, on_delete=fields.SET_NULL)
    target_location = fields.ForeignKeyField("models.Location", related_name="purchase_orders", null=True, on_delete=fields.SET_NULL)
    remark = fields.TextField(null=True)
    creator = fields.ForeignKeyField("models.User", related_name="created_pos", on_delete=fields.SET_NULL, null=True)
    reviewed_by = fields.ForeignKeyField("models.User", related_name="reviewed_pos", null=True, on_delete=fields.SET_NULL)
    reviewed_at = fields.DatetimeField(null=True)
    payment_method = fields.CharField(max_length=50, null=True)
    paid_by = fields.ForeignKeyField("models.User", related_name="paid_pos", null=True, on_delete=fields.SET_NULL)
    paid_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    return_tracking_no = fields.CharField(max_length=100, null=True)
    is_refunded = fields.BooleanField(default=False)
    return_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_used = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    returned_by = fields.ForeignKeyField("models.User", related_name="returned_pos", null=True, on_delete=fields.SET_NULL)
    returned_at = fields.DatetimeField(null=True)

    class Meta:
        table = "purchase_orders"


class PurchaseOrderItem(models.Model):
    id = fields.IntField(pk=True)
    purchase_order = fields.ForeignKeyField("models.PurchaseOrder", related_name="items", on_delete=fields.CASCADE)
    product = fields.ForeignKeyField("models.Product", related_name="purchase_items", on_delete=fields.RESTRICT)
    quantity = fields.IntField()
    tax_inclusive_price = fields.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.13"))
    tax_exclusive_price = fields.DecimalField(max_digits=12, decimal_places=2)
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    received_quantity = fields.IntField(default=0)
    returned_quantity = fields.IntField(default=0)
    rebate_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    target_warehouse = fields.ForeignKeyField("models.Warehouse", related_name="po_items", null=True, on_delete=fields.SET_NULL)
    target_location = fields.ForeignKeyField("models.Location", related_name="po_items", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "purchase_order_items"
