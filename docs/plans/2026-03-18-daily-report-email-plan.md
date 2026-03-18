# 每日业务日报邮件 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 每天定时自动生成业务日报（固定 SQL + V3 分析），通过邮件发送 HTML 正文 + Excel 附件。

**Architecture:** 后端三个新文件（email_service / daily_report_service / daily_report router），main.py 新增后台定时任务。前端在设置页面新增日报邮件配置卡片。数据查询用 8 条固定 SQL（今天 vs 昨天环比），V3 分析为 best-effort。SMTP 密码用 Fernet 加密存储。

**Tech Stack:** FastAPI + asyncpg + openpyxl / smtplib + email.mime（标准库）/ Vue 3 + Tailwind CSS

## Review 修正（实施时必须应用）

以下修正来自代码审查，实施者必须在对应 Task 中应用：

1. **CRITICAL — DSN 构建**：不要手写 DSN 解析。复用 `app/routers/ai_chat.py` 中的 `_build_ai_dsn()` 函数（它正确处理了 `quote_plus`）。实施时将该函数提取到 `app/config.py` 作为公共函数，三处调用统一 import。影响 Task 3（send-now）和 Task 4（lifespan）。
2. **IMPORTANT — SMTP STARTTLS**：Task 1 的 `send_email` 中，如果端口不是 465 则用 `smtplib.SMTP` + `starttls()` 代替 `SMTP_SSL`。
3. **IMPORTANT — 定时条件**：Task 2 `daily_report_loop` 的时间判断改为 `now.hour > hour or (now.hour == hour and now.minute >= minute)`，防止应用重启后跳过当天日报。
4. ~~IMPORTANT — SQL 时区~~：**已排除**。PostgreSQL 容器 `TZ=Asia/Shanghai`，`CURRENT_DATE` 已是北京时间，无需修改。
5. **IMPORTANT — 前端组件位置**：Task 5 的 `DailyReportSettings` 放在 SettingsView 的常规设置 grid `</div>` 之后（grid 外面），不要放在 2 列 grid 内部。使用 `defineAsyncComponent` 异步加载。
6. **SUGGESTION — smtp_password 检查**：Task 2 `generate_and_send_report` 在发送前检查 `smtp_password` 是否为空，为空则 log warning 并 return。
7. **SUGGESTION — send-now 防护**：Task 3 的 `send-now` 端点用 `force` 参数让 `generate_and_send_report` 跳过 last_sent_date 检查，而不是清除 last_sent_date（避免失败后状态不一致）。

---

### Task 1: 后端 — 邮件发送服务

**Files:**
- Create: `backend/app/services/email_service.py`

**Step 1: 创建邮件服务**

```python
"""SMTP 邮件发送服务"""
from __future__ import annotations
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from app.logger import get_logger

logger = get_logger("email")


async def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_email: str,
    from_name: str,
    to_email: str,
    subject: str,
    html_body: str,
    attachments: list[tuple[str, bytes]] | None = None,
):
    """发送 HTML 邮件，支持附件。

    Args:
        attachments: [(filename, bytes_content), ...]
    """
    import asyncio

    def _send():
        msg = MIMEMultipart()
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if attachments:
            for filename, content in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(content)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename=\"{filename}\"")
                msg.attach(part)

        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

    await asyncio.to_thread(_send)
    logger.info(f"邮件已发送: {to_email}, 主题: {subject}")
```

**Step 2: 验证语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && python3 -c "import ast; ast.parse(open('app/services/email_service.py').read()); print('OK')"`

**Step 3: Commit**

```bash
git add backend/app/services/email_service.py
git commit -m "feat(email): add SMTP email service with HTML + attachment support"
```

---

### Task 2: 后端 — 日报生成服务（SQL + 数据收集）

**Files:**
- Create: `backend/app/services/daily_report_service.py`

**Step 1: 创建日报服务**

```python
"""每日业务日报生成与发送服务"""
from __future__ import annotations
import asyncio
import io
from datetime import datetime, date

from app.logger import get_logger
from app.models import SystemSetting
from app.ai.encryption import decrypt_value

