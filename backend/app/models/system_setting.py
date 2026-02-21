"""系统设置模型"""
from tortoise import fields
from tortoise.models import Model


class SystemSetting(Model):
    id = fields.IntField(pk=True)
    key = fields.CharField(max_length=100, unique=True)
    value = fields.TextField(null=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "system_settings"
