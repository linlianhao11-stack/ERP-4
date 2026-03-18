from app.models import OperationLog
from app.logger import get_logger

logger = get_logger("audit")

# 安全相关的操作类型（双写：DB + 安全日志文件）
SECURITY_ACTIONS = {
    # 认证
    "LOGIN_FAIL", "LOGIN_SUCCESS", "PASSWORD_CHANGE",
    # 用户管理
    "USER_CREATE", "USER_TOGGLE", "USER_ROLE_CHANGE", "USER_PERMISSION_CHANGE",
    # 备份
    "BACKUP_CREATE", "BACKUP_RESTORE", "BACKUP_DELETE", "BACKUP_DOWNLOAD",
    # 删除操作
    "CUSTOMER_DELETE", "SUPPLIER_DELETE", "PRODUCT_DELETE",
    "VOUCHER_DELETE", "SHIPMENT_DELETE", "ORDER_CANCEL",
    # 发票
    "INVOICE_CANCEL",
    # 数据导出
    "PRODUCT_EXPORT", "STOCK_EXPORT", "VOUCHER_EXPORT",
    "REPORT_EXPORT", "LEDGER_EXPORT", "ORDER_EXPORT",
    "DEMO_EXPORT", "AI_EXPORT",
    # 批量操作
    "VOUCHER_BATCH_SUBMIT", "VOUCHER_BATCH_APPROVE", "VOUCHER_BATCH_POST",
    "DROPSHIP_BATCH_PAY",
    # 财务关键
    "VOUCHER_POST", "VOUCHER_UNPOST",
}


async def log_operation(user, action, target_type, target_id=None, detail=None):
    try:
        await OperationLog.create(
            action=action, target_type=target_type,
            target_id=target_id, detail=detail,
            operator=user  # 允许 None（如 LOGIN_FAIL）
        )
    except Exception as e:
        logger.error(f"记录操作日志失败: {e}", exc_info=e)
    if action in SECURITY_ACTIONS:
        username = user.username if user and hasattr(user, "username") else "(匿名)"
        logger.info(f"[安全审计] {action} by {username}: {detail}")