logger = get_logger("daily_report")

# 8 条固定 SQL（今天 vs 昨天环比）
REPORT_QUERIES = [
    {
        "title": "销售概况（环比）",
        "sql": """
            SELECT
                '今日' AS 日期,
                COUNT(DISTINCT order_no) AS 订单数,
                ROUND(SUM(amount)::numeric, 2) AS 销售额,
                ROUND(SUM(profit)::numeric, 2) AS 毛利,
                ROUND(SUM(profit)/NULLIF(SUM(amount),0)*100, 2) AS 毛利率
            FROM vw_sales_detail WHERE order_date = CURRENT_DATE
            UNION ALL
            SELECT
                '昨日',
                COUNT(DISTINCT order_no),
                ROUND(SUM(amount)::numeric, 2),
                ROUND(SUM(profit)::numeric, 2),
                ROUND(SUM(profit)/NULLIF(SUM(amount),0)*100, 2)
            FROM vw_sales_detail WHERE order_date = CURRENT_DATE - 1
        """,
    },
    {
        "title": "今日销售额 TOP5 客户",
        "sql": """
            SELECT customer_name AS 客户, COUNT(DISTINCT order_no) AS 订单数,
                   ROUND(SUM(amount)::numeric, 2) AS 销售额
            FROM vw_sales_detail WHERE order_date = CURRENT_DATE
            GROUP BY customer_name ORDER BY 销售额 DESC LIMIT 5
        """,
    },
    {
        "title": "今日销售额 TOP5 商品",
        "sql": """
            SELECT product_name AS 商品, brand AS 品牌, SUM(quantity) AS 销量,
                   ROUND(SUM(amount)::numeric, 2) AS 销售额
            FROM vw_sales_detail WHERE order_date = CURRENT_DATE
            GROUP BY product_name, brand ORDER BY 销售额 DESC LIMIT 5
        """,
    },
    {
        "title": "采购概况（环比）",
        "sql": """
            SELECT
                '今日' AS 日期,
                COUNT(DISTINCT po_no) AS 采购单数,
                ROUND(SUM(amount)::numeric, 2) AS 采购金额,
                SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS 已完成,
                SUM(CASE WHEN status='partial' THEN 1 ELSE 0 END) AS 部分到货,
                SUM(CASE WHEN status IN ('pending_review','pending','paid') THEN 1 ELSE 0 END) AS 进行中
            FROM vw_purchase_detail WHERE purchase_date = CURRENT_DATE
            UNION ALL
            SELECT
                '昨日',
                COUNT(DISTINCT po_no),
                ROUND(SUM(amount)::numeric, 2),
                SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status='partial' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status IN ('pending_review','pending','paid') THEN 1 ELSE 0 END)
            FROM vw_purchase_detail WHERE purchase_date = CURRENT_DATE - 1
        """,
    },
    {
        "title": "库存周转 TOP10（最慢）",
        "sql": """
            SELECT product_name AS 商品, brand AS 品牌, current_stock AS 库存,
                   sold_30d AS 近30天销量, ROUND(turnover_rate::numeric, 2) AS 周转率
            FROM vw_inventory_turnover WHERE current_stock > 0
            ORDER BY turnover_rate ASC LIMIT 10
        """,
    },
    {
        "title": "应收账款概况",
        "sql": """
            SELECT COUNT(*) AS 笔数,
                   ROUND(SUM(unreceived_amount)::numeric, 2) AS 未收总额,
                   ROUND(SUM(CASE WHEN age_days > 30 THEN unreceived_amount ELSE 0 END)::numeric, 2) AS 逾期金额
            FROM vw_receivables WHERE status != 'completed'
        """,
    },
    {
        "title": "应付账款概况",
        "sql": """
            SELECT COUNT(*) AS 笔数,
                   ROUND(SUM(unpaid_amount)::numeric, 2) AS 未付总额,
                   ROUND(SUM(CASE WHEN age_days > 30 THEN unpaid_amount ELSE 0 END)::numeric, 2) AS 逾期金额
            FROM vw_payables WHERE status != 'completed'
        """,
    },
    {
        "title": "账龄超30天客户欠款",
        "sql": """
            SELECT customer_name AS 客户, bill_no AS 单号, bill_date AS 账单日期,
                   ROUND(unreceived_amount::numeric, 2) AS 未收金额, age_days AS 账龄天数
            FROM vw_receivables WHERE status != 'completed' AND age_days > 30
            ORDER BY age_days DESC
        """,
    },
]


