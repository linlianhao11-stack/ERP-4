"""
轻量级 ERP 系统 v3.6
支持多仓库、寄售、库龄管理、权限控制、在账资金管理
FastAPI + Tortoise-ORM + SQLite + Vue3
"""
import os
import glob
import sqlite3
import asyncio
import secrets
import traceback
import hashlib
import json
import io
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, List
from contextlib import asynccontextmanager
from urllib.parse import quote

import httpx

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.hash import pbkdf2_sha256
from jose import JWTError, jwt
from tortoise import fields, models, Tortoise, transactions
from tortoise.expressions import Q, F
from tortoise.functions import Sum, Count

# 时区处理：统一使用无时区的 datetime
def now():
    """返回当前时间（无时区）"""
    return datetime.now()

def to_naive(dt):
    """将日期转换为无时区格式"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt

def days_between(dt1, dt2):
    """计算两个日期之间的天数差（自动处理时区）"""
    dt1 = to_naive(dt1) if dt1 else now()
    dt2 = to_naive(dt2) if dt2 else now()
    return (dt1 - dt2).days

# ==================== 配置 ====================
# 自动检测运行环境，设置正确的数据库路径
def get_database_url():
    # 优先使用环境变量
    if os.environ.get("DATABASE_URL"):
        return os.environ.get("DATABASE_URL")
    # 本地开发：在当前目录创建 data 文件夹
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "erp.db")
    # 使用正向斜杠，兼容 Windows 和 Docker
    db_path_norm = db_path.replace("\\", "/")
    return f"sqlite:///{db_path_norm}"

DATABASE_URL = get_database_url()
_default_secret = secrets.token_hex(32)
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = _default_secret
    print(f"[WARN] SECRET_KEY 未设置环境变量，已自动生成随机密钥（重启后所有用户需重新登录）")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
CONSIGNMENT_WAREHOUSE_NAME = "__寄售虚拟仓__"

# 备份配置
BACKUP_KEEP_DAYS = int(os.environ.get("BACKUP_KEEP_DAYS", "30"))
BACKUP_HOUR = int(os.environ.get("BACKUP_HOUR", "3"))  # 每天凌晨3点自动备份

def get_db_path():
    """从 DATABASE_URL 提取 SQLite 文件路径"""
    url = DATABASE_URL
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
        # Windows: sqlite:///C:/... → C:/...  (不能有前导/)
        return path
    if url.startswith("sqlite://"):
        return url[len("sqlite://"):]
    return None

def get_backup_dir():
    """获取备份目录，与 data/ 同级的 backups/ 目录"""
    db_path = get_db_path()
    if not db_path:
        return None
    data_dir = os.path.dirname(db_path)
    backup_dir = os.path.join(os.path.dirname(data_dir), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir

def do_backup(tag="auto"):
    """使用 SQLite 在线备份 API，不锁库、不停服"""
    db_path = get_db_path()
    backup_dir = get_backup_dir()
    if not db_path or not backup_dir:
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"erp_{tag}_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_name)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return backup_path

def cleanup_old_backups():
    """清理超过保留天数的旧备份"""
    backup_dir = get_backup_dir()
    if not backup_dir:
        return 0
    cutoff = datetime.now().timestamp() - BACKUP_KEEP_DAYS * 86400
    removed = 0
    for f in glob.glob(os.path.join(backup_dir, "erp_auto_*.db")):
        if os.path.getmtime(f) < cutoff:
            os.remove(f)
            removed += 1
    return removed

async def auto_backup_loop():
    """每天定时自动备份"""
    while True:
        now = datetime.now()
        # 计算到下一个备份时间点的秒数
        target = now.replace(hour=BACKUP_HOUR, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        try:
            path = do_backup("auto")
            removed = cleanup_old_backups()
            print(f"[自动备份] 完成: {os.path.basename(path)}, 清理旧备份: {removed}个")
        except Exception as e:
            print(f"[自动备份] 失败: {e}")

# 快递100配置（请通过环境变量设置，未配置时物流查询功能不可用）
KD100_KEY = os.environ.get("KD100_KEY", "")
KD100_CUSTOMER = os.environ.get("KD100_CUSTOMER", "")
KD100_POLL_URL = "https://poll.kuaidi100.com/poll"
KD100_QUERY_URL = "https://poll.kuaidi100.com/poll/query.do"
KD100_CALLBACK_URL = os.environ.get("KD100_CALLBACK_URL", "http://erp3.iepose.cn/api/logistics/kd100/callback")

security = HTTPBearer(auto_error=False)

# ==================== 数据库模型 ====================
class User(models.Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    password_hash = fields.CharField(max_length=255)
    display_name = fields.CharField(max_length=100, null=True)
    role = fields.CharField(max_length=20, default="user")  # admin, user
    permissions = fields.JSONField(default=list)  # ['dashboard','sales','logistics','consignment','stock_view','stock_edit','customer','finance','finance_confirm','logs','settings']
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

class Warehouse(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    is_default = fields.BooleanField(default=False)
    is_virtual = fields.BooleanField(default=False)  # 寄售虚拟仓
    customer_id = fields.IntField(null=True)  # 关联客户ID（独立寄售仓）
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "warehouses"

class Location(models.Model):
    """仓位 - 全局仓位，不区分仓库"""
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=50, unique=True)  # 仓位编号，如 A-01-02
    name = fields.CharField(max_length=100, null=True)   # 仓位名称（可选）
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "locations"

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

class WarehouseStock(models.Model):
    """仓库库存 - 每个商品在每个仓库每个仓位的库存"""
    id = fields.IntField(pk=True)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="stocks")
    product = fields.ForeignKeyField("models.Product", related_name="warehouse_stocks")
    location = fields.ForeignKeyField("models.Location", related_name="stocks", null=True)  # 仓位
    quantity = fields.IntField(default=0)
    weighted_cost = fields.DecimalField(max_digits=12, decimal_places=2, default=0)  # 加权平均成本
    weighted_entry_date = fields.DatetimeField(null=True)  # 加权入库日期（库龄计算）
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "warehouse_stocks"
        unique_together = (("warehouse", "product", "location"),)  # 三元组唯一

class Salesperson(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
    phone = fields.CharField(max_length=30, null=True)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    class Meta:
        table = "salespersons"

class Customer(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=200)
    contact_person = fields.CharField(max_length=100, null=True)
    phone = fields.CharField(max_length=50, null=True)
    address = fields.TextField(null=True)
    balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)  # 应收账款余额
    rebate_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)  # 返利余额
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "customers"

class Order(models.Model):
    """订单/交易记录"""
    id = fields.IntField(pk=True)
    order_no = fields.CharField(max_length=50, unique=True)
    order_type = fields.CharField(max_length=20)  # CASH, CREDIT, CONSIGN_OUT, CONSIGN_SETTLE, RETURN
    customer = fields.ForeignKeyField("models.Customer", related_name="orders", null=True)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="orders", null=True)
    related_order = fields.ForeignKeyField("models.Order", related_name="return_orders", null=True)  # 关联的原始销售订单（退货时使用）
    total_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_profit = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    rebate_used = fields.DecimalField(max_digits=12, decimal_places=2, default=0)  # 使用的返利总额
    is_cleared = fields.BooleanField(default=False)  # 是否已结清
    refunded = fields.BooleanField(default=False)  # 退货时：是否已退款给客户
    remark = fields.TextField(null=True)
    salesperson = fields.ForeignKeyField("models.Salesperson", related_name="orders", null=True)
    creator = fields.ForeignKeyField("models.User", related_name="orders", null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "orders"

class OrderItem(models.Model):
    """订单明细"""
    id = fields.IntField(pk=True)
    order = fields.ForeignKeyField("models.Order", related_name="items")
    product = fields.ForeignKeyField("models.Product", related_name="order_items")
    quantity = fields.IntField()
    unit_price = fields.DecimalField(max_digits=12, decimal_places=2)
    cost_price = fields.DecimalField(max_digits=12, decimal_places=2)
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    profit = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    rebate_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)  # 该行使用的返利

    class Meta:
        table = "order_items"

class Payment(models.Model):
    """收款记录"""
    id = fields.IntField(pk=True)
    payment_no = fields.CharField(max_length=50, unique=True)
    customer = fields.ForeignKeyField("models.Customer", related_name="payments")
    order = fields.ForeignKeyField("models.Order", related_name="cash_payments", null=True)
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    payment_method = fields.CharField(max_length=50, default="cash")
    source = fields.CharField(max_length=20, default="CREDIT")  # CASH=现款 / CREDIT=账期收款
    is_confirmed = fields.BooleanField(default=False)
    confirmed_by = fields.ForeignKeyField("models.User", related_name="confirmed_payments", null=True)
    confirmed_at = fields.DatetimeField(null=True)
    remark = fields.TextField(null=True)
    creator = fields.ForeignKeyField("models.User", related_name="payments", null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "payments"

class PaymentOrder(models.Model):
    """回款-订单关联（核销明细）"""
    id = fields.IntField(pk=True)
    payment = fields.ForeignKeyField("models.Payment", related_name="order_links")
    order = fields.ForeignKeyField("models.Order", related_name="payment_links")
    amount = fields.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        table = "payment_orders"

class StockLog(models.Model):
    """库存变动日志"""
    id = fields.IntField(pk=True)
    product = fields.ForeignKeyField("models.Product", related_name="stock_logs")
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="stock_logs")
    change_type = fields.CharField(max_length=50)  # RESTOCK, SALE, RETURN, CONSIGN_OUT, CONSIGN_SETTLE, ADJUST
    quantity = fields.IntField()
    before_qty = fields.IntField()
    after_qty = fields.IntField()
    reference_type = fields.CharField(max_length=50, null=True)
    reference_id = fields.IntField(null=True)
    remark = fields.TextField(null=True)
    creator = fields.ForeignKeyField("models.User", related_name="stock_logs", null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "stock_logs"

class PaymentMethod(models.Model):
    """收款方式"""
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=50, unique=True)
    name = fields.CharField(max_length=100)
    sort_order = fields.IntField(default=0)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    class Meta:
        table = "payment_methods"

class OperationLog(models.Model):
    """操作日志"""
    id = fields.IntField(pk=True)
    action = fields.CharField(max_length=50)
    target_type = fields.CharField(max_length=50)
    target_id = fields.IntField(null=True)
    detail = fields.TextField(null=True)
    operator = fields.ForeignKeyField("models.User", related_name="operation_logs")
    created_at = fields.DatetimeField(auto_now_add=True)
    class Meta:
        table = "operation_logs"

class Supplier(models.Model):
    """供应商"""
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    contact_person = fields.CharField(max_length=50, null=True)
    phone = fields.CharField(max_length=30, null=True)
    tax_id = fields.CharField(max_length=50, null=True)
    bank_account = fields.CharField(max_length=50, null=True)
    bank_name = fields.CharField(max_length=100, null=True)
    address = fields.TextField(null=True)
    rebate_balance = fields.DecimalField(max_digits=12, decimal_places=2, default=0)  # 返利余额
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "suppliers"

class PurchaseOrder(models.Model):
    """采购订单"""
    id = fields.IntField(pk=True)
    po_no = fields.CharField(max_length=30, unique=True)
    supplier = fields.ForeignKeyField("models.Supplier", related_name="purchase_orders")
    status = fields.CharField(max_length=20, default="pending_review")  # pending_review/pending/paid/partial/completed/cancelled/rejected
    total_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    rebate_used = fields.DecimalField(max_digits=12, decimal_places=2, default=0)  # 使用的返利总额
    target_warehouse = fields.ForeignKeyField("models.Warehouse", related_name="purchase_orders", null=True)
    target_location = fields.ForeignKeyField("models.Location", related_name="purchase_orders", null=True)
    remark = fields.TextField(null=True)
    creator = fields.ForeignKeyField("models.User", related_name="created_pos")
    reviewed_by = fields.ForeignKeyField("models.User", related_name="reviewed_pos", null=True)
    reviewed_at = fields.DatetimeField(null=True)
    paid_by = fields.ForeignKeyField("models.User", related_name="paid_pos", null=True)
    paid_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "purchase_orders"

class PurchaseOrderItem(models.Model):
    """采购明细"""
    id = fields.IntField(pk=True)
    purchase_order = fields.ForeignKeyField("models.PurchaseOrder", related_name="items")
    product = fields.ForeignKeyField("models.Product", related_name="purchase_items")
    quantity = fields.IntField()
    tax_inclusive_price = fields.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=0.13)
    tax_exclusive_price = fields.DecimalField(max_digits=12, decimal_places=2)
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    received_quantity = fields.IntField(default=0)
    rebate_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0)  # 该行使用的返利
    target_warehouse = fields.ForeignKeyField("models.Warehouse", related_name="po_items", null=True)
    target_location = fields.ForeignKeyField("models.Location", related_name="po_items", null=True)

    class Meta:
        table = "purchase_order_items"

class SystemSetting(models.Model):
    id = fields.IntField(pk=True)
    key = fields.CharField(max_length=100, unique=True)
    value = fields.TextField(null=True)
    updated_at = fields.DatetimeField(auto_now=True)
    class Meta:
        table = "system_settings"

class Voucher(models.Model):
    id = fields.IntField(pk=True)
    voucher_no = fields.CharField(max_length=50, unique=True)
    voucher_type = fields.CharField(max_length=10)
    seq_number = fields.IntField()
    source_type = fields.CharField(max_length=30)
    source_id = fields.IntField()
    voucher_date = fields.DateField()
    company_name = fields.CharField(max_length=200, null=True)
    total_debit = fields.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_credit = fields.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=0.13)
    remark = fields.TextField(null=True)
    creator = fields.ForeignKeyField("models.User", related_name="vouchers", null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    class Meta:
        table = "vouchers"

class VoucherEntry(models.Model):
    id = fields.IntField(pk=True)
    voucher = fields.ForeignKeyField("models.Voucher", related_name="entries")
    seq = fields.IntField()
    summary = fields.CharField(max_length=200)
    account = fields.CharField(max_length=200)
    debit_amount = fields.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit_amount = fields.DecimalField(max_digits=14, decimal_places=2, default=0)
    class Meta:
        table = "voucher_entries"

class RebateLog(models.Model):
    """返利流水"""
    id = fields.IntField(pk=True)
    target_type = fields.CharField(max_length=20)  # customer / supplier
    target_id = fields.IntField()
    type = fields.CharField(max_length=10)  # charge / use
    amount = fields.DecimalField(max_digits=12, decimal_places=2)
    balance_after = fields.DecimalField(max_digits=12, decimal_places=2)
    reference_type = fields.CharField(max_length=30, null=True)  # ORDER / PURCHASE_ORDER
    reference_id = fields.IntField(null=True)
    remark = fields.TextField(null=True)
    creator = fields.ForeignKeyField("models.User", related_name="rebate_logs")
    created_at = fields.DatetimeField(auto_now_add=True)
    class Meta:
        table = "rebate_logs"

class SnConfig(models.Model):
    """SN码管理配置（仓库+品牌）"""
    id = fields.IntField(pk=True)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="sn_configs")
    brand = fields.CharField(max_length=100)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "sn_configs"
        unique_together = (("warehouse_id", "brand"),)

class SnCode(models.Model):
    """SN码池"""
    id = fields.IntField(pk=True)
    sn_code = fields.CharField(max_length=200, unique=True)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="sn_codes")
    product = fields.ForeignKeyField("models.Product", related_name="sn_codes")
    location = fields.ForeignKeyField("models.Location", related_name="sn_codes", null=True)
    status = fields.CharField(max_length=20, default="in_stock")  # in_stock / shipped
    entry_type = fields.CharField(max_length=30, null=True)  # RESTOCK / PURCHASE_IN
    entry_reference_id = fields.IntField(null=True)
    entry_cost = fields.DecimalField(max_digits=12, decimal_places=2, null=True)
    entry_date = fields.DatetimeField(null=True)
    entry_user = fields.ForeignKeyField("models.User", related_name="sn_entries", null=True)
    shipment = fields.ForeignKeyField("models.Shipment", related_name="sn_codes_rel", null=True)
    ship_date = fields.DatetimeField(null=True)
    ship_user = fields.ForeignKeyField("models.User", related_name="sn_ships", null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "sn_codes"

class Shipment(models.Model):
    """物流记录"""
    id = fields.IntField(pk=True)
    order = fields.ForeignKeyField("models.Order", related_name="shipments")
    carrier_code = fields.CharField(max_length=30, null=True)
    carrier_name = fields.CharField(max_length=50, null=True)
    tracking_no = fields.CharField(max_length=50, null=True)
    status = fields.CharField(max_length=20, default="pending")  # pending/shipped/in_transit/signed/problem
    status_text = fields.CharField(max_length=50, default="待发货")
    last_tracking_info = fields.TextField(null=True)
    phone = fields.CharField(max_length=20, null=True)  # 顺丰/中通需要手机号后四位
    kd100_subscribed = fields.BooleanField(default=False)
    sn_code = fields.TextField(null=True)  # SN码
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "shipments"

# ==================== Pydantic 模型 ====================
class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class UserCreate(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    role: str = "user"
    permissions: List[str] = []

class WarehouseCreate(BaseModel):
    name: str
    is_default: bool = False

class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    is_default: Optional[bool] = None

class LocationCreate(BaseModel):
    code: str
    name: Optional[str] = None

class LocationUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None

class ProductCreate(BaseModel):
    sku: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    retail_price: Decimal = Decimal("0")
    cost_price: Decimal = Decimal("0")
    unit: str = "个"

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    retail_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    unit: Optional[str] = None

class CustomerCreate(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class RestockRequest(BaseModel):
    warehouse_id: int
    product_id: int
    location_id: int  # 必填：仓位ID
    quantity: int
    cost_price: Optional[Decimal] = None
    remark: Optional[str] = None
    sn_codes: Optional[List[str]] = None

class OrderItemRequest(BaseModel):
    product_id: int
    quantity: int
    unit_price: Decimal
    warehouse_id: Optional[int] = None  # 商品级别的仓库（一单多仓）
    location_id: Optional[int] = None   # 商品级别的仓位（一单多仓）
    rebate_amount: Optional[Decimal] = None  # 该行使用的返利金额

class SalespersonCreate(BaseModel):
    name: str
    phone: Optional[str] = None

class SalespersonUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None

class OrderCreate(BaseModel):
    order_type: str  # CASH, CREDIT, CONSIGN_OUT, CONSIGN_SETTLE, RETURN
    customer_id: Optional[int] = None
    salesperson_id: Optional[int] = None
    warehouse_id: Optional[int] = None
    location_id: Optional[int] = None  # 退货时指定退货仓位
    related_order_id: Optional[int] = None  # 退货时关联的原始销售订单ID
    refunded: Optional[bool] = False  # 退货时：是否已退款给客户
    use_credit: Optional[bool] = False  # 现款销售时：是否使用在账资金
    payment_method: Optional[str] = None  # 现款销售时的收款方式
    items: List[OrderItemRequest]
    remark: Optional[str] = None
    rebate_amount: Optional[Decimal] = None  # 返利总额（前端汇总）

class RebateChargeRequest(BaseModel):
    target_type: str  # customer / supplier
    target_id: int
    amount: Decimal
    remark: Optional[str] = None

class PaymentCreate(BaseModel):
    customer_id: int
    amount: Decimal
    order_ids: List[int]  # 要核销的订单ID列表
    payment_method: str = "cash"
    remark: Optional[str] = None

class StockAdjustRequest(BaseModel):
    warehouse_id: int
    product_id: int
    new_quantity: int
    remark: Optional[str] = None

class StockTransferRequest(BaseModel):
    product_id: int
    from_warehouse_id: int
    from_location_id: int
    to_warehouse_id: int
    to_location_id: int
    quantity: int
    remark: Optional[str] = None

class ConsignmentReturnItem(BaseModel):
    product_id: int
    quantity: int
    warehouse_id: int
    location_id: int

class ConsignmentReturnRequest(BaseModel):
    customer_id: int
    items: List[ConsignmentReturnItem]

class SupplierRequest(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    tax_id: Optional[str] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    address: Optional[str] = None

class PurchaseOrderItemRequest(BaseModel):
    product_id: int
    quantity: int
    tax_inclusive_price: Decimal
    tax_rate: Decimal = Decimal("0.13")
    target_warehouse_id: Optional[int] = None
    target_location_id: Optional[int] = None
    rebate_amount: Optional[Decimal] = None  # 该行使用的返利金额

class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    target_warehouse_id: Optional[int] = None
    target_location_id: Optional[int] = None
    remark: Optional[str] = None
    items: List[PurchaseOrderItemRequest]
    rebate_amount: Optional[Decimal] = None  # 返利总额

class ReceiveItemRequest(BaseModel):
    item_id: int
    receive_quantity: int
    warehouse_id: Optional[int] = None
    location_id: Optional[int] = None
    sn_codes: Optional[List[str]] = None

class ReceiveRequest(BaseModel):
    items: List[ReceiveItemRequest]

class ShipmentUpdate(BaseModel):
    carrier_code: str
    carrier_name: str
    tracking_no: Optional[str] = None
    phone: Optional[str] = None
    sn_code: Optional[str] = None
    sn_codes: Optional[List[str]] = None

class SNCodeUpdate(BaseModel):
    sn_code: Optional[str] = None
    sn_codes: Optional[List[str]] = None

class SnConfigCreate(BaseModel):
    warehouse_id: int
    brand: str

CARRIER_LIST = [
    {"code": "self_pickup", "name": "上门自提"},
    {"code": "shunfeng", "name": "顺丰速运"},
    {"code": "yuantong", "name": "圆通速递"},
    {"code": "zhongtong", "name": "中通快递"},
    {"code": "yunda", "name": "韵达快递"},
    {"code": "shentong", "name": "申通快递"},
    {"code": "ems", "name": "EMS"},
    {"code": "jd", "name": "京东物流"},
    {"code": "jtexpress", "name": "极兔速递"},
    {"code": "debangkuaidi", "name": "德邦快递"},
    {"code": "youzhengguonei", "name": "中国邮政"},
]

# 需要手机号才能查询的快递公司
PHONE_REQUIRED_CARRIERS = {"shunfeng", "shunfengkuaiyun", "zhongtong"}

KD100_STATE_MAP = {
    "0": ("in_transit", "在途中"),
    "1": ("shipped", "已揽收"),
    "2": ("problem", "疑难件"),
    "3": ("signed", "已签收"),
    "4": ("problem", "退签"),
    "5": ("in_transit", "派送中"),
    "6": ("problem", "退回"),
    "7": ("in_transit", "转投"),
    "8": ("in_transit", "清关中"),
    "14": ("problem", "拒签"),
}

def parse_kd100_state(state_val) -> tuple:
    """解析快递100状态码，支持简单码(3)和详细码(301)"""
    s = str(state_val)
    # 先精确匹配
    if s in KD100_STATE_MAP:
        return KD100_STATE_MAP[s]
    # 详细码取首位匹配（如 301→3, 501→5）
    if len(s) >= 2 and s[0] in KD100_STATE_MAP:
        return KD100_STATE_MAP[s[0]]
    return ("in_transit", "在途中")

# ==================== JWT 工具 ====================
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="未授权")
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token无效或已过期")
    user = await User.filter(id=payload.get("user_id"), is_active=True).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

def require_permission(*permissions):
    """要求用户拥有指定权限之一（多个参数为 OR 关系）"""
    async def checker(user: User = Depends(get_current_user)):
        if user.role == "admin":
            return user
        user_perms = user.permissions or []
        if any(p in user_perms for p in permissions):
            return user
        raise HTTPException(status_code=403, detail=f"缺少权限: {permissions[0]}")
    return checker

# ==================== 工具函数 ====================
def generate_order_no(prefix: str = "ORD"):
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(2).upper()}"

async def log_operation(user, action, target_type, target_id=None, detail=None):
    await OperationLog.create(action=action, target_type=target_type, target_id=target_id, detail=detail, operator=user)

async def get_or_create_consignment_warehouse(customer_id: int = None):
    """获取或创建客户独立寄售仓"""
    if customer_id:
        wh = await Warehouse.filter(customer_id=customer_id, is_virtual=True).first()
        if not wh:
            customer = await Customer.filter(id=customer_id).first()
            cname = customer.name if customer else str(customer_id)
            wh = await Warehouse.create(
                name=f"__寄售仓_{cname}__", is_virtual=True, is_default=False, customer_id=customer_id
            )
        return wh
    # 兼容旧调用（不应再使用）
    wh = await Warehouse.filter(name=CONSIGNMENT_WAREHOUSE_NAME).first()
    if not wh:
        wh = await Warehouse.create(name=CONSIGNMENT_WAREHOUSE_NAME, is_virtual=True, is_default=False)
    return wh

async def get_product_total_stock(product_id: int, exclude_virtual: bool = False) -> int:
    """获取商品总库存"""
    query = WarehouseStock.filter(product_id=product_id)
    if exclude_virtual:
        query = query.filter(warehouse__is_virtual=False)
    result = await query.annotate(total=Sum("quantity")).values("total")
    return result[0]["total"] or 0 if result else 0

async def calculate_inventory_age(weighted_entry_date) -> int:
    """计算库龄（天数）"""
    if not weighted_entry_date:
        return 0
    return days_between(now(), weighted_entry_date)

async def update_weighted_entry_date(warehouse_id: int, product_id: int, add_qty: int, cost_price: Decimal = None, location_id: int = None):
    """更新加权入库日期和加权成本"""
    stock = await WarehouseStock.filter(warehouse_id=warehouse_id, product_id=product_id, location_id=location_id).first()
    product = await Product.filter(id=product_id).first()
    
    if not stock:
        stock = await WarehouseStock.create(
            warehouse_id=warehouse_id, 
            product_id=product_id,
            location_id=location_id,
            quantity=0,
            weighted_cost=cost_price or (product.cost_price if product else Decimal("0")),
            weighted_entry_date=now()
        )
    
    old_qty = stock.quantity
    old_date = to_naive(stock.weighted_entry_date) or now()
    old_cost = float(stock.weighted_cost or 0)
    new_cost = float(cost_price) if cost_price else old_cost
    
    if old_qty + add_qty > 0:
        # 加权计算新的入库日期
        old_days = days_between(now(), old_date) if old_date else 0
        new_days = (old_qty * old_days + add_qty * 0) / (old_qty + add_qty)
        stock.weighted_entry_date = now() - timedelta(days=new_days)
        
        # 加权计算新的成本 (只有入库时才更新成本)
        if add_qty > 0 and cost_price:
            weighted_cost = (old_qty * old_cost + add_qty * new_cost) / (old_qty + add_qty)
            stock.weighted_cost = Decimal(str(round(weighted_cost, 2)))
    else:
        stock.weighted_entry_date = now()
        if cost_price:
            stock.weighted_cost = cost_price
    
    stock.quantity = old_qty + add_qty
    await stock.save()
    return stock

async def get_product_weighted_cost(product_id: int) -> Decimal:
    """获取商品的加权平均成本（所有仓库）"""
    stocks = await WarehouseStock.filter(product_id=product_id, quantity__gt=0).all()
    total_qty = sum(s.quantity for s in stocks)
    if total_qty <= 0:
        product = await Product.filter(id=product_id).first()
        return product.cost_price if product else Decimal("0")
    
    total_cost = sum(s.quantity * float(s.weighted_cost or 0) for s in stocks)
    return Decimal(str(round(total_cost / total_qty, 2)))

# ==================== SN码辅助函数 ====================
async def check_sn_required(warehouse_id: int, product_id: int) -> bool:
    """检查指定仓库+商品是否需要SN码管理"""
    product = await Product.filter(id=product_id).first()
    if not product or not product.brand:
        return False
    return await SnConfig.filter(warehouse_id=warehouse_id, brand=product.brand, is_active=True).exists()

async def validate_and_add_sn_codes(sn_codes: List[str], warehouse_id: int, product_id: int,
                                     location_id: int, quantity: int, entry_type: str,
                                     entry_cost: Decimal, user, reference_id: int = None):
    """验证并添加SN码到池中"""
    if len(sn_codes) != quantity:
        raise HTTPException(status_code=400, detail=f"SN码数量({len(sn_codes)})与入库数量({quantity})不匹配")
    # 检查重复
    seen = set()
    for sn in sn_codes:
        if sn in seen:
            raise HTTPException(status_code=400, detail=f"SN码重复: {sn}")
        seen.add(sn)
    # 检查全局唯一
    existing = await SnCode.filter(sn_code__in=sn_codes).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"SN码已存在: {existing.sn_code}")
    # 批量创建
    for sn in sn_codes:
        await SnCode.create(
            sn_code=sn, warehouse_id=warehouse_id, product_id=product_id,
            location_id=location_id, status="in_stock", entry_type=entry_type,
            entry_reference_id=reference_id, entry_cost=entry_cost,
            entry_date=now(), entry_user=user
        )

async def validate_and_consume_sn_codes(sn_codes: List[str], shipment, user):
    """验证并消费SN码（发货扣减）"""
    for sn in sn_codes:
        sn_obj = await SnCode.filter(sn_code=sn, status="in_stock").first()
        if not sn_obj:
            raise HTTPException(status_code=400, detail=f"SN码不可用(不存在或已发货): {sn}")
        sn_obj.status = "shipped"
        sn_obj.shipment = shipment
        sn_obj.ship_date = now()
        sn_obj.ship_user = user
        await sn_obj.save()

# ==================== 数据库初始化 ====================
async def init_db():
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": [__name__]}
    )
    await Tortoise.generate_schemas()

    # 启用 WAL 模式（并发读写不阻塞）和外键约束 — 通过原生 sqlite3 设置
    db_path = get_db_path()
    if db_path:
        try:
            _conn = sqlite3.connect(db_path)
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA foreign_keys=ON")
            _conn.close()
            print("[OK] SQLite WAL模式 + 外键约束已启用")
        except Exception as e:
            print(f"[WARN] PRAGMA设置: {e}")

    # 数据库迁移：给已有的 orders 表添加 salesperson_id 列
    conn = Tortoise.get_connection("default")
    try:
        await conn.execute_query("SELECT salesperson_id FROM orders LIMIT 1")
    except Exception:
        try:
            await conn.execute_script(
                "ALTER TABLE orders ADD COLUMN salesperson_id INTEGER REFERENCES salespersons(id)"
            )
            print("[OK] 已为 orders 表添加 salesperson_id 列")
        except Exception:
            pass

    # 数据库迁移：给已有的 shipments 表添加 sn_code 列
    try:
        await conn.execute_query("SELECT sn_code FROM shipments LIMIT 1")
    except Exception:
        try:
            await conn.execute_script("ALTER TABLE shipments ADD COLUMN sn_code TEXT")
            print("[OK] 已为 shipments 表添加 sn_code 列")
        except Exception:
            pass

    # 数据库迁移：payments 表添加新列
    pay_migration_cols = {
        "source": 'ALTER TABLE "payments" ADD COLUMN "source" VARCHAR(20) DEFAULT \'CREDIT\'',
        "is_confirmed": 'ALTER TABLE "payments" ADD COLUMN "is_confirmed" INT DEFAULT 0',
        "confirmed_by_id": 'ALTER TABLE "payments" ADD COLUMN "confirmed_by_id" INTEGER REFERENCES users(id)',
        "confirmed_at": 'ALTER TABLE "payments" ADD COLUMN "confirmed_at" TIMESTAMP',
        "order_id": 'ALTER TABLE "payments" ADD COLUMN "order_id" INTEGER REFERENCES orders(id)',
    }
    try:
        pay_cols_result = await conn.execute_query("PRAGMA table_info('payments')")
        pay_col_names = [row[1] if hasattr(row, '__getitem__') else '' for row in (pay_cols_result[1] if pay_cols_result else [])]
        for col_name, sql in pay_migration_cols.items():
            if col_name not in pay_col_names:
                try:
                    await conn.execute_script(sql)
                    print(f"[OK] payments 表已添加 {col_name} 列")
                except Exception:
                    pass
    except Exception as e:
        print(f"[WARN] payments迁移: {e}")

    # 初始化默认收款方式
    if not await PaymentMethod.exists():
        defaults = [
            ("cash", "现金", 1),
            ("bank_public", "对公转账", 2),
            ("bank_private", "对私转账", 3),
            ("wechat", "微信", 4),
            ("alipay", "支付宝", 5),
        ]
        for code, name, sort in defaults:
            await PaymentMethod.create(code=code, name=name, sort_order=sort)
        print("[OK] 默认收款方式已初始化")

    # 创建默认管理员
    admin = await User.filter(username="admin").first()
    if not admin:
        await User.create(
            username="admin",
            password_hash=pbkdf2_sha256.hash("admin123"),
            display_name="系统管理员",
            role="admin",
            permissions=["dashboard", "sales", "stock_view", "stock_edit", "finance", "logs", "admin", "purchase", "purchase_pay", "purchase_receive", "purchase_approve"]
        )
        print("[OK] 默认管理员已创建: admin / admin123")
    
    # 创建默认仓库
    default_wh = await Warehouse.filter(is_default=True).first()
    if not default_wh:
        await Warehouse.create(name="默认仓库", is_default=True)
        print("[OK] 默认仓库已创建")
    
    # 迁移：warehouses 表添加 customer_id 列（独立寄售仓）
    try:
        wh_cols = await conn.execute_query("PRAGMA table_info('warehouses')")
        wh_col_names = [row[1] if hasattr(row, '__getitem__') else '' for row in (wh_cols[1] if wh_cols else [])]
        if "customer_id" not in wh_col_names:
            await conn.execute_script('ALTER TABLE "warehouses" ADD COLUMN "customer_id" INTEGER')
            print("[OK] warehouses 表已添加 customer_id 列")
    except Exception as e:
        print(f"[WARN] warehouses customer_id迁移: {e}")

    # 迁移：将共享寄售仓库存拆分到各客户独立仓
    old_shared_wh = await Warehouse.filter(name=CONSIGNMENT_WAREHOUSE_NAME, is_virtual=True, customer_id=None).first()
    if not old_shared_wh:
        old_shared_wh = await Warehouse.filter(name=CONSIGNMENT_WAREHOUSE_NAME, is_virtual=True).first()
        if old_shared_wh and old_shared_wh.customer_id:
            old_shared_wh = None  # 已迁移过
    if old_shared_wh:
        shared_stocks = await WarehouseStock.filter(warehouse_id=old_shared_wh.id, quantity__gt=0).all()
        if shared_stocks:
            # 有共享库存需要迁移
            consign_outs = await Order.filter(order_type="CONSIGN_OUT").all()
            cust_ids = list(set(o.customer_id for o in consign_outs if o.customer_id))
            migrated = 0
            for cid in cust_ids:
                out_orders = await Order.filter(customer_id=cid, order_type="CONSIGN_OUT")
                settle_orders = await Order.filter(customer_id=cid, order_type="CONSIGN_SETTLE")
                product_qty = {}
                for order in out_orders:
                    items = await OrderItem.filter(order_id=order.id)
                    for item in items:
                        product_qty[item.product_id] = product_qty.get(item.product_id, 0) + item.quantity
                for order in settle_orders:
                    items = await OrderItem.filter(order_id=order.id)
                    for item in items:
                        product_qty[item.product_id] = product_qty.get(item.product_id, 0) - abs(item.quantity)
                return_logs = await StockLog.filter(
                    change_type="CONSIGN_RETURN", reference_type="CONSIGN_RETURN",
                    reference_id=cid, warehouse=old_shared_wh, quantity__lt=0
                )
                for log in return_logs:
                    product_qty[log.product_id] = product_qty.get(log.product_id, 0) - abs(log.quantity)
                cust_wh = await get_or_create_consignment_warehouse(cid)
                for pid, qty in product_qty.items():
                    if qty > 0:
                        existing = await WarehouseStock.filter(warehouse_id=cust_wh.id, product_id=pid).first()
                        if not existing:
                            await WarehouseStock.create(warehouse_id=cust_wh.id, product_id=pid, quantity=qty)
                        else:
                            existing.quantity = qty
                            await existing.save()
                        migrated += 1
            # 清空旧共享仓库存并停用
            await WarehouseStock.filter(warehouse_id=old_shared_wh.id).delete()
            old_shared_wh.is_active = False
            await old_shared_wh.save()
            if migrated > 0:
                print(f"[OK] 已将共享寄售仓库存迁移到 {len(cust_ids)} 个客户独立仓（{migrated}条记录）")

    # 迁移：移除 shipments 表 order_id 唯一约束（支持一单多件）
    try:
        res = await conn.execute_query("SELECT sql FROM sqlite_master WHERE type='table' AND name='shipments'")
        if res and res[1]:
            # sqlite3.Row 支持下标访问
            original_ddl = res[1][0][0] if hasattr(res[1][0], '__getitem__') else str(res[1][0])
            if original_ddl and "UNIQUE" in original_ddl:
                # 列顺序必须与原表一致（order_id 在最后）
                await conn.execute_script("""
                    DROP TABLE IF EXISTS "shipments_new";
                    CREATE TABLE "shipments_new" (
                        "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                        "carrier_code" VARCHAR(30),
                        "carrier_name" VARCHAR(50),
                        "tracking_no" VARCHAR(50),
                        "status" VARCHAR(20) NOT NULL DEFAULT 'pending',
                        "status_text" VARCHAR(50) NOT NULL DEFAULT '待发货',
                        "last_tracking_info" TEXT,
                        "kd100_subscribed" INT NOT NULL DEFAULT 0,
                        "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        "order_id" INT NOT NULL REFERENCES "orders" ("id") ON DELETE CASCADE
                    );
                    INSERT INTO "shipments_new" SELECT * FROM "shipments";
                    DROP TABLE "shipments";
                    ALTER TABLE "shipments_new" RENAME TO "shipments";
                """)
                print("[OK] 已移除 shipments 表唯一约束，支持一单多件")
    except Exception as e:
        print(f"[WARN] shipments迁移: {e}")

    # 迁移：shipments 表添加 phone 列（顺丰/中通查询需要）
    try:
        cols = await conn.execute_query("PRAGMA table_info('shipments')")
        col_names = [row[1] if hasattr(row, '__getitem__') else '' for row in (cols[1] if cols else [])]
        if "phone" not in col_names:
            await conn.execute_script('ALTER TABLE "shipments" ADD COLUMN "phone" VARCHAR(20)')
            print("[OK] shipments 表已添加 phone 列")
    except Exception as e:
        print(f"[WARN] shipments phone迁移: {e}")

    # 为已有的 CASH/CREDIT/CONSIGN_OUT 订单补建 shipment 记录
    existing_orders = await Order.filter(order_type__in=["CASH", "CREDIT", "CONSIGN_OUT"]).all()
    shipment_created = 0
    for o in existing_orders:
        exists = await Shipment.filter(order_id=o.id).exists()
        if not exists:
            await Shipment.create(order=o)
            shipment_created += 1
    if shipment_created > 0:
        print(f"[OK] 已为 {shipment_created} 个已有订单补建物流记录")

    # 迁移：自动创建采购模块表（suppliers, purchase_orders, purchase_order_items）
    try:
        await conn.execute_query("SELECT id FROM suppliers LIMIT 1")
    except Exception:
        try:
            await conn.execute_script("""
                CREATE TABLE IF NOT EXISTS "suppliers" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    "name" VARCHAR(100) NOT NULL,
                    "contact_person" VARCHAR(50),
                    "phone" VARCHAR(30),
                    "tax_id" VARCHAR(50),
                    "bank_account" VARCHAR(50),
                    "bank_name" VARCHAR(100),
                    "address" TEXT,
                    "is_active" INT NOT NULL DEFAULT 1,
                    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS "purchase_orders" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    "po_no" VARCHAR(30) NOT NULL UNIQUE,
                    "supplier_id" INT NOT NULL REFERENCES "suppliers" ("id") ON DELETE CASCADE,
                    "status" VARCHAR(20) NOT NULL DEFAULT 'pending_review',
                    "total_amount" DECIMAL(12,2) NOT NULL DEFAULT 0,
                    "target_warehouse_id" INT REFERENCES "warehouses" ("id") ON DELETE SET NULL,
                    "target_location_id" INT REFERENCES "locations" ("id") ON DELETE SET NULL,
                    "remark" TEXT,
                    "creator_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
                    "reviewed_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL,
                    "reviewed_at" TIMESTAMP,
                    "paid_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL,
                    "paid_at" TIMESTAMP,
                    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS "purchase_order_items" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    "purchase_order_id" INT NOT NULL REFERENCES "purchase_orders" ("id") ON DELETE CASCADE,
                    "product_id" INT NOT NULL REFERENCES "products" ("id") ON DELETE CASCADE,
                    "quantity" INT NOT NULL,
                    "tax_inclusive_price" DECIMAL(12,2) NOT NULL,
                    "tax_rate" DECIMAL(5,2) NOT NULL DEFAULT 0.13,
                    "tax_exclusive_price" DECIMAL(12,2) NOT NULL,
                    "amount" DECIMAL(12,2) NOT NULL,
                    "received_quantity" INT NOT NULL DEFAULT 0,
                    "target_warehouse_id" INT REFERENCES "warehouses" ("id") ON DELETE SET NULL,
                    "target_location_id" INT REFERENCES "locations" ("id") ON DELETE SET NULL
                );
            """)
            print("[OK] 采购模块表已创建（suppliers, purchase_orders, purchase_order_items）")
        except Exception as e:
            print(f"[WARN] 采购模块表创建: {e}")

    # 迁移：purchase_orders 表添加 reviewed_by_id、reviewed_at 列
    try:
        po_cols = await conn.execute_query("PRAGMA table_info('purchase_orders')")
        po_col_names = [row[1] if hasattr(row, '__getitem__') else '' for row in (po_cols[1] if po_cols else [])]
        if "reviewed_by_id" not in po_col_names:
            await conn.execute_script('ALTER TABLE "purchase_orders" ADD COLUMN "reviewed_by_id" INT REFERENCES "users" ("id") ON DELETE SET NULL')
            print("[OK] purchase_orders 表已添加 reviewed_by_id 列")
        if "reviewed_at" not in po_col_names:
            await conn.execute_script('ALTER TABLE "purchase_orders" ADD COLUMN "reviewed_at" TIMESTAMP')
            print("[OK] purchase_orders 表已添加 reviewed_at 列")
    except Exception as e:
        print(f"[WARN] purchase_orders 审核字段迁移: {e}")

    # 迁移：自动创建凭证模块表（system_settings, vouchers, voucher_entries）
    try:
        await conn.execute_query("SELECT id FROM system_settings LIMIT 1")
    except Exception:
        try:
            await conn.execute_script("""
                CREATE TABLE IF NOT EXISTS "system_settings" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    "key" VARCHAR(100) NOT NULL UNIQUE,
                    "value" TEXT,
                    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS "vouchers" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    "voucher_no" VARCHAR(50) NOT NULL UNIQUE,
                    "voucher_type" VARCHAR(10) NOT NULL,
                    "seq_number" INT NOT NULL,
                    "source_type" VARCHAR(30) NOT NULL,
                    "source_id" INT NOT NULL,
                    "voucher_date" DATE NOT NULL,
                    "company_name" VARCHAR(200),
                    "total_debit" DECIMAL(14,2) NOT NULL DEFAULT 0,
                    "total_credit" DECIMAL(14,2) NOT NULL DEFAULT 0,
                    "tax_rate" DECIMAL(5,2) NOT NULL DEFAULT 0.13,
                    "remark" TEXT,
                    "creator_id" INT REFERENCES "users" ("id") ON DELETE SET NULL,
                    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS "voucher_entries" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    "voucher_id" INT NOT NULL REFERENCES "vouchers" ("id") ON DELETE CASCADE,
                    "seq" INT NOT NULL,
                    "summary" VARCHAR(200) NOT NULL,
                    "account" VARCHAR(200) NOT NULL,
                    "debit_amount" DECIMAL(14,2) NOT NULL DEFAULT 0,
                    "credit_amount" DECIMAL(14,2) NOT NULL DEFAULT 0
                );
            """)
            print("[OK] 凭证模块表已创建（system_settings, vouchers, voucher_entries）")
        except Exception as e:
            print(f"[WARN] 凭证模块表创建: {e}")

    # SN码管理表
    try:
        await conn.execute_query("SELECT id FROM sn_configs LIMIT 1")
    except Exception:
        try:
            await conn.execute_script("""
                CREATE TABLE IF NOT EXISTS "sn_configs" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    "warehouse_id" INT NOT NULL REFERENCES "warehouses" ("id") ON DELETE CASCADE,
                    "brand" VARCHAR(100) NOT NULL,
                    "is_active" INT NOT NULL DEFAULT 1,
                    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE("warehouse_id", "brand")
                );
                CREATE TABLE IF NOT EXISTS "sn_codes" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    "sn_code" VARCHAR(200) NOT NULL UNIQUE,
                    "warehouse_id" INT NOT NULL REFERENCES "warehouses" ("id") ON DELETE CASCADE,
                    "product_id" INT NOT NULL REFERENCES "products" ("id") ON DELETE CASCADE,
                    "location_id" INT REFERENCES "locations" ("id") ON DELETE SET NULL,
                    "status" VARCHAR(20) NOT NULL DEFAULT 'in_stock',
                    "entry_type" VARCHAR(30),
                    "entry_reference_id" INT,
                    "entry_cost" DECIMAL(12,2),
                    "entry_date" TIMESTAMP,
                    "entry_user_id" INT REFERENCES "users" ("id") ON DELETE SET NULL,
                    "shipment_id" INT REFERENCES "shipments" ("id") ON DELETE SET NULL,
                    "ship_date" TIMESTAMP,
                    "ship_user_id" INT REFERENCES "users" ("id") ON DELETE SET NULL,
                    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS "idx_sn_codes_status" ON "sn_codes" ("status");
                CREATE INDEX IF NOT EXISTS "idx_sn_codes_warehouse_product" ON "sn_codes" ("warehouse_id", "product_id");
            """)
            print("[OK] SN码管理表已创建（sn_configs, sn_codes）")
        except Exception as e:
            print(f"[WARN] SN码管理表创建: {e}")

    # 迁移：返利系统 - customers 表添加 rebate_balance 列
    try:
        cust_cols = await conn.execute_query("PRAGMA table_info('customers')")
        cust_col_names = [row[1] if hasattr(row, '__getitem__') else '' for row in (cust_cols[1] if cust_cols else [])]
        if "rebate_balance" not in cust_col_names:
            await conn.execute_script('ALTER TABLE "customers" ADD COLUMN "rebate_balance" DECIMAL(12,2) DEFAULT 0')
            print("[OK] customers 表已添加 rebate_balance 列")
    except Exception as e:
        print(f"[WARN] customers rebate_balance迁移: {e}")

    # 迁移：返利系统 - suppliers 表添加 rebate_balance 列
    try:
        sup_cols = await conn.execute_query("PRAGMA table_info('suppliers')")
        sup_col_names = [row[1] if hasattr(row, '__getitem__') else '' for row in (sup_cols[1] if sup_cols else [])]
        if "rebate_balance" not in sup_col_names:
            await conn.execute_script('ALTER TABLE "suppliers" ADD COLUMN "rebate_balance" DECIMAL(12,2) DEFAULT 0')
            print("[OK] suppliers 表已添加 rebate_balance 列")
    except Exception as e:
        print(f"[WARN] suppliers rebate_balance迁移: {e}")

    # 迁移：返利系统 - orders 表添加 rebate_used 列
    try:
        ord_cols = await conn.execute_query("PRAGMA table_info('orders')")
        ord_col_names = [row[1] if hasattr(row, '__getitem__') else '' for row in (ord_cols[1] if ord_cols else [])]
        if "rebate_used" not in ord_col_names:
            await conn.execute_script('ALTER TABLE "orders" ADD COLUMN "rebate_used" DECIMAL(12,2) DEFAULT 0')
            print("[OK] orders 表已添加 rebate_used 列")
    except Exception as e:
        print(f"[WARN] orders rebate_used迁移: {e}")

    # 迁移：返利系统 - order_items 表添加 rebate_amount 列
    try:
        oi_cols = await conn.execute_query("PRAGMA table_info('order_items')")
        oi_col_names = [row[1] if hasattr(row, '__getitem__') else '' for row in (oi_cols[1] if oi_cols else [])]
        if "rebate_amount" not in oi_col_names:
            await conn.execute_script('ALTER TABLE "order_items" ADD COLUMN "rebate_amount" DECIMAL(12,2) DEFAULT 0')
            print("[OK] order_items 表已添加 rebate_amount 列")
    except Exception as e:
        print(f"[WARN] order_items rebate_amount迁移: {e}")

    # 迁移：返利系统 - purchase_orders 表添加 rebate_used 列
    try:
        po_cols2 = await conn.execute_query("PRAGMA table_info('purchase_orders')")
        po_col_names2 = [row[1] if hasattr(row, '__getitem__') else '' for row in (po_cols2[1] if po_cols2 else [])]
        if "rebate_used" not in po_col_names2:
            await conn.execute_script('ALTER TABLE "purchase_orders" ADD COLUMN "rebate_used" DECIMAL(12,2) DEFAULT 0')
            print("[OK] purchase_orders 表已添加 rebate_used 列")
    except Exception as e:
        print(f"[WARN] purchase_orders rebate_used迁移: {e}")

    # 迁移：返利系统 - purchase_order_items 表添加 rebate_amount 列
    try:
        poi_cols = await conn.execute_query("PRAGMA table_info('purchase_order_items')")
        poi_col_names = [row[1] if hasattr(row, '__getitem__') else '' for row in (poi_cols[1] if poi_cols else [])]
        if "rebate_amount" not in poi_col_names:
            await conn.execute_script('ALTER TABLE "purchase_order_items" ADD COLUMN "rebate_amount" DECIMAL(12,2) DEFAULT 0')
            print("[OK] purchase_order_items 表已添加 rebate_amount 列")
    except Exception as e:
        print(f"[WARN] purchase_order_items rebate_amount迁移: {e}")

    # 返利流水表
    try:
        await conn.execute_query("SELECT id FROM rebate_logs LIMIT 1")
    except Exception:
        try:
            await conn.execute_script("""
                CREATE TABLE IF NOT EXISTS "rebate_logs" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    "target_type" VARCHAR(20) NOT NULL,
                    "target_id" INT NOT NULL,
                    "type" VARCHAR(10) NOT NULL,
                    "amount" DECIMAL(12,2) NOT NULL,
                    "balance_after" DECIMAL(12,2) NOT NULL,
                    "reference_type" VARCHAR(30),
                    "reference_id" INT,
                    "remark" TEXT,
                    "creator_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
                    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
            print("[OK] 返利流水表已创建（rebate_logs）")
        except Exception as e:
            print(f"[WARN] rebate_logs表创建: {e}")

    print("[OK] 数据库初始化完成")

