"""出入库单模型"""
from tortoise import fields, models


class SalesDeliveryBill(models.Model):
    """销售出库单"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="sales_delivery_bills", on_delete=fields.CASCADE)
    customer = fields.ForeignKeyField("models.Customer", related_name="sales_delivery_bills", on_delete=fields.RESTRICT)
    order = fields.ForeignKeyField("models.Order", related_name="sales_delivery_bills", null=True, on_delete=fields.SET_NULL)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="sales_delivery_bills", null=True, on_delete=fields.SET_NULL)
    bill_date = fields.DateField()
    total_cost = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = fields.CharField(max_length=20, default="confirmed")
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="sales_delivery_bill")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_sales_deliveries", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "sales_delivery_bills"
        indexes = (("account_set_id", "customer_id"),)


class SalesDeliveryItem(models.Model):
    """出库单明细"""
    id = fields.IntField(pk=True)
    delivery_bill = fields.ForeignKeyField("models.SalesDeliveryBill", related_name="items", on_delete=fields.CASCADE)
    order_item = fields.ForeignKeyField("models.OrderItem", null=True, on_delete=fields.SET_NULL, related_name="delivery_items")
    product = fields.ForeignKeyField("models.Product", on_delete=fields.RESTRICT, related_name="delivery_items")
    product_name = fields.CharField(max_length=200)
    quantity = fields.IntField()
    cost_price = fields.DecimalField(max_digits=18, decimal_places=2)
    sale_price = fields.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        table = "sales_delivery_items"


class PurchaseReceiptBill(models.Model):
    """采购入库单"""
    id = fields.IntField(pk=True)
    bill_no = fields.CharField(max_length=30, unique=True)
    account_set = fields.ForeignKeyField("models.AccountSet", related_name="purchase_receipt_bills", on_delete=fields.CASCADE)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="purchase_receipt_bills", on_delete=fields.RESTRICT)
    purchase_order = fields.ForeignKeyField("models.PurchaseOrder", related_name="purchase_receipt_bills", null=True, on_delete=fields.SET_NULL)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="purchase_receipt_bills", null=True, on_delete=fields.SET_NULL)
    bill_date = fields.DateField()
    total_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount_without_tax = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_tax = fields.DecimalField(max_digits=18, decimal_places=2, default=0)
    status = fields.CharField(max_length=20, default="confirmed")
    voucher = fields.ForeignKeyField("models.Voucher", null=True, on_delete=fields.SET_NULL, related_name="purchase_receipt_bill")
    voucher_no = fields.CharField(max_length=30, null=True)
    remark = fields.TextField(default="")
    creator = fields.ForeignKeyField("models.User", related_name="created_purchase_receipts", null=True, on_delete=fields.SET_NULL)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "purchase_receipt_bills"
        indexes = (("account_set_id", "supplier_id"),)


class PurchaseReceiptItem(models.Model):
    """入库单明细"""
    id = fields.IntField(pk=True)
    receipt_bill = fields.ForeignKeyField("models.PurchaseReceiptBill", related_name="items", on_delete=fields.CASCADE)
    purchase_order_item = fields.ForeignKeyField("models.PurchaseOrderItem", null=True, on_delete=fields.SET_NULL, related_name="receipt_items")
    product = fields.ForeignKeyField("models.Product", on_delete=fields.RESTRICT, related_name="receipt_items")
    product_name = fields.CharField(max_length=200)
    quantity = fields.IntField()
    tax_inclusive_price = fields.DecimalField(max_digits=18, decimal_places=2)
    tax_exclusive_price = fields.DecimalField(max_digits=18, decimal_places=2)
    tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=13)

    class Meta:
        table = "purchase_receipt_items"
