from tortoise import fields, models


class User(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    password_hash = fields.CharField(max_length=255)
    display_name = fields.CharField(max_length=100, null=True)
    role = fields.CharField(max_length=20, default="user")
    permissions = fields.JSONField(default=list)
    is_active = fields.BooleanField(default=True)
    must_change_password = fields.BooleanField(default=False)
    token_version = fields.IntField(default=0)
    password_changed_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    def has_permission(self, perm: str) -> bool:
        return self.role == "admin" or perm in (self.permissions or [])

    class Meta:
        table = "users"
