"""备份管理路由"""
import os
import re
import glob
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from app.auth.dependencies import require_permission
from app.models import User
from app.services.backup_service import do_backup, do_restore, get_backup_dir, is_postgres
from app.services.operation_log_service import log_operation
from app.logger import get_logger

logger = get_logger("backup")

router = APIRouter(prefix="/api", tags=["备份管理"])


async def _run_post_restore_migrations():
    """恢复后运行迁移，确保 schema 与当前版本兼容"""
    try:
        from app.migrations import run_migrations
        await run_migrations()
        logger.info("恢复后迁移执行成功")
    except Exception as e:
        logger.warning("恢复后迁移执行异常（数据已恢复，部分新字段可能需要重启补全）", exc_info=e)


@router.post("/backup")
async def create_backup(user: User = Depends(require_permission("admin"))):
    """手动创建备份"""
    try:
        path = do_backup("manual")
        if not path:
            raise HTTPException(status_code=500, detail="备份功能不可用")
        size = os.path.getsize(path)
        await log_operation(user, "BACKUP_CREATE", "SYSTEM", None, f"手动备份 {os.path.basename(path)} ({round(size / 1024 / 1024, 2)}MB)")
        return {"message": "备份成功", "filename": os.path.basename(path), "size_mb": round(size / 1024 / 1024, 2)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("手动备份失败", exc_info=e)
        raise HTTPException(status_code=500, detail="备份失败，请查看服务器日志")


@router.get("/backups")
async def list_backups(user: User = Depends(require_permission("admin"))):
    """获取备份列表"""
    backup_dir = get_backup_dir()
    if not backup_dir:
        return []
    files = glob.glob(os.path.join(backup_dir, "erp_*.db")) + glob.glob(os.path.join(backup_dir, "erp_*.sql")) + glob.glob(os.path.join(backup_dir, "erp_*.tar.gz"))
    result = []
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        stat = os.stat(f)
        result.append({
            "filename": os.path.basename(f),
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    return result


@router.get("/backups/{filename}")
async def download_backup(filename: str, user: User = Depends(require_permission("admin"))):
    """下载备份文件"""
    if not re.match(r'^erp_[\w]+\.(sql|db|tar\.gz)$', filename):
        raise HTTPException(status_code=400, detail="非法文件名格式")
    backup_dir = get_backup_dir()
    if not backup_dir:
        raise HTTPException(status_code=404, detail="备份目录不存在")
    filepath = os.path.realpath(os.path.join(backup_dir, filename))
    if not filepath.startswith(os.path.realpath(backup_dir) + os.sep):
        raise HTTPException(status_code=400, detail="非法文件路径")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="备份文件不存在")

    def iter_file():
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    return StreamingResponse(iter_file(), media_type="application/octet-stream",
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.post("/backups/upload-restore")
async def upload_restore_backup(file: UploadFile = File(...), user: User = Depends(require_permission("admin"))):
    """上传备份文件并恢复数据库"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")
    fname = file.filename.lower()
    if fname.endswith(".tar.gz"):
        ext = ".tar.gz"
    else:
        ext = os.path.splitext(fname)[1]
    if ext not in (".sql", ".db", ".tar.gz"):
        raise HTTPException(status_code=400, detail="仅支持 .sql、.db 或 .tar.gz 备份文件")

    if is_postgres() and ext == ".db":
        raise HTTPException(status_code=400, detail="当前使用 PostgreSQL 数据库，无法恢复 SQLite (.db) 备份文件")
    if not is_postgres() and ext in (".sql", ".tar.gz"):
        raise HTTPException(status_code=400, detail="当前使用 SQLite 数据库，无法恢复 PostgreSQL 备份文件，请上传 .db 格式的备份")

    backup_dir = get_backup_dir()
    if not backup_dir:
        raise HTTPException(status_code=500, detail="备份目录不可用")
    # 保存上传文件到备份目录（streaming read with size limit）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_name = f"erp_uploaded_{timestamp}{ext}"
    saved_path = os.path.join(backup_dir, saved_name)
    try:
        MAX_SIZE = 100 * 1024 * 1024
        total_size = 0
        try:
            with open(saved_path, "wb") as f:
                while True:
                    chunk = await file.read(8192)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > MAX_SIZE:
                        raise HTTPException(status_code=400, detail="备份文件过大，最大支持 100MB")
                    f.write(chunk)
        except HTTPException:
            if os.path.exists(saved_path):
                os.remove(saved_path)
            raise
        # 执行恢复
        pre_backup = do_restore(saved_name)
        # 恢复后运行迁移，确保 schema 兼容
        await _run_post_restore_migrations()
        logger.info("数据库恢复(上传)", extra={"data": {"from": saved_name, "pre_backup": os.path.basename(pre_backup)}})
        await log_operation(user, "BACKUP_RESTORE", "SYSTEM", None, f"上传恢复 {saved_name}")
        return {
            "message": "恢复成功",
            "uploaded_as": saved_name,
            "pre_restore_backup": os.path.basename(pre_backup)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("上传恢复失败", exc_info=e)
        raise HTTPException(status_code=500, detail="恢复失败，请查看服务器日志")


@router.post("/backups/{filename}/restore")
async def restore_backup(filename: str, user: User = Depends(require_permission("admin"))):
    """从已有备份恢复数据库"""
    if not re.match(r'^erp_[\w]+\.(sql|db|tar\.gz)$', filename):
        raise HTTPException(status_code=400, detail="非法文件名格式")

    # 校验备份格式与当前数据库类型是否匹配
    if filename.endswith(".tar.gz"):
        ext = ".tar.gz"
    else:
        ext = os.path.splitext(filename)[1].lower()
    if is_postgres() and ext == ".db":
        raise HTTPException(status_code=400, detail="当前使用 PostgreSQL 数据库，无法恢复 SQLite (.db) 备份文件")
    if not is_postgres() and ext == ".sql":
        raise HTTPException(status_code=400, detail="当前使用 SQLite 数据库，无法恢复 PostgreSQL (.sql) 备份文件")

    try:
        pre_backup = do_restore(filename)
        # 恢复后运行迁移，确保 schema 兼容
        await _run_post_restore_migrations()
        logger.info("数据库恢复", extra={"data": {"from": filename, "pre_backup": os.path.basename(pre_backup)}})
        await log_operation(user, "BACKUP_RESTORE", "SYSTEM", None, f"恢复备份 {filename}")
        return {
            "message": "恢复成功",
            "pre_restore_backup": os.path.basename(pre_backup)
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("数据库恢复失败", exc_info=e)
        raise HTTPException(status_code=500, detail="恢复失败，请查看服务器日志")


@router.delete("/backups/{filename}")
async def delete_backup(filename: str, user: User = Depends(require_permission("admin"))):
    """删除备份文件"""
    if not re.match(r'^erp_[\w]+\.(sql|db|tar\.gz)$', filename):
        raise HTTPException(status_code=400, detail="非法文件名格式")
    backup_dir = get_backup_dir()
    if not backup_dir:
        raise HTTPException(status_code=404, detail="备份目录不存在")
    filepath = os.path.realpath(os.path.join(backup_dir, filename))
    if not filepath.startswith(os.path.realpath(backup_dir) + os.sep):
        raise HTTPException(status_code=400, detail="非法文件路径")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="备份文件不存在")
    os.remove(filepath)
    await log_operation(user, "BACKUP_DELETE", "SYSTEM", None, f"删除备份 {filename}")
    return {"message": "删除成功"}
