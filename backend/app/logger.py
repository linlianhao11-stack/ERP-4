import logging
import json
import sys
import contextvars
from datetime import datetime, timezone

# 请求级上下文：request_id 在中间件中设置，日志自动注入
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


class StructuredFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        # 注入请求 ID（如果当前在请求上下文中）
        rid = request_id_var.get()
        if rid:
            log_entry["request_id"] = rid
        if hasattr(record, "data"):
            log_entry["data"] = record.data
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"erp.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.propagate = False
        import os
        log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))
    return logger
