from tortoise import fields, models


class SnConfig(models.Model):
    id = fields.IntField(pk=True)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="sn_configs", on_delete=fields.RESTRICT)
    brand = fields.CharField(max_length=100)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "sn_configs"
        unique_together = (("warehouse", "brand"),)


class SnCode(models.Model):
    id = fields.IntField(pk=True)
    sn_code = fields.CharField(max_length=200, unique=True)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="sn_codes", on_delete=fields.RESTRICT)
    product = fields.ForeignKeyField("models.Product", related_name="sn_codes", on_delete=fields.RESTRICT)
    location = fields.ForeignKeyField("models.Location", related_name="sn_codes", null=True, on_delete=fields.SET_NULL)
    status = fields.CharField(max_length=20, default="in_stock")
    entry_type = fields.CharField(max_length=30, null=True)
    entry_reference_id = fields.IntField(null=True)
    entry_cost = fields.DecimalField(max_digits=12, decimal_places=2, null=True)
    entry_date = fields.DatetimeField(null=True)
    entry_user = fields.ForeignKeyField("models.User", related_name="sn_entries", null=True, on_delete=fields.SET_NULL)
    shipment = fields.ForeignKeyField("models.Shipment", related_name="sn_codes_rel", null=True, on_delete=fields.SET_NULL)
    ship_date = fields.DatetimeField(null=True)
    ship_user = fields.ForeignKeyField("models.User", related_name="sn_ships", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "sn_codes"
