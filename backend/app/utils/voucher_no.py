"""共享凭证号生成器，含 SELECT FOR UPDATE 防止并发重复"""
from __future__ import annotations


async def next_voucher_no(account_set_id: int, voucher_type: str, period_name: str) -> str:
    """生成凭证号，使用 select_for_update 防止并发重复。
    按 voucher_no 前缀查询而非 period_name 字段，避免字段不匹配导致重复。"""
    from app.models.accounting import AccountSet
    from app.models.voucher import Voucher

    account_set = await AccountSet.filter(id=account_set_id).first()
    if not account_set:
        raise ValueError(f"账套 {account_set_id} 不存在")
    prefix = f"{account_set.code}-{voucher_type}-{period_name.replace('-', '')}-"
    last = await Voucher.filter(
        voucher_no__startswith=prefix,
    ).order_by("-voucher_no").select_for_update().first()
    if last:
        seq = int(last.voucher_no[len(prefix):]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"


def extract_sequence_no(voucher_no: str) -> int:
    """从复合凭证号 'A01-记-202603-007' 中提取序号 7"""
    parts = voucher_no.rsplit("-", 1)
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0
