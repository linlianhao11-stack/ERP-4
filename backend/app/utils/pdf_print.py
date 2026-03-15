"""PDF 套打工具 — 凭证 / 出库单 / 入库单（24cm × 14cm）"""
from __future__ import annotations

import io
import os
from decimal import Decimal
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app.logger import get_logger

logger = get_logger("pdf_print")

PAGE_W, PAGE_H = 24 * cm, 14 * cm

_FONT_REGISTERED = False
FONT_NAME = "WenQuanYi"


def _ensure_font():
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, fp))
                _FONT_REGISTERED = True
                return
            except Exception:
                continue
    logger.warning("未找到中文字体，PDF 中文可能显示异常")


def _fmt(val) -> str:
    if val is None:
        return ""
    if isinstance(val, Decimal):
        return f"{val:,.2f}"
    try:
        return f"{Decimal(str(val)):,.2f}"
    except Exception:
        return str(val)


def amount_to_chinese(amount) -> str:
    """将数字金额转换为中文大写金额，如 9137.00 → 玖仟壹佰叁拾柒元整"""
    if amount is None:
        return ""
    if isinstance(amount, str):
        amount = Decimal(amount)
    elif not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    if amount < 0:
        return "负" + amount_to_chinese(-amount)
    if amount == 0:
        return "零元整"

    digits = "零壹贰叁肆伍陆柒捌玖"
    units_int = ["", "拾", "佰", "仟", "万", "拾", "佰", "仟", "亿"]
    units_dec = ["角", "分"]

    # 分离整数和小数
    amount = amount.quantize(Decimal("0.01"))
    s = str(amount)
    if "." in s:
        int_part, dec_part = s.split(".")
    else:
        int_part, dec_part = s, "00"
    dec_part = dec_part.ljust(2, "0")[:2]

    result = ""
    # 整数部分
    int_val = int(int_part)
    if int_val > 0:
        int_str = str(int_val)
        n = len(int_str)
        zero_flag = False
        for i, ch in enumerate(int_str):
            d = int(ch)
            unit_idx = n - 1 - i
            if unit_idx >= len(units_int):
                unit_idx = len(units_int) - 1
            if d != 0:
                if zero_flag:
                    result += "零"
                    zero_flag = False
                result += digits[d] + units_int[unit_idx]
            else:
                zero_flag = True
                # 万、亿位即使为零也要加单位
                if unit_idx == 4 and not result.endswith("亿"):
                    result += "万"
                elif unit_idx == 8:
                    result += "亿"
        result += "元"
    else:
        result = "零元"

    # 小数部分
    jiao = int(dec_part[0])
    fen = int(dec_part[1])
    if jiao == 0 and fen == 0:
        result += "整"
    else:
        if jiao > 0:
            result += digits[jiao] + "角"
        elif int_val > 0:
            result += "零"
        if fen > 0:
            result += digits[fen] + "分"

    return result


