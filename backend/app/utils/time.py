"""时区与日期工具"""
from datetime import datetime, timezone


def now():
    """返回当前 UTC 时间（带时区）"""
    return datetime.now(timezone.utc)


def to_naive(dt):
    """将日期转换为无时区的 UTC 格式"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def days_between(dt1, dt2):
    """计算两个日期之间的天数差（自动处理时区）"""
    dt1 = to_naive(dt1) if dt1 else to_naive(now())
    dt2 = to_naive(dt2) if dt2 else to_naive(now())
    return (dt1 - dt2).days
