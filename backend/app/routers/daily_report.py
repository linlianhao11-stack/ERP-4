"""日报邮件配置与手动触发"""
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.auth.dependencies import require_permission
from app.models import User, SystemSetting
from app.ai.encryption import encrypt_value, decrypt_value
from app.config import build_ai_dsn
from app.services.daily_report_service import CONFIG_KEYS
from app.logger import get_logger

logger = get_logger("daily_report")

router = APIRouter(prefix="/api/daily-report", tags=["日报邮件"])


class DailyReportConfig(BaseModel):
    enabled: bool = False
    send_time: str = "21:00"
    recipients: list[str] = []
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: Optional[str] = None
    from_email: str = ""
    from_name: str = "ERP系统"


@router.get("/config")
async def get_config(user: User = Depends(require_permission("admin"))):
    settings = await SystemSetting.filter(key__in=CONFIG_KEYS)
    cfg = {s.key: s.value for s in settings}
    return {
        "enabled": cfg.get("daily_report.enabled") == "true",
        "send_time": cfg.get("daily_report.send_time", "21:00"),
        "recipients": json.loads(cfg["daily_report.recipients"]) if cfg.get("daily_report.recipients") else [],
        "smtp_host": cfg.get("daily_report.smtp_host", ""),
        "smtp_port": int(cfg.get("daily_report.smtp_port", "465")),
        "smtp_user": cfg.get("daily_report.smtp_user", ""),
        "smtp_password_set": bool(cfg.get("daily_report.smtp_password")),
        "from_email": cfg.get("daily_report.from_email", ""),
        "from_name": cfg.get("daily_report.from_name", "ERP系统"),
        "last_sent_date": cfg.get("daily_report.last_sent_date"),
    }


@router.put("/config")
async def update_config(data: DailyReportConfig, user: User = Depends(require_permission("admin"))):
    pairs = {
        "daily_report.enabled": "true" if data.enabled else "false",
        "daily_report.send_time": data.send_time,
        "daily_report.recipients": json.dumps(data.recipients),
        "daily_report.smtp_host": data.smtp_host,
        "daily_report.smtp_port": str(data.smtp_port),
        "daily_report.smtp_user": data.smtp_user,
        "daily_report.from_email": data.from_email,
        "daily_report.from_name": data.from_name,
    }
    if data.smtp_password is not None:
        pairs["daily_report.smtp_password"] = encrypt_value(data.smtp_password)

    for key, value in pairs.items():
        setting = await SystemSetting.filter(key=key).first()
        if setting:
            setting.value = value
            await setting.save()
        else:
            await SystemSetting.create(key=key, value=value)
    return {"ok": True}


@router.post("/test")
async def test_send(user: User = Depends(require_permission("admin"))):
    """发送测试邮件到第一个收件人"""
    from app.services.email_service import send_email

    cfg_rows = await SystemSetting.filter(key__in=CONFIG_KEYS)
    cfg = {s.key: s.value for s in cfg_rows}

    recipients = json.loads(cfg.get("daily_report.recipients", "[]"))
    if not recipients:
        raise HTTPException(status_code=400, detail="未配置收件人")
    smtp_password = decrypt_value(cfg.get("daily_report.smtp_password", ""))
    if not smtp_password:
        raise HTTPException(status_code=400, detail="未配置 SMTP 密码")

    try:
        await send_email(
            smtp_host=cfg.get("daily_report.smtp_host", ""),
            smtp_port=int(cfg.get("daily_report.smtp_port", "465")),
            smtp_user=cfg.get("daily_report.smtp_user", ""),
            smtp_password=smtp_password,
            from_email=cfg.get("daily_report.from_email", ""),
            from_name=cfg.get("daily_report.from_name", "ERP系统"),
            to_email=recipients[0].strip(),
            subject="ERP 日报邮件 — 测试",
            html_body="<h2>测试邮件</h2><p>如果你看到这封邮件，说明 SMTP 配置正确。</p>",
        )
        return {"ok": True, "message": f"测试邮件已发送到 {recipients[0]}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)[:200]}")


@router.post("/send-now")
async def send_now(user: User = Depends(require_permission("admin"))):
    """立即发送一次日报"""
    from app.services.daily_report_service import generate_and_send_report

    try:
        dsn = build_ai_dsn()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        await generate_and_send_report(dsn, force=True)
        return {"ok": True, "message": "日报已发送"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)[:200]}")