def generate_voucher_pdf(voucher: dict, entries: list[dict]) -> bytes:
    """生成标准中式记账凭证 PDF（24cm x 14cm）"""
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    font = FONT_NAME if _FONT_REGISTERED else "Helvetica"

    # 页面边距
    margin_l = 1 * cm
    margin_r = 23 * cm
    table_w = margin_r - margin_l

    # === 标题 ===
    c.setFont(font, 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.2 * cm, "记 账 凭 证")

    # === 信息行 ===
    c.setFont(font, 9)
    voucher_date = voucher.get("voucher_date", "")
    voucher_type = voucher.get("voucher_type", "记")
    # 从 voucher_no 提取序号（格式 A01-记-202603-007 -> 007）
    vno = voucher.get("voucher_no", "")
    seq = vno.rsplit("-", 1)[-1] if "-" in vno else vno

    info_y = PAGE_H - 2 * cm
    c.drawString(margin_l, info_y, f"日期: {voucher_date}")
    c.drawCentredString(PAGE_W / 2, info_y,
                        f"核算单位: {voucher.get('account_set_name', '')}")
    c.drawRightString(margin_r, info_y, f"编号: {voucher_type}  {seq}")

    # === 附件行 ===
    att_y = info_y - 0.45 * cm
    att_count = voucher.get("attachment_count", 0)
    if att_count:
        c.setFont(font, 8)
        c.drawRightString(margin_r, att_y, f"附件: {att_count} 张")

    # === 表格 ===
    # 列宽分配: 摘要 5.5cm, 科目 8cm, 借方 4.25cm, 贷方 4.25cm
    col_x = [margin_l,
             margin_l + 5.5 * cm,
             margin_l + 13.5 * cm,
             margin_l + 17.75 * cm,
             margin_r]

    header_y = PAGE_H - 3 * cm

    # 表头横线
    c.setLineWidth(0.8)
    c.line(margin_l, header_y + 0.4 * cm, margin_r, header_y + 0.4 * cm)

    # 表头文字
    c.setFont(font, 9)
    c.drawCentredString((col_x[0] + col_x[1]) / 2, header_y, "摘  要")
    c.drawCentredString((col_x[1] + col_x[2]) / 2, header_y, "科  目")
    c.drawCentredString((col_x[2] + col_x[3]) / 2, header_y, "借  方")
    c.drawCentredString((col_x[3] + col_x[4]) / 2, header_y, "贷  方")

    # 表头下横线
    header_bottom = header_y - 0.25 * cm
    c.line(margin_l, header_bottom, margin_r, header_bottom)

    # 数据行
    c.setFont(font, 8)
    row_h = 0.6 * cm
    data_y = header_bottom - 0.1 * cm
    row_y = data_y

    max_rows = int((data_y - 3.2 * cm) / row_h)
    for i, entry in enumerate(entries):
        if i >= max_rows:
            break
        row_y = data_y - (i + 0.5) * row_h
        # 摘要（截断）
        summary = str(entry.get("summary", ""))
        if len(summary) > 14:
            summary = summary[:13] + "..."
        c.drawString(col_x[0] + 0.15 * cm, row_y, summary)
        # 科目
        acct = str(entry.get("account_name", ""))
        if len(acct) > 20:
            acct = acct[:19] + "..."
        c.drawString(col_x[1] + 0.15 * cm, row_y, acct)
        # 借方
        if entry.get("debit_amount") and Decimal(str(entry["debit_amount"])) > 0:
            c.drawRightString(col_x[3] - 0.15 * cm, row_y,
                              _fmt(entry["debit_amount"]))
        # 贷方
        if entry.get("credit_amount") and Decimal(str(entry["credit_amount"])) > 0:
            c.drawRightString(col_x[4] - 0.15 * cm, row_y,
                              _fmt(entry["credit_amount"]))

    # 数据区底部横线
    total_top_y = data_y - max(len(entries), 1) * row_h - 0.1 * cm
    if total_top_y < 2.8 * cm:
        total_top_y = 2.8 * cm
    c.setLineWidth(0.5)
    c.line(margin_l, total_top_y, margin_r, total_top_y)

    # === 合计行 ===
    c.setFont(font, 9)
    total_y = total_top_y - 0.4 * cm
    c.drawString(col_x[0] + 0.15 * cm, total_y, "合  计")

    # 大写金额
    total_debit = voucher.get("total_debit", 0)
    total_credit = voucher.get("total_credit", 0)
    chinese_amount = amount_to_chinese(total_debit)
    c.setFont(font, 7.5)
    c.drawString(col_x[1] + 0.15 * cm, total_y, chinese_amount)

    c.setFont(font, 9)
    c.drawRightString(col_x[3] - 0.15 * cm, total_y, _fmt(total_debit))
    c.drawRightString(col_x[4] - 0.15 * cm, total_y, _fmt(total_credit))

    # 合计行底部横线
    total_bottom_y = total_y - 0.3 * cm
    c.setLineWidth(0.8)
    c.line(margin_l, total_bottom_y, margin_r, total_bottom_y)

    # 竖线（从表头顶到合计底）
    c.setLineWidth(0.5)
    for x in col_x:
        c.line(x, header_y + 0.4 * cm, x, total_bottom_y)

    # === 签章行 ===
    c.setFont(font, 8)
    footer_y = 1 * cm
    c.drawString(margin_l, footer_y,
                 f"过账: {voucher.get('posted_by_name', '')}")
    c.drawString(7 * cm, footer_y, "出纳:")
    c.drawString(13 * cm, footer_y,
                 f"制单: {voucher.get('creator_name', '')}")
    c.drawString(19 * cm, footer_y,
                 f"审核: {voucher.get('approved_by_name', '')}")

    c.save()
    return buf.getvalue()


