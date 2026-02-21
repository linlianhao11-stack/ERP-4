from tortoise import fields, models


class RebateLog(models.Model):
    id = fields.IntField(pk=True)
    target_type = fields.CharField(max_length=20)
    target_id = fields.IntField()
    type = fields.CharField(max_length=20)
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    balance_after = fields.DecimalField(max_digits=12, decimal_places=2)
    reference_type = fields.CharField(max_length=30, null=True)
    reference_id = fields.IntField(null=True)
    remark = fields.TextField(null=True)
    creator = fields.ForeignKeyField("models.User", related_name="rebate_logs", on_delete=fields.RESTRICT)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "rebate_logs"
        indexes = (("target_type", "target_id"),)
