from tortoise import fields, models


class WarehouseStock(models.Model):
    id = fields.IntField(pk=True)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="stocks", on_delete=fields.RESTRICT)
    product = fields.ForeignKeyField("models.Product", related_name="warehouse_stocks", on_delete=fields.RESTRICT)
    location = fields.ForeignKeyField("models.Location", related_name="stocks", null=True, on_delete=fields.SET_NULL)
    quantity = fields.IntField(default=0)
    reserved_qty = fields.IntField(default=0)
    weighted_cost = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    weighted_entry_date = fields.DatetimeField(null=True)
    updated_at = fields.DatetimeField(auto_now=True)
    last_activity_at = fields.DatetimeField(null=True)

    class Meta:
        table = "warehouse_stocks"
        unique_together = (("warehouse", "product", "location"),)
        indexes = (("warehouse_id", "product_id"),)


class StockLog(models.Model):
    id = fields.IntField(pk=True)
    product = fields.ForeignKeyField("models.Product", related_name="stock_logs", on_delete=fields.RESTRICT)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="stock_logs", on_delete=fields.RESTRICT)
    change_type = fields.CharField(max_length=50)
    quantity = fields.IntField()
    before_qty = fields.IntField()
    after_qty = fields.IntField()
    reference_type = fields.CharField(max_length=50, null=True)
    reference_id = fields.IntField(null=True)
    remark = fields.TextField(null=True)
    creator = fields.ForeignKeyField("models.User", related_name="stock_logs", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "stock_logs"
        indexes = (("product_id", "warehouse_id", "created_at"), ("warehouse_id", "created_at"),)
