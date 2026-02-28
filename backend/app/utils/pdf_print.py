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


def generate_voucher_pdf(voucher: dict, entries: list[dict]) -> bytes:
    """生成记账凭证 PDF"""
    _ensure_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    font = FONT_NAME if _FONT_REGISTERED else "Helvetica"

    # 标题
    c.setFont(font, 14)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.2 * cm, "记 账 凭 证")

    # 凭证信息行
    c.setFont(font, 9)
    c.drawString(1 * cm, PAGE_H - 2 * cm, f"凭证字号: {voucher.get('voucher_no', '')}")
    c.drawString(10 * cm, PAGE_H - 2 * cm, f"日期: {voucher.get('voucher_date', '')}")
    c.drawString(18 * cm, PAGE_H - 2 * cm, f"附件: {voucher.get('attachment_count', 0)} 张")

    # 表头
    y = PAGE_H - 2.8 * cm
    headers = [("摘要", 1), ("科目", 6.5), ("借方金额", 13), ("贷方金额", 18)]
    c.setFont(font, 9)
    c.line(1 * cm, y + 0.3 * cm, 23 * cm, y + 0.3 * cm)
    for text, x in headers:
        c.drawString(x * cm, y, text)
    c.line(1 * cm, y - 0.2 * cm, 23 * cm, y - 0.2 * cm)

    # 分录行
    c.setFont(font, 8)
    row_y = y - 0.8 * cm
    for entry in entries:
        if row_y < 2 * cm:
            break
        c.drawString(1 * cm, row_y, str(entry.get("summary", ""))[:20])
        c.drawString(6.5 * cm, row_y, str(entry.get("account_name", "")))
        if entry.get("debit_amount") and Decimal(str(entry["debit_amount"])) > 0:
            c.drawRightString(16.5 * cm, row_y, _fmt(entry["debit_amount"]))
        if entry.get("credit_amount") and Decimal(str(entry["credit_amount"])) > 0:
            c.drawRightString(22 * cm, row_y, _fmt(entry["credit_amount"]))
        row_y -= 0.6 * cm

    # 合计行
    c.line(1 * cm, row_y + 0.3 * cm, 23 * cm, row_y + 0.3 * cm)
    c.setFont(font, 9)
    c.drawString(1 * cm, row_y, "合 计")
    c.drawRightString(16.5 * cm, row_y, _fmt(voucher.get("total_debit")))
    c.drawRightString(22 * cm, row_y, _fmt(voucher.get("total_credit")))
    c.line(1 * cm, row_y - 0.2 * cm, 23 * cm, row_y - 0.2 * cm)

    # 签章行
    footer_y = 1 * cm
    c.setFont(font, 8)
    c.drawString(1 * cm, footer_y, f"制单: {voucher.get('creator_name', '')}")
    c.drawString(8 * cm, footer_y, f"审核: {voucher.get('approved_by_name', '')}")
    c.drawString(15 * cm, footer_y, f"记账: {voucher.get('posted_by_name', '')}")

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
