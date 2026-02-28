"""ERP 系统后端入口"""
import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import CORS_ORIGINS
from app.database import init_db, close_db
from app.exceptions import http_exception_handler, unhandled_exception_handler
from app.migrations import run_migrations
from app.services.backup_service import auto_backup_loop

# 导入所有路由
from app.routers import (
    auth, users, warehouses, locations, products, stock,
    salespersons, customers, orders, finance, dashboard,
    consignment, logistics, backup, payment_methods,
    rebates, suppliers, purchase_orders, operation_logs,
    settings, sn, product_brands, disbursement_methods,
    account_sets, chart_of_accounts, accounting_periods, vouchers
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    await init_db()
    await run_migrations()
    # 启动自动备份任务
    backup_task = asyncio.create_task(auto_backup_loop())
    yield
    # 关闭
    backup_task.cancel()
    try:
        await backup_task
    except asyncio.CancelledError:
        pass
    await close_db()


_debug = os.environ.get("DEBUG", "false").lower() == "true"
app = FastAPI(
    title="轻量级ERP系统 v4.9.0",
    lifespan=lifespan,
    docs_url="/docs" if _debug else None,
    redoc_url="/redoc" if _debug else None,
    openapi_url="/openapi.json" if _debug else None,
)

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

# 注册所有路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(warehouses.router)
app.include_router(locations.router)
app.include_router(products.router)
app.include_router(stock.router)
app.include_router(salespersons.router)
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
async def health():
    db_ok = False
    try:
        from tortoise import connections
        conn = connections.get("default")
        await conn.execute_query("SELECT 1")
        db_ok = True
    except Exception:
        pass
    status = "ok" if db_ok else "degraded"
    return {"status": status, "db": db_ok}


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
        raise HTTPException(status_code=404, detail="Not found")
    return _html_response()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8090, reload=_debug)
