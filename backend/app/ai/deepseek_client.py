"""DeepSeek API 客户端 — R1 生成 SQL，V3 分析数据"""
from __future__ import annotations
import json
import httpx
from app.logger import get_logger

logger = get_logger("ai.deepseek")

# DeepSeek API 默认配置
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL_SQL = "deepseek-reasoner"
DEFAULT_MODEL_ANALYSIS = "deepseek-chat"

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """获取或创建 httpx 客户端（懒初始化）"""
    global _client
    if _client is None or _client.is_closed:
        # deepseek-chat 通常 3-10s 响应，30s 超时足够
        _client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
    return _client


async def close_client() -> None:
    """关闭 HTTP 客户端"""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def call_deepseek(
    messages: list[dict],
    *,
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL_SQL,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> dict | None:
    """
    调用 DeepSeek API。

    返回解析后的 JSON 响应内容，失败返回 None。
    不向上抛出异常。
    """
    if not api_key:
        logger.error("DeepSeek API Key 未配置")
        return None

    client = _get_client()
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # response_format 仅 deepseek-chat (V3) 支持，deepseek-reasoner (R1) 不支持
    if "reasoner" not in model:
        payload["response_format"] = {"type": "json_object"}

    for attempt in range(2):  # 最多重试 1 次
        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # 尝试解析为 JSON
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # 提取 JSON 块（处理 markdown 包裹的情况）
                    return _extract_json(content)
            else:
                logger.warning(
                    f"DeepSeek API 返回 {resp.status_code}（第{attempt+1}次）"
                )
                if attempt == 0 and resp.status_code >= 500:
                    continue  # 服务端错误重试
                return None
        except httpx.TimeoutException:
            logger.warning(f"DeepSeek API 超时（第{attempt+1}次）")
            if attempt == 0:
                continue
            return None
        except Exception as e:
            logger.error(f"DeepSeek API 调用异常: {type(e).__name__}")
            return None

    return None


async def test_connection(api_key: str, base_url: str = DEFAULT_BASE_URL) -> tuple[bool, str]:
    """测试 DeepSeek 连接。返回 (success, message)"""
    try:
        client = _get_client()
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": DEFAULT_MODEL_ANALYSIS,
            "messages": [{"role": "user", "content": "回复 ok"}],
            "temperature": 0.0,
            "max_tokens": 10,
        }
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            return True, "连接成功"
        elif resp.status_code == 401:
            return False, "API Key 无效或已过期"
        elif resp.status_code == 402:
            return False, "API 账户余额不足"
        elif resp.status_code == 429:
            return False, "请求过于频繁，请稍后再试"
        else:
            body = resp.text[:200]
            return False, f"API 返回 {resp.status_code}: {body}"
    except httpx.TimeoutException:
        return False, "连接超时，请检查 Base URL 是否正确"
    except Exception as e:
        return False, f"连接失败: {type(e).__name__}"


def _extract_json(text: str) -> dict | None:
    """从可能包含 markdown 的文本中提取 JSON"""
    # 尝试找 ```json ... ``` 块
    import re
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试找第一个 { ... } 块
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None
