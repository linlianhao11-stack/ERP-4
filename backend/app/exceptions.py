from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from app.logger import get_logger

logger = get_logger("exception")


async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTPException 统一包装 — 保持现有行为，增加日志"""
    if exc.status_code >= 500:
        logger.error("HTTP %d: %s %s", exc.status_code, request.method, request.url.path,
                     extra={"data": {"detail": exc.detail}})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def unhandled_exception_handler(request: Request, exc: Exception):
    """未捕获异常 — 记录完整堆栈，返回统一 500"""
    logger.error("未处理异常: %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请重试"})
