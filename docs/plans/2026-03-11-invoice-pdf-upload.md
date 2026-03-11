# 发票 PDF 上传与备份增强 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 支持发票 PDF 上传/预览/下载，并将备份系统升级为包含文件的 tar.gz 打包格式。

**Architecture:** Invoice 模型新增 `pdf_files` JSONField 存储相对路径数组。文件存在 `uploads/invoices/{YYYY}/{MM}/` 目录。备份从纯 SQL 升级为 tar.gz（SQL + uploads/）。前端操作列改为智能主按钮 + 下拉菜单。

**Tech Stack:** FastAPI（UploadFile, StreamingResponse）, Tortoise ORM（JSONField）, tarfile（备份打包）, Vue 3（Teleport 下拉菜单, iframe PDF 预览）

---

### Task 1: 数据库迁移 — Invoice 新增 pdf_files 字段

**Files:**
- Modify: `backend/app/models/invoice.py:5-30`
- Modify: `backend/app/migrations.py:10-25`

**Step 1: Invoice 模型新增字段**

在 `backend/app/models/invoice.py` 的 Invoice 类中，在 `updated_at` 字段前添加：

```python
pdf_files = fields.JSONField(default=[])  # [{path, name, size, uploaded_at}]
```

**Step 2: 添加迁移函数**

在 `backend/app/migrations.py` 底部添加：

```python
async def migrate_invoice_pdf_files():
    """为 invoices 表添加 pdf_files 列（幂等）"""
    conn = connections.get("default")
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'invoices'"
    )
    if not any(col["name"] == "pdf_files" for col in columns):
        await conn.execute_query(
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS pdf_files JSONB DEFAULT '[]'"
        )
        logger.info("迁移: invoices 表添加 pdf_files 列")
```

在 `run_migrations()` 函数中 `await migrate_purchase_returns()` 之后添加：

```python
await migrate_invoice_pdf_files()
```

**Step 3: 验证**

运行：`npm run build`（前端无改动，仅确认不破坏）

---

### Task 2: 后端配置 — UPLOAD_ROOT 常量 + Docker 挂载

**Files:**
- Modify: `backend/app/config.py:28-29`
- Modify: `docker-compose.yml:38-39`
- Modify: `Dockerfile:41-43`

**Step 1: config.py 添加上传目录常量**

在 `BACKUP_HOUR` 行之后添加：

```python
# 文件上传根目录
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(os.path.join(UPLOAD_ROOT, "invoices"), exist_ok=True)
```

**Step 2: docker-compose.yml 添加 uploads 挂载**

在 `erp` 服务的 `volumes` 中添加：

```yaml
    volumes:
      - ./backups:/app/backups
      - ./uploads:/app/uploads    # 新增
```

**Step 3: Dockerfile 创建 uploads 目录**

修改 `RUN mkdir -p /app/backups` 行为：

```dockerfile
RUN mkdir -p /app/backups /app/uploads/invoices \
    && adduser --disabled-password --no-create-home appuser \
    && chown -R appuser:appuser /app
```

---

### Task 3: 后端 API — PDF 上传/下载/删除

**Files:**
- Modify: `backend/app/routers/invoices.py`

**Step 1: 添加 import**

在文件顶部添加：

```python
import os
from datetime import datetime
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse
from urllib.parse import quote
from app.config import UPLOAD_ROOT
```

**Step 2: 上传 PDF 端点**

在 `cancel_invoice_endpoint` 之后添加：