async def close_db():
    await Tortoise.close_connections()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # 启动时做一次备份
    try:
        path = do_backup("startup")
        print(f"[启动备份] {os.path.basename(path)}")
    except Exception as e:
        print(f"[启动备份] 跳过: {e}")
    # 启动每日自动备份定时任务
    backup_task = asyncio.create_task(auto_backup_loop())
    yield
    backup_task.cancel()
    await close_db()

# ==================== FastAPI 应用 ====================
app = FastAPI(title="轻量级ERP系统 v3.4", lifespan=lifespan)
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ==================== 认证 API ====================
_login_attempts = {}  # {ip: [timestamp, ...]}
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 300  # 5分钟内最多5次
_LOGIN_MAX_IPS = 10000  # 最多追踪的IP数量

def _cleanup_login_attempts():
    """清理过期的登录尝试记录，防止内存泄漏"""
    if len(_login_attempts) <= _LOGIN_MAX_IPS:
        return
    now_ts = datetime.now().timestamp()
    expired_ips = [ip for ip, atts in _login_attempts.items()
                   if not atts or now_ts - max(atts) > _LOGIN_WINDOW_SECONDS]
    for ip in expired_ips:
        del _login_attempts[ip]

@app.post("/api/auth/login")
async def login(data: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now_ts = datetime.now().timestamp()
    # 清理过期记录并检查频率
    attempts = _login_attempts.get(client_ip, [])
    attempts = [t for t in attempts if now_ts - t < _LOGIN_WINDOW_SECONDS]
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail=f"登录尝试过于频繁，请{_LOGIN_WINDOW_SECONDS // 60}分钟后再试")
    user = await User.filter(username=data.username, is_active=True).first()
    if not user or not pbkdf2_sha256.verify(data.password, user.password_hash):
        attempts.append(now_ts)
        _login_attempts[client_ip] = attempts
        _cleanup_login_attempts()
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    _login_attempts.pop(client_ip, None)  # 登录成功，清除失败记录
    token = create_access_token({"user_id": user.id, "username": user.username, "role": user.role})
    return {
        "access_token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "permissions": user.permissions or []
        }
    }

