from tortoise import fields, models


class Department(models.Model):
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=20, unique=True)
    name = fields.CharField(max_length=100)
    sort_order = fields.IntField(default=0)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "departments"


class Employee(models.Model):
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=20, unique=True)
    name = fields.CharField(max_length=100)
    phone = fields.CharField(max_length=30, default="")
    department = fields.ForeignKeyField(
        "models.Department", null=True,
        on_delete=fields.SET_NULL, related_name="employees"
    )
    is_salesperson = fields.BooleanField(default=False)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "employees"
