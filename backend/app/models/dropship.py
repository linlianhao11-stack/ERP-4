"""代采代发模型"""
from __future__ import annotations

from tortoise import fields, models


class DropshipOrder(models.Model):
    """代采代发订单"""
    id = fields.IntField(pk=True)
    ds_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="dropship_orders", on_delete=fields.RESTRICT)
    status = fields.CharField(max_length=20, default="draft")
    # draft | pending_payment | paid_pending_ship | shipped | completed | cancelled

    # 采购信息
    supplier = fields.ForeignKeyField("models.Supplier", related_name="dropship_orders", on_delete=fields.RESTRICT)
    product = fields.ForeignKeyField("models.Product", related_name="dropship_orders", null=True, on_delete=fields.SET_NULL)
    product_name = fields.CharField(max_length=200)
    purchase_price = fields.DecimalField(max_digits=12, decimal_places=2)
    quantity = fields.IntField()
    purchase_total = fields.DecimalField(max_digits=12, decimal_places=2)
    invoice_type = fields.CharField(max_length=10, default="special")  # special | normal
    purchase_tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=13)

    # 销售信息
    customer = fields.ForeignKeyField("models.Customer", related_name="dropship_orders", on_delete=fields.RESTRICT)
    platform_order_no = fields.CharField(max_length=100)
    sale_price = fields.DecimalField(max_digits=12, decimal_places=2)
    sale_total = fields.DecimalField(max_digits=12, decimal_places=2)
    sale_tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=13)
    settlement_type = fields.CharField(max_length=10, default="credit")  # prepaid | credit
    advance_receipt = fields.ForeignKeyField("models.ReceiptBill", related_name="dropship_orders", null=True, on_delete=fields.SET_NULL)

    # 毛利
    gross_profit = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_margin = fields.DecimalField(max_digits=5, decimal_places=2, default=0)

    # 物流信息
    shipping_mode = fields.CharField(max_length=10, default="direct")  # direct | transit
    carrier_code = fields.CharField(max_length=30, null=True)
    carrier_name = fields.CharField(max_length=50, null=True)
    tracking_no = fields.CharField(max_length=100, null=True)
    kd100_subscribed = fields.BooleanField(default=False)
    last_tracking_info = fields.TextField(null=True)

    # 状态管理
    urged_at = fields.DatetimeField(null=True)
    cancel_reason = fields.CharField(max_length=200, null=True)
    note = fields.TextField(null=True)

    # 关联财务单据
    payable_bill = fields.ForeignKeyField("models.PayableBill", related_name="dropship_orders", null=True, on_delete=fields.SET_NULL)
    disbursement_bill = fields.ForeignKeyField("models.DisbursementBill", related_name="dropship_orders", null=True, on_delete=fields.SET_NULL)
    receivable_bill = fields.ForeignKeyField("models.ReceivableBill", related_name="dropship_orders", null=True, on_delete=fields.SET_NULL)

    # 付款信息
    payment_method = fields.CharField(max_length=50, null=True)
    payment_employee = fields.ForeignKeyField("models.Employee", related_name="dropship_payments", null=True, on_delete=fields.SET_NULL)

    creator = fields.ForeignKeyField("models.User", related_name="created_dropships", on_delete=fields.SET_NULL, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "dropship_orders"
        ordering = ["-created_at"]