```python
@router.post("/{invoice_id}/upload-pdf")
async def upload_invoice_pdf(
    invoice_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("accounting_edit")),
):
    inv = await Invoice.filter(id=invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    if inv.status == "cancelled":
        raise HTTPException(status_code=400, detail="已作废的发票不能上传附件")

    # 校验文件
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 格式文件")

    # 校验 magic bytes
    header = await file.read(5)
    if not header.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="文件内容不是有效的 PDF")
    await file.seek(0)

    current_files = inv.pdf_files or []
    if len(current_files) >= 5:
        raise HTTPException(status_code=400, detail="每张发票最多上传 5 个 PDF 文件")

    # 保存文件（streaming，限制 10MB）
    year = str(inv.invoice_date.year)
    month = f"{inv.invoice_date.month:02d}"
    save_dir = os.path.join(UPLOAD_ROOT, "invoices", year, month)
    os.makedirs(save_dir, exist_ok=True)

    seq = len(current_files) + 1
    safe_no = inv.invoice_no.replace("/", "_")
    filename = f"{safe_no}_{seq}.pdf"
    filepath = os.path.join(save_dir, filename)

    MAX_SIZE = 10 * 1024 * 1024
    total_size = 0
    with open(filepath, "wb") as f:
        while True:
            chunk = await file.read(8192)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > MAX_SIZE:
                f.close()
                os.remove(filepath)
                raise HTTPException(status_code=400, detail="文件过大，最大支持 10MB")
            f.write(chunk)

    relative_path = f"invoices/{year}/{month}/{filename}"
    current_files.append({
        "path": relative_path,
        "name": file.filename,
        "size": total_size,
        "uploaded_at": datetime.now().isoformat(),
    })
    inv.pdf_files = current_files
    await inv.save()

    return {"message": "上传成功", "pdf_count": len(current_files), "index": seq - 1}
```

**Step 3: 下载/预览 PDF 端点**

```python
@router.get("/{invoice_id}/pdf/{index}")
async def download_invoice_pdf(
    invoice_id: int,
    index: int,
    user: User = Depends(require_permission("accounting_view")),
):
    inv = await Invoice.filter(id=invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    files = inv.pdf_files or []
    if index < 0 or index >= len(files):
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    file_info = files[index]
    filepath = os.path.join(UPLOAD_ROOT, file_info["path"])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="PDF 文件已丢失")

    def iter_file():
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    original_name = file_info.get("name", f"invoice_{index}.pdf")
    return StreamingResponse(
        iter_file(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(original_name)}",
        },
    )
```

**Step 4: 删除 PDF 端点**

```python
@router.delete("/{invoice_id}/pdf/{index}")
async def delete_invoice_pdf(
    invoice_id: int,
    index: int,
    user: User = Depends(require_permission("accounting_edit")),
):
    inv = await Invoice.filter(id=invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="发票不存在")
    files = inv.pdf_files or []
    if index < 0 or index >= len(files):
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    file_info = files[index]
    filepath = os.path.join(UPLOAD_ROOT, file_info["path"])
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass  # 文件已不存在，不阻塞

    files.pop(index)
    inv.pdf_files = files
    await inv.save()

    return {"message": "删除成功", "pdf_count": len(files)}
```

**Step 5: 修改列表接口返回 pdf_count**

在 `list_invoices` 函数的 items.append 中添加 `"pdf_count"` 字段：

```python
"pdf_count": len(inv.pdf_files or []),
```

同样在 `get_invoice` 返回中添加：

```python
"pdf_files": inv.pdf_files or [],
```

---

### Task 4: 发票作废时自动清理 PDF 文件

**Files:**
- Modify: `backend/app/services/invoice_service.py:280-297`

**Step 1: 导入**

在文件顶部添加：

```python
import os
from app.config import UPLOAD_ROOT
```

**Step 2: 修改 cancel_invoice 函数**

在 `inv.status = "cancelled"` 之后、`await inv.save()` 之前添加 PDF 清理：

```python
        # 清理 PDF 文件
        for pdf in (inv.pdf_files or []):
            try:
                fpath = os.path.join(UPLOAD_ROOT, pdf["path"])
                if os.path.exists(fpath):
                    os.remove(fpath)
            except Exception as e:
                logger.warning(f"清理发票PDF失败: {pdf.get('path')}, {e}")
        inv.pdf_files = []
```

---

### Task 5: 备份系统升级为 tar.gz 格式

**Files:**
- Modify: `backend/app/services/backup_service.py`
- Modify: `backend/app/routers/backup.py`