def generate_delivery_pdf(bill: dict, items: list[dict], title: str = "销售出库单") -> bytes:
    """生成出库单/入库单 PDF"""
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    font = FONT_NAME if _FONT_REGISTERED else "Helvetica"

    # 标题
    c.setFont(font, 14)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.2 * cm, title)

    # 信息行
    c.setFont(font, 9)
    c.drawString(1 * cm, PAGE_H - 2 * cm, f"单号: {bill.get('bill_no', '')}")
    c.drawString(8 * cm, PAGE_H - 2 * cm, f"日期: {bill.get('bill_date', '')}")
    partner_label = "客户" if "customer_name" in bill else "供应商"
    partner_name = bill.get("customer_name") or bill.get("supplier_name", "")
    c.drawString(15 * cm, PAGE_H - 2 * cm, f"{partner_label}: {partner_name}")

    # 表头
    y = PAGE_H - 2.8 * cm
    if title == "销售出库单":
        headers = [("商品名称", 1), ("数量", 10), ("成本单价", 13), ("销售单价", 17), ("成本小计", 20)]
    else:
        headers = [("商品名称", 1), ("数量", 10), ("含税单价", 13), ("不含税单价", 17), ("税率", 20.5)]
    c.setFont(font, 9)
    c.line(1 * cm, y + 0.3 * cm, 23 * cm, y + 0.3 * cm)
    for text, x in headers:
        c.drawString(x * cm, y, text)
    c.line(1 * cm, y - 0.2 * cm, 23 * cm, y - 0.2 * cm)

    # 明细行
    c.setFont(font, 8)
    row_y = y - 0.8 * cm
    for it in items:
        if row_y < 2 * cm:
            break
        c.drawString(1 * cm, row_y, str(it.get("product_name", ""))[:30])
        c.drawRightString(12 * cm, row_y, str(it.get("quantity", "")))
        if title == "销售出库单":
            c.drawRightString(16 * cm, row_y, _fmt(it.get("cost_price")))
            c.drawRightString(19.5 * cm, row_y, _fmt(it.get("sale_price")))
            cost_sub = Decimal(str(it.get("quantity", 0))) * Decimal(str(it.get("cost_price", 0)))
            c.drawRightString(22.5 * cm, row_y, _fmt(cost_sub.quantize(Decimal("0.01"))))
        else:
            c.drawRightString(16 * cm, row_y, _fmt(it.get("tax_inclusive_price")))
            c.drawRightString(19.5 * cm, row_y, _fmt(it.get("tax_exclusive_price")))
            c.drawRightString(22 * cm, row_y, f"{it.get('tax_rate', 13)}%")
        row_y -= 0.6 * cm

    # 合计行
    c.line(1 * cm, row_y + 0.3 * cm, 23 * cm, row_y + 0.3 * cm)
    c.setFont(font, 9)
    if title == "销售出库单":
        c.drawString(1 * cm, row_y, f"成本合计: {_fmt(bill.get('total_cost'))}    销售合计: {_fmt(bill.get('total_amount'))}")
    else:
        c.drawString(1 * cm, row_y, f"含税合计: {_fmt(bill.get('total_amount'))}    不含税: {_fmt(bill.get('total_amount_without_tax'))}    税额: {_fmt(bill.get('total_tax'))}")

    # 签章
    footer_y = 1 * cm
    c.setFont(font, 8)
    c.drawString(1 * cm, footer_y, f"制单: {bill.get('creator_name', '')}")
    c.drawString(12 * cm, footer_y, f"凭证号: {bill.get('voucher_no', '')}")

    c.save()
    return buf.getvalue()


def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    """合并多个 PDF 为一个"""
    if len(pdf_bytes_list) == 1:
        return pdf_bytes_list[0]
    from io import BytesIO
    try:
        from PyPDF2 import PdfMerger
        merger = PdfMerger()
        for pdf in pdf_bytes_list:
            merger.append(BytesIO(pdf))
        output = BytesIO()
        merger.write(output)
        return output.getvalue()
    except ImportError:
        # 没有 PyPDF2 则返回第一个
        return pdf_bytes_list[0]
