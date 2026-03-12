"""API 密钥 + AI 配置管理路由（仅 admin 角色）"""
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth.dependencies import require_permission
from app.models import User, SystemSetting
from app.ai.encryption import encrypt_value, decrypt_value, mask_key
from app.ai.deepseek_client import test_connection
from app.services.ai_chat_service import invalidate_config_cache
from app.logger import get_logger

logger = get_logger("api_keys")
router = APIRouter(prefix="/api/api-keys", tags=["API密钥管理"])

# 允许通过此接口管理的 key 白名单
MANAGED_KEYS = {
    "ai.deepseek.api_key",
    "ai.deepseek.base_url",
    "ai.deepseek.model_sql",
    "ai.deepseek.model_analysis",
    "api.kd100.key",
    "api.kd100.customer",
}

# 需要加密存储的 key
ENCRYPTED_KEYS = {"ai.deepseek.api_key", "api.kd100.key"}


@router.get("")
async def get_api_keys(user: User = Depends(require_permission("admin"))):
    """获取所有 API 配置（密钥脱敏）"""
    result = {}
    for key in MANAGED_KEYS:
        setting = await SystemSetting.filter(key=key).first()
        if setting and setting.value:
            if key in ENCRYPTED_KEYS:
                decrypted = decrypt_value(setting.value)
                result[key] = mask_key(decrypted) if decrypted else ""
            else:
                result[key] = setting.value
        else:
            result[key] = ""
    return result


@router.put("")
async def update_api_keys(body: dict, user: User = Depends(require_permission("admin"))):
    """更新 API 密钥配置"""
    updated = []
    for key, value in body.items():
        if key not in MANAGED_KEYS:
            continue
        if value is None or value == "":
            # 清空配置
            await SystemSetting.filter(key=key).delete()
            updated.append(key)
            continue
        # 如果值是脱敏的（含 ***），跳过不更新
        if "***" in str(value):
            continue
        # 加密敏感值
        store_value = encrypt_value(value) if key in ENCRYPTED_KEYS else value
        setting = await SystemSetting.filter(key=key).first()
        if setting:
            setting.value = store_value
            await setting.save()
        else:
            await SystemSetting.create(key=key, value=store_value)
        updated.append(key)

    invalidate_config_cache()
    logger.info(f"API 密钥已更新: {updated}（操作人: {user.username}）")
    return {"ok": True, "updated": updated}


@router.post("/test-deepseek")
async def test_deepseek_connection(user: User = Depends(require_permission("admin"))):
    """测试 DeepSeek API 连接"""
    api_key_setting = await SystemSetting.filter(key="ai.deepseek.api_key").first()
    if not api_key_setting or not api_key_setting.value:
        raise HTTPException(status_code=400, detail="请先配置 DeepSeek API Key")

    api_key = decrypt_value(api_key_setting.value)
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 解密失败，请重新设置")

    base_url_setting = await SystemSetting.filter(key="ai.deepseek.base_url").first()
    base_url = base_url_setting.value if base_url_setting and base_url_setting.value else "https://api.deepseek.com"

    success, msg = await test_connection(api_key, base_url)
    return {"success": success, "message": msg}


# ===== AI 配置管理 =====

@router.get("/ai-config")
async def get_ai_config(user: User = Depends(require_permission("admin"))):
    """获取 AI 配置（提示词、词典、示例、快捷问题）"""
    result = {}
    for key in ["ai.prompt.system", "ai.prompt.analysis", "ai.business_dict", "ai.few_shots", "ai.preset_queries"]:
        setting = await SystemSetting.filter(key=key).first()
        if setting and setting.value:
            if key in ("ai.business_dict", "ai.few_shots", "ai.preset_queries"):
                try:
                    result[key] = json.loads(setting.value)
                except json.JSONDecodeError:
                    result[key] = None
            else:
                result[key] = setting.value
        else:
            result[key] = None
    return result


@router.put("/ai-config")
async def update_ai_config(body: dict, user: User = Depends(require_permission("admin"))):
    """更新 AI 配置"""
    allowed_keys = {"ai.prompt.system", "ai.prompt.analysis", "ai.business_dict", "ai.few_shots", "ai.preset_queries"}
    updated = []
    for key, value in body.items():
        if key not in allowed_keys:
            continue
        # JSON 类型的配置序列化存储
        if key in ("ai.business_dict", "ai.few_shots", "ai.preset_queries"):
            store_value = json.dumps(value, ensure_ascii=False) if value else None
        else:
            store_value = value

        if store_value is None:
            await SystemSetting.filter(key=key).delete()
        else:
            setting = await SystemSetting.filter(key=key).first()
            if setting:
                setting.value = store_value
                await setting.save()
            else:
                await SystemSetting.create(key=key, value=store_value)
        updated.append(key)

    invalidate_config_cache()
    logger.info(f"AI 配置已更新: {updated}（操作人: {user.username}）")
    return {"ok": True, "updated": updated}
