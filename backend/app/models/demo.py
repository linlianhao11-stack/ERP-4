from __future__ import annotations

from tortoise import fields, models


class DemoUnit(models.Model):
    """样机台账"""

    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=30, unique=True)

    product = fields.ForeignKeyField(
        "models.Product", related_name="demo_units", on_delete=fields.RESTRICT,
    )
    sn_code = fields.ForeignKeyField(
        "models.SnCode", related_name="demo_units", null=True, on_delete=fields.SET_NULL,
    )
    warehouse = fields.ForeignKeyField(
        "models.Warehouse", related_name="demo_units", on_delete=fields.RESTRICT,
    )

    status = fields.CharField(max_length=20, default="in_stock")
    condition = fields.CharField(max_length=10, default="new")
    cost_price = fields.DecimalField(max_digits=12, decimal_places=2, default=0)

    current_holder_type = fields.CharField(max_length=10, null=True)
    current_holder_id = fields.IntField(null=True)

    total_loan_count = fields.IntField(default=0)
    total_loan_days = fields.IntField(default=0)
    notes = fields.TextField(null=True)

    created_by = fields.ForeignKeyField(
        "models.User", related_name="created_demo_units", null=True, on_delete=fields.SET_NULL,
    )
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "demo_units"
        ordering = ["-created_at"]


class DemoLoan(models.Model):
    """样机借还记录"""

    id = fields.IntField(pk=True)
    loan_no = fields.CharField(max_length=30, unique=True)

    demo_unit = fields.ForeignKeyField(
        "models.DemoUnit", related_name="loans", on_delete=fields.RESTRICT,
    )

    loan_type = fields.CharField(max_length=20)
    borrower_type = fields.CharField(max_length=10)
    borrower_id = fields.IntField()
    handler = fields.ForeignKeyField(
        "models.Employee", related_name="demo_loans", null=True, on_delete=fields.SET_NULL,
    )

    status = fields.CharField(max_length=20, default="pending_approval")

    loan_date = fields.DateField(null=True)
    expected_return_date = fields.DateField()
    actual_return_date = fields.DateField(null=True)

    condition_on_loan = fields.CharField(max_length=10)
    condition_on_return = fields.CharField(max_length=10, null=True)
    return_notes = fields.TextField(null=True)

    approved_by = fields.ForeignKeyField(
        "models.User", related_name="approved_demo_loans", null=True, on_delete=fields.SET_NULL,
    )
    approved_at = fields.DatetimeField(null=True)
    purpose = fields.TextField(null=True)

    created_by = fields.ForeignKeyField(
        "models.User", related_name="created_demo_loans", null=True, on_delete=fields.SET_NULL,
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "demo_loans"
        ordering = ["-created_at"]


class DemoDisposal(models.Model):
    """样机处置记录"""

    id = fields.IntField(pk=True)

    demo_unit = fields.ForeignKeyField(
        "models.DemoUnit", related_name="disposals", on_delete=fields.RESTRICT,
    )

    disposal_type = fields.CharField(max_length=20)
    amount = fields.DecimalField(max_digits=12, decimal_places=2, null=True)
    refurbish_cost = fields.DecimalField(max_digits=12, decimal_places=2, null=True)

    order_id = fields.IntField(null=True)
    receivable_bill_id = fields.IntField(null=True)
    voucher_id = fields.IntField(null=True)

    target_warehouse_id = fields.IntField(null=True)
    target_location_id = fields.IntField(null=True)

    reason = fields.TextField(null=True)

    approved_by = fields.ForeignKeyField(
        "models.User", related_name="approved_demo_disposals", null=True, on_delete=fields.SET_NULL,
    )
    created_by = fields.ForeignKeyField(
        "models.User", related_name="created_demo_disposals", null=True, on_delete=fields.SET_NULL,
    )
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "demo_disposals"
        ordering = ["-created_at"]
