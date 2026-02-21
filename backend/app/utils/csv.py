from decimal import Decimal


def csv_safe(val) -> str:
    """转义 CSV 单元格值，防止公式注入（数值类型不受影响）"""
    if isinstance(val, (int, float, Decimal)):
        return f'"{val}"'
    s = str(val).replace('"', '""')
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r', '\n'):
        s = "'" + s
    return f'"{s}"'
