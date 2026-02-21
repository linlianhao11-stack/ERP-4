"""统一错误消息和快捷函数"""
from fastapi import HTTPException


def not_found(entity: str = "资源"):
    """抛出 404 HTTPException"""
    raise HTTPException(status_code=404, detail=f"{entity}不存在")


def bad_request(detail: str):
    """抛出 400 HTTPException"""
    raise HTTPException(status_code=400, detail=detail)


def parse_date(date_str: str, field_name: str = "日期"):
    """
    安全解析日期字符串，格式错误时抛出 400。

    Args:
        date_str: ISO 格式日期字符串
        field_name: 字段名称，用于错误消息

    Returns:
        datetime 对象
    """
    from datetime import datetime
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"{field_name} 格式错误，请使用 YYYY-MM-DD 格式")
