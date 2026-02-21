"""编号生成工具"""
import secrets
from datetime import datetime


def generate_order_no(prefix: str = "ORD"):
    """生成订单号：前缀 + 时间戳 + 6字节随机串。数据库 unique 约束是最终防线。"""
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(6).upper()}"
