from app.models import OperationLog
from app.logger import get_logger

logger = get_logger("audit")

# 安全相关的操作类型
SECURITY_ACTIONS = {
    "LOGIN_FAIL", "LOGIN_SUCCESS", "PASSWORD_CHANGE",
    "USER_CREATE", "USER_TOGGLE",
    "BACKUP_CREATE", "BACKUP_RESTORE", "BACKUP_DELETE",
}


async def log_operation(user, action, target_type, target_id=None, detail=None):
    try:
        await OperationLog.create(
            action=action, target_type=target_type,
            target_id=target_id, detail=detail, operator=user
        )
    except Exception as e:
        logger.error(f"记录操作日志失败: {e}", exc_info=e)
    if action in SECURITY_ACTIONS:
        username = user.username if hasattr(user, "username") else str(user)
        logger.info(f"[安全审计] {action} by {username}: {detail}")
