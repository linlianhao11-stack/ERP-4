from tortoise import fields, models


class Shipment(models.Model):
    id = fields.IntField(pk=True)
    shipment_no = fields.CharField(max_length=30, unique=True, null=True)
    order = fields.ForeignKeyField("models.Order", related_name="shipments", on_delete=fields.RESTRICT)
    carrier_code = fields.CharField(max_length=30, null=True)
    carrier_name = fields.CharField(max_length=50, null=True)
    tracking_no = fields.CharField(max_length=50, null=True)
    status = fields.CharField(max_length=20, default="pending")
    status_text = fields.CharField(max_length=50, default="待发货")
    last_tracking_info = fields.TextField(null=True)
    phone = fields.CharField(max_length=20, null=True)
    kd100_subscribed = fields.BooleanField(default=False)
    sn_code = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "shipments"
        indexes = (("order_id", "status"),)


class ShipmentItem(models.Model):
    id = fields.IntField(pk=True)
    shipment = fields.ForeignKeyField("models.Shipment", related_name="items", on_delete=fields.CASCADE)
    order_item = fields.ForeignKeyField("models.OrderItem", related_name="shipment_items", on_delete=fields.RESTRICT)
    product = fields.ForeignKeyField("models.Product", related_name="shipment_items", on_delete=fields.RESTRICT)
    quantity = fields.IntField()
    sn_codes = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "shipment_items"
        indexes = (("shipment_id",),)
