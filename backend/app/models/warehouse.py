from tortoise import fields, models


class Warehouse(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    is_default = fields.BooleanField(default=False)
    is_virtual = fields.BooleanField(default=False)
    customer_id = fields.IntField(null=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "warehouses"


class Location(models.Model):
    id = fields.IntField(pk=True)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="locations", on_delete=fields.CASCADE)
    code = fields.CharField(max_length=50)
    name = fields.CharField(max_length=100, null=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "locations"
        unique_together = (("warehouse", "code"),)
