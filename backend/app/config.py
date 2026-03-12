"""
ERP 系统配置
"""
import os
import secrets
import logging

# 数据库配置 - PostgreSQL
def get_database_url():
    url = os.environ.get("DATABASE_URL")
    return url if url else "postgres://erp@localhost:5432/erp"

DATABASE_URL = get_database_url()

# JWT 配置
_default_secret = secrets.token_hex(32)
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = _default_secret
    logging.getLogger("erp.config").warning("SECRET_KEY 未设置环境变量，已自动生成随机密钥（重启后所有用户需重新登录）")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# 寄售虚拟仓名称
CONSIGNMENT_WAREHOUSE_NAME = "__寄售虚拟仓__"

# 备份配置
BACKUP_KEEP_DAYS = int(os.environ.get("BACKUP_KEEP_DAYS", "30"))
BACKUP_HOUR = int(os.environ.get("BACKUP_HOUR", "3"))

# 文件上传根目录
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(os.path.join(UPLOAD_ROOT, "invoices"), exist_ok=True)

# 快递100配置
KD100_KEY = os.environ.get("KD100_KEY", "")
KD100_CUSTOMER = os.environ.get("KD100_CUSTOMER", "")
KD100_POLL_URL = "https://poll.kuaidi100.com/poll"
KD100_QUERY_URL = "https://poll.kuaidi100.com/poll/query.do"
KD100_CALLBACK_URL = os.environ.get("KD100_CALLBACK_URL", "")

# CORS（生产环境请设置 CORS_ORIGINS 环境变量为前端域名，如 "https://erp.example.com"）
_cors_raw = os.environ.get("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()] if _cors_raw else ["http://localhost:5173", "http://localhost:8090"]

# 快递公司列表
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
    {"code": "kuayue", "name": "跨越速运"},
    {"code": "youzhengguonei", "name": "中国邮政"},
]

# 需要手机号才能查询的快递公司
PHONE_REQUIRED_CARRIERS = {"shunfeng", "shunfengkuaiyun", "zhongtong"}

# 快递100状态映射
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

# 登录限制
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300

# AI 数据库只读用户密码
AI_DB_PASSWORD = os.environ.get("AI_DB_PASSWORD", "")