@app.get("/api/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "permissions": user.permissions or []
    }

@app.post("/api/auth/change-password")
async def change_password(data: ChangePasswordRequest, user: User = Depends(get_current_user)):
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码长度不能少于6位")
    if not pbkdf2_sha256.verify(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    user.password_hash = pbkdf2_sha256.hash(data.new_password)
    await user.save()
    return {"message": "密码修改成功"}

# ==================== 用户管理 API ====================
@app.get("/api/users")
async def list_users(user: User = Depends(require_permission("admin"))):
    users = await User.all().order_by("id")
    return [{"id": u.id, "username": u.username, "display_name": u.display_name, "role": u.role, "permissions": u.permissions, "is_active": u.is_active} for u in users]

@app.post("/api/users")
async def create_user(data: UserCreate, user: User = Depends(require_permission("admin"))):
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于6位")
    if await User.filter(username=data.username).exists():
        raise HTTPException(status_code=400, detail="用户名已存在")
    new_user = await User.create(
        username=data.username,
        password_hash=pbkdf2_sha256.hash(data.password),
        display_name=data.display_name or data.username,
        role=data.role,
        permissions=data.permissions
    )
    await log_operation(user, "USER_CREATE", "USER", new_user.id,
        f"创建用户 {data.username}，角色 {data.role}")
    return {"id": new_user.id, "message": "创建成功"}

@app.put("/api/users/{user_id}")
async def update_user(user_id: int, data: UserCreate, admin: User = Depends(require_permission("admin"))):
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.display_name = data.display_name
    user.role = data.role
    user.permissions = data.permissions
    if data.password:
        user.password_hash = pbkdf2_sha256.hash(data.password)
    await user.save()
    return {"message": "更新成功"}

@app.post("/api/users/{user_id}/toggle")
async def toggle_user(user_id: int, admin: User = Depends(require_permission("admin"))):
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    user.is_active = not user.is_active
    await user.save()
    action_text = "启用" if user.is_active else "禁用"
    await log_operation(admin, "USER_TOGGLE", "USER", user.id,
        f"{action_text}用户 {user.username}")
    return {"message": "状态更新成功", "is_active": user.is_active}

# ==================== 仓库管理 API ====================
@app.get("/api/warehouses")
async def list_warehouses(include_virtual: bool = False, user: User = Depends(get_current_user)):
    query = Warehouse.filter(is_active=True)
    if not include_virtual:
        query = query.filter(is_virtual=False)
    warehouses = await query.order_by("-is_default", "name")
    return [{"id": w.id, "name": w.name, "is_default": w.is_default, "is_virtual": w.is_virtual, "customer_id": w.customer_id} for w in warehouses]

@app.post("/api/warehouses")
async def create_warehouse(data: WarehouseCreate, user: User = Depends(require_permission("stock_edit"))):
    if await Warehouse.filter(name=data.name).exists():
        raise HTTPException(status_code=400, detail="仓库名已存在")
    if data.is_default:
        await Warehouse.filter(is_default=True).update(is_default=False)
    wh = await Warehouse.create(name=data.name, is_default=data.is_default)
    return {"id": wh.id, "message": "创建成功"}

@app.put("/api/warehouses/{warehouse_id}")
async def update_warehouse(warehouse_id: int, data: WarehouseUpdate, user: User = Depends(require_permission("stock_edit"))):
    wh = await Warehouse.filter(id=warehouse_id).first()
    if not wh:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if wh.is_virtual:
        raise HTTPException(status_code=400, detail="不能修改系统仓库")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if "name" in update_data:
        if await Warehouse.filter(name=update_data["name"]).exclude(id=warehouse_id).exists():
            raise HTTPException(status_code=400, detail="仓库名已存在")
    if update_data.get("is_default"):
        await Warehouse.filter(is_default=True).update(is_default=False)
    if update_data:
        await Warehouse.filter(id=warehouse_id).update(**update_data)
    return {"message": "更新成功"}

@app.delete("/api/warehouses/{warehouse_id}")
async def delete_warehouse(warehouse_id: int, user: User = Depends(require_permission("stock_edit"))):
    wh = await Warehouse.filter(id=warehouse_id).first()
    if not wh:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if wh.is_default:
        raise HTTPException(status_code=400, detail="不能删除默认仓库")
    if wh.is_virtual:
        raise HTTPException(status_code=400, detail="不能删除系统仓库")
    # 检查是否有库存
    has_stock = await WarehouseStock.filter(warehouse_id=warehouse_id, quantity__gt=0).exists()
    if has_stock:
        raise HTTPException(status_code=400, detail="仓库有库存，无法删除")
    wh.is_active = False
    await wh.save()
    return {"message": "删除成功"}

# ==================== 仓位管理 API ====================
@app.get("/api/locations")
async def list_locations(user: User = Depends(get_current_user)):
    locations = await Location.filter(is_active=True).order_by("code")
    return [{"id": loc.id, "code": loc.code, "name": loc.name} for loc in locations]

@app.post("/api/locations")
async def create_location(data: LocationCreate, user: User = Depends(require_permission("stock_edit"))):
    if await Location.filter(code=data.code).exists():
        raise HTTPException(status_code=400, detail="仓位编号已存在")
    loc = await Location.create(code=data.code, name=data.name)
    return {"id": loc.id, "message": "创建成功"}

@app.put("/api/locations/{location_id}")
async def update_location(location_id: int, data: LocationUpdate, user: User = Depends(require_permission("stock_edit"))):
    loc = await Location.filter(id=location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="仓位不存在")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if "code" in update_data:
        if await Location.filter(code=update_data["code"]).exclude(id=location_id).exists():
            raise HTTPException(status_code=400, detail="仓位编号已存在")
    if update_data:
        await Location.filter(id=location_id).update(**update_data)
    return {"message": "更新成功"}

@app.delete("/api/locations/{location_id}")
async def delete_location(location_id: int, user: User = Depends(require_permission("stock_edit"))):
    loc = await Location.filter(id=location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="仓位不存在")
    # 检查是否有库存
    has_stock = await WarehouseStock.filter(location_id=location_id, quantity__gt=0).exists()
    if has_stock:
        raise HTTPException(status_code=400, detail="仓位有库存，无法删除")
    loc.is_active = False
    await loc.save()
    return {"message": "删除成功"}

# ==================== 商品管理 API ====================
@app.get("/api/products")
async def list_products(keyword: Optional[str] = None, category: Optional[str] = None, warehouse_id: Optional[int] = None, user: User = Depends(get_current_user)):
    query = Product.filter(is_active=True)
    if keyword:
        for word in keyword.split():
            query = query.filter(Q(sku__icontains=word) | Q(name__icontains=word) | Q(brand__icontains=word) | Q(category__icontains=word))
    if category:
        query = query.filter(category=category)
    products = await query.order_by("-updated_at")
    
    result = []
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])
    
    for p in products:
        # 获取各仓库库存（包含仓位信息，含虚拟仓以支持寄售结算）
        stock_query = WarehouseStock.filter(product_id=p.id)
        if warehouse_id:
            stock_query = stock_query.filter(warehouse_id=warehouse_id)
        stocks = await stock_query.select_related("warehouse", "location")
        # total_qty 只统计实体仓库存（用于显示）
        total_qty = sum(s.quantity for s in stocks if not s.warehouse.is_virtual)
        
        # 计算库龄（取最早的加权日期）
        oldest_date = None
        for s in stocks:
            if s.quantity > 0 and s.weighted_entry_date:
                s_date = to_naive(s.weighted_entry_date)
                if oldest_date is None or s_date < oldest_date:
                    oldest_date = s_date
        
        age_days = days_between(now(), oldest_date) if oldest_date else 0
        
        # 构建库存明细（包含仓位）
        stock_details = []
        for s in stocks:
            if s.quantity > 0:
                stock_details.append({
                    "warehouse_id": s.warehouse_id,
                    "warehouse_name": s.warehouse.name,
                    "location_id": s.location_id,
                    "location_code": s.location.code if s.location else None,
                    "quantity": s.quantity,
                    "is_virtual": s.warehouse.is_virtual
                })
        
        item = {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "brand": p.brand,
            "category": p.category,
            "retail_price": float(p.retail_price),
            "unit": p.unit,
            "total_stock": total_qty,
            "age_days": age_days,
            "stocks": stock_details
        }
        if has_finance:
            item["cost_price"] = float(p.cost_price)
        result.append(item)
    
    return result

# 固定路径路由必须在 {product_id} 动态路由之前定义
@app.get("/api/products/categories/list")
async def list_categories(user: User = Depends(get_current_user)):
    products = await Product.filter(is_active=True, category__isnull=False).distinct().values_list("category", flat=True)
    return list(set(p for p in products if p))

@app.get("/api/products/export")
async def export_products(user: User = Depends(require_permission("stock_view"))):
    """导出商品Excel"""
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas未安装")
    
    products = await Product.filter(is_active=True)
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])
    
    data = []
    for p in products:
        stocks = await WarehouseStock.filter(product_id=p.id, quantity__gt=0).select_related("warehouse")
        total_qty = sum(s.quantity for s in stocks if not s.warehouse.is_virtual)
        
        row = {
            "SKU": p.sku, "名称": p.name, "品牌": p.brand or "",
            "分类": p.category or "", "单位": p.unit,
            "零售价": float(p.retail_price), "库存": total_qty
        }
        if has_finance:
            row["成本价"] = float(p.cost_price)
        data.append(row)
    
    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=products.xlsx"}
    )

@app.get("/api/products/template")
async def download_template(user: User = Depends(require_permission("stock_edit"))):
    """下载导入模板"""
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas未安装")
    
    df = pd.DataFrame({
        "SKU": ["SKU001", "SKU002"], 
        "名称": ["示例商品1", "示例商品2"], 
        "品牌": ["品牌A", "品牌B"],
        "分类": ["分类1", "分类1"], 
        "单位": ["个", "件"], 
        "零售价": [99.00, 150.00], 
        "成本价": [50.00, 80.00],
        "仓库": ["实体仓库", "实体仓库"],
        "仓位": ["A-01", "A-02"],
        "数量": [10, 20],
        "备注": ["批次1", "批次2"]
    })
    output = io.BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=import_template.xlsx"}
    )

@app.post("/api/products/import/preview")
async def preview_import(file: UploadFile = File(...), user: User = Depends(require_permission("stock_edit"))):
    """预览导入内容，不实际入库"""
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas未安装")

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="请上传Excel文件")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB限制
        raise HTTPException(status_code=400, detail="文件过大，最大支持10MB")
    df = pd.read_excel(io.BytesIO(content))

    required_cols = ["SKU", "名称"]
    for col in required_cols:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"缺少必要列: {col}")

    preview_items = []
    warnings = []

    for idx, row in df.iterrows():
        sku = str(row["SKU"]).strip() if pd.notna(row.get("SKU")) else ""
        if not sku:
            continue

        name = str(row.get("名称", "")) if pd.notna(row.get("名称")) else ""
        brand = str(row.get("品牌", "")) if pd.notna(row.get("品牌")) else ""
        category = str(row.get("分类", "")) if pd.notna(row.get("分类")) else ""
        warehouse_name = str(row.get("仓库", "")).strip() if pd.notna(row.get("仓库")) else ""
        location_code = str(row.get("仓位", "")).strip() if pd.notna(row.get("仓位")) else ""
        quantity = int(row.get("数量", 0)) if pd.notna(row.get("数量")) and row.get("数量", 0) > 0 else 0
        retail_price = float(row.get("零售价", 0)) if pd.notna(row.get("零售价")) else 0
        cost_price = float(row.get("成本价", 0)) if pd.notna(row.get("成本价")) else 0
        remark = str(row.get("备注", "")) if pd.notna(row.get("备注")) else ""

        # 检查是否有效
        status = "valid"
        status_msg = ""
        current_stock = 0  # 当前库存
        after_stock = 0    # 导入后库存

        if not warehouse_name or quantity <= 0:
            status = "skip"
            status_msg = "缺少仓库或数量"
        elif not location_code:
            status = "skip"
            status_msg = "缺少仓位"
        else:
            # 检查SKU是否已存在
            existing = await Product.filter(sku=sku).first()
            if existing:
                status_msg = "更新商品"
                # 检查是否有现有库存
                wh = await Warehouse.filter(name=warehouse_name).first()
                loc = await Location.filter(code=location_code).first()
                if wh and loc:
                    existing_stock = await WarehouseStock.filter(
                        warehouse_id=wh.id,
                        product_id=existing.id,
                        location_id=loc.id
                    ).first()
                    if existing_stock and existing_stock.quantity > 0:
                        current_stock = existing_stock.quantity
                        after_stock = current_stock + quantity
                        status_msg = f"叠加库存 ({current_stock}→{after_stock})"
                    else:
                        after_stock = quantity
                else:
                    after_stock = quantity
            else:
                status_msg = "新建商品"
                after_stock = quantity

            # 检查仓库是否存在
            wh = await Warehouse.filter(name=warehouse_name).first()
            if not wh:
                status_msg += "，新建仓库"

            # 检查仓位是否存在
            loc = await Location.filter(code=location_code).first()
            if not loc:
                status_msg += "，新建仓位"

        preview_items.append({
            "row": idx + 2,  # Excel行号从2开始（1是表头）
            "sku": sku,
            "name": name,
            "brand": brand,
            "category": category,
            "warehouse": warehouse_name,
            "location": location_code,
            "quantity": quantity,
            "current_stock": current_stock,
            "after_stock": after_stock,
            "retail_price": retail_price,
            "cost_price": cost_price,
            "remark": remark,
            "status": status,
            "status_msg": status_msg
        })

    valid_count = len([i for i in preview_items if i["status"] == "valid"])
    skip_count = len([i for i in preview_items if i["status"] == "skip"])

    return {
        "total": len(preview_items),
        "valid_count": valid_count,
        "skip_count": skip_count,
        "items": preview_items
    }

@app.post("/api/products/import")
async def import_products(file: UploadFile = File(...), user: User = Depends(require_permission("stock_edit"))):
    """导入商品Excel（支持自动入库）"""
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas未安装")
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="请上传Excel文件")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大，最大支持10MB")
    df = pd.read_excel(io.BytesIO(content))
    
    required_cols = ["SKU", "名称"]
    for col in required_cols:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"缺少必要列: {col}")
    
    created, updated, stocked, skipped = 0, 0, 0, 0
    errors = []
    
    async with transactions.in_transaction():
        for idx, row in df.iterrows():
            try:
                sku = str(row["SKU"]).strip()
                if not sku:
                    continue
                
                # 先检查是否提供了仓库和数量（方案1：只导入有库存的商品）
                warehouse_name = str(row.get("仓库", "")).strip() if pd.notna(row.get("仓库")) else None
                quantity = int(row.get("数量", 0)) if pd.notna(row.get("数量")) and row.get("数量", 0) > 0 else 0
                
                if not warehouse_name or quantity <= 0:
                    skipped += 1
                    errors.append(f"第{idx+2}行: {sku} - 缺少仓库或数量，已跳过（需要同时提供仓库和数量才能导入）")
                    continue
                
                # 商品数据
                data = {
                    "name": str(row.get("名称", "")),
                    "brand": str(row.get("品牌", "")) if pd.notna(row.get("品牌")) else None,
                    "category": str(row.get("分类", "")) if pd.notna(row.get("分类")) else None,
                    "unit": str(row.get("单位", "个")) if pd.notna(row.get("单位")) else "个",
                    "retail_price": float(row.get("零售价", 0)) if pd.notna(row.get("零售价")) else 0,
                    "cost_price": float(row.get("成本价", 0)) if pd.notna(row.get("成本价")) else 0
                }
                
                # 创建或更新商品
                existing = await Product.filter(sku=sku).first()
                if existing:
                    await Product.filter(id=existing.id).update(**data)
                    product = existing
                    updated += 1
                else:
                    product = await Product.create(sku=sku, **data)
                    created += 1
                
                # 处理库存入库
                if warehouse_name and quantity > 0:
                    # 查找或创建仓库
                    warehouse = await Warehouse.filter(name=warehouse_name).first()
                    if not warehouse:
                        warehouse = await Warehouse.create(name=warehouse_name, is_virtual=False, is_default=False, is_active=True)
                    
                    # 查找或创建仓位
                    location_code = str(row.get("仓位", "")).strip() if pd.notna(row.get("仓位")) else None
                    location = None
                    if location_code:
                        location = await Location.filter(code=location_code).first()
                        if not location:
                            location = await Location.create(code=location_code, name=location_code, is_active=True)
                    
                    if not location:
                        errors.append(f"第{idx+2}行: {sku} - 未指定仓位，跳过入库")
                        continue
                    
                    # 入库操作 - 使用Excel成本价，如果为0则使用商品默认成本价
                    import_cost = Decimal(str(data["cost_price"])) if data["cost_price"] > 0 else Decimal(str(float(product.cost_price or 0)))

                    # 更新库存
                    stock = await WarehouseStock.filter(
                        warehouse_id=warehouse.id,
                        product_id=product.id,
                        location_id=location.id
                    ).first()

                    if stock:
                        # 计算加权平均成本和库龄
                        old_qty = stock.quantity
                        old_cost = float(stock.weighted_cost or 0)
                        old_date = to_naive(stock.weighted_entry_date) or now()
                        new_qty = old_qty + quantity

                        # 加权平均成本
                        new_cost = ((old_qty * old_cost) + (quantity * float(import_cost))) / new_qty if new_qty > 0 else float(import_cost)

                        # 加权库龄：老库存的天数 * 老数量 + 新库存0天 * 新数量
                        old_days = days_between(now(), old_date) if old_date else 0
                        new_days = (old_qty * old_days + quantity * 0) / new_qty if new_qty > 0 else 0
                        new_entry_date = now() - timedelta(days=new_days)

                        await WarehouseStock.filter(id=stock.id).update(
                            quantity=new_qty,
                            weighted_cost=Decimal(str(round(new_cost, 2))),
                            weighted_entry_date=new_entry_date
                        )
                    else:
                        await WarehouseStock.create(
                            warehouse_id=warehouse.id,
                            product_id=product.id,
                            location_id=location.id,
                            quantity=quantity,
                            weighted_cost=import_cost,
                            weighted_entry_date=now()
                        )
                    
                    # 记录入库日志
                    remark = str(row.get("备注", "Excel批量导入")) if pd.notna(row.get("备注")) else "Excel批量导入"
                    # 获取更新后的库存记录
                    updated_stock = await WarehouseStock.filter(
                        warehouse_id=warehouse.id,
                        product_id=product.id,
                        location_id=location.id
                    ).first()
                    before_qty = (updated_stock.quantity - quantity) if updated_stock else 0
                    after_qty = updated_stock.quantity if updated_stock else quantity
                    await StockLog.create(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        change_type="RESTOCK",
                        quantity=quantity,
                        before_qty=before_qty,
                        after_qty=after_qty,
                        remark=f"仓位:{location.code}, {remark}",
                        creator=user
                    )
                    
                    stocked += 1
                    
            except Exception as e:
                errors.append(f"第{idx+2}行错误: {str(e)}")
                continue
    
    # 构建详细的返回消息
    msg_parts = []
    if created > 0:
        msg_parts.append(f"新建商品{created}条")
    if updated > 0:
        msg_parts.append(f"更新商品{updated}条")
    if stocked > 0:
        msg_parts.append(f"入库{stocked}条")
    if skipped > 0:
        msg_parts.append(f"跳过{skipped}条")
    
    result = {"message": f"导入完成: {', '.join(msg_parts) if msg_parts else '无数据处理'}"}
    if errors:
        result["errors"] = errors[:20]  # 返回前20条错误信息
        result["message"] += f"（共{len(errors)}条错误/警告）"
        result["total_errors"] = len(errors)
    
    return result

@app.get("/api/products/{product_id}")
async def get_product(product_id: int, user: User = Depends(get_current_user)):
    p = await Product.filter(id=product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])
    stocks = await WarehouseStock.filter(product_id=p.id, warehouse__is_virtual=False).select_related("warehouse")

    result = {
        "id": p.id, "sku": p.sku, "name": p.name, "brand": p.brand, "category": p.category,
        "retail_price": float(p.retail_price), "unit": p.unit,
        "stocks": [{"warehouse_id": s.warehouse_id, "warehouse_name": s.warehouse.name, "quantity": s.quantity} for s in stocks]
    }
    if has_finance:
        result["cost_price"] = float(p.cost_price)
    return result

@app.post("/api/products")
async def create_product(data: ProductCreate, user: User = Depends(require_permission("stock_edit"))):
    if await Product.filter(sku=data.sku).exists():
        raise HTTPException(status_code=400, detail="SKU已存在")
    p = await Product.create(**data.model_dump())
    return {"id": p.id, "message": "创建成功"}

