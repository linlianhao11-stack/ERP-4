"""版本化迁移系统"""
from __future__ import annotations

from app.migrations.runner import run_migrations

__all__ = ["run_migrations"]