**Step 1: 修改 do_backup() — 打包为 tar.gz**

替换 `do_backup` 函数中 PostgreSQL 分支的逻辑。在 pg_dump 成功后，用 tarfile 将 SQL 文件和 uploads 目录一起打包：

```python
import tarfile
from app.config import UPLOAD_ROOT

def do_backup(tag="auto"):
    backup_dir = get_backup_dir()
    if not backup_dir:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if is_postgres():
        # 1. pg_dump 到临时 SQL 文件
        tmp_sql = os.path.join(backup_dir, f"_tmp_{timestamp}.sql")
        try:
            result = subprocess.run(
                _pg_conn_args("pg_dump") + [
                    "--clean", "--if-exists",
                    "--no-owner", "--no-privileges",
                    "-f", tmp_sql],
                capture_output=True, text=True, timeout=120,
                env=_pg_env()
            )
            if result.returncode != 0:
                raise RuntimeError(f"pg_dump 失败: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError("pg_dump 未安装或不在 PATH 中")

        # 2. 打包为 tar.gz（SQL + uploads/）
        tar_name = f"erp_{tag}_{timestamp}.tar.gz"
        tar_path = os.path.join(backup_dir, tar_name)
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(tmp_sql, arcname="database.sql")
            if os.path.isdir(UPLOAD_ROOT):
                tar.add(UPLOAD_ROOT, arcname="uploads")
        os.remove(tmp_sql)
        return tar_path
    else:
        # SQLite：保持原有逻辑
        db_path = get_db_path()
        if not db_path:
            return None
        import sqlite3
        backup_name = f"erp_{tag}_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_name)
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        return backup_path
```

**Step 2: 修改 do_restore() — 支持 tar.gz 解压还原**

在 `do_restore` 函数开头判断文件格式，tar.gz 格式先解压再还原：

```python
def do_restore(filename):
    backup_dir = get_backup_dir()
    if not backup_dir:
        raise RuntimeError("备份目录不可用")
    import re
    if not re.match(r'^[a-zA-Z0-9_.\-]+$', filename):
        raise ValueError("文件名包含非法字符")
    filepath = os.path.join(backup_dir, filename)
    if os.path.realpath(filepath) != os.path.join(os.path.realpath(backup_dir), filename):
        raise ValueError("非法文件路径")
    if not os.path.exists(filepath):
        raise FileNotFoundError("备份文件不存在")

    # 恢复前自动备份
    pre_backup = do_backup("pre_restore")
    if not pre_backup:
        raise RuntimeError("无法创建安全备份，取消恢复操作")

    if filename.endswith(".tar.gz"):
        # tar.gz 格式：解压 → 还原 SQL → 还原 uploads
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with tarfile.open(filepath, "r:gz") as tar:
                tar.extractall(tmpdir)

            sql_path = os.path.join(tmpdir, "database.sql")
            if not os.path.exists(sql_path):
                raise RuntimeError("备份包中缺少 database.sql")

            _restore_pg_sql(sql_path)

            # 还原 uploads 目录
            uploads_src = os.path.join(tmpdir, "uploads")
            if os.path.isdir(uploads_src):
                import shutil
                if os.path.isdir(UPLOAD_ROOT):
                    shutil.rmtree(UPLOAD_ROOT)
                shutil.copytree(uploads_src, UPLOAD_ROOT)
                logger.info("uploads 目录已从备份恢复")

    elif is_postgres():
        _restore_pg_sql(filepath)
    else:
        import shutil
        shutil.copy2(filepath, get_db_path())

    return pre_backup
```

抽取一个 `_restore_pg_sql(filepath)` 辅助函数，包含原有的 drop schema + psql + verify 逻辑。

**Step 3: 修改 cleanup_old_backups()**

在清理的 pattern 列表中添加 tar.gz：

```python
for pattern in ["erp_auto_*", "erp_pre_restore_*"]:
    for f in glob.glob(os.path.join(backup_dir, pattern)):
```