@app.put("/api/products/{product_id}")
async def update_product(product_id: int, data: ProductUpdate, user: User = Depends(require_permission("stock_edit"))):
    p = await Product.filter(id=product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data:
        await Product.filter(id=product_id).update(**update_data)
    return {"message": "更新成功"}

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: int, user: User = Depends(require_permission("stock_edit"))):
    p = await Product.filter(id=product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    p.is_active = False
    await p.save()
    return {"message": "删除成功"}

# ==================== 库存管理 API ====================
@app.post("/api/stock/restock")
async def restock(data: RestockRequest, user: User = Depends(require_permission("stock_edit"))):
    """入库/补货"""
    async with transactions.in_transaction():
        try:
            product = await Product.filter(id=data.product_id, is_active=True).first()
            if not product:
                raise HTTPException(status_code=404, detail="商品不存在")
            
            warehouse = await Warehouse.filter(id=data.warehouse_id, is_active=True, is_virtual=False).first()
            if not warehouse:
                raise HTTPException(status_code=404, detail="仓库不存在")
            
            location = await Location.filter(id=data.location_id, is_active=True).first()
            if not location:
                raise HTTPException(status_code=404, detail="仓位不存在")

            # SN码检查
            sn_required = await check_sn_required(data.warehouse_id, data.product_id)
            if sn_required and not data.sn_codes:
                raise HTTPException(status_code=400, detail="该仓库+品牌已启用SN管理，入库时必须填写SN码")

            # 获取入库成本价
            cost_price = Decimal(str(data.cost_price)) if data.cost_price and data.cost_price > 0 else product.cost_price

            # 验证并添加SN码
            if sn_required and data.sn_codes:
                await validate_and_add_sn_codes(
                    data.sn_codes, data.warehouse_id, data.product_id, data.location_id,
                    data.quantity, "RESTOCK", cost_price, user
                )

            # 获取当前库存（按仓库+商品+仓位）
            stock = await WarehouseStock.filter(warehouse_id=data.warehouse_id, product_id=data.product_id, location_id=data.location_id).first()
            before_qty = stock.quantity if stock else 0

            # 更新加权入库日期、库存和加权成本
            await update_weighted_entry_date(data.warehouse_id, data.product_id, data.quantity, cost_price, data.location_id)

            # 重新获取更新后的库存
            stock = await WarehouseStock.filter(warehouse_id=data.warehouse_id, product_id=data.product_id, location_id=data.location_id).first()

            # 同时更新商品的默认成本价为最新的加权成本
            product.cost_price = stock.weighted_cost
            await product.save()

            # 记录日志
            await StockLog.create(
                product_id=data.product_id,
                warehouse_id=data.warehouse_id,
                change_type="RESTOCK",
                quantity=data.quantity,
                before_qty=before_qty,
                after_qty=stock.quantity,
                remark=f"仓位:{location.code}, 入库成本: ¥{cost_price}" + (f", {data.remark}" if data.remark else ""),
                creator=user
            )

            await log_operation(user, "STOCK_RESTOCK", "STOCK", product.id,
                f"入库 {product.sku} {product.name}，仓位 {location.code}，数量 {data.quantity}，成本 ¥{float(cost_price):.2f}")

            return {"message": "入库成功", "new_quantity": stock.quantity, "weighted_cost": float(stock.weighted_cost)}
        except HTTPException:
            raise
        except Exception as e:
            traceback.print_exc()
            print(f"[ERROR] 入库失败: {e}"); raise HTTPException(status_code=500, detail="入库失败，请重试")

@app.post("/api/stock/adjust")
async def adjust_stock(data: StockAdjustRequest, user: User = Depends(require_permission("stock_edit"))):
    """库存盘点调整"""
    async with transactions.in_transaction():
        stock = await WarehouseStock.filter(warehouse_id=data.warehouse_id, product_id=data.product_id).first()
        before_qty = stock.quantity if stock else 0
        
        if not stock:
            stock = await WarehouseStock.create(
                warehouse_id=data.warehouse_id,
                product_id=data.product_id,
                quantity=data.new_quantity,
                weighted_entry_date=now()
            )
        else:
            stock.quantity = data.new_quantity
            await stock.save()
        
        await StockLog.create(
            product_id=data.product_id,
            warehouse_id=data.warehouse_id,
            change_type="ADJUST",
            quantity=data.new_quantity - before_qty,
            before_qty=before_qty,
            after_qty=data.new_quantity,
            remark=data.remark,
            creator=user
        )

        product = await Product.filter(id=data.product_id).first()
        await log_operation(user, "STOCK_ADJUST", "STOCK", data.product_id,
            f"库存调整 {product.sku if product else data.product_id}，{before_qty} → {data.new_quantity}")

        return {"message": "调整成功"}

@app.post("/api/stock/transfer")
async def transfer_stock(data: StockTransferRequest, user: User = Depends(require_permission("stock_edit"))):
    """库存调拨 - 从一个仓库/仓位转移到另一个仓库/仓位"""
    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="调拨数量必须大于0")
    
    if data.from_warehouse_id == data.to_warehouse_id and data.from_location_id == data.to_location_id:
        raise HTTPException(status_code=400, detail="源和目标位置不能相同")
    
    async with transactions.in_transaction():
        try:
            # 验证商品
            product = await Product.filter(id=data.product_id, is_active=True).first()
            if not product:
                raise HTTPException(status_code=404, detail="商品不存在")
            
            # 验证仓库
            from_wh = await Warehouse.filter(id=data.from_warehouse_id, is_active=True).first()
            to_wh = await Warehouse.filter(id=data.to_warehouse_id, is_active=True).first()
            if not from_wh or not to_wh:
                raise HTTPException(status_code=404, detail="仓库不存在")
            
            # 验证仓位
            from_loc = await Location.filter(id=data.from_location_id, is_active=True).first()
            to_loc = await Location.filter(id=data.to_location_id, is_active=True).first()
            if not from_loc or not to_loc:
                raise HTTPException(status_code=404, detail="仓位不存在")
            
            # 获取源库存
            from_stock = await WarehouseStock.filter(
                warehouse_id=data.from_warehouse_id,
                product_id=data.product_id,
                location_id=data.from_location_id
            ).first()
            
            if not from_stock or from_stock.quantity < data.quantity:
                raise HTTPException(status_code=400, detail="源库存不足")
            
            from_before = from_stock.quantity
            
            # 获取或创建目标库存
            to_stock = await WarehouseStock.filter(
                warehouse_id=data.to_warehouse_id,
                product_id=data.product_id,
                location_id=data.to_location_id
            ).first()
            
            if not to_stock:
                to_stock = await WarehouseStock.create(
                    warehouse_id=data.to_warehouse_id,
                    product_id=data.product_id,
                    location_id=data.to_location_id,
                    quantity=0,
                    weighted_cost=from_stock.weighted_cost,
                    weighted_entry_date=from_stock.weighted_entry_date
                )
            
            to_before = to_stock.quantity

            # 执行调拨（原子操作）
            updated = await WarehouseStock.filter(id=from_stock.id, quantity__gte=data.quantity).update(quantity=F('quantity') - data.quantity)
            if not updated:
                raise HTTPException(status_code=400, detail="源库存不足，调拨失败")
            await WarehouseStock.filter(id=to_stock.id).update(quantity=F('quantity') + data.quantity)
            await from_stock.refresh_from_db()
            await to_stock.refresh_from_db()
            
            # 记录日志 - 出库
            remark_out = f"调拨至 {to_wh.name}/{to_loc.code}"
            if data.remark:
                remark_out += f", {data.remark}"
            await StockLog.create(
                product_id=data.product_id,
                warehouse_id=data.from_warehouse_id,
                change_type="TRANSFER_OUT",
                quantity=-data.quantity,
                before_qty=from_before,
                after_qty=from_stock.quantity,
                remark=remark_out,
                creator=user
            )
            
            # 记录日志 - 入库
            remark_in = f"从 {from_wh.name}/{from_loc.code} 调入"
            if data.remark:
                remark_in += f", {data.remark}"
            await StockLog.create(
                product_id=data.product_id,
                warehouse_id=data.to_warehouse_id,
                change_type="TRANSFER_IN",
                quantity=data.quantity,
                before_qty=to_before,
                after_qty=to_stock.quantity,
                remark=remark_in,
                creator=user
            )
            
            await log_operation(user, "STOCK_TRANSFER", "STOCK", data.product_id,
                f"库存调拨 {product.sku}，{from_wh.name}/{from_loc.code} → {to_wh.name}/{to_loc.code}，数量 {data.quantity}")

            return {"message": "调拨成功", "from_qty": from_stock.quantity, "to_qty": to_stock.quantity}
        except HTTPException:
            raise
        except Exception as e:
            traceback.print_exc()
            print(f"[ERROR] 调拨失败: {e}"); raise HTTPException(status_code=500, detail="调拨失败，请重试")

@app.get("/api/stock/logs")
async def get_stock_logs(product_id: Optional[int] = None, warehouse_id: Optional[int] = None, limit: int = 100, user: User = Depends(require_permission("logs"))):
    limit = min(limit, 1000)
    query = StockLog.all()
    if product_id:
        query = query.filter(product_id=product_id)
    if warehouse_id:
        query = query.filter(warehouse_id=warehouse_id)
    
    logs = await query.order_by("-created_at").limit(limit).select_related("product", "warehouse", "creator")
    return [{
        "id": l.id,
        "product_name": l.product.name,
        "product_sku": l.product.sku,
        "warehouse_name": l.warehouse.name,
        "change_type": l.change_type,
        "quantity": l.quantity,
        "before_qty": l.before_qty,
        "after_qty": l.after_qty,
        "remark": l.remark,
        "creator_name": l.creator.display_name if l.creator else None,
        "created_at": l.created_at.isoformat()
    } for l in logs]

@app.get("/api/stock/export")
async def export_stock(warehouse_id: Optional[int] = None, user: User = Depends(require_permission("stock_view"))):
    """导出库存到Excel"""

    try:
        products = await Product.filter(is_active=True).order_by("sku")

        stock_query = WarehouseStock.all()
        if warehouse_id:
            stock_query = stock_query.filter(warehouse_id=warehouse_id)
        stocks = await stock_query.select_related("product", "warehouse", "location")

        stock_by_product = {}
        for s in stocks:
            if s.product_id not in stock_by_product:
                stock_by_product[s.product_id] = []
            stock_by_product[s.product_id].append(s)

        output = io.StringIO()
        output.write('\ufeff')

        headers = ["SKU", "商品名称", "品牌", "分类", "仓库", "仓位", "库存数量", "SN码数量", "加权成本", "库存金额", "零售价", "库龄(天)", "入库时间"]
        output.write(','.join(headers) + '\n')

        for p in products:
            product_stocks = stock_by_product.get(p.id, [])
            if not product_stocks:
                if not warehouse_id:
                    row = [p.sku, p.name, p.brand or "-", p.category or "-", "-", "-", "0", "0", f"{float(p.cost_price or 0):.2f}", "0.00", f"{float(p.retail_price or 0):.2f}", "-", "-"]
                    output.write(','.join(f'"{str(item)}"' for item in row) + '\n')
            else:
                for s in product_stocks:
                    age_days = "-"
                    entry_date_str = "-"
                    entry_date = to_naive(s.weighted_entry_date) if s.weighted_entry_date else None
                    if entry_date:
                        age_days = str((datetime.now() - entry_date).days)
                        entry_date_str = entry_date.strftime("%Y-%m-%d")
                    stock_value = float(s.quantity) * float(s.weighted_cost or p.cost_price or 0)
                    sn_count = await SnCode.filter(warehouse_id=s.warehouse_id, product_id=s.product_id, location_id=s.location_id, status="in_stock").count()
                    row = [p.sku, p.name, p.brand or "-", p.category or "-", s.warehouse.name if s.warehouse else "-", s.location.code if s.location else "-", str(s.quantity), str(sn_count), f"{float(s.weighted_cost or 0):.2f}", f"{stock_value:.2f}", f"{float(p.retail_price or 0):.2f}", age_days, entry_date_str]
                    output.write(','.join(f'"{str(item)}"' for item in row) + '\n')

        output.seek(0)
        filename = f"库存表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return StreamingResponse(
            iter([output.getvalue().encode('utf-8')]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
        )
    except Exception as e:
        traceback.print_exc()
        print(f"[ERROR] 导出失败: {e}"); raise HTTPException(status_code=500, detail="导出失败，请重试")

# ==================== 销售员管理 API ====================
@app.get("/api/salespersons")
async def list_salespersons(user: User = Depends(get_current_user)):
    sps = await Salesperson.filter(is_active=True).order_by("name")
    return [{"id": s.id, "name": s.name, "phone": s.phone} for s in sps]

@app.post("/api/salespersons")
async def create_salesperson(data: SalespersonCreate, user: User = Depends(require_permission("admin"))):
    if await Salesperson.filter(name=data.name).exists():
        raise HTTPException(status_code=400, detail="销售员姓名已存在")
    sp = await Salesperson.create(name=data.name, phone=data.phone)
    return {"id": sp.id, "message": "创建成功"}

@app.put("/api/salespersons/{sp_id}")
async def update_salesperson(sp_id: int, data: SalespersonUpdate, user: User = Depends(require_permission("admin"))):
    sp = await Salesperson.filter(id=sp_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="销售员不存在")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if "name" in update_data:
        if await Salesperson.filter(name=update_data["name"]).exclude(id=sp_id).exists():
            raise HTTPException(status_code=400, detail="销售员姓名已存在")
    if update_data:
        await Salesperson.filter(id=sp_id).update(**update_data)
    return {"message": "更新成功"}

@app.delete("/api/salespersons/{sp_id}")
async def delete_salesperson(sp_id: int, user: User = Depends(require_permission("admin"))):
    sp = await Salesperson.filter(id=sp_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="销售员不存在")
    sp.is_active = False
    await sp.save()
    return {"message": "删除成功"}

# ==================== 客户管理 API ====================
@app.get("/api/customers")
async def list_customers(keyword: Optional[str] = None, user: User = Depends(get_current_user)):
    query = Customer.filter(is_active=True)
    if keyword:
        for word in keyword.split():
            query = query.filter(Q(name__icontains=word) | Q(phone__icontains=word))
    customers = await query.order_by("name")
    return [{"id": c.id, "name": c.name, "contact_person": c.contact_person, "phone": c.phone, "address": c.address, "balance": float(c.balance), "rebate_balance": float(c.rebate_balance)} for c in customers]

@app.post("/api/customers")
async def create_customer(data: CustomerCreate, user: User = Depends(require_permission("customer", "sales"))):
    c = await Customer.create(**data.model_dump())
    return {"id": c.id, "message": "创建成功"}

@app.put("/api/customers/{customer_id}")
async def update_customer(customer_id: int, data: CustomerCreate, user: User = Depends(require_permission("customer", "sales"))):
    c = await Customer.filter(id=customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="客户不存在")
    await Customer.filter(id=customer_id).update(**data.model_dump())
    return {"message": "更新成功"}

@app.delete("/api/customers/{customer_id}")
async def delete_customer(customer_id: int, user: User = Depends(require_permission("customer", "sales"))):
    c = await Customer.filter(id=customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="客户不存在")
    if c.balance != 0:
        raise HTTPException(status_code=400, detail="客户有未结清款项，无法删除")
    c.is_active = False
    await c.save()
    return {"message": "删除成功"}

@app.get("/api/customers/{customer_id}/transactions")
async def get_customer_transactions(customer_id: int, year: Optional[int] = None, month: Optional[int] = None, user: User = Depends(get_current_user)):
    """获取客户交易明细"""
    customer = await Customer.filter(id=customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    # 构建查询
    query = Order.filter(customer_id=customer_id)
    
    # 按月筛选
    if year and month:
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        query = query.filter(created_at__gte=start_date, created_at__lt=end_date)
    
    orders = await query.order_by("-created_at").select_related("warehouse", "creator", "salesperson")
    
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])
    
    # 按类型分组统计
    stats = {
        "CASH": {"count": 0, "amount": 0, "profit": 0},
        "CREDIT": {"count": 0, "amount": 0, "profit": 0},
        "CONSIGN_OUT": {"count": 0, "amount": 0, "profit": 0},
        "CONSIGN_SETTLE": {"count": 0, "amount": 0, "profit": 0},
        "RETURN": {"count": 0, "amount": 0, "profit": 0}
    }
    
    transactions = []
    for o in orders:
        otype = o.order_type
        if otype in stats:
            stats[otype]["count"] += 1
            stats[otype]["amount"] += float(o.total_amount)
            stats[otype]["profit"] += float(o.total_profit)
        
        item = {
            "id": o.id,
            "order_no": o.order_no,
            "order_type": o.order_type,
            "warehouse_name": o.warehouse.name if o.warehouse else "-",
            "total_amount": float(o.total_amount),
            "paid_amount": float(o.paid_amount),
            "is_cleared": o.is_cleared,
            "remark": o.remark,
            "salesperson_name": o.salesperson.name if o.salesperson else "-",
            "creator_name": o.creator.display_name if o.creator else "-",
            "created_at": o.created_at.isoformat()
        }
        if has_finance:
            item["total_cost"] = float(o.total_cost)
            item["total_profit"] = float(o.total_profit)
        transactions.append(item)
    
    # 获取可用的月份列表
    all_orders = await Order.filter(customer_id=customer_id).order_by("created_at")
    months_set = set()
    for o in all_orders:
        months_set.add(f"{o.created_at.year}-{o.created_at.month:02d}")
    available_months = sorted(list(months_set), reverse=True)
    
    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "balance": float(customer.balance)
        },
        "stats": stats if has_finance else None,
        "transactions": transactions,
        "available_months": available_months
    }

