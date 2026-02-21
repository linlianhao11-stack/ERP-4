from typing import Optional
from fastapi import APIRouter, Depends
from app.auth.dependencies import require_permission
from app.models import User, OperationLog

router = APIRouter(prefix="/api/operation-logs", tags=["操作日志"])


@router.get("")
async def list_operation_logs(action: Optional[str] = None, limit: int = 200, user: User = Depends(require_permission("logs", "admin"))):
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