这行不用改，因为 `erp_auto_*` 已经能匹配 `.tar.gz` 后缀。

**Step 4: 修改 backup.py 路由**

- `list_backups`：glob 扩展为 `erp_*.tar.gz`
- `download_backup`：文件名正则扩展为 `r'^erp_[\w]+\.(sql|db|tar\.gz)$'`
- `upload_restore_backup`：ext 支持 `.tar.gz`（用 `endswith` 判断）
- `restore_backup`：同上正则扩展
- `delete_backup`：同上正则扩展

---

### Task 6: 前端 API — 新增发票 PDF 接口

**Files:**
- Modify: `frontend/src/api/accounting.js`

**Step 1: 添加 PDF 相关 API 函数**

```javascript
export const uploadInvoicePdf = (invoiceId, file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post(`/invoices/${invoiceId}/upload-pdf`, formData)
}

export const getInvoicePdfUrl = (invoiceId, index) =>
  `/api/invoices/${invoiceId}/pdf/${index}`

export const deleteInvoicePdf = (invoiceId, index) =>
  api.delete(`/invoices/${invoiceId}/pdf/${index}`)
```

---

### Task 7: 前端 — SalesInvoiceTab 操作列改造（主按钮 + 下拉菜单）

**Files:**
- Modify: `frontend/src/components/business/SalesInvoiceTab.vue`

**Step 1: 操作列 template 改造**

将操作列 `<td>` 中的多个按钮替换为：一个主按钮 + 「...」下拉按钮。

主按钮逻辑：
- `draft` → 「确认」（绿色）
- `confirmed` + `pdf_count > 0` → 「下载」（蓝色）
- `confirmed` + `pdf_count === 0` → 「上传」（蓝色）
- `cancelled` → 「查看」（灰色）

「...」下拉菜单使用 `<Teleport to="body">` + `position: fixed` + `getBoundingClientRect()`（同 VoucherPanel 已有实现）。

菜单项根据状态动态生成。

**Step 2: script 部分**

添加：
- `openMenuId` ref + `menuPosition` ref
- `toggleActionMenu(inv, event)` 函数
- 点击外部关闭菜单
- `triggerUpload(inv)` — 创建隐藏 input[type=file]，选择后调用 `uploadInvoicePdf`
- `downloadFirstPdf(inv)` — `window.open(getInvoicePdfUrl(inv.id, 0))` 新窗口打开

**Step 3: style 部分**

添加非 scoped 的下拉菜单样式（Teleport 元素不受 scoped 限制）。

---

### Task 8: 前端 — 确认开票后弹窗提示上传

**Files:**
- Modify: `frontend/src/components/business/SalesInvoiceTab.vue`

**Step 1: 修改 handleConfirm 函数**

确认成功后，调用 `appStore.customConfirm` 提示用户是否上传 PDF：

```javascript
async function handleConfirm(inv) {
  if (!await appStore.customConfirm('确认操作', `确认发票 ${inv.invoice_no}？`)) return
  try {
    await confirmInvoice(inv.id)
    appStore.showToast('确认成功', 'success')
    loadList()
    // 提示上传 PDF
    const doUpload = await appStore.customConfirm(
      '上传电子发票',
      '发票已确认，是否立即上传电子发票 PDF？'
    )
    if (doUpload) {
      triggerUpload(inv)
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '确认失败', 'error')
  }
}
```

---

### Task 9: 前端 — 详情弹窗增加"电子发票"区域

**Files:**
- Modify: `frontend/src/components/business/SalesInvoiceTab.vue`

**Step 1: 详情弹窗 template**

在购方开票信息区块 (`</div>`) 和金额汇总区块之间，添加电子发票区域：

