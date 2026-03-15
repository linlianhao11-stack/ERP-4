"""会计基础模型：账套、科目、会计期间"""
from tortoise import fields, models


class AccountSet(models.Model):
    """账套"""
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=20, unique=True)
    name = fields.CharField(max_length=100)
    company_name = fields.CharField(max_length=200, default="")
    tax_id = fields.CharField(max_length=30, default="")
    legal_person = fields.CharField(max_length=50, default="")
    address = fields.TextField(default="")
    bank_name = fields.CharField(max_length=100, default="")
    bank_account = fields.CharField(max_length=50, default="")
    start_year = fields.IntField()
    start_month = fields.IntField(default=1)
    current_period = fields.CharField(max_length=7)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "account_sets"


class ChartOfAccount(models.Model):
    """会计科目"""
    id = fields.IntField(pk=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="accounts", on_delete=fields.CASCADE)
    code = fields.CharField(max_length=20)
    name = fields.CharField(max_length=100)
    parent_code = fields.CharField(max_length=20, null=True)
    level = fields.IntField(default=1)
    category = fields.CharField(max_length=20)  # asset/liability/equity/cost/profit_loss
    direction = fields.CharField(max_length=6)   # debit/credit
    is_leaf = fields.BooleanField(default=True)
    is_active = fields.BooleanField(default=True)
    aux_customer = fields.BooleanField(default=False)
    aux_supplier = fields.BooleanField(default=False)
    aux_employee = fields.BooleanField(default=False)
    aux_department = fields.BooleanField(default=False)
    aux_product = fields.BooleanField(default=False)
    aux_bank = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chart_of_accounts"
        unique_together = (("account_set", "code"),)


class AccountingPeriod(models.Model):
    """会计期间"""
    id = fields.IntField(pk=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="periods", on_delete=fields.CASCADE)
    period_name = fields.CharField(max_length=7)
    year = fields.IntField()
    month = fields.IntField()
    is_closed = fields.BooleanField(default=False)
    closed_at = fields.DatetimeField(null=True)
    closed_by = fields.ForeignKeyField("models.User", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "accounting_periods"
        unique_together = (("account_set", "period_name"),)
