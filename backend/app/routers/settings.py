from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import get_current_user, require_permission
from app.models import User, SystemSetting
from app.schemas.settings import SettingUpdate

router = APIRouter(prefix="/api/settings", tags=["系统设置"])

# 允许读写的 settings key 白名单
ALLOWED_KEYS = {"company_name", "voucher_maker_checker"}


@router.get("/{key}")
async def get_setting(key: str, user: User = Depends(get_current_user)):
    if key not in ALLOWED_KEYS:
        raise HTTPException(status_code=400, detail=f"不支持的配置项: {key}")
    setting = await SystemSetting.filter(key=key).first()
    return {"key": key, "value": setting.value if setting else None}


@router.put("/{key}")
async def update_setting(key: str, body: SettingUpdate, user: User = Depends(require_permission("admin"))):
    if key not in ALLOWED_KEYS:
        raise HTTPException(status_code=400, detail=f"不支持的配置项: {key}")
    setting = await SystemSetting.filter(key=key).first()
    if setting:
        setting.value = body.value
        await setting.save()
    else:
        await SystemSetting.create(key=key, value=body.value)
    return {"ok": True}