async def _load_config() -> dict | None:
    """从 system_settings 加载日报配置"""
    keys = [
        "daily_report.enabled", "daily_report.send_time",
        "daily_report.recipients", "daily_report.smtp_host",
        "daily_report.smtp_port", "daily_report.smtp_user",
        "daily_report.smtp_password", "daily_report.from_email",
        "daily_report.from_name", "daily_report.last_sent_date",
    ]
    settings = await SystemSetting.filter(key__in=keys)
    cfg = {s.key: s.value for s in settings}
    if cfg.get("daily_report.enabled") != "true":
        return None
    if not cfg.get("daily_report.recipients") or not cfg.get("daily_report.smtp_host"):
        return None
    return cfg


def _serialize_value(val):
    """将数据库值转为 JSON 友好格式"""
    from decimal import Decimal
    from datetime import date as _date, datetime as _dt
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (_date, _dt)):
        return val.isoformat()
    return val


async def _execute_queries(db_dsn: str) -> list[dict]:
    """执行所有固定 SQL，返回 tables 数组"""
    from app.services.ai_chat_service import get_ai_pool
    tables = []
    pool = await get_ai_pool(db_dsn)
    for q in REPORT_QUERIES:
        try:
            async with pool.acquire() as conn:
                async with conn.transaction(readonly=True):
                    rows = await conn.fetch(q["sql"])
            if rows:
                columns = list(rows[0].keys())
                row_data = [[_serialize_value(r[c]) for c in columns] for r in rows]
                tables.append({"title": q["title"], "columns": columns, "rows": row_data, "row_count": len(rows)})
            else:
                tables.append({"title": q["title"], "columns": [], "rows": [], "row_count": 0})
        except Exception as e:
            logger.warning(f"日报查询失败 [{q['title']}]: {e}")
            tables.append({"title": q["title"], "columns": [], "rows": [], "row_count": 0})
    return tables


async def _generate_analysis(tables: list[dict], config: dict) -> str | None:
    """调用 V3 生成分析摘要（best-effort）"""
    try:
        from app.ai.prompt_builder import build_analysis_prompt
        from app.ai.deepseek_client import call_deepseek

        api_key_encrypted = await _get_setting("ai.deepseek.api_key")
        api_key = decrypt_value(api_key_encrypted)
        if not api_key:
            return None

        base_url = await _get_setting("ai.deepseek.base_url") or "https://api.deepseek.com"
        model = await _get_setting("ai.deepseek.model_analysis") or "deepseek-chat"

        analysis_prompt = build_analysis_prompt(None)
        today = datetime.now().strftime("%Y-%m-%d")
        data_summary = f"用户问题: 生成{today}的业务日报\n\n查询了 {len(tables)} 组数据:\n"
        for t in tables:
            data_summary += f"\n### {t['title']} ({t['row_count']} 行)\n"
            if t["columns"]:
                data_summary += f"列: {t['columns']}\n"
                for row in t["rows"][:10]:
                    data_summary += str(row) + "\n"

        result = await call_deepseek(
            messages=[
                {"role": "system", "content": analysis_prompt},
                {"role": "user", "content": data_summary},
            ],
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=0.7,
            max_tokens=2048,
            timeout=60.0,
        )
        if result:
            return result.get("analysis")
    except Exception as e:
        logger.warning(f"日报 AI 分析失败（降级为纯数据）: {e}")
    return None


async def _get_setting(key: str) -> str | None:
    s = await SystemSetting.filter(key=key).first()
    return s.value if s else None


def _build_html(tables: list[dict], analysis: str | None, report_date: str) -> str:
    """拼装 HTML 邮件正文"""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #1a1a1a; max-width: 800px; margin: 0 auto; padding: 20px; }}
