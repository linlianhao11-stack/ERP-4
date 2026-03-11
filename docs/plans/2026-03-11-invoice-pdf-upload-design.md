# 发票 PDF 上传与备份增强设计

## 背景

财务人员在 ERP 中确认开票后，需要到税控系统手动开具电子发票。开具完成后需要将 PDF 回传到 ERP 系统，便于后续查阅和归档。同时现有备份系统只备份数据库，不包含上传文件，需要一并解决。

## 需求摘要

1. 发票确认开具后弹窗提示上传 PDF
2. 发票详情中支持在线预览和下载 PDF
3. 一张发票可关联多个 PDF（发票限额拆分场景）
4. 操作列智能布局：一个主按钮 + 「...」下拉菜单
5. 备份系统升级为 tar.gz 打包（SQL + uploads 目录）
6. 发票作废时自动清理磁盘上的 PDF 文件

## 存储设计

### 目录结构

```
uploads/                     # Docker 挂载根目录
└── invoices/               # 发票 PDF 子目录
    └── 2026/
        └── 03/
            ├── INV2026031100001_1.pdf
            └── INV2026031100001_2.pdf
```

### 数据库字段

Invoice 模型新增 `pdf_files` 字段（JSONField，默认空数组）：

```python
pdf_files = fields.JSONField(default=[])
# 存储格式：
# [
#   {"path": "invoices/2026/03/INV_1.pdf", "name": "原始文件名.pdf", "size": 102400, "uploaded_at": "2026-03-11T12:00:00"},
#   ...
# ]
```

数据库只存**相对路径**（相对于 `uploads/`），后端用 `UPLOAD_ROOT = /app/uploads` 拼接完整路径。迁移服务器时只要 Docker 挂载 `./uploads:/app/uploads` 即可，无需关心宿主机路径。

### 限制

- 单个 PDF 最大 10MB
- 单张发票最多 5 个文件
- 仅接受 `.pdf` 格式（校验扩展名 + magic bytes）

## 后端 API

### 新增端点

| 方法 | 路径 | 功能 | 权限 |
|------|------|------|------|
| POST | `/api/invoices/{id}/upload-pdf` | 上传 PDF | `accounting_edit` |
| GET | `/api/invoices/{id}/pdf/{index}` | 下载/预览 PDF（返回文件流） | `accounting_view` |
| DELETE | `/api/invoices/{id}/pdf/{index}` | 删除单个 PDF | `accounting_edit` |

### 上传流程

1. 校验发票存在且状态非 `cancelled`
2. 校验文件扩展名 `.pdf` + magic bytes `%PDF`
3. 校验文件大小 ≤ 10MB
4. 校验当前文件数 < 5
5. 生成文件名：`{invoice_no}_{序号}.pdf`
6. 保存到 `uploads/invoices/{YYYY}/{MM}/`
7. 更新 `pdf_files` JSON 数组

### 下载流程

1. 从 `pdf_files[index]` 取相对路径
2. 拼接 `UPLOAD_ROOT` 返回 `StreamingResponse`
3. 设置 `Content-Type: application/pdf` 支持浏览器内嵌预览

### 列表接口变更

`GET /api/invoices` 返回的每条记录增加 `pdf_count` 字段（整数），用于前端判断是否有 PDF。

## 前端交互

### 操作列布局

一个主按钮 + 「...」下拉菜单，主按钮根据状态智能切换：

| 发票状态 | 外露按钮 | 菜单内 |
|---------|---------|--------|
| 草稿 `draft` | **确认** | 查看、编辑、上传发票、作废 |
| 已确认 + 有 PDF | **下载发票** | 查看、上传发票、作废 |
| 已确认 + 无 PDF | **上传发票** | 查看、作废 |
| 已作废 | **查看** | 下载发票（有则显示） |

下拉菜单使用 `<Teleport to="body">` + `position: fixed` 避免表格溢出裁剪。

### 确认开票后弹窗

`handleConfirm()` 成功后：
1. 显示成功 toast
2. 弹窗提示"发票已确认，是否立即上传电子发票 PDF？"
3. 「上传」→ 打开文件选择器
4. 「稍后」→ 关闭弹窗

### 详情弹窗"电子发票"区域

位于购方开票信息下方：
- 标题「电子发票」+ 上传按钮（非作废状态可用）
- 文件列表：文件名、大小、上传时间、预览/删除按钮
- 点击预览 → 新弹窗内 `<iframe src="...">` 渲染 PDF
- 无文件时显示"暂未上传电子发票"提示

### 文件上传组件

使用 `<input type="file" accept=".pdf">` + `FormData`，复用现有产品导入的 multipart 上传模式。

## 备份系统升级

### 备份格式变更

从纯 `.sql` / `.db` 升级为 `.tar.gz`：

```
erp_manual_20260311_120000.tar.gz
├── database.sql          # pg_dump 输出
└── uploads/              # 完整 uploads 目录
    └── invoices/
        └── 2026/03/...
```

### do_backup() 改造

1. 先 `pg_dump` 生成临时 SQL 文件
2. 用 `tarfile` 打包 SQL + `uploads/` 目录
3. 删除临时 SQL
4. 返回 `.tar.gz` 路径

### do_restore() 改造

1. 判断文件格式：
   - `.tar.gz` → 解压，还原 SQL，用解压的 `uploads/` 覆盖当前 `uploads/`
   - `.sql` / `.db` → 向后兼容，只还原数据库（uploads 不动）
2. 恢复前仍创建安全备份（也是 tar.gz 格式）

### 其他调整

- 备份列表支持 `.tar.gz` 格式
- 下载接口支持 `.tar.gz`
- 上传恢复支持 `.tar.gz`
- 自动清理覆盖 `.tar.gz` 文件
- 文件名正则从 `erp_*.sql|db` 扩展为 `erp_*.sql|db|tar.gz`

## Docker 配置

```yaml
# docker-compose.yml
erp:
  volumes:
    - ./backups:/app/backups
    - ./uploads:/app/uploads    # 新增
```

Dockerfile 中新增 `RUN mkdir -p /app/uploads/invoices`。

## 文件清理策略

- 发票作废（`cancel_invoice`）时：遍历 `pdf_files` 数组，删除磁盘文件，清空字段
- 删除失败不阻塞（文件可能已不存在），仅记录 warning 日志
- 不做定时清理孤儿文件（YAGNI，当前场景下不会产生孤儿）

## 不改动的内容

- 不改变发票的业务逻辑（创建、确认、作废流程）
- 不改变进项发票（PurchaseInvoiceTab）的操作方式（本次仅做销项）
- 不做 PDF 自动生成/打印功能
- 不做 OCR 识别功能

## 迁移方案

新增 `pdf_files` JSONField 需要数据库迁移。在 `app/migrations.py` 中添加：
- `ALTER TABLE invoices ADD COLUMN IF NOT EXISTS pdf_files JSONB DEFAULT '[]'`