# ==================== 订单/销售 API ====================
@app.post("/api/orders")
async def create_order(data: OrderCreate, user: User = Depends(require_permission("sales"))):
    """
    创建订单
    CASH: 现款销售 - 扣库存，不产生应收
    CREDIT: 账期销售 - 扣库存，增加客户应收
    CONSIGN_OUT: 寄售调拨 - 从实体仓扣库存，加到虚拟寄售仓
    CONSIGN_SETTLE: 寄售结算 - 从虚拟仓扣库存，增加客户应收
    RETURN: 退货 - 增加库存，减少客户应收
    """
    async with transactions.in_transaction():
        try:
            order_no = generate_order_no("ORD")
            total_amount = Decimal("0")
            total_cost = Decimal("0")
            total_profit = Decimal("0")
            
            customer = None
            if data.customer_id:
                customer = await Customer.filter(id=data.customer_id).first()
                if not customer:
                    raise HTTPException(status_code=404, detail="客户不存在")

            salesperson = None
            if data.salesperson_id:
                salesperson = await Salesperson.filter(id=data.salesperson_id, is_active=True).first()
                if not salesperson:
                    raise HTTPException(status_code=404, detail="销售员不存在")

            warehouse = None
            if data.warehouse_id:
                warehouse = await Warehouse.filter(id=data.warehouse_id, is_active=True).first()
                if not warehouse:
                    raise HTTPException(status_code=404, detail="仓库不存在")
            
            # 验证订单类型所需参数
            if data.order_type in ["CASH", "CREDIT", "CONSIGN_OUT"]:
                # 如果订单级别没有仓库，检查是否为一单多仓模式（每个商品都有仓库）
                if not warehouse:
                    # 一单多仓模式：验证每个商品都有仓库和仓位
                    for idx, item in enumerate(data.items):
                        if not item.warehouse_id or not item.location_id:
                            raise HTTPException(status_code=400, detail=f"商品 {idx+1} 需要选择仓库和仓位")
                elif warehouse.is_virtual:
                    raise HTTPException(status_code=400, detail="需要选择实体仓库")
            # 所有订单类型都必须选择客户
            if data.order_type in ["CASH", "CREDIT", "CONSIGN_OUT", "CONSIGN_SETTLE", "RETURN"]:
                if not customer:
                    raise HTTPException(status_code=400, detail="需要选择客户")

            # 寄售相关：使用客户独立仓
            consignment_wh = None
            if data.order_type in ["CONSIGN_OUT", "CONSIGN_SETTLE"]:
                consignment_wh = await get_or_create_consignment_warehouse(customer.id)
            if data.order_type == "CONSIGN_SETTLE":
                warehouse = consignment_wh
            if data.order_type == "RETURN":
                if not data.related_order_id:
                    raise HTTPException(status_code=400, detail="退货需要选择原始销售订单")
                # 如果订单级别没有仓库，检查是否为一单多仓模式（每个商品都有仓库）
                if not warehouse:
                    # 一单多仓模式：验证每个商品都有仓库和仓位
                    for idx, item in enumerate(data.items):
                        if not item.warehouse_id or not item.location_id:
                            raise HTTPException(status_code=400, detail=f"商品 {idx+1} 需要选择退货仓库和仓位")
                else:
                    # 传统模式：验证订单级别的仓位
                    if not data.location_id:
                        raise HTTPException(status_code=400, detail="退货需要选择仓位")
                    location = await Location.filter(id=data.location_id, is_active=True).first()
                    if not location:
                        raise HTTPException(status_code=404, detail="仓位不存在")
                # 验证关联订单
                related_order = await Order.filter(id=data.related_order_id, order_type__in=["CASH", "CREDIT"]).first()
                if not related_order:
                    raise HTTPException(status_code=404, detail="关联的销售订单不存在或类型错误")
                # 验证客户是否一致
                if related_order.customer_id != customer.id:
                    raise HTTPException(status_code=400, detail="退货客户必须与原订单客户一致")
            
            # 创建订单
            # 已结清判断：
            # 1. 现款销售自动结清
            # 2. 退货且已退款给客户也算结清（钱已经退了）
            is_cleared = data.order_type == "CASH" or (data.order_type == "RETURN" and data.refunded)
            order = await Order.create(
                order_no=order_no,
                order_type=data.order_type,
                customer=customer,
                warehouse=warehouse,
                related_order_id=data.related_order_id if data.order_type == "RETURN" else None,
                refunded=data.refunded if data.order_type == "RETURN" else False,
                remark=data.remark,
                salesperson=salesperson,
                creator=user,
                is_cleared=is_cleared
            )
            
            # 处理订单明细
            for item in data.items:
                product = await Product.filter(id=item.product_id, is_active=True).first()
                if not product:
                    raise HTTPException(status_code=404, detail=f"商品不存在: {item.product_id}")
                
                qty = item.quantity
                unit_price = Decimal(str(item.unit_price))
                
                # 获取商品级别的仓库和仓位（一单多仓支持）
                item_warehouse = None
                item_location = None
                if item.warehouse_id:
                    item_warehouse = await Warehouse.filter(id=item.warehouse_id, is_active=True).first()
                    if not item_warehouse:
                        raise HTTPException(status_code=404, detail=f"商品的仓库不存在: {item.warehouse_id}")
                if item.location_id:
                    item_location = await Location.filter(id=item.location_id, is_active=True).first()
                    if not item_location:
                        raise HTTPException(status_code=404, detail=f"商品的仓位不存在: {item.location_id}")
                
                # 确定使用哪个仓库（优先使用商品级别的仓库，否则使用订单级别的仓库）
                working_warehouse = item_warehouse if item_warehouse else warehouse
                working_location = item_location if item_location else (await Location.filter(id=data.location_id).first() if data.location_id else None)

                # 禁止普通销售/寄售调拨/退货使用虚拟仓
                if data.order_type in ["CASH", "CREDIT", "CONSIGN_OUT", "RETURN"]:
                    if working_warehouse and working_warehouse.is_virtual:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 不能从寄售虚拟仓出库，请选择实体仓库")
                
                # 获取加权成本（优先从仓库库存获取）
                if working_warehouse and not working_warehouse.is_virtual:
                    stock_for_cost = await WarehouseStock.filter(warehouse_id=working_warehouse.id, product_id=product.id, location_id=working_location.id if working_location else None).first()
                    cost_price = stock_for_cost.weighted_cost if stock_for_cost and stock_for_cost.weighted_cost else product.cost_price
                else:
                    cost_price = await get_product_weighted_cost(product.id)
                
                amount = unit_price * qty
                # 返利抵扣
                item_rebate = Decimal(str(item.rebate_amount)) if item.rebate_amount else Decimal("0")
                if item_rebate > 0:
                    if item_rebate > amount:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 返利金额不能超过行金额")
                    amount = amount - item_rebate
                profit = amount - cost_price * qty

                if data.order_type == "RETURN":
                    # 退货：金额和利润为负
                    amount = -abs(amount)
                    profit = -abs(profit)
                    qty = abs(qty)
                    item_rebate = Decimal("0")  # 退货不使用返利

                total_amount += amount
                total_cost += cost_price * qty
                total_profit += profit

                await OrderItem.create(
                    order=order,
                    product=product,
                    quantity=qty if data.order_type != "RETURN" else -qty,
                    unit_price=unit_price,
                    cost_price=cost_price,
                    amount=amount,
                    profit=profit,
                    rebate_amount=item_rebate
                )
                
                # 处理库存变动
                if data.order_type in ["CASH", "CREDIT"]:
                    # 销售：扣减仓库库存（使用商品级别的仓库和仓位）
                    if not working_warehouse:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定仓库")
                    if not working_location:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定仓位")
                    
                    updated = await WarehouseStock.filter(
                        warehouse_id=working_warehouse.id,
                        product_id=product.id,
                        location_id=working_location.id,
                        quantity__gte=qty
                    ).update(quantity=F('quantity') - qty)
                    if not updated:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 在 {working_warehouse.name}-{working_location.code} 库存不足")
                    stock = await WarehouseStock.filter(warehouse_id=working_warehouse.id, product_id=product.id, location_id=working_location.id).first()
                    await StockLog.create(
                        product=product, warehouse=working_warehouse, change_type="SALE",
                        quantity=-qty, before_qty=stock.quantity + qty, after_qty=stock.quantity,
                        reference_type="ORDER", reference_id=order.id, creator=user
                    )
                
                elif data.order_type == "CONSIGN_OUT":
                    # 寄售调拨：从实体仓扣，加到虚拟仓（使用商品级别的仓库和仓位）
                    if not working_warehouse:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定仓库")
                    if not working_location:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定仓位")
                    
                    updated = await WarehouseStock.filter(
                        warehouse_id=working_warehouse.id,
                        product_id=product.id,
                        location_id=working_location.id,
                        quantity__gte=qty
                    ).update(quantity=F('quantity') - qty)
                    if not updated:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 在 {working_warehouse.name}-{working_location.code} 库存不足")
                    stock = await WarehouseStock.filter(warehouse_id=working_warehouse.id, product_id=product.id, location_id=working_location.id).first()
                    await StockLog.create(
                        product=product, warehouse=working_warehouse, change_type="CONSIGN_OUT",
                        quantity=-qty, before_qty=stock.quantity + qty, after_qty=stock.quantity,
                        reference_type="ORDER", reference_id=order.id, creator=user
                    )
                    # 加到虚拟仓
                    await update_weighted_entry_date(consignment_wh.id, product.id, qty)
                    v_stock = await WarehouseStock.filter(warehouse_id=consignment_wh.id, product_id=product.id).first()
                    await StockLog.create(
                        product=product, warehouse=consignment_wh, change_type="CONSIGN_OUT",
                        quantity=qty, before_qty=v_stock.quantity - qty, after_qty=v_stock.quantity,
                        reference_type="ORDER", reference_id=order.id, creator=user
                    )
                
                elif data.order_type == "CONSIGN_SETTLE":
                    # 寄售结算：从虚拟仓扣
                    updated = await WarehouseStock.filter(
                        warehouse_id=consignment_wh.id, product_id=product.id, quantity__gte=qty
                    ).update(quantity=F('quantity') - qty)
                    if not updated:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 寄售库存不足")
                    stock = await WarehouseStock.filter(warehouse_id=consignment_wh.id, product_id=product.id).first()
                    await StockLog.create(
                        product=product, warehouse=consignment_wh, change_type="CONSIGN_SETTLE",
                        quantity=-qty, before_qty=stock.quantity + qty, after_qty=stock.quantity,
                        reference_type="ORDER", reference_id=order.id, creator=user
                    )
                
                elif data.order_type == "RETURN":
                    # 退货：增加库存到指定仓位（使用商品级别的仓库和仓位）
                    if not working_warehouse:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定退货仓库")
                    if not working_location:
                        raise HTTPException(status_code=400, detail=f"商品 {product.name} 没有指定退货仓位")
                    
                    await update_weighted_entry_date(working_warehouse.id, product.id, qty, location_id=working_location.id)
                    stock = await WarehouseStock.filter(warehouse_id=working_warehouse.id, product_id=product.id, location_id=working_location.id).first()
                    await StockLog.create(
                        product=product, warehouse=working_warehouse, change_type="RETURN",
                        quantity=qty, before_qty=stock.quantity - qty, after_qty=stock.quantity,
                        reference_type="ORDER", reference_id=order.id, creator=user
                    )
            
            # 处理返利扣减
            total_rebate = sum(
                Decimal(str(it.rebate_amount)) if it.rebate_amount else Decimal("0")
                for it in data.items
            )
            if total_rebate > 0 and data.order_type != "RETURN":
                if not customer:
                    raise HTTPException(status_code=400, detail="使用返利需要选择客户")
                await customer.refresh_from_db()
                if customer.rebate_balance < total_rebate:
                    raise HTTPException(status_code=400, detail=f"客户返利余额不足，可用 ¥{float(customer.rebate_balance):.2f}，需要 ¥{float(total_rebate):.2f}")
                await Customer.filter(id=customer.id).update(rebate_balance=F('rebate_balance') - total_rebate)
                await customer.refresh_from_db()
                order.rebate_used = total_rebate
                # 自动追加备注
                rebate_remark = f"[返利抵扣] 使用返利 ¥{float(total_rebate):.2f}"
                order.remark = f"{order.remark}\n{rebate_remark}" if order.remark else rebate_remark
                # 写入返利流水
                await RebateLog.create(
                    target_type="customer", target_id=customer.id,
                    type="use", amount=total_rebate,
                    balance_after=customer.rebate_balance,
                    reference_type="ORDER", reference_id=order.id,
                    remark=f"销售订单 {order_no} 使用返利", creator=user
                )

            # 更新订单金额
            order.total_amount = total_amount
            order.total_cost = total_cost
            order.total_profit = total_profit

            # 设置已付金额和结清状态
            # 退货且已退款时：is_cleared=True, paid_amount=退货金额绝对值
            if data.order_type == "RETURN" and data.refunded:
                order.is_cleared = True
                order.paid_amount = abs(total_amount)
            elif is_cleared:
                order.paid_amount = abs(total_amount)  # 使用绝对值，退货时total_amount是负数
            await order.save()
            
            # 初始化实际使用的在账资金标志
            actual_credit_used = 0
            
            # 更新客户余额和在账资金抵扣
            if customer and data.order_type in ["CREDIT", "CONSIGN_SETTLE"]:
                # 账期销售/寄售结算：增加客户欠款（原子更新）
                old_balance = customer.balance
                await Customer.filter(id=customer.id).update(balance=F('balance') + total_amount)
                await customer.refresh_from_db()

                # 检查是否有在账资金可以抵扣（余额为负数表示有在账资金）
                if old_balance < 0:
                    # 有在账资金，自动抵扣
                    available_credit = abs(old_balance)  # 可用在账资金
                    amount_to_deduct = min(available_credit, abs(total_amount))  # 可抵扣金额

                    order.paid_amount = Decimal(str(amount_to_deduct))
                    if order.paid_amount >= abs(total_amount):
                        order.is_cleared = True
                    await order.save()
                
            elif customer and data.order_type == "CASH":
                # 现款销售：如果使用了在账资金
                if data.use_credit and customer.balance < 0:
                    available_credit = abs(customer.balance)  # 可用在账资金
                    amount_to_use = min(available_credit, abs(total_amount))  # 实际使用金额
                    
                    # 从在账资金扣除（原子更新）
                    await Customer.filter(id=customer.id).update(balance=F('balance') + Decimal(str(amount_to_use)))
                    await customer.refresh_from_db()

                    order.paid_amount = Decimal(str(amount_to_use))
                    order.is_cleared = True  # 现款销售始终是已结清
                    await order.save()
                    
                    # 标记：实际使用了在账资金
                    actual_credit_used = amount_to_use
                else:
                    # 没有使用在账资金
                    actual_credit_used = 0
                    
            elif customer and data.order_type == "RETURN":
                # 退货逻辑：
                # - 如果已退款(refunded=True)：不修改客户余额（钱已经退给客户了）
                # - 如果未退款(refunded=False)：客户余额减少（total_amount是负数，相加后余额减少，形成预付款/在账资金）
                if not data.refunded:
                    await Customer.filter(id=customer.id).update(balance=F('balance') + total_amount)
                    await customer.refresh_from_db()
            
            # 计算实际应付金额（用于返回给前端）
            actual_amount_due = float(total_amount) - float(order.paid_amount)
            
            # 计算实际使用的在账资金
            credit_used = 0
            if data.order_type == "CASH":
                # 现款销售：使用上面设置的标志变量
                if actual_credit_used > 0:
                    credit_used = float(actual_credit_used)
            elif data.order_type in ["CREDIT", "CONSIGN_SETTLE"]:
                # 账期/寄售：如果paid_amount > 0说明自动抵扣了在账资金
                if order.paid_amount > 0:
                    credit_used = float(order.paid_amount)
            
            # 现款销售自动创建收款记录
            if data.order_type == "CASH" and customer:
                actual_pay = abs(float(total_amount)) - float(credit_used)
                if actual_pay > 0:
                    pay_no = generate_order_no("PAY")
                    await Payment.create(
                        payment_no=pay_no, customer=customer, order=order,
                        amount=Decimal(str(actual_pay)),
                        payment_method=data.payment_method or "cash",
                        source="CASH", is_confirmed=False,
                        remark=f"现款销售 {order_no}", creator=user
                    )

            # 对销售类/寄售调拨订单创建物流记录
            if data.order_type in ["CASH", "CREDIT", "CONSIGN_OUT"]:
                await Shipment.create(order=order)

            # 记录操作日志
            order_type_names = {'CASH':'现款','CREDIT':'账期','CONSIGN_OUT':'寄售调拨','CONSIGN_SETTLE':'寄售结算','RETURN':'退货'}
            await log_operation(user, "ORDER_CREATE", "ORDER", order.id,
                f"创建{order_type_names.get(data.order_type, data.order_type)}订单 {order_no}，金额 ¥{float(total_amount):.2f}")

            return {
                "id": order.id,
                "order_no": order_no,
                "total_amount": float(total_amount),
                "paid_amount": float(order.paid_amount),
                "rebate_used": float(order.rebate_used),
                "credit_used": credit_used,  # 实际使用的在账资金
                "amount_due": actual_amount_due,
                "message": "订单创建成功"
            }

        except HTTPException:
            raise
        except Exception as e:
            traceback.print_exc()
            print(f"[ERROR] 操作失败: {e}"); raise HTTPException(status_code=500, detail="操作失败，请重试")

@app.get("/api/orders")
async def list_orders(order_type: Optional[str] = None, customer_id: Optional[int] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100, user: User = Depends(get_current_user)):
    limit = min(limit, 1000)
    query = Order.all()
    if order_type:
        query = query.filter(order_type=order_type)
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if start_date:
        query = query.filter(created_at__gte=datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(created_at__lte=datetime.fromisoformat(end_date) + timedelta(days=1))
    
    orders = await query.order_by("-created_at").limit(limit).select_related("customer", "warehouse", "creator", "related_order", "salesperson")

    has_finance = user.role == "admin" or "finance" in (user.permissions or [])

    result = []
    for o in orders:
        item = {
            "id": o.id, "order_no": o.order_no, "order_type": o.order_type,
            "customer_name": o.customer.name if o.customer else None,
            "customer_id": o.customer_id,
            "warehouse_name": o.warehouse.name if o.warehouse else None,
            "total_amount": float(o.total_amount),
            "paid_amount": float(o.paid_amount),
            "is_cleared": o.is_cleared,
            "remark": o.remark,
            "salesperson_name": o.salesperson.name if o.salesperson else None,
            "creator_name": o.creator.display_name if o.creator else None,
            "created_at": o.created_at.isoformat(),
            "related_order_no": o.related_order.order_no if o.related_order else None,
            "related_order_id": o.related_order_id
        }
        if has_finance:
            item["total_cost"] = float(o.total_cost)
            item["total_profit"] = float(o.total_profit)
        result.append(item)

    return result

@app.get("/api/orders/{order_id}")
async def get_order(order_id: int, user: User = Depends(get_current_user)):
    order = await Order.filter(id=order_id).select_related("customer", "warehouse", "creator", "related_order", "salesperson").first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    items = await OrderItem.filter(order_id=order_id).select_related("product")
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])
    
    # 如果是销售订单（CASH/CREDIT），计算已退货数量
    returned_quantities = {}
    if order.order_type in ["CASH", "CREDIT"]:
        # 查询所有关联此订单的退货订单
        return_orders = await Order.filter(related_order_id=order_id, order_type="RETURN")
        for ret_order in return_orders:
            ret_items = await OrderItem.filter(order_id=ret_order.id)
            for ret_item in ret_items:
                if ret_item.product_id not in returned_quantities:
                    returned_quantities[ret_item.product_id] = 0
                # 退货的quantity是负数，取绝对值
                returned_quantities[ret_item.product_id] += abs(ret_item.quantity)
    
    # 计算在账资金使用和其他付款
    credit_used = 0
    other_payment = 0

    if order.order_type == "CASH":
        # 现款销售：只有实际使用了在账资金才显示
        if order.paid_amount > 0:
            credit_used = float(order.paid_amount)
            # 如果paid_amount小于total_amount，说明有其他付款
            if order.paid_amount < order.total_amount:
                other_payment = float(order.total_amount) - float(order.paid_amount)
    elif order.order_type in ["CREDIT", "CONSIGN_SETTLE"]:
        # 账期/寄售结算：paid_amount是抵扣的在账资金，剩余是欠款
        if order.paid_amount > 0:
            credit_used = float(order.paid_amount)
            other_payment = float(order.total_amount) - float(order.paid_amount)

    # 查询关联的收款记录
    payment_records = []
    # 1. 直接关联的收款（现款销售）
    direct_payments = await Payment.filter(order_id=order.id).all()
    for dp in direct_payments:
        payment_records.append({
            "id": dp.id, "payment_no": dp.payment_no,
            "amount": float(dp.amount), "payment_method": dp.payment_method,
            "source": dp.source, "is_confirmed": dp.is_confirmed,
            "created_at": dp.created_at.isoformat()
        })
    # 2. 通过PaymentOrder关联的收款（账期收款）
    po_links = await PaymentOrder.filter(order_id=order.id).select_related("payment").all()
    seen_ids = {dp.id for dp in direct_payments}
    for link in po_links:
        if link.payment_id not in seen_ids:
            seen_ids.add(link.payment_id)
            payment_records.append({
                "id": link.payment.id, "payment_no": link.payment.payment_no,
                "amount": float(link.amount), "payment_method": link.payment.payment_method,
                "source": link.payment.source, "is_confirmed": link.payment.is_confirmed,
                "created_at": link.payment.created_at.isoformat()
            })
    
    # 查询物流信息（一单多件）
    shipment_list = await Shipment.filter(order_id=order_id).order_by("id").all()
    shipments_info = []
    for sh in shipment_list:
        ti = []
        if sh.last_tracking_info:
            try:
                ti = json.loads(sh.last_tracking_info)
            except Exception:
                pass
        shipments_info.append({
            "id": sh.id,
            "carrier_name": sh.carrier_name,
            "tracking_no": sh.tracking_no,
            "sn_code": sh.sn_code,
            "status": sh.status,
            "status_text": sh.status_text,
            "last_info": ti[0].get("context", "") if ti else None,
            "tracking_info": ti
        })

    return {
        "id": order.id, "order_no": order.order_no, "order_type": order.order_type,
        "customer": {"id": order.customer.id, "name": order.customer.name} if order.customer else None,
        "warehouse": {"id": order.warehouse.id, "name": order.warehouse.name} if order.warehouse else None,
        "total_amount": float(order.total_amount),
        "total_cost": float(order.total_cost) if has_finance else None,
        "total_profit": float(order.total_profit) if has_finance else None,
        "paid_amount": float(order.paid_amount),
        "rebate_used": float(order.rebate_used),
        "credit_used": credit_used,  # 使用的在账资金
        "other_payment": other_payment,  # 其他付款
        "payment_records": payment_records,  # 关联收款记录
        "is_cleared": order.is_cleared,
        "refunded": order.refunded,  # 退货时是否已退款
        "remark": order.remark,
        "salesperson_name": order.salesperson.name if order.salesperson else None,
        "creator_name": order.creator.display_name if order.creator else None,
        "created_at": order.created_at.isoformat(),
        "related_order": {"id": order.related_order.id, "order_no": order.related_order.order_no} if order.related_order else None,
        "shipments": shipments_info,
        "items": [{
            "product_id": i.product_id,
            "product_sku": i.product.sku,
            "product_name": i.product.name,
            "quantity": i.quantity,
            "returned_quantity": returned_quantities.get(i.product_id, 0),  # 已退货数量
            "available_return_quantity": i.quantity - returned_quantities.get(i.product_id, 0),  # 可退数量
            "unit_price": float(i.unit_price),
            "cost_price": float(i.cost_price) if has_finance else None,
            "amount": float(i.amount),
            "profit": float(i.profit) if has_finance else None,
            "rebate_amount": float(i.rebate_amount) if i.rebate_amount else 0
        } for i in items]
    }

