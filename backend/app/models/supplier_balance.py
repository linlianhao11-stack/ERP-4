from tortoise import fields, models


class SupplierAccountBalance(models.Model):
    """供应商按账套隔离的返利余额和在账资金余额"""
    id = fields.IntField(pk=True)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="account_balances", on_delete=fields.RESTRICT)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="supplier_balances", on_delete=fields.RESTRICT)
    rebate_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        table = "supplier_account_balances"
        unique_together = (("supplier", "account_set"),)
