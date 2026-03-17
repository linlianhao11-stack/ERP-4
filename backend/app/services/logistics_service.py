import json
import hashlib
import httpx

from app.logger import get_logger
from app.models import SystemSetting
from app.ai.encryption import decrypt_value
from app.config import (
    KD100_KEY, KD100_CUSTOMER, KD100_POLL_URL, KD100_QUERY_URL,
    KD100_CALLBACK_URL, PHONE_REQUIRED_CARRIERS, KD100_STATE_MAP
)

logger = get_logger("logistics")


def parse_kd100_state(state_val) -> tuple:
    s = str(state_val)
    if s in KD100_STATE_MAP:
        return KD100_STATE_MAP[s]
    if len(s) >= 2 and s[0] in KD100_STATE_MAP:
        return KD100_STATE_MAP[s[0]]
    return ("in_transit", "在途中")


async def _get_kd100_config() -> tuple:
    """获取 KD100 配置（优先 SystemSetting，fallback 环境变量）"""
    key = ""
    customer = ""

    # 优先从数据库读取
    try:
        key_setting = await SystemSetting.filter(key="api.kd100.key").first()
        if key_setting and key_setting.value:
            key = decrypt_value(key_setting.value) or ""
        customer_setting = await SystemSetting.filter(key="api.kd100.customer").first()
        if customer_setting and customer_setting.value:
            customer = customer_setting.value or ""
    except Exception as e:
        logger.warning("从数据库读取 KD100 配置失败，将使用环境变量", exc_info=e)

    # Fallback 到环境变量
    if not key:
        key = KD100_KEY
    if not customer:
        customer = KD100_CUSTOMER

    return key, customer


async def subscribe_kd100(carrier_code: str, tracking_no: str, order_id: int,
                           shipment_id: int = None, phone: str = None):
    key, customer = await _get_kd100_config()
    if not key or not customer:
        return {"returnCode": "500", "message": "KD100未配置"}
    cb_url = KD100_CALLBACK_URL + f"?order_id={order_id}"
    if shipment_id:
        cb_url += f"&shipment_id={shipment_id}"
    param_dict = {
        "company": carrier_code,
        "number": tracking_no,
        "key": key,
        "parameters": {
            "callbackurl": cb_url,
            "salt": key,
            "resultv2": "4"
        }
    }
    if phone and carrier_code in PHONE_REQUIRED_CARRIERS:
        param_dict["parameters"]["phone"] = phone
    param = json.dumps(param_dict, ensure_ascii=False)
    sign = hashlib.md5((param + key + customer).encode()).hexdigest().upper()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(KD100_POLL_URL, data={
            "schema": "json", "param": param, "sign": sign, "customer": customer
        })
    if resp.status_code != 200:
        logger.warning(f"KD100订阅请求失败: HTTP {resp.status_code}")
        return {"returnCode": str(resp.status_code), "message": "KD100请求失败"}
    try:
        return resp.json()
    except Exception:
        logger.warning(f"KD100订阅响应解析失败: {resp.text[:200]}")
        return {"returnCode": "500", "message": "KD100响应解析失败"}


async def query_kd100(carrier_code: str, tracking_no: str, phone: str = None):
    key, customer = await _get_kd100_config()
    if not key or not customer:
        return {"message": "KD100未配置"}
    param_dict = {"com": carrier_code, "num": tracking_no, "resultv2": "4"}
    if phone and carrier_code in PHONE_REQUIRED_CARRIERS:
        param_dict["phone"] = phone
    param = json.dumps(param_dict, ensure_ascii=False)
    sign = hashlib.md5((param + key + customer).encode()).hexdigest().upper()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(KD100_QUERY_URL, data={
            "customer": customer, "sign": sign, "param": param
        })
    if resp.status_code != 200:
        logger.warning(f"KD100查询请求失败: HTTP {resp.status_code}")
        return {"message": "KD100请求失败"}
    try:
        return resp.json()
    except Exception:
        logger.warning(f"KD100查询响应解析失败: {resp.text[:200]}")
        return {"message": "KD100响应解析失败"}


async def refresh_shipment_tracking(shipment) -> dict:
    if not shipment.carrier_code or not shipment.tracking_no:
        return None
    try:
        resp = await query_kd100(shipment.carrier_code, shipment.tracking_no, phone=shipment.phone)
        if resp.get("message") == "ok" and resp.get("data"):
            tracking_data = resp["data"]
            state = str(resp.get("state", ""))
            if str(resp.get("ischeck")) == "1":
                shipment.status = "signed"
                shipment.status_text = "已签收"
            else:
                status_info = parse_kd100_state(state)
                shipment.status = status_info[0]
                shipment.status_text = status_info[1]
            shipment.last_tracking_info = json.dumps(tracking_data, ensure_ascii=False)
            await shipment.save()
            return {"tracking_info": tracking_data, "status": shipment.status, "status_text": shipment.status_text}
    except Exception as e:
        logger.warning("快递100查询失败", exc_info=e)
    return None
