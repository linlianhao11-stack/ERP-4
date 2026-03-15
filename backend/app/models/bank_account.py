from tortoise import fields, models


class BankAccount(models.Model):
    id = fields.IntField(pk=True)
    account_set = fields.ForeignKeyField(
        "models.AccountSet", related_name="bank_accounts", on_delete=fields.RESTRICT
    )
    bank_name = fields.CharField(max_length=100)
    account_number = fields.CharField(max_length=50)
    short_name = fields.CharField(max_length=50, default="")
    sort_order = fields.IntField(default=0)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "bank_accounts"
        unique_together = (("account_set", "account_number"),)