```html
<!-- 电子发票 -->
<div class="border border-line rounded-xl p-3 mb-3">
  <div class="flex items-center justify-between mb-2">
    <div class="text-xs font-semibold text-secondary">电子发票</div>
    <button v-if="detail.status !== 'cancelled'"
      @click="triggerUploadForDetail"
      class="text-xs px-2 py-0.5 rounded-md bg-primary text-white font-medium">
      上传
    </button>
  </div>
  <div v-if="detail.pdf_files && detail.pdf_files.length">
    <div v-for="(pdf, idx) in detail.pdf_files" :key="idx"
      class="flex items-center justify-between py-1.5 text-[13px]"
      :class="idx > 0 ? 'border-t border-line' : ''">
      <div class="flex items-center gap-2 min-w-0">
        <span class="text-muted">📄</span>
        <span class="truncate max-w-48" :title="pdf.name">{{ pdf.name }}</span>
        <span class="text-muted text-[11px]">{{ (pdf.size / 1024).toFixed(0) }}KB</span>
      </div>
      <div class="flex gap-1.5">
        <button @click="previewPdf(detail.id, idx)"
          class="text-xs px-2 py-0.5 rounded-md bg-info-subtle text-info-emphasis font-medium">
          预览
        </button>
        <button v-if="detail.status !== 'cancelled'"
          @click="handleDeletePdf(detail.id, idx)"
          class="text-xs px-2 py-0.5 rounded-md bg-error-subtle text-error-emphasis font-medium">
          删除
        </button>
      </div>
    </div>
  </div>
  <div v-else class="text-[13px] text-muted py-2">暂未上传电子发票</div>
</div>
```

**Step 2: PDF 预览弹窗**

新增一个弹窗，用 `<iframe>` 渲染 PDF：

```html
<Transition name="fade">
  <div v-if="showPdfPreview" class="modal-backdrop" @click.self="showPdfPreview = false">
    <div class="modal max-w-4xl" style="height: 80vh">
      <div class="modal-header">
        <h3>预览电子发票</h3>
        <button @click="showPdfPreview = false" class="modal-close">&times;</button>
      </div>
      <iframe :src="pdfPreviewUrl" class="w-full flex-1 border-0" style="height: calc(80vh - 56px)"></iframe>
    </div>
  </div>
</Transition>
```

**Step 3: script 函数**

```javascript
const showPdfPreview = ref(false)
const pdfPreviewUrl = ref('')

function previewPdf(invoiceId, index) {
  pdfPreviewUrl.value = `/api/invoices/${invoiceId}/pdf/${index}`
  showPdfPreview.value = true
}

async function handleDeletePdf(invoiceId, index) {
  if (!await appStore.customConfirm('删除确认', '确认删除此 PDF 文件？')) return
  try {
    await deleteInvoicePdf(invoiceId, index)
    appStore.showToast('删除成功', 'success')
    // 刷新详情
    const res = await getInvoice(invoiceId)
    detail.value = res.data
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

function triggerUploadForDetail() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf'
  input.onchange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      await uploadInvoicePdf(detail.value.id, file)
      appStore.showToast('上传成功', 'success')
      const res = await getInvoice(detail.value.id)
      detail.value = res.data
      loadList()
    } catch (err) {
      appStore.showToast(err.response?.data?.detail || '上传失败', 'error')
    }
  }
  input.click()
}
```

---

### Task 10: 构建 + Docker 重建 + 验证

**Step 1: 前端构建**

```bash
cd frontend && npm run build
```

**Step 2: Docker 重建**

```bash
orb start && docker compose up -d --build erp
```

**Step 3: 验证清单**

1. 发票列表 — 操作列显示主按钮 + 「...」菜单
2. 草稿发票 — 主按钮为「确认」，菜单有查看/编辑/上传/作废
3. 确认发票后 — 弹窗提示上传 PDF
4. 上传 PDF — 文件保存到 uploads/invoices/YYYY/MM/
5. 发票详情 — 电子发票区域显示已上传文件
6. 点击预览 — iframe 内嵌显示 PDF
7. 已确认+有 PDF — 主按钮变为「下载」
8. 作废发票 — PDF 文件自动从磁盘删除
9. 设置 → 备份管理 → 手动备份 — 生成 .tar.gz
10. 备份恢复 — 数据和 uploads 目录一起恢复
