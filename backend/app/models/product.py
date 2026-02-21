from tortoise import fields, models


class Product(models.Model):
    id = fields.IntField(pk=True)
    sku = fields.CharField(max_length=50, unique=True)
    name = fields.CharField(max_length=200)
    brand = fields.CharField(max_length=100, null=True)
    category = fields.CharField(max_length=100, null=True)
    retail_price = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_price = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = fields.CharField(max_length=20, default="个")
    description = fields.TextField(null=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "products"
