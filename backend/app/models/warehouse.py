from tortoise import fields, models


class Warehouse(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    is_default = fields.BooleanField(default=False)
    is_virtual = fields.BooleanField(default=False)
    customer = fields.ForeignKeyField("models.Customer", related_name="warehouses", null=True, on_delete=fields.SET_NULL)
    is_active = fields.BooleanField(default=True)
    color = fields.CharField(max_length=20, default="blue")
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="warehouses", null=True, on_delete=fields.SET_NULL)
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
