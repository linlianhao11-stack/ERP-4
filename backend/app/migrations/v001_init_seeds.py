"""v001 — 初始化种子数据

创建默认收款方式、付款方式、管理员用户、默认仓库。
"""
from __future__ import annotations

from app.auth.password import hash_password
from app.logger import get_logger
from app.models import DisbursementMethod, PaymentMethod, User, Warehouse

logger = get_logger("migrations")


async def up(conn):
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
        logger.info("默认收款方式已初始化")

    # 初始化默认付款方式
    if not await DisbursementMethod.exists():
        defaults = [
            ("bank_public", "对公转账", 1),
            ("bank_private", "对私转账", 2),
            ("wechat", "微信", 3),
            ("alipay", "支付宝", 4),
            ("cash", "现金", 5),
        ]
        for code, name, sort in defaults:
            await DisbursementMethod.create(code=code, name=name, sort_order=sort)
        logger.info("默认付款方式已初始化")

    # 创建默认管理员
    admin = await User.filter(username="admin").first()
    if not admin:
        await User.create(
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="系统管理员",
            role="admin",
            must_change_password=True,
            permissions=["dashboard", "sales", "stock_view", "stock_edit", "finance",
                         "logs", "admin", "purchase", "purchase_pay", "purchase_receive",
                         "purchase_approve"]
        )
        logger.info("默认管理员已创建: admin（首次登录需修改密码）")

    # 创建默认仓库
    default_wh = await Warehouse.filter(is_default=True).first()
    if not default_wh:
        default_wh = await Warehouse.create(name="默认仓库", is_default=True)
        logger.info("默认仓库已创建")
