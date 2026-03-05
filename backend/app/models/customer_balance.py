from tortoise import fields, models


class CustomerAccountBalance(models.Model):
    """客户按账套隔离的返利余额"""
    id = fields.IntField(pk=True)
    customer = fields.ForeignKeyField("models.Customer", related_name="account_balances", on_delete=fields.RESTRICT)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="customer_balances", on_delete=fields.RESTRICT)
    rebate_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        table = "customer_account_balances"
        unique_together = (("customer", "account_set"),)
