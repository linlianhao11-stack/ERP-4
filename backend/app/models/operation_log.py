from tortoise import fields, models


class OperationLog(models.Model):
    id = fields.IntField(pk=True)
    action = fields.CharField(max_length=50)
    target_type = fields.CharField(max_length=50)
    target_id = fields.IntField(null=True)
    detail = fields.TextField(null=True)
    operator = fields.ForeignKeyField("models.User", related_name="operation_logs", on_delete=fields.RESTRICT)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "operation_logs"
        indexes = (("created_at",),)
