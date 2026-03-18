"""ERP 系统后端入口"""
import os
import time
import uuid
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import CORS_ORIGINS
from app.rate_limit import limiter
from app.logger import get_logger, request_id_var
from app.database import init_db, close_db
from app.exceptions import http_exception_handler, unhandled_exception_handler
from app.migrations import run_migrations
from app.services.backup_service import auto_backup_loop
from app.services.tracking_refresh_service import tracking_refresh_loop

# 导入所有路由
from app.routers import (
    auth, users, warehouses, locations, products, stock,
    customers, orders, finance, dashboard,
    consignment, logistics, backup, payment_methods,
    rebates, suppliers, purchase_orders, operation_logs,
    settings, sn, product_brands, disbursement_methods,
    account_sets, chart_of_accounts, accounting_periods, vouchers,
    receivables, payables,
    ledgers,
    sales_delivery, purchase_receipt, invoices,
    period_end, financial_reports,
    purchase_returns,
    ai_chat, api_keys,
    departments, employees,
    bank_accounts,
    dropship,
    demo,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    await init_db()
    await run_migrations()
    # 启动后台任务
    backup_task = asyncio.create_task(auto_backup_loop())
    tracking_task = asyncio.create_task(tracking_refresh_loop())
    yield
    # 关闭
    backup_task.cancel()
    tracking_task.cancel()
    try:
        await backup_task
    except asyncio.CancelledError:
        pass
    try:
        await tracking_task
    except asyncio.CancelledError:
        pass
    # 关闭 AI 资源
    try:
        from app.services.ai_chat_service import close_ai_pool
        from app.ai.deepseek_client import close_client
        await close_ai_pool()
        await close_client()
    except Exception as e:
        import logging
        logging.getLogger("main").error("关闭 AI 资源失败", exc_info=e)
    await close_db()


_debug = os.environ.get("DEBUG", "false").lower() == "true"
app = FastAPI(
    title="轻量级ERP系统 v4.17.0",
    lifespan=lifespan,
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
    openapi_url="/openapi.json" if _debug else None,
)

# 速率限制
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 全局异常处理
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# CORS（先注册，作为外层中间件）
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# 安全 Headers 中间件（后注册，作为内层，确保所有响应都带安全头）
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        # HSTS: 仅在 HTTPS 请求时添加（直接 HTTPS 或经反向代理转发）
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 请求体大小限制中间件（防止大 payload 耗尽内存）
MAX_BODY_SIZE = 50 * 1024 * 1024  # 50MB


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(status_code=413, content={"detail": f"请求体过大，最大允许 {MAX_BODY_SIZE // 1048576}MB"})
        # For chunked encoding without Content-Length, uvicorn/nginx should enforce limits.
        # Deploy behind nginx with client_max_body_size for chunked transfer encoding protection.
        return await call_next(request)

app.add_middleware(RequestSizeLimitMiddleware)

# 请求日志中间件（记录每个请求的耗时/状态码/路径）
_access_logger = get_logger("access")
_SKIP_PREFIXES = ("/health", "/assets/")
_SLOW_THRESHOLD_MS = 1000  # 超过 1s 视为慢请求


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith(_SKIP_PREFIXES):
            return await call_next(request)

        # 设置请求 ID（UUID 前 8 位）
        rid = uuid.uuid4().hex[:8]
        request_id_var.set(rid)

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            _access_logger.error(
                "%s %s 500 %dms", request.method, path, duration_ms,
                extra={"data": {"client": request.client.host if request.client else "-"}}
            )
            raise
        duration_ms = int((time.monotonic() - start) * 1000)
        status = response.status_code

        # 根据状态码和耗时决定日志级别
        if status >= 500:
            log_fn = _access_logger.error
        elif duration_ms >= _SLOW_THRESHOLD_MS:
            log_fn = _access_logger.warning
        else:
            log_fn = _access_logger.info

        log_fn(
            "%s %s %d %dms", request.method, path, status, duration_ms,
            extra={"data": {"client": request.client.host if request.client else "-"}}
        )
        return response

app.add_middleware(AccessLogMiddleware)

# 注册所有路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(warehouses.router)
app.include_router(locations.router)
app.include_router(products.router)
app.include_router(stock.router)
app.include_router(customers.router)
app.include_router(orders.router)
app.include_router(finance.router)
app.include_router(dashboard.router)
app.include_router(consignment.router)
app.include_router(logistics.router)
app.include_router(backup.router)
app.include_router(payment_methods.router)
app.include_router(rebates.router)
app.include_router(suppliers.router)
app.include_router(purchase_orders.router)
app.include_router(operation_logs.router)
app.include_router(settings.router)
app.include_router(sn.router)
app.include_router(product_brands.router)
app.include_router(disbursement_methods.router)
app.include_router(account_sets.router)
app.include_router(chart_of_accounts.router)
app.include_router(accounting_periods.router)
app.include_router(vouchers.router)
app.include_router(receivables.router)
app.include_router(payables.router)
app.include_router(ledgers.router)
app.include_router(sales_delivery.router)
app.include_router(purchase_receipt.router)
app.include_router(invoices.router)
app.include_router(period_end.router)
app.include_router(financial_reports.router)
app.include_router(purchase_returns.router)
app.include_router(ai_chat.router)
app.include_router(api_keys.router)
app.include_router(departments.router)
app.include_router(employees.router)
app.include_router(bank_accounts.router)
app.include_router(dropship.router)
app.include_router(demo.router)

# 静态文件服务（生产环境）
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")


# Thread safety note: _index_html_cache uses a check-then-set pattern without a lock.
# In the worst case two requests may read the file simultaneously before the cache is set,
# which is benign since Python's GIL + asyncio single event loop make this safe in practice.
_index_html_cache = None


def _read_index_html():
    global _index_html_cache
    if not _debug and _index_html_cache is not None:
        return _index_html_cache
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
            if not _debug:
                _index_html_cache = content
            return content
    return "<h1>请确保前端文件存在</h1>"


def _html_response():
    """返回 index.html，禁止浏览器缓存"""
    return Response(
        content=_read_index_html(),
        media_type="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


@app.get("/", response_class=HTMLResponse)
async def root():
    return _html_response()


@app.get("/health")
async def health_check():
    """健康检查端点（含数据库连接状态）"""
    from tortoise import connections
    try:
        conn = connections.get("default")
        await conn.execute_query("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": str(e)}
        )


# SPA catch-all: 非 /api、非静态资源的前端路由返回 index.html
_STATIC_EXTENSIONS = frozenset({
    '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
    '.woff', '.woff2', '.ttf', '.map', '.json', '.webp',
})


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def spa_fallback(full_path: str):
    if full_path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Not found")
    last_segment = full_path.rsplit('/', 1)[-1]
    dot_pos = last_segment.rfind('.')
    if dot_pos > 0 and last_segment[dot_pos:] in _STATIC_EXTENSIONS:
        file_path = os.path.join(static_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        raise HTTPException(status_code=404, detail="Not found")
    return _html_response()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8090, reload=_debug)