# ==================== 财务/回款 API ====================
@app.get("/api/finance/all-orders")
async def get_all_orders(order_type: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, search: Optional[str] = None, limit: int = 200, user: User = Depends(require_permission("finance"))):
    """获取所有订单（财务视角）"""
    limit = min(limit, 1000)
    query = Order.all()
    if order_type:
        query = query.filter(order_type=order_type)
    if start_date:
        query = query.filter(created_at__gte=datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(created_at__lte=datetime.fromisoformat(end_date) + timedelta(days=1))

    # 搜索：需要关联 shipments 查 SN码/快递单号
    search_order_ids = None
    if search:
        keywords = search.lower().split()
        # 先查 shipments 中匹配的 order_id
        all_shipments = await Shipment.all().select_related("order")
        shipment_order_ids = set()
        for s in all_shipments:
            fields = (s.tracking_no or "") + " " + (s.sn_code or "")
            fields_lower = fields.lower()
            fields_nospace = fields_lower.replace(" ", "")
            if all(w in fields_lower or w in fields_nospace for w in keywords):
                shipment_order_ids.add(s.order_id)
        search_order_ids = shipment_order_ids

    orders = await query.order_by("-created_at").limit(limit).select_related("customer", "warehouse", "creator", "related_order", "salesperson")

    result = []
    filtered_orders = []
    for o in orders:
        # 搜索过滤：订单号、客户名 或 物流匹配
        if search:
            keywords = search.lower().split()
            order_fields = ((o.order_no or "") + " " + (o.customer.name if o.customer else "")).lower()
            order_fields_nospace = order_fields.replace(" ", "")
            order_match = all(w in order_fields or w in order_fields_nospace for w in keywords)
            shipment_match = search_order_ids and o.id in search_order_ids
            if not order_match and not shipment_match:
                continue
        filtered_orders.append(o)

    # 批量查询订单的未确认收款状态
    order_ids = [o.id for o in filtered_orders]
    unconfirmed_order_ids = set()
    if order_ids:
        # CASH订单直接通过 order_id 关联
        cash_payments = await Payment.filter(order_id__in=order_ids, is_confirmed=False).all()
        for p in cash_payments:
            unconfirmed_order_ids.add(p.order_id)
        # CREDIT订单通过 PaymentOrder 关联
        po_links = await PaymentOrder.filter(order_id__in=order_ids).select_related("payment").all()
        for po in po_links:
            if not po.payment.is_confirmed:
                unconfirmed_order_ids.add(po.order_id)

    for o in filtered_orders:
        result.append({
            "id": o.id, "order_no": o.order_no, "order_type": o.order_type,
            "customer_name": o.customer.name if o.customer else "-",
            "customer_id": o.customer_id,
            "warehouse_name": o.warehouse.name if o.warehouse else "-",
            "total_amount": float(o.total_amount),
            "total_cost": float(o.total_cost),
            "total_profit": float(o.total_profit),
            "paid_amount": float(o.paid_amount),
            "is_cleared": o.is_cleared,
            "has_unconfirmed_payment": o.id in unconfirmed_order_ids,
            "refunded": o.refunded,
            "remark": o.remark,
            "salesperson_name": o.salesperson.name if o.salesperson else "-",
            "creator_name": o.creator.display_name if o.creator else "-",
            "created_at": o.created_at.isoformat(),
            "related_order_no": o.related_order.order_no if o.related_order else None,
            "related_order_id": o.related_order_id
        })
    return result

@app.get("/api/finance/all-orders/export")
async def export_orders(order_type: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, user: User = Depends(require_permission("finance"))):
    """导出订单到Excel"""
    
    query = Order.all()
    if order_type:
        query = query.filter(order_type=order_type)
    if start_date:
        query = query.filter(created_at__gte=datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(created_at__lte=datetime.fromisoformat(end_date) + timedelta(days=1))
    
    orders = await query.order_by("-created_at").select_related("customer", "warehouse", "creator", "related_order", "salesperson")

    # 创建CSV内容
    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Excel

    # 写入表头
    headers = ["订单号", "订单类型", "客户", "仓库", "金额", "成本", "毛利", "已付", "状态", "退款状态", "备注", "销售员", "创建人", "创建时间", "关联订单",
               "商品SKU", "商品名称", "数量", "单价", "成本价", "小计", "利润"]
    output.write(','.join(headers) + '\n')

    # 类型映射
    type_names = {
        "CASH": "现款", "CREDIT": "账期",
        "CONSIGN_OUT": "寄售调拨", "CONSIGN_SETTLE": "寄售结算",
        "CONSIGN_RETURN": "寄售退货",
        "RETURN": "退货"
    }

    def csv_safe(val):
        """防止CSV公式注入"""
        s = str(val).replace('"', '""')
        if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
            s = "'" + s
        return f'"{s}"'

    # 写入数据（每个订单项一行）
    for o in orders:
        order_base = [
            o.order_no,
            type_names.get(o.order_type, o.order_type),
            o.customer.name if o.customer else "-",
            o.warehouse.name if o.warehouse else "-",
            f"{float(o.total_amount):.2f}",
            f"{float(o.total_cost):.2f}",
            f"{float(o.total_profit):.2f}",
            f"{float(o.paid_amount):.2f}",
            "已结清" if o.is_cleared else "未结清",
            ("已退款" if o.refunded else "未退款") if o.order_type == "RETURN" else "-",
            (o.remark or "").replace('\n', ' '),
            o.salesperson.name if o.salesperson else "-",
            o.creator.display_name if o.creator else "-",
            o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            o.related_order.order_no if o.related_order else "-"
        ]
        items = await OrderItem.filter(order_id=o.id).select_related("product")
        if items:
            for it in items:
                row = order_base + [
                    it.product.sku if it.product else "-",
                    it.product.name if it.product else "-",
                    str(it.quantity),
                    f"{float(it.unit_price):.2f}",
                    f"{float(it.cost_price):.2f}",
                    f"{float(it.amount):.2f}",
                    f"{float(it.profit):.2f}"
                ]
                output.write(','.join(csv_safe(item) for item in row) + '\n')
        else:
            row = order_base + ["-"] * 7
            output.write(','.join(csv_safe(item) for item in row) + '\n')
    
    # 准备下载
    output.seek(0)
    filename = f"订单明细_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    from urllib.parse import quote
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    )

@app.get("/api/finance/stock-logs")
async def get_finance_stock_logs(change_type: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 200, user: User = Depends(require_permission("finance"))):
    """获取所有出入库日志（财务视角）"""
    limit = min(limit, 1000)
    # 类型中文映射
    type_names = {
        "RESTOCK": "入库",
        "SALE": "销售出库", 
        "RETURN": "退货入库",
        "CONSIGN_OUT": "寄售调拨",
        "CONSIGN_SETTLE": "寄售结算",
        "CONSIGN_RETURN": "寄售退货",
        "ADJUST": "库存调整",
        "PURCHASE_IN": "采购入库"
    }
    
    query = StockLog.all()
    if change_type:
        query = query.filter(change_type=change_type)
    if start_date:
        query = query.filter(created_at__gte=datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(created_at__lte=datetime.fromisoformat(end_date) + timedelta(days=1))
    
    logs = await query.order_by("-created_at").limit(limit).select_related("product", "warehouse", "creator")
    
    return [{
        "id": l.id,
        "product_sku": l.product.sku,
        "product_name": l.product.name,
        "warehouse_name": l.warehouse.name,
        "change_type": l.change_type,
        "change_type_name": type_names.get(l.change_type, l.change_type),
        "quantity": l.quantity,
        "before_qty": l.before_qty,
        "after_qty": l.after_qty,
        "reference_type": l.reference_type,
        "reference_id": l.reference_id,
        "remark": l.remark,
        "creator_name": l.creator.display_name if l.creator else "-",
        "created_at": l.created_at.isoformat()
    } for l in logs]

@app.get("/api/finance/unpaid-orders")
async def get_unpaid_orders(customer_id: Optional[int] = None, user: User = Depends(require_permission("finance"))):
    """获取未结清的账期/寄售结算订单"""
    query = Order.filter(is_cleared=False, order_type__in=["CREDIT", "CONSIGN_SETTLE"])
    if customer_id:
        query = query.filter(customer_id=customer_id)
    orders = await query.order_by("created_at").select_related("customer", "salesperson")
    return [{
        "id": o.id, "order_no": o.order_no, "order_type": o.order_type,
        "customer_id": o.customer_id, "customer_name": o.customer.name if o.customer else None,
        "salesperson_name": o.salesperson.name if o.salesperson else None,
        "total_amount": float(o.total_amount), "paid_amount": float(o.paid_amount),
        "unpaid_amount": float(o.total_amount - o.paid_amount),
        "created_at": o.created_at.isoformat()
    } for o in orders]

@app.post("/api/finance/payment")
async def create_payment(data: PaymentCreate, user: User = Depends(require_permission("finance"))):
    """回款核销"""
    async with transactions.in_transaction():
        customer = await Customer.filter(id=data.customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="客户不存在")
        
        orders = await Order.filter(id__in=data.order_ids, customer_id=data.customer_id, is_cleared=False).all()
        if len(orders) != len(data.order_ids):
            raise HTTPException(status_code=400, detail="部分订单不存在或已结清")
        
        # 计算总欠款
        total_unpaid = sum(float(o.total_amount - o.paid_amount) for o in orders)
        if data.amount > total_unpaid:
            raise HTTPException(status_code=400, detail=f"付款金额超过欠款总额 {total_unpaid}")
        
        payment_no = generate_order_no("PAY")
        payment = await Payment.create(
            payment_no=payment_no,
            customer=customer,
            amount=Decimal(str(data.amount)),
            payment_method=data.payment_method,
            source="CREDIT",
            is_confirmed=False,
            remark=data.remark,
            creator=user
        )

        # 按订单时间顺序核销
        remaining = Decimal(str(data.amount))
        for order in sorted(orders, key=lambda x: x.created_at):
            unpaid = order.total_amount - order.paid_amount
            if remaining <= 0:
                break
            pay_this = min(remaining, unpaid)
            order.paid_amount += pay_this
            if order.paid_amount >= order.total_amount:
                order.is_cleared = True
            await order.save()

            await PaymentOrder.create(payment=payment, order=order, amount=pay_this)
            remaining -= pay_this

        # 更新客户余额（原子更新）
        await Customer.filter(id=customer.id).update(balance=F('balance') - Decimal(str(data.amount)))

        # 记录操作日志
        await log_operation(user, "PAYMENT_CREATE", "PAYMENT", payment.id,
            f"账期收款 {payment_no}，客户 {customer.name}，金额 ¥{float(data.amount):.2f}")

        return {"id": payment.id, "payment_no": payment_no, "message": "收款成功"}

@app.get("/api/finance/payments")
async def list_payments(customer_id: Optional[int] = None, source: Optional[str] = None, limit: int = 100, user: User = Depends(require_permission("finance"))):
    limit = min(limit, 1000)
    query = Payment.all()
    if customer_id:
        query = query.filter(customer_id=customer_id)
    if source:
        query = query.filter(source=source)
    payments = await query.order_by("-created_at").limit(limit).select_related("customer", "creator", "confirmed_by", "order")
    result = []
    for p in payments:
        # 获取关联订单号
        order_nos = []
        if p.order_id and p.order:
            order_nos.append({"id": p.order.id, "order_no": p.order.order_no})
        else:
            # 账期收款通过 PaymentOrder 关联
            po_links = await PaymentOrder.filter(payment_id=p.id).select_related("order")
            for link in po_links:
                if link.order:
                    order_nos.append({"id": link.order.id, "order_no": link.order.order_no})
        result.append({
            "id": p.id, "payment_no": p.payment_no,
            "customer_name": p.customer.name, "customer_id": p.customer_id,
            "amount": float(p.amount), "payment_method": p.payment_method,
            "source": p.source,
            "is_confirmed": p.is_confirmed,
            "confirmed_by_name": p.confirmed_by.display_name if p.confirmed_by else None,
            "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
            "remark": p.remark,
            "creator_name": p.creator.display_name if p.creator else None,
            "created_at": p.created_at.isoformat(),
            "order_nos": order_nos
        })
    return result

@app.post("/api/finance/payment/{payment_id}/confirm")
async def confirm_payment(payment_id: int, user: User = Depends(require_permission("finance_confirm", "finance"))):
    """确认收款到账"""
    payment = await Payment.filter(id=payment_id).select_related("customer").first()
    if not payment:
        raise HTTPException(status_code=404, detail="收款记录不存在")
    if payment.is_confirmed:
        raise HTTPException(status_code=400, detail="该收款已确认")
    payment.is_confirmed = True
    payment.confirmed_by = user
    payment.confirmed_at = now()
    await payment.save()

    await log_operation(user, "PAYMENT_CONFIRM", "PAYMENT", payment.id,
        f"确认收款 {payment.payment_no}，客户 {payment.customer.name}，金额 ¥{float(payment.amount):.2f}")

    return {"message": "确认成功"}

@app.get("/api/finance/customer-statement/{customer_id}")
async def get_customer_statement(customer_id: int, user: User = Depends(require_permission("finance"))):
    """客户对账单"""
    customer = await Customer.filter(id=customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    # 获取所有订单
    orders = await Order.filter(customer_id=customer_id).order_by("created_at")
    # 获取所有回款
    payments = await Payment.filter(customer_id=customer_id).order_by("created_at")
    
    records = []
    for o in orders:
        records.append({
            "type": "order", "date": o.created_at.isoformat(),
            "order_no": o.order_no, "order_type": o.order_type,
            "amount": float(o.total_amount), "description": f"{o.order_type}订单"
        })
    for p in payments:
        records.append({
            "type": "payment", "date": p.created_at.isoformat(),
            "payment_no": p.payment_no,
            "amount": -float(p.amount), "description": f"回款-{p.payment_method}"
        })
    
    records.sort(key=lambda x: x["date"])
    
    return {
        "customer": {"id": customer.id, "name": customer.name, "balance": float(customer.balance)},
        "records": records
    }

# ==================== Dashboard API ====================
@app.get("/api/dashboard")
async def get_dashboard(user: User = Depends(get_current_user)):
    today = now().replace(hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = today - timedelta(days=30)
    
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])
    
    # 今日销售额（包含退货）
    today_orders = await Order.filter(
        created_at__gte=today,
        order_type__in=["CASH", "CREDIT", "CONSIGN_SETTLE"]
    )
    today_sales = sum(float(o.total_amount) for o in today_orders)
    
    # 今日毛利（销售毛利 - 退货毛利扣减）
    if has_finance:
        today_profit = sum(float(o.total_profit) for o in today_orders)
        # 扣减今日退货的毛利
        today_returns = await Order.filter(
            created_at__gte=today,
            order_type="RETURN"
        )
        return_profit_loss = sum(float(o.total_profit) for o in today_returns)  # 退货的profit是负数
        today_profit += return_profit_loss  # 加上负数 = 扣减
    else:
        today_profit = None
    
    # 库存总值（成本）
    all_stocks = await WarehouseStock.filter(quantity__gt=0).select_related("product", "warehouse")
    total_stock_value = sum(s.quantity * float(s.product.cost_price) for s in all_stocks if not s.warehouse.is_virtual)
    consignment_value = sum(s.quantity * float(s.product.cost_price) for s in all_stocks if s.warehouse.is_virtual)
    
    # 总应收
    total_receivable = await Customer.filter(is_active=True).annotate(total=Sum("balance")).values("total")
    total_receivable = float(total_receivable[0]["total"] or 0) if total_receivable else 0
    
    # 库龄分布
    normal_count, slow_count, dead_count = 0, 0, 0
    for s in all_stocks:
        if s.warehouse.is_virtual:
            continue
        age = days_between(now(), to_naive(s.weighted_entry_date)) if s.weighted_entry_date else 0
        if age < 30:
            normal_count += s.quantity
        elif age < 90:
            slow_count += s.quantity
        else:
            dead_count += s.quantity
    
    # Top 10 畅销商品（30天）
    order_items = await OrderItem.filter(
        order__created_at__gte=thirty_days_ago,
        order__order_type__in=["CASH", "CREDIT", "CONSIGN_SETTLE"]
    ).select_related("product")
    
    product_sales = {}
    for item in order_items:
        pid = item.product_id
        if pid not in product_sales:
            product_sales[pid] = {"name": item.product.name, "sku": item.product.sku, "quantity": 0, "amount": 0}
        product_sales[pid]["quantity"] += item.quantity
        product_sales[pid]["amount"] += float(item.amount)
    
    top_products = sorted(product_sales.values(), key=lambda x: x["quantity"], reverse=True)[:10]
    
    result = {
        "today_sales": today_sales,
        "total_receivable": total_receivable,
        "inventory_age": {"normal": normal_count, "slow": slow_count, "dead": dead_count},
        "top_products": top_products
    }
    
    if has_finance:
        result["today_profit"] = today_profit
        result["stock_value"] = total_stock_value
        result["consignment_value"] = consignment_value
    
    return result

# ==================== 寄售管理 API ====================
@app.get("/api/consignment/summary")
async def get_consignment_summary(user: User = Depends(get_current_user)):
    """获取寄售汇总数据"""
    # 从所有客户独立虚拟仓聚合库存
    stocks = await WarehouseStock.filter(warehouse__is_virtual=True, quantity__gt=0).select_related("product")

    # 获取所有寄售客户（有寄售调拨记录的客户）
    consign_orders = await Order.filter(order_type="CONSIGN_OUT").select_related("customer").distinct()
    customer_ids = list(set(o.customer_id for o in consign_orders if o.customer_id))

    # 按客户统计寄售库存价值
    customer_stats = {}
    total_settle_unpaid = 0  # 寄售结算总欠款

    for cid in customer_ids:
        customer = await Customer.filter(id=cid).first()
        if customer:
            cust_wh = await get_or_create_consignment_warehouse(cid)
            # 获取该客户的寄售调拨订单
            out_orders = await Order.filter(customer_id=cid, order_type="CONSIGN_OUT")
            settle_orders = await Order.filter(customer_id=cid, order_type="CONSIGN_SETTLE")

            total_out = sum(float(o.total_cost) for o in out_orders)
            total_settle = sum(float(o.total_cost) for o in settle_orders)

            # 计算退货成本：从CONSIGN_RETURN订单获取 + 兼容旧StockLog
            return_orders = await Order.filter(customer_id=cid, order_type="CONSIGN_RETURN")
            total_return = sum(float(o.total_cost) for o in return_orders)
            # 兼容旧数据
            old_return_logs = await StockLog.filter(
                change_type="CONSIGN_RETURN", reference_type="CONSIGN_RETURN",
                reference_id=cid, warehouse__is_virtual=True, quantity__lt=0
            ).select_related("product")
            for log in old_return_logs:
                product = await Product.filter(id=log.product_id).first()
                if product:
                    total_return += abs(log.quantity) * float(product.cost_price)

            # 计算该客户寄售结算的欠款（未结清的寄售结算订单）
            settle_unpaid = sum(float(o.total_amount - o.paid_amount) for o in settle_orders if not o.is_cleared)
            total_settle_unpaid += settle_unpaid

            customer_stats[cid] = {
                "customer_id": cid,
                "customer_name": customer.name,
                "total_out_cost": total_out,
                "total_settle_cost": total_settle,
                "total_return_cost": total_return,
                "remaining_cost": total_out - total_settle - total_return,
                "settle_unpaid": settle_unpaid,
                "balance": float(customer.balance)
            }

    # 寄售库存明细（聚合所有虚拟仓同商品库存）
    product_stock_map = {}
    for s in stocks:
        pid = s.product_id
        if pid not in product_stock_map:
            product_stock_map[pid] = {
                "product_id": pid,
                "product_sku": s.product.sku,
                "product_name": s.product.name,
                "quantity": 0,
                "cost_price": float(s.product.cost_price),
                "retail_price": float(s.product.retail_price),
            }
        product_stock_map[pid]["quantity"] += s.quantity
    stock_details = []
    for item in product_stock_map.values():
        item["total_cost"] = item["quantity"] * item["cost_price"]
        item["total_retail"] = item["quantity"] * item["retail_price"]
        stock_details.append(item)
    
    total_cost_value = sum(item["total_cost"] for item in stock_details)
    total_retail_value = sum(item["total_retail"] for item in stock_details)
    
    return {
        "total_cost_value": total_cost_value,
        "total_retail_value": total_retail_value,
        "total_settle_unpaid": total_settle_unpaid,
        "total_items": len(stock_details),
        "total_quantity": sum(s.quantity for s in stocks),
        "customer_stats": list(customer_stats.values()),
        "stock_details": stock_details
    }

@app.get("/api/consignment/customer/{customer_id}")
async def get_customer_consignment(customer_id: int, user: User = Depends(get_current_user)):
    """获取指定客户的寄售详情"""
    customer = await Customer.filter(id=customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")
    
    consignment_wh = await get_or_create_consignment_warehouse(customer_id)

    # 获取该客户的寄售调拨明细
    out_orders = await Order.filter(customer_id=customer_id, order_type="CONSIGN_OUT").order_by("-created_at")
    settle_orders = await Order.filter(customer_id=customer_id, order_type="CONSIGN_SETTLE").order_by("-created_at")

    # 统计各商品的寄售数量
    product_stats = {}

    for order in out_orders:
        items = await OrderItem.filter(order_id=order.id).select_related("product")
        for item in items:
            pid = item.product_id
            if pid not in product_stats:
                product_stats[pid] = {
                    "product_id": pid,
                    "product_sku": item.product.sku,
                    "product_name": item.product.name,
                    "out_quantity": 0,
                    "settle_quantity": 0,
                    "return_quantity": 0,
                    "remaining_quantity": 0,
                    "cost_price": float(item.cost_price),
                    "retail_price": float(item.product.retail_price)
                }
            product_stats[pid]["out_quantity"] += item.quantity

    for order in settle_orders:
        items = await OrderItem.filter(order_id=order.id).select_related("product")
        for item in items:
            pid = item.product_id
            if pid in product_stats:
                product_stats[pid]["settle_quantity"] += abs(item.quantity)

    # 统计退货数量：优先从CONSIGN_RETURN订单获取，兼容旧StockLog
    return_orders = await Order.filter(customer_id=customer_id, order_type="CONSIGN_RETURN")
    for order in return_orders:
        items = await OrderItem.filter(order_id=order.id).select_related("product")
        for item in items:
            pid = item.product_id
            if pid in product_stats:
                product_stats[pid]["return_quantity"] += abs(item.quantity)

    # 兼容旧数据：查旧格式StockLog（reference_type="CONSIGN_RETURN"的旧记录）
    return_logs = await StockLog.filter(
        change_type="CONSIGN_RETURN", reference_type="CONSIGN_RETURN",
        reference_id=customer_id, warehouse__is_virtual=True, quantity__lt=0
    ).select_related("product")
    for log in return_logs:
        pid = log.product_id
        if pid in product_stats:
            product_stats[pid]["return_quantity"] += abs(log.quantity)

    # 计算剩余：调拨出去 - 已结算 - 已退货
    for pid in product_stats:
        product_stats[pid]["remaining_quantity"] = (
            product_stats[pid]["out_quantity"] 
            - product_stats[pid]["settle_quantity"]
            - product_stats[pid]["return_quantity"]
        )
    
    # 过滤掉已结算完的商品
    remaining_products = [p for p in product_stats.values() if p["remaining_quantity"] > 0]
    
    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "balance": float(customer.balance)
        },
        "total_out_orders": len(out_orders),
        "total_settle_orders": len(settle_orders),
        "remaining_products": remaining_products,
        "out_orders": [{
            "id": o.id,
            "order_no": o.order_no,
            "total_amount": float(o.total_amount),
            "total_cost": float(o.total_cost),
            "created_at": o.created_at.isoformat()
        } for o in out_orders[:20]],
        "settle_orders": [{
            "id": o.id,
            "order_no": o.order_no,
            "total_amount": float(o.total_amount),
            "paid_amount": float(o.paid_amount),
            "is_cleared": o.is_cleared,
            "created_at": o.created_at.isoformat()
        } for o in settle_orders[:20]]
    }

@app.get("/api/consignment/customers")
async def get_consignment_customers(user: User = Depends(get_current_user)):
    """获取有寄售记录的客户列表"""
    # 查找有寄售调拨的客户
    orders = await Order.filter(order_type="CONSIGN_OUT").select_related("customer")
    customer_ids = list(set(o.customer_id for o in orders if o.customer_id))
    
    result = []
    for cid in customer_ids:
        customer = await Customer.filter(id=cid).first()
        if customer:
            cust_wh = await get_or_create_consignment_warehouse(cid)
            # 计算寄售统计
            out_orders = await Order.filter(customer_id=cid, order_type="CONSIGN_OUT")
            settle_orders = await Order.filter(customer_id=cid, order_type="CONSIGN_SETTLE")

            total_out = sum(float(o.total_cost) for o in out_orders)
            total_settle = sum(float(o.total_cost) for o in settle_orders)

            # 计算退货成本：从CONSIGN_RETURN订单获取 + 兼容旧StockLog
            return_orders = await Order.filter(customer_id=cid, order_type="CONSIGN_RETURN")
            total_return = sum(float(o.total_cost) for o in return_orders)
            old_return_logs = await StockLog.filter(
                change_type="CONSIGN_RETURN", reference_type="CONSIGN_RETURN",
                reference_id=cid, warehouse__is_virtual=True, quantity__lt=0
            ).select_related("product")
            for log in old_return_logs:
                product = await Product.filter(id=log.product_id).first()
                if product:
                    total_return += abs(log.quantity) * float(product.cost_price)

            result.append({
                "id": customer.id,
                "name": customer.name,
                "phone": customer.phone,
                "balance": float(customer.balance),
                "consign_out_count": len(out_orders),
                "consign_settle_count": len(settle_orders),
                "consign_out_cost": total_out,
                "consign_settle_cost": total_settle,
                "consign_return_cost": total_return,
                "consign_remaining_cost": total_out - total_settle - total_return
            })
    
    return result

@app.post("/api/consignment/return")
async def consignment_return(
    data: ConsignmentReturnRequest,
    user: User = Depends(get_current_user)
):
    """寄售退货：从虚拟仓调回实际仓库，同时生成寄售退货订单"""
    try:
        customer_id = data.customer_id
        items = data.items

        customer = await Customer.filter(id=customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail="客户不存在")

        consignment_wh = await get_or_create_consignment_warehouse(customer_id)
        order_no = generate_order_no("CSR")

        async with transactions.in_transaction():
            # 先创建订单
            order = await Order.create(
                order_no=order_no, order_type="CONSIGN_RETURN",
                customer=customer, warehouse=None,
                total_amount=Decimal("0"), total_cost=Decimal("0"), total_profit=Decimal("0"),
                is_cleared=True, creator=user
            )
            total_cost = Decimal("0")

            for item in items:
                product_id = item.product_id
                quantity = item.quantity
                warehouse_id = item.warehouse_id
                location_id = item.location_id

                product = await Product.filter(id=product_id).first()
                if not product:
                    raise HTTPException(status_code=404, detail=f"商品不存在: {product_id}")

                warehouse = await Warehouse.filter(id=warehouse_id, is_active=True).first()
                if not warehouse or warehouse.is_virtual:
                    raise HTTPException(status_code=400, detail="必须选择实体仓库")

                location = await Location.filter(id=location_id, is_active=True).first()
                if not location:
                    raise HTTPException(status_code=404, detail="仓位不存在")

                cost_price = product.cost_price
                item_cost = cost_price * quantity
                total_cost += item_cost

                # 创建订单项
                await OrderItem.create(
                    order=order, product=product, quantity=quantity,
                    unit_price=cost_price, cost_price=cost_price,
                    amount=item_cost, profit=Decimal("0"),
                    warehouse_id=warehouse_id, location_id=location_id
                )

                # 从虚拟仓扣减库存
                updated = await WarehouseStock.filter(
                    warehouse_id=consignment_wh.id, product_id=product_id, quantity__gte=quantity
                ).update(quantity=F('quantity') - quantity)
                if not updated:
                    raise HTTPException(status_code=400, detail=f"商品 {product.name} 在虚拟仓库存不足")
                virtual_stock = await WarehouseStock.filter(warehouse_id=consignment_wh.id, product_id=product_id).first()

                await StockLog.create(
                    product=product, warehouse=consignment_wh,
                    change_type="CONSIGN_RETURN", quantity=-quantity,
                    before_qty=virtual_stock.quantity + quantity, after_qty=virtual_stock.quantity,
                    reference_type="ORDER", reference_id=order.id,
                    creator=user, remark=f"寄售退货-{customer.name}"
                )

                # 添加到实体仓库
                await update_weighted_entry_date(warehouse_id, product_id, quantity, location_id=location_id)
                real_stock = await WarehouseStock.filter(
                    warehouse_id=warehouse_id, product_id=product_id, location_id=location_id
                ).first()

                await StockLog.create(
                    product=product, warehouse=warehouse,
                    change_type="CONSIGN_RETURN", quantity=quantity,
                    before_qty=real_stock.quantity - quantity, after_qty=real_stock.quantity,
                    reference_type="ORDER", reference_id=order.id,
                    creator=user, remark=f"寄售退货-{customer.name}"
                )

            # 更新订单合计
            order.total_amount = total_cost
            order.total_cost = total_cost
            await order.save()

            return {"message": "寄售退货成功", "count": len(items), "order_no": order_no}

    except HTTPException:
        raise
    except Exception as e:
        print(f"寄售退货错误: {str(e)}")
        traceback.print_exc()
        print(f"[ERROR] 寄售退货失败: {e}"); raise HTTPException(status_code=500, detail="寄售退货失败，请重试")

# ==================== 物流管理 API ====================
async def subscribe_kd100(carrier_code: str, tracking_no: str, order_id: int, shipment_id: int = None, phone: str = None):
    """订阅快递100物流推送"""
    if not KD100_KEY or not KD100_CUSTOMER:
        return {"returnCode": "500", "message": "KD100未配置"}
    cb_url = KD100_CALLBACK_URL + f"?order_id={order_id}"
    if shipment_id:
        cb_url += f"&shipment_id={shipment_id}"
    param_dict = {
        "company": carrier_code,
        "number": tracking_no,
        "key": KD100_KEY,
        "parameters": {
            "callbackurl": cb_url,
            "salt": KD100_KEY,
            "resultv2": "4"
        }
    }
    # 顺丰速运、顺丰快运必须传手机号
    if phone and carrier_code in PHONE_REQUIRED_CARRIERS:
        param_dict["parameters"]["phone"] = phone
    param = json.dumps(param_dict, ensure_ascii=False)
    sign = hashlib.md5((param + KD100_KEY + KD100_CUSTOMER).encode()).hexdigest().upper()
    async with httpx.AsyncClient() as client:
        resp = await client.post(KD100_POLL_URL, data={
            "schema": "json",
            "param": param,
            "sign": sign,
            "customer": KD100_CUSTOMER
        })
    return resp.json()

async def query_kd100(carrier_code: str, tracking_no: str, phone: str = None):
    """实时查询快递100物流信息"""
    if not KD100_KEY or not KD100_CUSTOMER:
        return {"message": "KD100未配置"}
    param_dict = {
        "com": carrier_code,
        "num": tracking_no,
        "resultv2": "4"
    }
    # 顺丰速运、顺丰快运必须传手机号
    if phone and carrier_code in PHONE_REQUIRED_CARRIERS:
        param_dict["phone"] = phone
    param = json.dumps(param_dict, ensure_ascii=False)
    sign = hashlib.md5((param + KD100_KEY + KD100_CUSTOMER).encode()).hexdigest().upper()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(KD100_QUERY_URL, data={
            "customer": KD100_CUSTOMER,
            "sign": sign,
            "param": param
        })
    return resp.json()

async def refresh_shipment_tracking(shipment) -> dict:
    """查询快递100并更新shipment记录，返回更新后的shipment信息"""
    if not shipment.carrier_code or not shipment.tracking_no:
        return None
    try:
        resp = await query_kd100(shipment.carrier_code, shipment.tracking_no, phone=shipment.phone)
        print(f"[KD100] 查询结果: state={resp.get('state')}, ischeck={resp.get('ischeck')}, message={resp.get('message')}, status={resp.get('status')}")
        if resp.get("message") == "ok" and resp.get("data"):
            tracking_data = resp["data"]
            state = str(resp.get("state", ""))
            # ischeck=1 表示已签收，优先判断
            if str(resp.get("ischeck")) == "1":
                shipment.status = "signed"
                shipment.status_text = "已签收"
            else:
                status_info = parse_kd100_state(state)
                shipment.status = status_info[0]
                shipment.status_text = status_info[1]
            shipment.last_tracking_info = json.dumps(tracking_data, ensure_ascii=False)
            await shipment.save()
            return {"tracking_info": tracking_data, "status": shipment.status, "status_text": shipment.status_text}
        print(f"快递100查询返回: {resp.get('message', '未知错误')}")
    except Exception as e:
        print(f"快递100查询失败: {e}")
    return None

@app.get("/api/logistics/carriers")
async def get_carriers(user: User = Depends(get_current_user)):
    return CARRIER_LIST

@app.get("/api/logistics")
async def list_shipments(status: Optional[str] = None, search: Optional[str] = None, user: User = Depends(get_current_user)):
    """物流列表 - 按订单分组，每个订单一行"""
    # 先按订单分组查询
    all_shipments = await Shipment.all().order_by("id").select_related("order")

    # 按 order_id 分组
    order_map = OrderedDict()
    for s in all_shipments:
        oid = s.order_id
        if oid not in order_map:
            order_map[oid] = []
        order_map[oid].append(s)

    result = []
    for oid, slist in order_map.items():
        order = slist[0].order
        await order.fetch_related("customer")

        # 第一个物流单作为主显示
        first = slist[0]

        # 状态筛选：基于第一个物流单
        if status and first.status != status:
            continue

        # 搜索过滤（多关键词模糊匹配）
        if search:
            keywords = search.lower().split()
            fields = [
                (order.order_no or "").lower(),
                (order.customer.name if order.customer else "").lower(),
            ] + [(s.tracking_no or "").lower() for s in slist] + [(s.carrier_name or "").lower() for s in slist]
            combined = " ".join(fields)
            combined_nospace = combined.replace(" ", "")
            if not all(w in combined or w in combined_nospace for w in keywords):
                continue

        # 第一个物流单的最后物流信息
        last_info = None
        if first.last_tracking_info:
            try:
                info_list = json.loads(first.last_tracking_info)
                if info_list:
                    last_info = info_list[0].get("context", "") or info_list[0].get("desc", "")
            except Exception:
                pass

        # 所有物流单的快递信息（用于复制）
        all_tracking = []
        for s in slist:
            if s.tracking_no:
                all_tracking.append({
                    "carrier_name": s.carrier_name or "",
                    "tracking_no": s.tracking_no,
                    "sn_code": s.sn_code or ""
                })

        result.append({
            "order_id": order.id,
            "order_no": order.order_no,
            "order_type": order.order_type,
            "customer_name": order.customer.name if order.customer else None,
            "total_amount": float(order.total_amount),
            "carrier_name": first.carrier_name,
            "tracking_no": first.tracking_no,
            "status": first.status,
            "status_text": first.status_text,
            "last_info": last_info,
            "shipment_count": len(slist),
            "all_tracking": all_tracking,
            "sn_status": "已添加" if any(s.sn_code for s in slist) else "未添加",
            "created_at": order.created_at.isoformat(),
            "updated_at": first.updated_at.isoformat()
        })

    # 按更新时间降序
    result.sort(key=lambda x: x["updated_at"], reverse=True)
    return result[:200]

def _shipment_to_dict(s, tracking_info=None):
    """Shipment 对象转字典"""
    ti = tracking_info
    if ti is None and s.last_tracking_info:
        try:
            ti = json.loads(s.last_tracking_info)
        except Exception:
            ti = []
    ti = ti or []
    return {
        "id": s.id,
        "order_id": s.order_id,
        "carrier_code": s.carrier_code,
        "carrier_name": s.carrier_name,
        "tracking_no": s.tracking_no,
        "phone": s.phone,
        "status": s.status,
        "status_text": s.status_text,
        "kd100_subscribed": s.kd100_subscribed,
        "sn_code": s.sn_code,
        "last_info": ti[0].get("context", "") if ti else None,
        "tracking_info": ti,
        "updated_at": s.updated_at.isoformat()
    }

@app.get("/api/logistics/{order_id}")
async def get_shipment_detail(order_id: int, user: User = Depends(get_current_user)):
    order = await Order.filter(id=order_id).select_related("customer", "warehouse", "creator", "salesperson").first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    items = await OrderItem.filter(order_id=order_id).select_related("product")
    shipment_list = await Shipment.filter(order_id=order_id).order_by("id").all()

    return {
        "order": {
            "id": order.id,
            "order_no": order.order_no,
            "order_type": order.order_type,
            "customer_name": order.customer.name if order.customer else None,
            "total_amount": float(order.total_amount),
            "salesperson_name": order.salesperson.name if order.salesperson else None,
            "creator_name": order.creator.display_name if order.creator else None,
            "created_at": order.created_at.isoformat(),
            "remark": order.remark,
            "items": [{
                "product_name": i.product.name,
                "product_sku": i.product.sku,
                "quantity": i.quantity,
                "unit_price": float(i.unit_price),
                "amount": float(i.amount)
            } for i in items]
        },
        "shipments": [_shipment_to_dict(s) for s in shipment_list]
    }

@app.post("/api/logistics/{order_id}/add")
async def add_shipment(order_id: int, data: ShipmentUpdate, user: User = Depends(require_permission("logistics", "sales"))):
    """为订单添加新物流单"""
    order = await Order.filter(id=order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    is_self_pickup = data.carrier_code == "self_pickup"
    shipment = await Shipment.create(
        order=order,
        carrier_code=data.carrier_code,
        carrier_name=data.carrier_name,
        tracking_no=data.tracking_no or None,
        phone=data.phone or None,
        sn_code=data.sn_code or None,
        status="signed" if is_self_pickup else "shipped",
        status_text="已自提" if is_self_pickup else "已发货"
    )

    # SN码池扣减
    if data.sn_codes:
        await validate_and_consume_sn_codes(data.sn_codes, shipment, user)

    tracking_info = []
    if not is_self_pickup and data.tracking_no:
        # 实时查询物流信息
        result = await refresh_shipment_tracking(shipment)
        if result:
            tracking_info = result.get("tracking_info", [])

        # 尝试订阅快递100推送
        try:
            resp = await subscribe_kd100(data.carrier_code, data.tracking_no, order_id, shipment.id, phone=shipment.phone)
            if resp.get("returnCode") == "200" or resp.get("result") is True:
                shipment.kd100_subscribed = True
                await shipment.save()
        except Exception:
            pass

    return {"message": "已标记自提完成" if is_self_pickup else "物流单已添加", "shipment": _shipment_to_dict(shipment, tracking_info)}

@app.put("/api/logistics/shipment/{shipment_id}/ship")
async def ship_order(shipment_id: int, data: ShipmentUpdate, user: User = Depends(require_permission("logistics", "sales"))):
    shipment = await Shipment.filter(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="物流记录不存在")

    is_self_pickup = data.carrier_code == "self_pickup"
    tracking_changed = (shipment.tracking_no != data.tracking_no) or (shipment.carrier_code != data.carrier_code)

    shipment.carrier_code = data.carrier_code
    shipment.carrier_name = data.carrier_name
    shipment.tracking_no = data.tracking_no or None
    shipment.phone = data.phone or shipment.phone
    shipment.sn_code = data.sn_code if data.sn_code is not None else shipment.sn_code
    shipment.status = "signed" if is_self_pickup else "shipped"
    shipment.status_text = "已自提" if is_self_pickup else "已发货"

    if tracking_changed:
        shipment.last_tracking_info = None
        shipment.kd100_subscribed = False

    await shipment.save()

    tracking_info = []
    if not is_self_pickup and data.tracking_no and tracking_changed:
        result = await refresh_shipment_tracking(shipment)
        if result:
            tracking_info = result.get("tracking_info", [])

        # 订阅推送
        try:
            resp = await subscribe_kd100(data.carrier_code, data.tracking_no, shipment.order_id, shipment.id, phone=shipment.phone)
            if resp.get("returnCode") == "200" or resp.get("result") is True:
                shipment.kd100_subscribed = True
                await shipment.save()
        except Exception:
            pass

    return {"message": "已标记自提完成" if is_self_pickup else "发货信息已保存", "shipment": _shipment_to_dict(shipment, tracking_info)}

@app.post("/api/logistics/shipment/{shipment_id}/update-sn")
async def update_shipment_sn(shipment_id: int, data: SNCodeUpdate, user: User = Depends(require_permission("logistics", "sales"))):
    """独立更新物流单SN码"""
    shipment = await Shipment.filter(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="物流记录不存在")

    async with transactions.in_transaction():
        # 释放旧SN码
        old_sn_objs = await SnCode.filter(shipment_id=shipment_id, status="shipped").all()
        for sn_obj in old_sn_objs:
            sn_obj.status = "in_stock"
            sn_obj.shipment = None
            sn_obj.ship_date = None
            sn_obj.ship_user = None
            await sn_obj.save()

        # 绑定新SN码
        if data.sn_codes:
            await validate_and_consume_sn_codes(data.sn_codes, shipment, user)

        shipment.sn_code = data.sn_code or None
        await shipment.save()

    return {"message": "SN码已保存", "shipment": _shipment_to_dict(shipment)}

@app.delete("/api/logistics/shipment/{shipment_id}")
async def delete_shipment(shipment_id: int, user: User = Depends(require_permission("logistics", "sales"))):
    shipment = await Shipment.filter(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="物流记录不存在")
    await shipment.delete()
    return {"message": "物流单已删除"}

@app.post("/api/logistics/shipment/{shipment_id}/refresh")
async def refresh_shipment(shipment_id: int, user: User = Depends(get_current_user)):
    """实时查询快递100获取最新物流信息"""
    shipment = await Shipment.filter(id=shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="物流记录不存在")
    if not shipment.carrier_code or not shipment.tracking_no:
        raise HTTPException(status_code=400, detail="请先填写快递信息")

    result = await refresh_shipment_tracking(shipment)
    if result:
        return {"message": "物流信息已更新", "shipment": _shipment_to_dict(shipment)}
    raise HTTPException(status_code=400, detail="未查询到物流信息，请检查快递公司和单号是否正确")

@app.post("/api/logistics/kd100/callback")
async def kd100_callback(request: Request, order_id: Optional[int] = None, shipment_id: Optional[int] = None):
    """快递100回调接口"""
    form = await request.form()
    param_str = form.get("param", "")
    sign_received = form.get("sign", "")

    expected_sign = hashlib.md5((param_str + KD100_KEY).encode()).hexdigest().upper()
    if sign_received != expected_sign:
        return {"result": False, "returnCode": "500", "message": "签名验证失败"}

    try:
        param = json.loads(param_str)
        state = str(param.get("state", ""))
        tracking_no = param.get("lastResult", {}).get("nu", "")
        tracking_data = param.get("lastResult", {}).get("data", [])

        # 优先用 shipment_id 匹配，其次用 tracking_no
        shipment = None
        if shipment_id:
            shipment = await Shipment.filter(id=shipment_id).first()
        elif tracking_no:
            shipment = await Shipment.filter(tracking_no=tracking_no).first()
        elif order_id:
            shipment = await Shipment.filter(order_id=order_id).first()

        if shipment:
            if str(param.get("lastResult", {}).get("ischeck")) == "1":
                shipment.status = "signed"
                shipment.status_text = "已签收"
            else:
                status_info = parse_kd100_state(state)
                shipment.status = status_info[0]
                shipment.status_text = status_info[1]
            shipment.last_tracking_info = json.dumps(tracking_data, ensure_ascii=False)
            await shipment.save()
    except Exception as e:
        print(f"快递100回调处理错误: {e}")

    return {"result": True, "returnCode": "200", "message": "成功"}

# ==================== 数据库备份 API ====================
@app.post("/api/backup")
async def create_backup(user: User = Depends(require_permission("admin"))):
    """手动创建备份（仅管理员）"""
    try:
        path = do_backup("manual")
        size = os.path.getsize(path)
        return {"message": "备份成功", "filename": os.path.basename(path), "size_mb": round(size / 1024 / 1024, 2)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"备份失败: {e}")

@app.get("/api/backups")
async def list_backups(user: User = Depends(require_permission("admin"))):
    """获取备份列表（仅管理员）"""
    backup_dir = get_backup_dir()
    if not backup_dir:
        return []
    files = glob.glob(os.path.join(backup_dir, "erp_*.db"))
    result = []
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        stat = os.stat(f)
        result.append({
            "filename": os.path.basename(f),
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    return result

@app.get("/api/backups/{filename}")
async def download_backup(filename: str, user: User = Depends(require_permission("admin"))):
    """下载备份文件（仅管理员）"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    backup_dir = get_backup_dir()
    if not backup_dir:
        raise HTTPException(status_code=404, detail="备份目录不存在")
    filepath = os.path.join(backup_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="备份文件不存在")
    def iter_file():
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                yield chunk
    return StreamingResponse(iter_file(), media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})

@app.delete("/api/backups/{filename}")
async def delete_backup(filename: str, user: User = Depends(require_permission("admin"))):
    """删除备份文件（仅管理员）"""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    backup_dir = get_backup_dir()
    if not backup_dir:
        raise HTTPException(status_code=404, detail="备份目录不存在")
    filepath = os.path.join(backup_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="备份文件不存在")
    os.remove(filepath)
    return {"message": "删除成功"}

# ==================== 收款方式管理 API ====================
@app.get("/api/payment-methods")
async def list_payment_methods(user: User = Depends(get_current_user)):
    """获取收款方式列表"""
    methods = await PaymentMethod.filter(is_active=True).order_by("sort_order", "id")
    return [{"id": m.id, "code": m.code, "name": m.name, "sort_order": m.sort_order} for m in methods]

@app.post("/api/payment-methods")
async def create_payment_method(request: Request, user: User = Depends(require_permission("finance"))):
    """新增收款方式"""
    data = await request.json()
    code = data.get("code", "").strip()
    name = data.get("name", "").strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="编码和名称不能为空")
    if await PaymentMethod.filter(code=code).exists():
        raise HTTPException(status_code=400, detail="编码已存在")
    max_sort = await PaymentMethod.all().order_by("-sort_order").first()
    sort_order = (max_sort.sort_order + 1) if max_sort else 1
    m = await PaymentMethod.create(code=code, name=name, sort_order=sort_order)
    return {"id": m.id, "message": "添加成功"}

@app.put("/api/payment-methods/{method_id}")
async def update_payment_method(method_id: int, request: Request, user: User = Depends(require_permission("finance"))):
    """修改收款方式"""
    m = await PaymentMethod.filter(id=method_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="收款方式不存在")
    data = await request.json()
    if "name" in data and data["name"].strip():
        m.name = data["name"].strip()
    if "code" in data and data["code"].strip():
        if data["code"] != m.code and await PaymentMethod.filter(code=data["code"]).exists():
            raise HTTPException(status_code=400, detail="编码已存在")
        m.code = data["code"].strip()
    await m.save()
    return {"message": "更新成功"}

@app.delete("/api/payment-methods/{method_id}")
async def delete_payment_method(method_id: int, user: User = Depends(require_permission("finance"))):
    """删除收款方式（软删除）"""
    m = await PaymentMethod.filter(id=method_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="收款方式不存在")
    m.is_active = False
    await m.save()
    return {"message": "删除成功"}

# ==================== 返利管理 API ====================
@app.get("/api/rebates/summary")
async def get_rebate_summary(target_type: str, user: User = Depends(require_permission("finance"))):
    """返利汇总（有余额的客户/供应商列表）"""
    if target_type == "customer":
        items = await Customer.filter(is_active=True).order_by("name")
        return [{"id": c.id, "name": c.name, "rebate_balance": float(c.rebate_balance)} for c in items]
    elif target_type == "supplier":
        items = await Supplier.filter(is_active=True).order_by("-created_at")
        return [{"id": s.id, "name": s.name, "rebate_balance": float(s.rebate_balance)} for s in items]
    else:
        raise HTTPException(status_code=400, detail="target_type 必须是 customer 或 supplier")

@app.get("/api/rebates/logs")
async def get_rebate_logs(target_type: str, target_id: int, user: User = Depends(require_permission("finance"))):
    """返利流水明细"""
    logs = await RebateLog.filter(target_type=target_type, target_id=target_id).order_by("-created_at").select_related("creator")
    return [{
        "id": l.id, "type": l.type, "amount": float(l.amount),
        "balance_after": float(l.balance_after),
        "reference_type": l.reference_type, "reference_id": l.reference_id,
        "remark": l.remark,
        "creator_name": l.creator.display_name if l.creator else None,
        "created_at": l.created_at.isoformat()
    } for l in logs]

@app.post("/api/rebates/charge")
async def charge_rebate(data: RebateChargeRequest, user: User = Depends(require_permission("finance"))):
    """返利充值"""
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="充值金额必须大于0")
    async with transactions.in_transaction():
        if data.target_type == "customer":
            target = await Customer.filter(id=data.target_id, is_active=True).first()
            if not target:
                raise HTTPException(status_code=404, detail="客户不存在")
            await Customer.filter(id=data.target_id).update(rebate_balance=F('rebate_balance') + data.amount)
            await target.refresh_from_db()
            target_name = target.name
        elif data.target_type == "supplier":
            target = await Supplier.filter(id=data.target_id, is_active=True).first()
            if not target:
                raise HTTPException(status_code=404, detail="供应商不存在")
            await Supplier.filter(id=data.target_id).update(rebate_balance=F('rebate_balance') + data.amount)
            await target.refresh_from_db()
            target_name = target.name
        else:
            raise HTTPException(status_code=400, detail="target_type 必须是 customer 或 supplier")

        await RebateLog.create(
            target_type=data.target_type, target_id=data.target_id,
            type="charge", amount=data.amount,
            balance_after=target.rebate_balance,
            remark=data.remark, creator=user
        )
        await log_operation(user, "REBATE_CHARGE", data.target_type.upper(), data.target_id,
            f"返利充值 {target_name} ¥{float(data.amount):.2f}，余额 ¥{float(target.rebate_balance):.2f}")
    return {"message": "充值成功", "balance": float(target.rebate_balance)}

# ==================== 供应商 API ====================
@app.get("/api/suppliers")
async def list_suppliers(user: User = Depends(require_permission("purchase"))):
    suppliers = await Supplier.filter(is_active=True).order_by("-created_at")
    return [{"id": s.id, "name": s.name, "contact_person": s.contact_person, "phone": s.phone,
             "tax_id": s.tax_id, "bank_account": s.bank_account, "bank_name": s.bank_name,
             "address": s.address, "rebate_balance": float(s.rebate_balance), "created_at": s.created_at.isoformat()} for s in suppliers]

@app.post("/api/suppliers")
async def create_supplier(data: SupplierRequest, user: User = Depends(require_permission("purchase"))):
    s = await Supplier.create(**data.model_dump())
    await log_operation(user, "SUPPLIER_CREATE", "SUPPLIER", s.id, f"新增供应商 {data.name}")
    return {"id": s.id, "message": "创建成功"}

@app.put("/api/suppliers/{supplier_id}")
async def update_supplier(supplier_id: int, data: SupplierRequest, user: User = Depends(require_permission("purchase"))):
    s = await Supplier.filter(id=supplier_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="供应商不存在")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data:
        await Supplier.filter(id=supplier_id).update(**update_data)
    return {"message": "更新成功"}

@app.delete("/api/suppliers/{supplier_id}")
async def delete_supplier(supplier_id: int, user: User = Depends(require_permission("purchase"))):
    s = await Supplier.filter(id=supplier_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="供应商不存在")
    s.is_active = False
    await s.save()
    return {"message": "删除成功"}

# ==================== 采购订单 API ====================
@app.get("/api/purchase-orders")
async def list_purchase_orders(status: Optional[str] = None, start_date: Optional[str] = None,
                                end_date: Optional[str] = None, search: Optional[str] = None,
                                user: User = Depends(require_permission("purchase", "purchase_approve", "purchase_pay", "purchase_receive"))):
    query = PurchaseOrder.all()
    if status:
        query = query.filter(status=status)
    if start_date:
        query = query.filter(created_at__gte=datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(created_at__lte=datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
    if search:
        query = query.filter(Q(po_no__icontains=search) | Q(supplier__name__icontains=search))
    orders = await query.order_by("-created_at").select_related("supplier", "creator", "paid_by",
                                                                  "reviewed_by", "target_warehouse", "target_location")
    return [{
        "id": o.id, "po_no": o.po_no, "supplier_id": o.supplier_id,
        "supplier_name": o.supplier.name if o.supplier else "",
        "status": o.status, "total_amount": float(o.total_amount),
        "target_warehouse_name": o.target_warehouse.name if o.target_warehouse else None,
        "target_location_code": o.target_location.code if o.target_location else None,
        "remark": o.remark,
        "creator_name": o.creator.display_name if o.creator else None,
        "reviewed_by_name": o.reviewed_by.display_name if o.reviewed_by else None,
        "reviewed_at": o.reviewed_at.isoformat() if o.reviewed_at else None,
        "paid_by_name": o.paid_by.display_name if o.paid_by else None,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "created_at": o.created_at.isoformat(),
    } for o in orders]

@app.get("/api/purchase-orders/export")
async def export_purchase_orders(status: Optional[str] = None, start_date: Optional[str] = None,
                                  end_date: Optional[str] = None, search: Optional[str] = None,
                                  user: User = Depends(require_permission("purchase", "finance"))):
    """导出采购订单到CSV（含商品明细）"""
    query = PurchaseOrder.all()
    if status:
        query = query.filter(status=status)
    if start_date:
        query = query.filter(created_at__gte=datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(created_at__lte=datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
    if search:
        query = query.filter(Q(po_no__icontains=search) | Q(supplier__name__icontains=search))
    orders = await query.order_by("-created_at").select_related(
        "supplier", "creator", "paid_by", "reviewed_by", "target_warehouse", "target_location")

    status_names = {
        "pending_review": "待审核", "pending": "待付款", "paid": "在途",
        "partial": "部分到货", "completed": "已完成", "cancelled": "已取消", "rejected": "已拒绝"
    }

    def csv_safe(val):
        s = str(val).replace('"', '""')
        if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
            s = "'" + s
        return f'"{s}"'

    output = io.StringIO()
    output.write('\ufeff')
    headers = ["采购单号", "供应商", "状态", "总金额", "目标仓库", "备注", "创建人", "审核人", "审核时间", "付款人", "付款时间", "创建时间",
               "商品SKU", "商品名称", "数量", "含税单价", "税率", "不含税单价", "小计金额", "已收货数量"]
    output.write(','.join(headers) + '\n')

    for o in orders:
        order_base = [
            o.po_no,
            o.supplier.name if o.supplier else "-",
            status_names.get(o.status, o.status),
            f"{float(o.total_amount):.2f}",
            o.target_warehouse.name if o.target_warehouse else "-",
            (o.remark or "").replace('\n', ' '),
            o.creator.display_name if o.creator else "-",
            o.reviewed_by.display_name if o.reviewed_by else "-",
            o.reviewed_at.strftime("%Y-%m-%d %H:%M") if o.reviewed_at else "-",
            o.paid_by.display_name if o.paid_by else "-",
            o.paid_at.strftime("%Y-%m-%d %H:%M") if o.paid_at else "-",
            o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        ]
        items = await PurchaseOrderItem.filter(purchase_order_id=o.id).select_related("product")
        if items:
            for it in items:
                row = order_base + [
                    it.product.sku if it.product else "-",
                    it.product.name if it.product else "-",
                    str(it.quantity),
                    f"{float(it.tax_inclusive_price):.2f}",
                    f"{float(it.tax_rate * 100):.0f}%",
                    f"{float(it.tax_exclusive_price):.2f}",
                    f"{float(it.amount):.2f}",
                    str(it.received_quantity),
                ]
                output.write(','.join(csv_safe(item) for item in row) + '\n')
        else:
            row = order_base + ["-"] * 8
            output.write(','.join(csv_safe(item) for item in row) + '\n')

    output.seek(0)
    filename = f"采购订单_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    )

@app.post("/api/purchase-orders")
async def create_purchase_order(data: PurchaseOrderCreate, user: User = Depends(require_permission("purchase"))):
    if not data.items:
        raise HTTPException(status_code=400, detail="请添加采购明细")
    supplier = await Supplier.filter(id=data.supplier_id, is_active=True).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    po_no = generate_order_no("PO")
    async with transactions.in_transaction():
        po = await PurchaseOrder.create(
            po_no=po_no, supplier=supplier, status="pending_review",
            target_warehouse_id=data.target_warehouse_id,
            target_location_id=data.target_location_id,
            remark=data.remark, creator=user
        )
        total = Decimal("0")
        total_rebate = Decimal("0")
        for item in data.items:
            product = await Product.filter(id=item.product_id, is_active=True).first()
            if not product:
                raise HTTPException(status_code=404, detail=f"商品ID {item.product_id} 不存在")
            item_rebate = Decimal(str(item.rebate_amount)) if item.rebate_amount else Decimal("0")
            raw_amount = round(item.tax_inclusive_price * item.quantity, 2)
            if item_rebate > 0:
                if item_rebate > raw_amount:
                    raise HTTPException(status_code=400, detail=f"商品 {product.name} 返利金额不能超过行金额")
                amount = raw_amount - item_rebate
                total_rebate += item_rebate
            else:
                amount = raw_amount
            tax_exclusive = round(amount / item.quantity / (1 + item.tax_rate), 2)
            await PurchaseOrderItem.create(
                purchase_order=po, product=product,
                quantity=item.quantity, tax_inclusive_price=item.tax_inclusive_price,
                tax_rate=item.tax_rate, tax_exclusive_price=tax_exclusive,
                amount=amount, rebate_amount=item_rebate,
                target_warehouse_id=item.target_warehouse_id,
                target_location_id=item.target_location_id
            )
            total += amount
        # 处理返利扣减
        if total_rebate > 0:
            await supplier.refresh_from_db()
            if supplier.rebate_balance < total_rebate:
                raise HTTPException(status_code=400, detail=f"供应商返利余额不足，可用 ¥{float(supplier.rebate_balance):.2f}，需要 ¥{float(total_rebate):.2f}")
            await Supplier.filter(id=supplier.id).update(rebate_balance=F('rebate_balance') - total_rebate)
            await supplier.refresh_from_db()
            po.rebate_used = total_rebate
            rebate_remark = f"[返利抵扣] 使用返利 ¥{float(total_rebate):.2f}"
            po.remark = f"{po.remark}\n{rebate_remark}" if po.remark else rebate_remark
            await RebateLog.create(
                target_type="supplier", target_id=supplier.id,
                type="use", amount=total_rebate,
                balance_after=supplier.rebate_balance,
                reference_type="PURCHASE_ORDER", reference_id=po.id,
                remark=f"采购单 {po_no} 使用返利", creator=user
            )
        po.total_amount = total
        await po.save()
        await log_operation(user, "PURCHASE_CREATE", "PURCHASE_ORDER", po.id,
            f"创建采购单 {po_no}，供应商 {supplier.name}，金额 ¥{float(total):.2f}")
    return {"id": po.id, "po_no": po_no, "message": "采购订单创建成功"}

@app.get("/api/purchase-orders/receivable")
async def list_receivable_orders(user: User = Depends(require_permission("purchase_receive"))):
    orders = await PurchaseOrder.filter(status__in=["paid", "partial"]).order_by("-created_at") \
        .select_related("supplier", "target_warehouse", "target_location")
    result = []
    for o in orders:
        items = await PurchaseOrderItem.filter(purchase_order_id=o.id).select_related(
            "product", "target_warehouse", "target_location")
        item_list = [{
            "id": it.id, "product_id": it.product_id,
            "product_name": f"{it.product.sku} - {it.product.name}" if it.product else "",
            "quantity": it.quantity, "received_quantity": it.received_quantity,
            "pending_quantity": it.quantity - it.received_quantity,
            "tax_inclusive_price": float(it.tax_inclusive_price),
            "target_warehouse_id": it.target_warehouse_id or o.target_warehouse_id,
            "target_warehouse_name": (it.target_warehouse.name if it.target_warehouse else
                                       o.target_warehouse.name if o.target_warehouse else None),
            "target_location_id": it.target_location_id or o.target_location_id,
            "target_location_code": (it.target_location.code if it.target_location else
                                      o.target_location.code if o.target_location else None),
        } for it in items if it.received_quantity < it.quantity]
        if item_list:
            result.append({
                "id": o.id, "po_no": o.po_no,
                "supplier_name": o.supplier.name if o.supplier else "",
                "status": o.status, "total_amount": float(o.total_amount),
                "items": item_list
            })
    return result

@app.get("/api/purchase-orders/{po_id}")
async def get_purchase_order(po_id: int, user: User = Depends(require_permission("purchase", "purchase_approve", "purchase_pay", "purchase_receive"))):
    po = await PurchaseOrder.filter(id=po_id).select_related(
        "supplier", "creator", "paid_by", "reviewed_by", "target_warehouse", "target_location").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    items = await PurchaseOrderItem.filter(purchase_order_id=po.id).select_related(
        "product", "target_warehouse", "target_location")
    return {
        "id": po.id, "po_no": po.po_no,
        "supplier_id": po.supplier_id,
        "supplier_name": po.supplier.name if po.supplier else "",
        "status": po.status, "total_amount": float(po.total_amount),
        "rebate_used": float(po.rebate_used),
        "target_warehouse_id": po.target_warehouse_id,
        "target_warehouse_name": po.target_warehouse.name if po.target_warehouse else None,
        "target_location_id": po.target_location_id,
        "target_location_code": po.target_location.code if po.target_location else None,
        "remark": po.remark,
        "creator_name": po.creator.display_name if po.creator else None,
        "reviewed_by_name": po.reviewed_by.display_name if po.reviewed_by else None,
        "reviewed_at": po.reviewed_at.isoformat() if po.reviewed_at else None,
        "paid_by_name": po.paid_by.display_name if po.paid_by else None,
        "paid_at": po.paid_at.isoformat() if po.paid_at else None,
        "created_at": po.created_at.isoformat(),
        "items": [{
            "id": it.id, "product_id": it.product_id,
            "product_sku": it.product.sku if it.product else "",
            "product_name": it.product.name if it.product else "",
            "quantity": it.quantity,
            "tax_inclusive_price": float(it.tax_inclusive_price),
            "tax_rate": float(it.tax_rate),
            "tax_exclusive_price": float(it.tax_exclusive_price),
            "amount": float(it.amount),
            "rebate_amount": float(it.rebate_amount) if it.rebate_amount else 0,
            "received_quantity": it.received_quantity,
            "target_warehouse_name": (it.target_warehouse.name if it.target_warehouse else
                                       po.target_warehouse.name if po.target_warehouse else None),
            "target_location_code": (it.target_location.code if it.target_location else
                                      po.target_location.code if po.target_location else None),
        } for it in items]
    }

# ==================== 应付管理 API ====================
@app.post("/api/purchase-orders/{po_id}/pay")
async def confirm_purchase_payment(po_id: int, user: User = Depends(require_permission("purchase_pay"))):
    po = await PurchaseOrder.filter(id=po_id).select_related("supplier").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    if po.status != "pending":
        raise HTTPException(status_code=400, detail="该采购单不是待付款状态")
    po.status = "paid"
    po.paid_by = user
    po.paid_at = now()
    await po.save()
    await log_operation(user, "PURCHASE_PAY", "PURCHASE_ORDER", po.id,
        f"确认付款 {po.po_no}，供应商 {po.supplier.name}，金额 ¥{float(po.total_amount):.2f}")
    return {"message": "付款确认成功"}

@app.post("/api/purchase-orders/{po_id}/approve")
async def approve_purchase_order(po_id: int, user: User = Depends(require_permission("purchase_approve"))):
    po = await PurchaseOrder.filter(id=po_id).select_related("supplier").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    if po.status != "pending_review":
        raise HTTPException(status_code=400, detail="该采购单不是待审核状态")
    po.status = "pending"
    po.reviewed_by = user
    po.reviewed_at = now()
    await po.save()
    await log_operation(user, "PURCHASE_APPROVE", "PURCHASE_ORDER", po.id,
        f"审核通过采购单 {po.po_no}，供应商 {po.supplier.name}，金额 ¥{float(po.total_amount):.2f}")
    return {"message": "审核通过"}

@app.post("/api/purchase-orders/{po_id}/reject")
async def reject_purchase_order(po_id: int, user: User = Depends(require_permission("purchase_approve"))):
    po = await PurchaseOrder.filter(id=po_id).select_related("supplier").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    if po.status != "pending_review":
        raise HTTPException(status_code=400, detail="该采购单不是待审核状态")
    po.status = "rejected"
    po.reviewed_by = user
    po.reviewed_at = now()
    await po.save()
    await log_operation(user, "PURCHASE_REJECT", "PURCHASE_ORDER", po.id,
        f"拒绝采购单 {po.po_no}，供应商 {po.supplier.name}，金额 ¥{float(po.total_amount):.2f}")
    return {"message": "已拒绝"}

@app.post("/api/purchase-orders/{po_id}/cancel")
async def cancel_purchase_order(po_id: int, user: User = Depends(require_permission("purchase_pay"))):
    po = await PurchaseOrder.filter(id=po_id).select_related("supplier").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    if po.status not in ("pending_review", "pending"):
        raise HTTPException(status_code=400, detail="只有待审核或待付款状态的采购单才能取消")
    po.status = "cancelled"
    await po.save()
    await log_operation(user, "PURCHASE_CANCEL", "PURCHASE_ORDER", po.id,
        f"取消采购单 {po.po_no}，供应商 {po.supplier.name}，金额 ¥{float(po.total_amount):.2f}")
    return {"message": "采购单已取消"}

# ==================== 采购收货 API ====================
@app.post("/api/purchase-orders/{po_id}/receive")
async def receive_purchase_order(po_id: int, data: ReceiveRequest, user: User = Depends(require_permission("purchase_receive"))):
    po = await PurchaseOrder.filter(id=po_id).select_related("supplier").first()
    if not po:
        raise HTTPException(status_code=404, detail="采购订单不存在")
    if po.status not in ("paid", "partial"):
        raise HTTPException(status_code=400, detail="该采购单不可收货（需为已付款或部分到货状态）")

    async with transactions.in_transaction():
        received_details = []
        for recv_item in data.items:
            if recv_item.receive_quantity <= 0:
                continue
            poi = await PurchaseOrderItem.filter(id=recv_item.item_id, purchase_order_id=po.id).select_related("product").first()
            if not poi:
                raise HTTPException(status_code=404, detail=f"采购明细 {recv_item.item_id} 不存在")
            pending = poi.quantity - poi.received_quantity
            if recv_item.receive_quantity > pending:
                raise HTTPException(status_code=400, detail=f"{poi.product.name} 本次收货数量({recv_item.receive_quantity})超过待收数量({pending})")

            # 确定目标仓库/仓位
            wh_id = recv_item.warehouse_id or poi.target_warehouse_id or po.target_warehouse_id
            loc_id = recv_item.location_id or poi.target_location_id or po.target_location_id
            if not wh_id or not loc_id:
                raise HTTPException(status_code=400, detail=f"{poi.product.name} 缺少目标仓库或仓位")

            warehouse = await Warehouse.filter(id=wh_id, is_active=True, is_virtual=False).first()
            if not warehouse:
                raise HTTPException(status_code=404, detail="目标仓库不存在")
            location = await Location.filter(id=loc_id, is_active=True).first()
            if not location:
                raise HTTPException(status_code=404, detail="目标仓位不存在")

            # 使用返利后的有效单价作为入库成本
            cost_price = poi.amount / poi.quantity if poi.quantity > 0 else poi.tax_inclusive_price

            # SN码检查
            sn_required = await check_sn_required(wh_id, poi.product_id)
            if sn_required and not recv_item.sn_codes:
                raise HTTPException(status_code=400, detail=f"{poi.product.name} 已启用SN管理，收货时必须填写SN码")
            if sn_required and recv_item.sn_codes:
                await validate_and_add_sn_codes(
                    recv_item.sn_codes, wh_id, poi.product_id, loc_id,
                    recv_item.receive_quantity, "PURCHASE_IN", cost_price, user, po.id
                )

            # 获取当前库存
            stock = await WarehouseStock.filter(warehouse_id=wh_id, product_id=poi.product_id, location_id=loc_id).first()
            before_qty = stock.quantity if stock else 0

            # 更新加权入库日期和成本
            await update_weighted_entry_date(wh_id, poi.product_id, recv_item.receive_quantity, cost_price, loc_id)

            # 重新获取更新后的库存
            stock = await WarehouseStock.filter(warehouse_id=wh_id, product_id=poi.product_id, location_id=loc_id).first()

            # 更新商品默认成本价
            product = await Product.filter(id=poi.product_id).first()
            if product and stock:
                product.cost_price = stock.weighted_cost
                await product.save()

            # 记录库存日志
            await StockLog.create(
                product_id=poi.product_id, warehouse_id=wh_id,
                change_type="PURCHASE_IN", quantity=recv_item.receive_quantity,
                before_qty=before_qty, after_qty=stock.quantity if stock else recv_item.receive_quantity,
                reference_type="PURCHASE_ORDER", reference_id=po.id,
                remark=f"采购收货 {po.po_no}，仓位:{location.code}，成本:¥{float(cost_price)}",
                creator=user
            )

            # 更新明细行已收数量
            poi.received_quantity += recv_item.receive_quantity
            await poi.save()
            received_details.append(f"{poi.product.name}×{recv_item.receive_quantity}")

        # 判断整体状态
        all_items = await PurchaseOrderItem.filter(purchase_order_id=po.id).all()
        all_received = all(it.received_quantity >= it.quantity for it in all_items)
        any_received = any(it.received_quantity > 0 for it in all_items)

        if all_received:
            po.status = "completed"
        elif any_received:
            po.status = "partial"
        await po.save()

        await log_operation(user, "PURCHASE_RECEIVE", "PURCHASE_ORDER", po.id,
            f"采购收货 {po.po_no}，{', '.join(received_details)}，状态→{po.status}")

    return {"message": "收货成功", "status": po.status}

# ==================== 操作日志 API ====================
@app.get("/api/operation-logs")
async def list_operation_logs(action: Optional[str] = None, limit: int = 200, user: User = Depends(require_permission("admin"))):
    """查询操作日志（仅管理员）"""
    limit = min(limit, 1000)
    query = OperationLog.all()
    if action:
        query = query.filter(action=action)
    logs = await query.order_by("-created_at").limit(limit).select_related("operator")
    return [{
        "id": l.id, "action": l.action,
        "target_type": l.target_type, "target_id": l.target_id,
        "detail": l.detail,
        "operator_name": l.operator.display_name if l.operator else None,
        "created_at": l.created_at.isoformat()
    } for l in logs]

# ==================== 系统设置 API ====================
@app.get("/api/settings/{key}")
async def get_setting(key: str, user: User = Depends(get_current_user)):
    setting = await SystemSetting.filter(key=key).first()
    return {"key": key, "value": setting.value if setting else None}

@app.put("/api/settings/{key}")
async def update_setting(key: str, request: Request, user: User = Depends(require_permission("settings", "finance"))):
    body = await request.json()
    value = body.get("value", "")
    setting = await SystemSetting.filter(key=key).first()
    if setting:
        setting.value = value
        await setting.save()
    else:
        await SystemSetting.create(key=key, value=value)
    return {"ok": True}

# ==================== SN码管理 API ====================
@app.get("/api/sn-configs")
async def list_sn_configs(user: User = Depends(require_permission("settings", "admin"))):
    """获取SN配置列表"""
    configs = await SnConfig.filter(is_active=True).select_related("warehouse").order_by("-created_at")
    return [{"id": c.id, "warehouse_id": c.warehouse_id, "warehouse_name": c.warehouse.name if c.warehouse else "", "brand": c.brand} for c in configs]

@app.post("/api/sn-configs")
async def create_sn_config(data: SnConfigCreate, user: User = Depends(require_permission("settings", "admin"))):
    """创建SN配置"""
    warehouse = await Warehouse.filter(id=data.warehouse_id, is_active=True, is_virtual=False).first()
    if not warehouse:
        raise HTTPException(status_code=404, detail="仓库不存在")
    if not data.brand or not data.brand.strip():
        raise HTTPException(status_code=400, detail="品牌不能为空")
    existing = await SnConfig.filter(warehouse_id=data.warehouse_id, brand=data.brand.strip()).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=400, detail="该仓库+品牌配置已存在")
        existing.is_active = True
        await existing.save()
        return {"id": existing.id, "message": "配置已恢复"}
    config = await SnConfig.create(warehouse_id=data.warehouse_id, brand=data.brand.strip())
    return {"id": config.id, "message": "配置已创建"}

@app.delete("/api/sn-configs/{config_id}")
async def delete_sn_config(config_id: int, user: User = Depends(require_permission("settings", "admin"))):
    """删除SN配置（软删除）"""
    config = await SnConfig.filter(id=config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    config.is_active = False
    await config.save()
    return {"message": "配置已删除"}

@app.get("/api/sn-codes/check-required")
async def check_sn_required_api(warehouse_id: int, product_id: int, user: User = Depends(get_current_user)):
    """检查是否需要SN码"""
    required = await check_sn_required(warehouse_id, product_id)
    return {"required": required}

@app.get("/api/sn-codes/available")
async def list_available_sn_codes(warehouse_id: int, product_id: int, user: User = Depends(require_permission("stock_view", "logistics", "sales"))):
    """查询可用SN码"""
    codes = await SnCode.filter(warehouse_id=warehouse_id, product_id=product_id, status="in_stock").order_by("entry_date")
    return [{"id": c.id, "sn_code": c.sn_code, "entry_date": c.entry_date.isoformat() if c.entry_date else None} for c in codes]

@app.get("/api/product-brands")
async def list_product_brands(user: User = Depends(get_current_user)):
    """返回products表中distinct brand列表"""
    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != '' AND is_active=1 ORDER BY brand")
    return [row[0] if hasattr(row, '__getitem__') else str(row) for row in (rows[1] if rows else [])]

# ==================== 凭证 API ====================
@app.get("/api/vouchers/by-source")
async def get_voucher_by_source(source_type: str, source_id: int, user: User = Depends(require_permission("finance"))):
    voucher = await Voucher.filter(source_type=source_type, source_id=source_id).first()
    if not voucher:
        return {"exists": False}
    entries = await VoucherEntry.filter(voucher=voucher).order_by("seq")
    return {
        "exists": True,
        "voucher": {
            "id": voucher.id,
            "voucher_no": voucher.voucher_no,
            "voucher_type": voucher.voucher_type,
            "voucher_date": voucher.voucher_date.isoformat() if voucher.voucher_date else None,
            "company_name": voucher.company_name,
            "total_debit": float(voucher.total_debit),
            "total_credit": float(voucher.total_credit),
            "tax_rate": float(voucher.tax_rate),
            "remark": voucher.remark,
            "creator_name": (await voucher.creator).display_name if voucher.creator_id else None,
            "created_at": voucher.created_at.isoformat() if voucher.created_at else None,
            "entries": [{
                "seq": e.seq, "summary": e.summary, "account": e.account,
                "debit_amount": float(e.debit_amount), "credit_amount": float(e.credit_amount)
            } for e in entries]
        }
    }

@app.post("/api/vouchers/generate")
async def generate_voucher(request: Request, user: User = Depends(require_permission("finance"))):
    body = await request.json()
    source_type = body.get("source_type")
    source_id = body.get("source_id")
    tax_rate = Decimal(str(body.get("tax_rate", "0.13")))

    # 检查是否已存在
    existing = await Voucher.filter(source_type=source_type, source_id=source_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="该单据已生成凭证")

    # 获取公司名称
    company_setting = await SystemSetting.filter(key="company_name").first()
    company_name = company_setting.value if company_setting else ""

    entries = []
    voucher_type = "转"

    if source_type == "ORDER":
        order = await Order.filter(id=source_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        customer = await order.customer if order.customer_id else None
        customer_name = customer.name if customer else "未知客户"
        items = await OrderItem.filter(order=order).select_related("product")
        total_amount = float(order.total_amount)

        if tax_rate > 0:
            tax_amount = round(total_amount / (1 + float(tax_rate)) * float(tax_rate), 2)
            revenue_before_tax = round(total_amount - tax_amount, 2)
        else:
            tax_amount = 0
            revenue_before_tax = total_amount

        seq = 1
        # 借：应收账款
        entries.append({"seq": seq, "summary": f"应收款-{customer_name}", "account": f"应收账款_{customer_name}", "debit_amount": total_amount, "credit_amount": 0})
        seq += 1

        if tax_amount > 0:
            # 贷：应交税费
            entries.append({"seq": seq, "summary": "结转销项税金", "account": "应交税费_应交增值税_销项税额", "debit_amount": 0, "credit_amount": tax_amount})
            seq += 1

        # 贷：主营业务收入（按商品拆分）
        total_item_revenue = 0
        for idx, item in enumerate(items):
            product_name = item.product.name if item.product else "商品"
            item_amount = float(item.amount)
            if tax_rate > 0:
                item_revenue = round(item_amount / (1 + float(tax_rate)), 2)
            else:
                item_revenue = item_amount
            # 最后一项用差额法避免尾差
            if idx == len(items) - 1 and len(items) > 1:
                item_revenue = round(revenue_before_tax - total_item_revenue, 2)
            total_item_revenue += item_revenue
            entries.append({"seq": seq, "summary": f"确认收入-{product_name}", "account": f"主营业务收入_商品销售_{product_name}", "debit_amount": 0, "credit_amount": item_revenue})
            seq += 1

        # 借：主营业务成本 / 贷：发出商品
        for item in items:
            product_name = item.product.name if item.product else "商品"
            item_cost = float(item.cost_price) * item.quantity
            if item_cost > 0:
                entries.append({"seq": seq, "summary": f"结转商品成本-{product_name}", "account": f"主营业务成本_商品销售_{product_name}", "debit_amount": item_cost, "credit_amount": 0})
                seq += 1
                entries.append({"seq": seq, "summary": f"销售出库-{product_name}", "account": f"发出商品_{product_name}", "debit_amount": 0, "credit_amount": item_cost})
                seq += 1
        voucher_type = "转"

    elif source_type == "PURCHASE_PAY":
        po = await PurchaseOrder.filter(id=source_id).first()
        if not po:
            raise HTTPException(status_code=404, detail="采购订单不存在")
        supplier = await po.supplier if po.supplier_id else None
        supplier_name = supplier.name if supplier else "未知供应商"
        total_amount = float(po.total_amount)
        entries = [
            {"seq": 1, "summary": f"往来款-{supplier_name}转款", "account": f"应付账款_{supplier_name}", "debit_amount": total_amount, "credit_amount": 0},
            {"seq": 2, "summary": f"往来款-{supplier_name}转款", "account": "银行存款", "debit_amount": 0, "credit_amount": total_amount},
        ]
        voucher_type = "付"

    elif source_type == "PAYMENT":
        payment = await Payment.filter(id=source_id).first()
        if not payment:
            raise HTTPException(status_code=404, detail="收款记录不存在")
        customer = await payment.customer if payment.customer_id else None
        customer_name = customer.name if customer else "未知客户"
        amount = float(payment.amount)
        entries = [
            {"seq": 1, "summary": "收到货款", "account": "银行存款", "debit_amount": amount, "credit_amount": 0},
            {"seq": 2, "summary": "收到货款", "account": f"应收账款_{customer_name}", "debit_amount": 0, "credit_amount": amount},
        ]
        voucher_type = "收"
    else:
        raise HTTPException(status_code=400, detail=f"不支持的来源类型: {source_type}")

    # 计算借贷合计
    total_debit = round(sum(e["debit_amount"] for e in entries), 2)
    total_credit = round(sum(e["credit_amount"] for e in entries), 2)

    # 生成凭证编号
    type_map = {"转": "转字", "收": "收字", "付": "付字"}
    type_prefix = type_map.get(voucher_type, "转字")
    last_voucher = await Voucher.filter(voucher_type=voucher_type).order_by("-seq_number").first()
    seq_number = (last_voucher.seq_number + 1) if last_voucher else 1
    voucher_no = f"{type_prefix}第{seq_number}号"

    # 创建凭证
    voucher = await Voucher.create(
        voucher_no=voucher_no,
        voucher_type=voucher_type,
        seq_number=seq_number,
        source_type=source_type,
        source_id=source_id,
        voucher_date=now().date(),
        company_name=company_name,
        total_debit=Decimal(str(total_debit)),
        total_credit=Decimal(str(total_credit)),
        tax_rate=tax_rate,
        remark=body.get("remark"),
        creator=user
    )

    # 创建分录
    for e in entries:
        await VoucherEntry.create(
            voucher=voucher,
            seq=e["seq"],
            summary=e["summary"],
            account=e["account"],
            debit_amount=Decimal(str(e["debit_amount"])),
            credit_amount=Decimal(str(e["credit_amount"]))
        )

    await log_operation(user, "VOUCHER_CREATE", "voucher", voucher.id, f"生成凭证 {voucher_no}")

    return {
        "id": voucher.id,
        "voucher_no": voucher.voucher_no,
        "voucher_type": voucher.voucher_type,
        "voucher_date": voucher.voucher_date.isoformat(),
        "company_name": voucher.company_name,
        "total_debit": float(voucher.total_debit),
        "total_credit": float(voucher.total_credit),
        "tax_rate": float(voucher.tax_rate),
        "creator_name": user.display_name,
        "created_at": voucher.created_at.isoformat() if voucher.created_at else None,
        "entries": entries
    }

@app.get("/api/vouchers/{voucher_id}")
async def get_voucher(voucher_id: int, user: User = Depends(require_permission("finance"))):
    voucher = await Voucher.filter(id=voucher_id).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="凭证不存在")
    entries = await VoucherEntry.filter(voucher=voucher).order_by("seq")
    creator = await voucher.creator if voucher.creator_id else None
    return {
        "id": voucher.id,
        "voucher_no": voucher.voucher_no,
        "voucher_type": voucher.voucher_type,
        "voucher_date": voucher.voucher_date.isoformat() if voucher.voucher_date else None,
        "company_name": voucher.company_name,
        "total_debit": float(voucher.total_debit),
        "total_credit": float(voucher.total_credit),
        "tax_rate": float(voucher.tax_rate),
        "remark": voucher.remark,
        "creator_name": creator.display_name if creator else None,
        "created_at": voucher.created_at.isoformat() if voucher.created_at else None,
        "entries": [{
            "seq": e.seq, "summary": e.summary, "account": e.account,
            "debit_amount": float(e.debit_amount), "credit_amount": float(e.credit_amount)
        } for e in entries]
    }

# ==================== 前端页面 ====================
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>请确保 index.html 文件存在</h1>"

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