h1 {{ font-size: 20px; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }}
h2 {{ font-size: 15px; color: #374151; margin-top: 24px; margin-bottom: 8px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th {{ background: #f3f4f6; padding: 8px 12px; text-align: left; font-weight: 600; border: 1px solid #e5e7eb; }}
td {{ padding: 6px 12px; border: 1px solid #e5e7eb; }}
tr:nth-child(even) {{ background: #f9fafb; }}
.analysis {{ background: #f0f9ff; border-left: 3px solid #3b82f6; padding: 12px 16px; margin: 16px 0; font-size: 14px; line-height: 1.6; }}
.empty {{ color: #9ca3af; font-style: italic; font-size: 13px; }}
.footer {{ margin-top: 32px; padding-top: 12px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af; }}
</style></head><body>
<h1>业务日报 — {report_date}（截至发送时刻）</h1>
"""
    if analysis:
        html += f'<div class="analysis">{analysis}</div>\n'

    for t in tables:
        html += f"<h2>{t['title']}</h2>\n"
        if not t["columns"]:
            html += '<p class="empty">暂无数据</p>\n'
            continue
        html += "<table><thead><tr>"
        for col in t["columns"]:
            html += f"<th>{col}</th>"
        html += "</tr></thead><tbody>\n"
        for row in t["rows"][:20]:
            html += "<tr>"
            for cell in row:
                val = cell if cell is not None else "-"
                if isinstance(val, float):
                    val = f"{val:,.2f}"
                html += f"<td>{val}</td>"
            html += "</tr>\n"
        if t["row_count"] > 20:
            html += f'<tr><td colspan="{len(t["columns"])}" style="text-align:center;color:#9ca3af">... 共 {t["row_count"]} 行，完整数据见 Excel 附件</td></tr>\n'
        html += "</tbody></table>\n"

    html += f'<div class="footer">此邮件由 ERP 系统自动发送 · {report_date}</div></body></html>'
    return html


def _build_excel(tables: list[dict], report_date: str) -> bytes:
    """生成 Excel 附件（多 sheet）"""
    import openpyxl
    wb = openpyxl.Workbook()
    for ti, t in enumerate(tables):
        if ti == 0:
            ws = wb.active
        else:
            ws = wb.create_sheet()
        ws.title = t["title"][:31]
        for col, name in enumerate(t.get("columns", []), 1):
            ws.cell(row=1, column=col, value=name)
        for row_idx, row in enumerate(t.get("rows", []), 2):
            for col_idx, val in enumerate(row, 1):
                ws.cell(row=row_idx, column=col_idx, value=val)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def generate_and_send_report(db_dsn: str):
    """主入口：生成日报并发送邮件"""
    import json
    from app.services.email_service import send_email
    from app.services.operation_log_service import log_operation

    cfg = await _load_config()
    if not cfg:
        return

    today = datetime.now().strftime("%Y-%m-%d")

    # 防重复
    if cfg.get("daily_report.last_sent_date") == today:
        return

    logger.info("开始生成日报...")

    # 1. 执行查询
    tables = await _execute_queries(db_dsn)

    # 2. AI 分析（best-effort）
    analysis = await _generate_analysis(tables, cfg)

    # 3. 生成 HTML + Excel
    html = _build_html(tables, analysis, today)
    excel_bytes = _build_excel(tables, today)

    # 4. 发送邮件
    recipients = json.loads(cfg.get("daily_report.recipients", "[]"))
    smtp_password = decrypt_value(cfg.get("daily_report.smtp_password", ""))
    from_name = cfg.get("daily_report.from_name", "ERP系统")
    from_email = cfg.get("daily_report.from_email", "")
    subject = f"{from_name} 业务日报 — {today}"

    success_count = 0
    for recipient in recipients:
        try:
            await send_email(
                smtp_host=cfg["daily_report.smtp_host"],
                smtp_port=int(cfg.get("daily_report.smtp_port", "465")),
                smtp_user=cfg.get("daily_report.smtp_user", ""),
                smtp_password=smtp_password,
                from_email=from_email,
                from_name=from_name,
                to_email=recipient.strip(),
                subject=subject,
                html_body=html,
                attachments=[(f"业务日报_{today}.xlsx", excel_bytes)],
            )
            success_count += 1
        except Exception as e:
            logger.error(f"日报发送失败 [{recipient}]: {e}")

    # 5. 记录发送状态
    setting = await SystemSetting.filter(key="daily_report.last_sent_date").first()
    if setting:
        setting.value = today
        await setting.save()
    else:
        await SystemSetting.create(key="daily_report.last_sent_date", value=today)

    logger.info(f"日报发送完成: {success_count}/{len(recipients)} 成功")

    try:
        await log_operation(None, "DAILY_REPORT_SEND", "SYSTEM", None,
            f"日报发送: {success_count}/{len(recipients)} 成功, AI分析: {'有' if analysis else '无'}")
    except Exception:
        pass


async def daily_report_loop(db_dsn: str):
    """后台定时任务循环（类似 auto_backup_loop）"""
    logger.info("日报邮件循环已启动")
    while True:
        await asyncio.sleep(60)
        try:
            cfg = await _load_config()
            if not cfg:
                continue
            send_time = cfg.get("daily_report.send_time", "21:00")
            now = datetime.now()
            hour, minute = map(int, send_time.split(":"))
            if now.hour == hour and now.minute >= minute:
                today = now.strftime("%Y-%m-%d")
                if cfg.get("daily_report.last_sent_date") != today:
                    await generate_and_send_report(db_dsn)
        except Exception as e:
            logger.error(f"日报循环异常: {e}")
```

**Step 2: 验证语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && python3 -c "import ast; ast.parse(open('app/services/daily_report_service.py').read()); print('OK')"`

**Step 3: Commit**

```bash
git add backend/app/services/daily_report_service.py
git commit -m "feat(daily-report): add report generation service with fixed SQL, V3 analysis, HTML + Excel"
```

---

### Task 3: 后端 — 日报设置路由

**Files:**
- Create: `backend/app/routers/daily_report.py`

**Step 1: 创建路由**

```python
"""日报邮件配置与手动触发"""
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.auth.dependencies import require_permission
from app.models import User, SystemSetting
from app.ai.encryption import encrypt_value, decrypt_value, mask_key
from app.logger import get_logger

logger = get_logger("daily_report")

router = APIRouter(prefix="/api/daily-report", tags=["日报邮件"])

# 配置 keys
_KEYS = [
    "daily_report.enabled", "daily_report.send_time",
    "daily_report.recipients", "daily_report.smtp_host",
    "daily_report.smtp_port", "daily_report.smtp_user",
    "daily_report.smtp_password", "daily_report.from_email",
    "daily_report.from_name", "daily_report.last_sent_date",
]


class DailyReportConfig(BaseModel):
    enabled: bool = False
    send_time: str = "21:00"
    recipients: list[str] = []
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: Optional[str] = None  # None 表示不修改
    from_email: str = ""
    from_name: str = "ERP系统"


@router.get("/config")
async def get_config(user: User = Depends(require_permission("admin"))):
    settings = await SystemSetting.filter(key__in=_KEYS)
    cfg = {s.key: s.value for s in settings}
    return {
        "enabled": cfg.get("daily_report.enabled") == "true",
        "send_time": cfg.get("daily_report.send_time", "21:00"),
        "recipients": json.loads(cfg["daily_report.recipients"]) if cfg.get("daily_report.recipients") else [],
        "smtp_host": cfg.get("daily_report.smtp_host", ""),
        "smtp_port": int(cfg.get("daily_report.smtp_port", "465")),
        "smtp_user": cfg.get("daily_report.smtp_user", ""),
        "smtp_password_set": bool(cfg.get("daily_report.smtp_password")),
        "from_email": cfg.get("daily_report.from_email", ""),
        "from_name": cfg.get("daily_report.from_name", "ERP系统"),
        "last_sent_date": cfg.get("daily_report.last_sent_date"),
    }


@router.put("/config")
async def update_config(data: DailyReportConfig, user: User = Depends(require_permission("admin"))):
    pairs = {
        "daily_report.enabled": "true" if data.enabled else "false",
        "daily_report.send_time": data.send_time,
        "daily_report.recipients": json.dumps(data.recipients),
        "daily_report.smtp_host": data.smtp_host,
        "daily_report.smtp_port": str(data.smtp_port),
        "daily_report.smtp_user": data.smtp_user,
        "daily_report.from_email": data.from_email,
        "daily_report.from_name": data.from_name,
    }
    if data.smtp_password is not None:
        pairs["daily_report.smtp_password"] = encrypt_value(data.smtp_password)

    for key, value in pairs.items():
        setting = await SystemSetting.filter(key=key).first()
        if setting:
            setting.value = value
            await setting.save()
        else:
            await SystemSetting.create(key=key, value=value)
    return {"ok": True}


@router.post("/test")
async def test_send(user: User = Depends(require_permission("admin"))):
    """发送测试邮件到第一个收件人"""
    from app.services.email_service import send_email

    cfg_rows = await SystemSetting.filter(key__in=_KEYS)
    cfg = {s.key: s.value for s in cfg_rows}

    recipients = json.loads(cfg.get("daily_report.recipients", "[]"))
    if not recipients:
        raise HTTPException(status_code=400, detail="未配置收件人")
    smtp_password = decrypt_value(cfg.get("daily_report.smtp_password", ""))
    if not smtp_password:
        raise HTTPException(status_code=400, detail="未配置 SMTP 密码")

    try:
        await send_email(
            smtp_host=cfg.get("daily_report.smtp_host", ""),
            smtp_port=int(cfg.get("daily_report.smtp_port", "465")),
            smtp_user=cfg.get("daily_report.smtp_user", ""),
            smtp_password=smtp_password,
            from_email=cfg.get("daily_report.from_email", ""),
            from_name=cfg.get("daily_report.from_name", "ERP系统"),
            to_email=recipients[0].strip(),
            subject="ERP 日报邮件 — 测试",
            html_body="<h2>测试邮件</h2><p>如果你看到这封邮件，说明 SMTP 配置正确。</p>",
        )
        return {"ok": True, "message": f"测试邮件已发送到 {recipients[0]}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)[:200]}")


@router.post("/send-now")
async def send_now(user: User = Depends(require_permission("admin"))):
    """立即发送一次日报"""
    from app.services.daily_report_service import generate_and_send_report
    from app.config import DATABASE_URL

    # 构建 AI 数据库 DSN
    import os
    ai_pwd = os.environ.get("AI_DB_PASSWORD", "")
    if not ai_pwd:
        raise HTTPException(status_code=400, detail="AI_DB_PASSWORD 未配置，无法查询数据")

    from urllib.parse import urlparse
    parsed = urlparse(DATABASE_URL)
    db_dsn = f"postgresql://erp_ai_readonly:{ai_pwd}@{parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}"

    # 临时清除 last_sent_date 以允许重发
    setting = await SystemSetting.filter(key="daily_report.last_sent_date").first()
    if setting:
        setting.value = ""
        await setting.save()

    try:
        await generate_and_send_report(db_dsn)
        return {"ok": True, "message": "日报已发送"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)[:200]}")
```

**Step 2: 验证语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && python3 -c "import ast; ast.parse(open('app/routers/daily_report.py').read()); print('OK')"`

**Step 3: Commit**

```bash
git add backend/app/routers/daily_report.py
git commit -m "feat(daily-report): add config CRUD, test send, and manual trigger endpoints"
```

---

### Task 4: 后端 — 注册路由 + 后台任务

**Files:**
- Modify: `backend/main.py`

**Step 1: 添加 import 和路由注册**

在 `main.py` 的 import 区域（约第 42 行 `demo,` 之后）添加：

```python
    daily_report,
```

在路由注册区域（约第 224 行 `demo.router` 之后）添加：

```python
app.include_router(daily_report.router)
```

**Step 2: 在 lifespan 中添加后台任务**

在 `backup_task` 和 `tracking_task` 创建之后（约第 53 行），添加：

```python
    # 构建 AI 只读数据库 DSN
    import os as _os
    from urllib.parse import urlparse as _urlparse
    _ai_pwd = _os.environ.get("AI_DB_PASSWORD", "")
    _dr_task = None
    if _ai_pwd:
        _parsed = _urlparse(_os.environ.get("DATABASE_URL", ""))
        _ai_dsn = f"postgresql://erp_ai_readonly:{_ai_pwd}@{_parsed.hostname}:{_parsed.port or 5432}/{_parsed.path.lstrip('/')}"
        from app.services.daily_report_service import daily_report_loop
        _dr_task = asyncio.create_task(daily_report_loop(_ai_dsn))
```

在 yield 之后的关闭部分（tracking_task cancel 之后），添加：

```python
    if _dr_task:
        _dr_task.cancel()
        try:
            await _dr_task
        except asyncio.CancelledError:
            pass
```

**Step 3: 验证语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && python3 -c "import ast; ast.parse(open('../main.py').read()); print('OK')"`

**Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat(daily-report): register router and background loop in lifespan"
```

---

### Task 5: 前端 — 日报设置组件

**Files:**
- Create: `frontend/src/api/dailyReport.js`
- Create: `frontend/src/components/business/settings/DailyReportSettings.vue`
- Modify: `frontend/src/views/SettingsView.vue`

**Step 1: 创建 API 模块**

```javascript
import api from './index'

export const getDailyReportConfig = () => api.get('/daily-report/config')
export const updateDailyReportConfig = (data) => api.put('/daily-report/config', data)
export const testDailyReportEmail = () => api.post('/daily-report/test')
export const sendDailyReportNow = () => api.post('/daily-report/send-now')
```

**Step 2: 创建设置组件 `DailyReportSettings.vue`**

```vue
<template>
  <div class="card p-4 mt-4">
    <h3 class="font-semibold mb-3 text-sm">日报邮件</h3>
    <div class="space-y-3">
      <!-- 启用开关 -->
      <label class="flex items-center gap-2 cursor-pointer text-sm" for="dr-enabled">
        <input id="dr-enabled" type="checkbox" v-model="form.enabled" class="w-4 h-4" @change="save">
        <span>启用每日自动发送</span>
      </label>

      <div class="grid grid-cols-2 gap-3">
        <!-- 发送时间 -->
        <div>
          <label class="label text-xs" for="dr-time">发送时间</label>
          <input id="dr-time" type="time" v-model="form.send_time" class="input text-sm" @change="save">
        </div>
        <!-- 发件人名称 -->
        <div>
          <label class="label text-xs" for="dr-from-name">发件人名称</label>
          <input id="dr-from-name" v-model="form.from_name" class="input text-sm" placeholder="ERP系统" @change="save">
        </div>
      </div>

      <!-- 收件人 -->
      <div>
        <label class="label text-xs" for="dr-recipients">收件人（每行一个邮箱）</label>
        <textarea id="dr-recipients" v-model="recipientsText" class="input text-sm" rows="3" placeholder="admin@company.com" @change="saveRecipients"></textarea>
      </div>

      <!-- SMTP 配置 -->
      <details class="border rounded-lg">
        <summary class="px-3 py-2 text-xs font-medium text-secondary cursor-pointer bg-elevated rounded-lg">SMTP 配置</summary>
        <div class="p-3 space-y-2">
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="label text-xs" for="dr-smtp-host">SMTP 服务器</label>
              <input id="dr-smtp-host" v-model="form.smtp_host" class="input text-sm" placeholder="smtp.company.com" @change="save">
            </div>
            <div>
              <label class="label text-xs" for="dr-smtp-port">端口</label>
              <input id="dr-smtp-port" type="number" v-model.number="form.smtp_port" class="input text-sm" placeholder="465" @change="save">
            </div>
          </div>
          <div>
            <label class="label text-xs" for="dr-smtp-user">用户名</label>
            <input id="dr-smtp-user" v-model="form.smtp_user" class="input text-sm" @change="save">
          </div>
          <div>
            <label class="label text-xs" for="dr-smtp-pwd">密码</label>
            <input id="dr-smtp-pwd" type="password" v-model="form.smtp_password" class="input text-sm" :placeholder="passwordSet ? '已设置（留空不修改）' : '请输入'" @change="save">
          </div>
          <div>
            <label class="label text-xs" for="dr-from-email">发件邮箱</label>
            <input id="dr-from-email" v-model="form.from_email" class="input text-sm" placeholder="noreply@company.com" @change="save">
          </div>
        </div>
      </details>

      <!-- 操作按钮 -->
      <div class="flex gap-2 pt-2">
        <button @click="testSend" :disabled="testing" class="btn btn-secondary btn-sm text-xs">
          {{ testing ? '发送中...' : '测试发送' }}
        </button>
        <button @click="sendNow" :disabled="sending" class="btn btn-primary btn-sm text-xs">
          {{ sending ? '生成中...' : '立即发送日报' }}
        </button>
        <span v-if="lastSentDate" class="text-xs text-muted self-center ml-2">上次发送: {{ lastSentDate }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { getDailyReportConfig, updateDailyReportConfig, testDailyReportEmail, sendDailyReportNow } from '../../../api/dailyReport'

const appStore = useAppStore()

const form = ref({
  enabled: false,
  send_time: '21:00',
  recipients: [],
  smtp_host: '',
  smtp_port: 465,
  smtp_user: '',
  smtp_password: null,
  from_email: '',
  from_name: 'ERP系统',
})
const recipientsText = ref('')
const passwordSet = ref(false)
const lastSentDate = ref('')
const testing = ref(false)
const sending = ref(false)

const load = async () => {
  try {
    const { data } = await getDailyReportConfig()
    form.value = { ...data, smtp_password: null }
    recipientsText.value = (data.recipients || []).join('\n')
    passwordSet.value = data.smtp_password_set
    lastSentDate.value = data.last_sent_date || ''
  } catch {}
}

const save = async () => {
  try {
    const payload = { ...form.value }
    if (!payload.smtp_password) payload.smtp_password = null
    await updateDailyReportConfig(payload)
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  }
}

const saveRecipients = async () => {
  form.value.recipients = recipientsText.value.split('\n').map(s => s.trim()).filter(Boolean)
  await save()
}

const testSend = async () => {
  testing.value = true
  try {
    const { data } = await testDailyReportEmail()
    appStore.showToast(data.message || '测试邮件已发送')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '发送失败', 'error')
  } finally {
    testing.value = false
  }
}

const sendNow = async () => {
  sending.value = true
  try {
    const { data } = await sendDailyReportNow()
    appStore.showToast(data.message || '日报已发送')
    await load()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '发送失败', 'error')
  } finally {
    sending.value = false
  }
}

onMounted(load)
</script>
```

**Step 3: 在 SettingsView.vue 中注册组件**

在 import 区域添加：
```javascript
import DailyReportSettings from '../components/business/settings/DailyReportSettings.vue'
```

在常规设置 tab 的 `<EmployeeSettings>` 之后添加：
```html
      <DailyReportSettings v-if="hasPermission('admin')" />
```

**Step 4: 验证构建**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

**Step 5: Commit**

```bash
git add frontend/src/api/dailyReport.js frontend/src/components/business/settings/DailyReportSettings.vue frontend/src/views/SettingsView.vue
git commit -m "feat(daily-report): add settings UI with SMTP config, test send, and manual trigger"
```

---

### Task 6: Docker 集成验证

**Step 1: 构建前端**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

**Step 2: 构建并启动 Docker**

Run: `cd /Users/lin/Desktop/erp-4 && docker compose up --build -d`

**Step 3: 检查容器日志**

Run: `docker compose logs erp --tail=20`
Expected: 无 ImportError/SyntaxError，看到 "日报邮件循环已启动"（如果 AI_DB_PASSWORD 已配置）

**Step 4: 验证端点**

Run: `curl -s -X GET http://localhost:8090/api/daily-report/config`
Expected: 401（未授权，说明路由注册成功）

**Step 5: Commit（如有修复）**

```bash
git add -A && git commit -m "fix: address issues found during Docker integration test"
```
