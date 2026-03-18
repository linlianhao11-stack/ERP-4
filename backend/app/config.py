"""
ERP 系统配置
"""
import os
import secrets
import logging

_logger = logging.getLogger("erp.config")

# 调试模式
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

# 数据库配置 - PostgreSQL
def get_database_url():
    url = os.environ.get("DATABASE_URL")
    return url if url else "postgres://erp@localhost:5432/erp"

DATABASE_URL = get_database_url()

# JWT 配置
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = secrets.token_hex(32)
        _logger.warning("SECRET_KEY 未设置环境变量，DEBUG 模式下已自动生成随机密钥（重启后所有用户需重新登录）")
    else:
        raise RuntimeError("SECRET_KEY must be set via environment variable")
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
# 生产环境应设置为实际域名（如 "https://erp.example.com"），不应包含 localhost
_cors_raw = os.environ.get("CORS_ORIGINS", "")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()] if _cors_raw else ["http://localhost:5173", "http://localhost:8090"]

# CORS 生产环境校验：未设置或包含 localhost 时发出警告（不阻止启动，因内网部署可能合理使用 localhost）
if not DEBUG:
    if not _cors_raw:
        _logger.warning("CORS_ORIGINS 未设置，默认允许 localhost。生产环境请设置为实际前端域名")
    elif any("localhost" in o or "127.0.0.1" in o for o in CORS_ORIGINS):
        _logger.warning("CORS_ORIGINS 包含 localhost/127.0.0.1 地址，请确认是否为生产环境")

# 备份加密密钥（Phase 1.5 预留，可选）
BACKUP_ENCRYPTION_KEY = os.environ.get("BACKUP_ENCRYPTION_KEY", "")

# 快递公司列表
CARRIER_LIST = [
    {"code": "self_pickup", "name": "上门自提"},
    {"code": "self_delivery", "name": "自配送"},
    {"code": "shunfeng", "name": "顺丰速运"},
    {"code": "shunfengkuaiyun", "name": "顺丰快运"},
    {"code": "yuantong", "name": "圆通速递"},
    {"code": "zhongtong", "name": "中通快递"},
    {"code": "zhongtongkuaiyun", "name": "中通快运"},
    {"code": "yunda", "name": "韵达快递"},
    {"code": "yundakuaiyun", "name": "韵达快运"},
    {"code": "shentong", "name": "申通快递"},
    {"code": "ems", "name": "EMS"},
    {"code": "jd", "name": "京东物流"},
    {"code": "jtexpress", "name": "极兔速递"},
    {"code": "debangkuaidi", "name": "德邦快递"},
    {"code": "huitongkuaidi", "name": "百世快递"},
    {"code": "tiantian", "name": "天天快递"},
    {"code": "youzhengguonei", "name": "中国邮政"},
    {"code": "youzhengbk", "name": "邮政标准快递"},
    {"code": "kuayue", "name": "跨越速运"},
    {"code": "fengwang", "name": "丰网速运"},
    {"code": "annengwuliu", "name": "安能快运"},
    {"code": "yimidida", "name": "壹米滴答"},
    {"code": "ztky", "name": "中铁快运"},
    {"code": "zhaijisong", "name": "宅急送"},
    {"code": "guotongkuaidi", "name": "国通快递"},
    {"code": "jiayunmeiwuliu", "name": "加运美"},
    {"code": "xinfengwuliu", "name": "信丰物流"},
    {"code": "jinguangsudikuaijian", "name": "京广速递"},
]

# 无需物流跟踪的配送方式（自提/自配送）
NO_LOGISTICS_CARRIERS = {"self_pickup", "self_delivery"}

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

# 密码过期天数（0 表示不过期）
PASSWORD_EXPIRY_DAYS = int(os.environ.get("PASSWORD_EXPIRY_DAYS", "90"))

# AI 数据库只读用户密码
AI_DB_PASSWORD = os.environ.get("AI_DB_PASSWORD", "")


def build_ai_dsn() -> str:
    """构建 AI 只读用户的数据库连接字符串"""
    import re
    from urllib.parse import quote_plus
    match = re.match(r'postgres(?:ql)?://[^@]+@([^/]+)/([\w-]+)', DATABASE_URL)
    if not match:
        raise RuntimeError("无法解析 DATABASE_URL")
    host_port = match.group(1)
    dbname = match.group(2)
    if not AI_DB_PASSWORD:
        raise RuntimeError("AI_DB_PASSWORD 环境变量未设置，无法连接 AI 只读数据库")
    return f"postgresql://erp_ai_readonly:{quote_plus(AI_DB_PASSWORD)}@{host_port}/{dbname}"
