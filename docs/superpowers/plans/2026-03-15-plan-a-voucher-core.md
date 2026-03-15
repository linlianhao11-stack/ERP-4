# Plan A: 凭证管理核心改进 - 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 凭证号分开显示、双视图+搜索+导出、凭证号自动跟随、批量操作、maker-checker 设置、科目搜索、分录列顺序调整

**Architecture:** 后端新增 3 个查询 API + 3 个批量操作 API + 设置白名单扩展；前端将 558 行的 VoucherPanel 拆分为 4 个子组件，新增双视图切换和批量操作

**Tech Stack:** FastAPI + Tortoise ORM, Vue 3 Composition API, openpyxl (Excel 导出), SearchableSelect

**Spec:** `docs/superpowers/specs/2026-03-14-financial-ux-improvements-design.md` — Plan A 章节

**执行顺序：** A1+A7 → A3+A5 → 重构 VoucherPanel → A6 → A4 → A2

---

## 文件结构变更

### 新增文件
| 文件 | 说明 |
|------|------|
| `frontend/src/components/business/VoucherListView.vue` | 凭证视图（从 VoucherPanel 抽出） |
| `frontend/src/components/business/VoucherEntryListView.vue` | 分录视图（A2 新增） |
| `frontend/src/components/business/VoucherDetailModal.vue` | 凭证详情/编辑弹窗（从 VoucherPanel 抽出） |

### 修改文件
| 文件 | 改动 |
|------|------|
| `backend/app/routers/vouchers.py` | 新增 next-number / entries / entries-export / batch-submit / batch-approve / batch-post 6 个 API；列表 API 返回 sequence_no；列表 API 添加 search |
| `backend/app/routers/settings.py` | ALLOWED_KEYS 加入 voucher_maker_checker |
| `frontend/src/components/business/VoucherPanel.vue` | 重构为容器组件，管理视图切换和子组件协调 |
| `frontend/src/api/accounting.js` | 新增 API 调用函数 |
| `frontend/src/api/settings.js` | 新增 voucher_maker_checker API |
| `frontend/src/views/SettingsView.vue` | 财务设置 tab 增加凭证审核规则开关 |

---

## Chunk 1: A1 + A7 + A3 + A5（独立后端改动 + 小前端改动）

### Task 1: A1 后端 — 凭证列表 API 返回 sequence_no

**需求：** 凭证号从复合字符串（如 `A01-记-202603-007`）中提取纯序号（`7`），供前端分列显示。

**Files:**
- Modify: `backend/app/routers/vouchers.py`

- [ ] **Step 1: 在 voucher_no.py 中添加 extract_sequence_no 工具函数**

在 `backend/app/utils/voucher_no.py` 中添加：

```python
def extract_sequence_no(voucher_no: str) -> int:
    """从复合凭证号 'A01-记-202603-007' 中提取序号 7"""
    parts = voucher_no.rsplit("-", 1)
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0
```

- [ ] **Step 2: 修改凭证列表 API 的返回数据**

在 `vouchers.py` 的 `list_vouchers` 中，import 并使用 `extract_sequence_no`：
```python
from app.utils.voucher_no import next_voucher_no, extract_sequence_no
```

遍历 items 时追加：
```python
item["sequence_no"] = extract_sequence_no(item["voucher_no"])
```

- [ ] **Step 2: 修改凭证详情 API 的返回数据**

在 `get_voucher`（约第 64-105 行）中同样追加 `sequence_no`。

- [ ] **Step 3: 验证并提交**

```bash
cd /Users/lin/Desktop/ERP-4-main/backend && python3 -c "from app.routers.vouchers import router; print('OK')"
git add backend/app/routers/vouchers.py
git commit -m "feat(A1): 凭证 API 返回 sequence_no 序号字段"
```

---

### Task 2: A1 前端 + A7 — 凭证号分列显示 + 分录列顺序调整

**Files:**
- Modify: `frontend/src/components/business/VoucherPanel.vue`

- [ ] **Step 1: 凭证列表表头拆分凭证号列**

将现有的 "凭证号" 列拆分为两列：
- 凭证字：显示 `v.voucher_type`（记/收/付/转）
- 凭证号：显示 `v.sequence_no`

修改表头 `<th>` 和对应 `<td>`。列配置 `useColumnConfig` 中也需更新列定义。

- [ ] **Step 2: A7 — 分录表格列顺序调整**

在凭证详情弹窗的分录表格中（约第 137-209 行），重排列顺序为：
序号 → 摘要 → 科目编码 → 科目全名 → 核算维度 → 借方金额 → 贷方金额

当前顺序需要读取代码确认后调整 `<th>` 和 `<td>` 的顺序。

- [ ] **Step 3: 验证并提交**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
git add frontend/src/components/business/VoucherPanel.vue
git commit -m "feat(A1+A7): 凭证号分列显示（凭证字+序号）+ 分录列顺序调整"
```

---

### Task 3: A3 后端 — next-number API

**需求：** 新增预览下一个凭证号的 API，用于前端预填。

**Files:**
- Modify: `backend/app/routers/vouchers.py`
- Read: `backend/app/utils/voucher_no.py`

- [ ] **Step 1: 新增 GET /api/vouchers/next-number 端点**

```python
from app.utils.voucher_no import next_voucher_no as _next_voucher_no, extract_sequence_no

@router.get("/next-number")
async def get_next_voucher_number(
    account_set_id: int = Query(...),
    period: str = Query(...),          # YYYY-MM
    voucher_type: str = Query("记"),
    user: User = Depends(require_permission("accounting_view")),
):
    """预览下一个凭证号（仅供前端显示，非最终分配）"""
    async with transactions.in_transaction():
        voucher_no = await _next_voucher_no(account_set_id, voucher_type, period)
    sequence_no = extract_sequence_no(voucher_no)
    return {"voucher_no": voucher_no, "sequence_no": sequence_no}
```

**重要：** `next_voucher_no()` 内部使用 `select_for_update()`，必须在事务中调用，所以用 `in_transaction()` 包装。返回的号码仅供预览，实际保存时后端在事务中重新分配。

**注意路由顺序：** 此端点必须定义在 `/{voucher_id}` 路由（约第 64 行）之前、`list_vouchers`（第 28 行）之后，否则 FastAPI 会把 "next-number" 当作 id 参数匹配。

- [ ] **Step 2: 前端 API 层新增调用函数**

在 `frontend/src/api/accounting.js` 中添加：
```javascript
export const getNextVoucherNumber = (params) => api.get('/vouchers/next-number', { params })
```

- [ ] **Step 3: 验证并提交**

```bash
cd /Users/lin/Desktop/ERP-4-main/backend && python3 -c "from app.routers.vouchers import router; print('OK')"
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
git add backend/app/routers/vouchers.py frontend/src/api/accounting.js
git commit -m "feat(A3): 新增 next-number API 预览下一个凭证号"
```

---

### Task 4: A5 — maker-checker 设置（后端 + 前端）

**需求：** 允许管理员在设置页面控制"凭证制单人 = 审核人"的规则。

**Files:**
- Modify: `backend/app/routers/settings.py` — 白名单扩展
- Modify: `frontend/src/api/settings.js` — 新增 API
- Modify: `frontend/src/views/SettingsView.vue` — 财务设置 tab 增加开关

- [ ] **Step 1: 后端白名单扩展**

在 `backend/app/routers/settings.py` 中，将 `ALLOWED_KEYS` 从 `{"company_name"}` 扩展为 `{"company_name", "voucher_maker_checker"}`。

- [ ] **Step 2: 前端 API 新增**

在 `frontend/src/api/settings.js` 中新增：
```javascript
export const getVoucherMakerChecker = () => api.get('/settings/voucher_maker_checker')
export const saveVoucherMakerChecker = (data) => api.put('/settings/voucher_maker_checker', data)
```

- [ ] **Step 3: 前端设置页面增加开关**

在 SettingsView.vue 的"财务设置" tab 中，在现有 PaymentMethodSettings 组件下方添加一个凭证审核设置区块：

```html
<div class="card p-4 mt-4">
  <h3 class="text-sm font-medium mb-3">凭证审核规则</h3>
  <label class="flex items-center gap-2 text-sm">
    <input type="checkbox" v-model="allowSamePerson" @change="saveMakerChecker" class="rounded" />
    允许制单人自行审核和过账（关闭则强制制单人 ≠ 审核人）
  </label>
</div>
```

逻辑：
- `allowSamePerson = true` → 保存 `value: "false"`（maker_checker = false 表示不检查 = 允许同人）
- `allowSamePerson = false` → 保存 `value: "true"`（maker_checker = true 表示检查 = 强制分离）
- 页面加载时读取设置值初始化

注意：需要确认 SettingsView 的财务设置 tab 结构。如果财务设置是独立组件，则在该组件中添加。

- [ ] **Step 4: 修改 maker-checker 默认行为**

在 `backend/app/routers/vouchers.py` 的 `approve_voucher` 函数中（约第 295-298 行），将：
```python
strict = await SystemSetting.filter(key="voucher_maker_checker").first()
if not strict or strict.value != "false":
    if v.creator_id == user.id:
        raise HTTPException(status_code=400, detail="制单人不能审核自己的凭证")
```
改为：
```python
strict = await SystemSetting.filter(key="voucher_maker_checker").first()
if strict and strict.value == "true":
    if v.creator_id == user.id:
        raise HTTPException(status_code=400, detail="制单人不能审核自己的凭证")
```

这样默认行为变为"允许同人审核"（设置不存在或值不为 "true" 时不检查），只有管理员在设置中打开"强制分离"时才检查。

- [ ] **Step 5: 验证并提交**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
git add backend/app/routers/settings.py backend/app/routers/vouchers.py frontend/src/api/settings.js frontend/src/views/SettingsView.vue
git commit -m "feat(A5): 凭证审核规则设置——允许制单人自行审核和过账"
```

---

## Chunk 2: 重构 VoucherPanel + A6 + A4

### Task 5: 重构 — 拆分 VoucherPanel 为子组件

**需求：** VoucherPanel 当前 558 行，即将新增双视图、批量操作、搜索导出，必须先拆分。

**Files:**
- Modify: `frontend/src/components/business/VoucherPanel.vue` — 瘦身为容器
- Create: `frontend/src/components/business/VoucherDetailModal.vue` — 详情/编辑弹窗
- Create: `frontend/src/components/business/VoucherListView.vue` — 凭证列表视图

**拆分策略：**

1. **VoucherDetailModal.vue**（约 200 行）：
   - 包含凭证详情弹窗的所有模板（当前 VoucherPanel 第 104-226 行的 modal 部分）
   - 包含 `showDetail`, `isCreating`, `isEditing`, `detailVoucher`, `leafAccounts` 等状态
   - 包含 `viewVoucher`, `openCreateForm`, `startEdit`, `handleCreate`, `handleUpdate` 等函数
   - Props: `modelValue`(visible), `voucherId`(查看时), `mode`(view/create/edit)
   - Emits: `update:modelValue`, `saved`, `deleted`

2. **VoucherListView.vue**（约 200 行）：
   - 包含凭证列表表格（当前 VoucherPanel 第 32-102 行）
   - 包含 `vouchers`, `page`, `total`, `selectedIds`, `filters` 等状态
   - 包含 `loadList`, `toggleSelectAll` 等函数
   - 包含工作流操作按钮（提交/审核/过账/驳回/反过账/删除）
   - Props: `accountSetId`
   - Emits: `view-voucher`, `create-voucher`, `selection-change`

3. **VoucherPanel.vue** 瘦身为容器（约 80 行）：
   - 管理视图切换状态（`viewMode = 'voucher' | 'entry'`）
   - 渲染 PageToolbar（筛选 + 操作按钮）
   - 条件渲染 VoucherListView / VoucherEntryListView
   - 渲染 VoucherDetailModal
   - 协调子组件间的事件

- [ ] **Step 1: 创建 VoucherDetailModal.vue**

从 VoucherPanel.vue 中提取弹窗相关代码。组件接口：
```javascript
const props = defineProps({
  visible: Boolean,
  voucherId: { type: Number, default: null },
  mode: { type: String, default: 'view' }, // view / create / edit
  accountSetId: { type: Number, required: true }
})
const emit = defineEmits(['update:visible', 'saved'])
```

- [ ] **Step 2: 创建 VoucherListView.vue**

从 VoucherPanel.vue 中提取列表表格和工作流操作。组件接口：
```javascript
const props = defineProps({
  accountSetId: { type: Number, required: true },
  filters: { type: Object, required: true }, // { period, voucher_type, status, search }
})
const emit = defineEmits(['view-voucher', 'create-voucher'])
// selectedIds 在此组件内管理，通过 defineExpose 暴露给父组件
const selectedIds = ref([])
defineExpose({ selectedIds, loadList })
```

**`selectedIds` 所有权**：`selectedIds` 定义在 VoucherListView 中，VoucherPanel 通过 `listViewRef.value?.selectedIds` 访问来显示批量按钮计数。

- [ ] **Step 3: 重构 VoucherPanel.vue 为容器**

保留：
- `PageToolbar` 渲染（筛选下拉、操作按钮）
- 视图切换状态
- 子组件协调逻辑

删除：已移到子组件的所有代码

- [ ] **Step 4: 验证并提交**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
git add frontend/src/components/business/VoucherPanel.vue \
        frontend/src/components/business/VoucherDetailModal.vue \
        frontend/src/components/business/VoucherListView.vue
git commit -m "refactor: 拆分 VoucherPanel 为 VoucherListView + VoucherDetailModal 子组件"
```

---

### Task 6: A6 — 凭证号预填 + 科目搜索

**需求：** 新建凭证时预填下一个凭证号；科目选择器改为可搜索。

**Files:**
- Modify: `frontend/src/components/business/VoucherDetailModal.vue`

- [ ] **Step 1: 新建凭证时预填凭证号**

在 `openCreateForm`（或组件 mounted/watch 逻辑）中：
```javascript
// 当 mode === 'create' 时自动获取下一个凭证号
const { data } = await getNextVoucherNumber({
  account_set_id: props.accountSetId,
  period: currentPeriod,  // 取当前日期的 YYYY-MM
  voucher_type: form.voucher_type || '记'
})
form.voucher_no = data.voucher_no
previewSequenceNo.value = data.sequence_no
```

日期或凭证类型变更时重新调用此 API。

- [ ] **Step 2: 科目选择器改为 SearchableSelect**

将分录表格中的科目 `<select>` 改为 `SearchableSelect` 组件：
```html
<SearchableSelect
  :options="accountOptions"
  v-model="entry.account_id"
  placeholder="选择科目"
  search-placeholder="搜索编码或名称..."
/>
```

`accountOptions` 从 `leafAccounts` 映射：
```javascript
const accountOptions = computed(() =>
  leafAccounts.value.map(a => ({
    id: a.id,
    label: `${a.code} ${a.name}`,
    sublabel: a.category
  }))
)
```

- [ ] **Step 3: 验证并提交**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
git add frontend/src/components/business/VoucherDetailModal.vue
git commit -m "feat(A6): 新建凭证预填凭证号 + 科目搜索下拉"
```

---

### Task 7: A4 后端 — 批量提交/审核/过账 API

**Files:**
- Modify: `backend/app/routers/vouchers.py`

- [ ] **Step 1: 新增 POST /api/vouchers/batch-submit**

```python
class BatchVoucherRequest(BaseModel):
    voucher_ids: list[int]

@router.post("/batch-submit")
async def batch_submit_vouchers(
    req: BatchVoucherRequest,
    user: User = Depends(require_permission("accounting_edit")),
):
    success = []
    failed = []
    vouchers = await Voucher.filter(id__in=req.voucher_ids).all()
    for v in vouchers:
        if v.status != "draft":
            failed.append({"id": v.id, "reason": f"凭证状态为{v.status}，不是草稿"})
            continue
        v.status = "pending"
        await v.save()
        success.append(v.id)
    return {"success": success, "failed": failed}
```

- [ ] **Step 2: 新增 POST /api/vouchers/batch-approve**

```python
@router.post("/batch-approve")
async def batch_approve_vouchers(
    req: BatchVoucherRequest,
    user: User = Depends(require_permission("accounting_approve")),
):
    strict = await SystemSetting.filter(key="voucher_maker_checker").first()
    success = []
    failed = []
    vouchers = await Voucher.filter(id__in=req.voucher_ids).all()
    for v in vouchers:
        if v.status != "pending":
            failed.append({"id": v.id, "reason": f"凭证状态为{v.status}，不是待审核"})
            continue
        if strict and strict.value == "true" and v.creator_id == user.id:
            failed.append({"id": v.id, "reason": "制单人不能审核自己的凭证"})
            continue
        v.status = "approved"
        v.approved_by = user
        v.approved_at = datetime.now(timezone.utc)
        await v.save()
        success.append(v.id)
    return {"success": success, "failed": failed}
```

- [ ] **Step 3: 新增 POST /api/vouchers/batch-post**

```python
@router.post("/batch-post")
async def batch_post_vouchers(
    req: BatchVoucherRequest,
    user: User = Depends(require_permission("accounting_post")),
):
    success = []
    failed = []
    vouchers = await Voucher.filter(id__in=req.voucher_ids).all()
    for v in vouchers:
        if v.status != "approved":
            failed.append({"id": v.id, "reason": f"凭证状态为{v.status}，不是已审核"})
            continue
        period = await AccountingPeriod.filter(
            account_set_id=v.account_set_id, period_name=v.period_name
        ).first()
        if period and period.is_closed:
            failed.append({"id": v.id, "reason": "该期间已结账"})
            continue
        v.status = "posted"
        v.posted_by = user
        v.posted_at = datetime.now(timezone.utc)
        await v.save()
        success.append(v.id)
    return {"success": success, "failed": failed}
```

- [ ] **Step 4: 确保路由顺序**

所有 batch-* 和 next-number 路由必须在 `/{id}` 路由之前定义。

- [ ] **Step 5: 新增前端 API 函数**

在 `frontend/src/api/accounting.js` 中：
```javascript
export const batchSubmitVouchers = (ids) => api.post('/vouchers/batch-submit', { voucher_ids: ids })
export const batchApproveVouchers = (ids) => api.post('/vouchers/batch-approve', { voucher_ids: ids })
export const batchPostVouchers = (ids) => api.post('/vouchers/batch-post', { voucher_ids: ids })
```

- [ ] **Step 6: 验证并提交**

```bash
cd /Users/lin/Desktop/ERP-4-main/backend && python3 -c "from app.routers.vouchers import router; print('OK')"
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
git add backend/app/routers/vouchers.py frontend/src/api/accounting.js
git commit -m "feat(A4): 批量提交/审核/过账 API"
```

---

### Task 8: A4 前端 — 批量操作按钮

**Files:**
- Modify: `frontend/src/components/business/VoucherPanel.vue` — 工具栏添加按钮
- Modify: `frontend/src/components/business/VoucherListView.vue` — 操作结果展示

- [ ] **Step 1: VoucherPanel 工具栏添加批量按钮**

在 `#actions` 插槽中，已有"新增凭证"按钮旁添加。注意 `selectedIds` 通过 `listViewRef` 访问：
```javascript
const listViewRef = ref(null)
const selectedCount = computed(() => listViewRef.value?.selectedIds?.length || 0)
```
```html
<button v-if="selectedCount > 0" class="btn btn-primary btn-sm" @click="handleBatchSubmit">
  批量提交 ({{ selectedCount }})
</button>
<button v-if="selectedCount > 0" class="btn btn-success btn-sm" @click="handleBatchApprove">
  批量审核 ({{ selectedCount }})
</button>
<button v-if="selectedCount > 0" class="btn btn-secondary btn-sm" @click="handleBatchPost">
  批量过账 ({{ selectedCount }})
</button>
```

- [ ] **Step 2: 批量操作函数**

```javascript
async function handleBatchSubmit() {
  const ids = listViewRef.value?.selectedIds || []
  if (!await appStore.customConfirm('批量提交', `确认提交 ${ids.length} 张凭证？`)) return
  try {
    const { data } = await batchSubmitVouchers(ids)
    const msg = `成功 ${data.success.length} 条` + (data.failed.length ? `，失败 ${data.failed.length} 条` : '')
    appStore.showToast(msg, data.failed.length ? 'warning' : 'success')
    listViewRef.value.selectedIds = []
    listViewRef.value?.loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}
```

批量审核和批量过账同理。

- [ ] **Step 3: 验证并提交**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
git add frontend/src/components/business/VoucherPanel.vue \
        frontend/src/components/business/VoucherListView.vue
git commit -m "feat(A4): 前端批量提交/审核/过账按钮"
```

---

## Chunk 3: A2 双视图 + 搜索 + 导出

### Task 9: A2 后端 — 分录列表 + Excel 导出 API

**Files:**
- Modify: `backend/app/routers/vouchers.py`

- [ ] **Step 1: 新增 GET /api/vouchers/entries**

返回分录级平铺数据：
```python
from tortoise.expressions import Q

@router.get("/entries")
async def list_voucher_entries(
    account_set_id: int = Query(...),
    period_name: str = Query(None),
    voucher_type: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("accounting_view")),
):
    query = VoucherEntry.filter(voucher__account_set_id=account_set_id)
    if period_name:
        query = query.filter(voucher__period_name=period_name)
    if voucher_type:
        query = query.filter(voucher__voucher_type=voucher_type)
    if status:
        query = query.filter(voucher__status=status)
    if search:
        query = query.filter(
            Q(summary__icontains=search) | Q(account__name__icontains=search) | Q(account__code__icontains=search)
        )
    total = await query.count()
    entries = await query.offset((page-1)*page_size).limit(page_size) \
        .select_related("voucher", "account", "aux_customer", "aux_supplier", "aux_employee", "aux_department") \
        .prefetch_related("voucher__creator", "voucher__approved_by", "voucher__posted_by") \
        .order_by("voucher__voucher_no", "line_no")
    items = []
    for e in entries:
        v = e.voucher
        # 核算维度：汇总各辅助核算名称
        aux_parts = []
        if e.aux_customer:
            aux_parts.append(f"客户:{e.aux_customer.name}")
        if e.aux_supplier:
            aux_parts.append(f"供应商:{e.aux_supplier.name}")
        if e.aux_employee:
            aux_parts.append(f"员工:{e.aux_employee.name}")
        if e.aux_department:
            aux_parts.append(f"部门:{e.aux_department.name}")
        items.append({
            "id": e.id,
            "voucher_id": v.id,
            "voucher_date": str(v.voucher_date),
            "period_name": v.period_name,
            "voucher_type": v.voucher_type,
            "voucher_no": v.voucher_no,
            "sequence_no": extract_sequence_no(v.voucher_no),
            "entry_summary": e.summary,
            "account_code": e.account.code,
            "account_name": e.account.name,
            "aux_info": " | ".join(aux_parts) if aux_parts else "",
            "debit_amount": str(e.debit_amount),
            "credit_amount": str(e.credit_amount),
            "creator_name": v.creator.display_name if v.creator else "",
            "approved_by_name": v.approved_by.display_name if v.approved_by else "",
            "posted_by_name": v.posted_by.display_name if v.posted_by else "",
            "status": v.status,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}
```

- [ ] **Step 2: 新增 GET /api/vouchers/entries/export**

```python
from io import BytesIO
from starlette.responses import StreamingResponse
import openpyxl

@router.get("/entries/export")
async def export_voucher_entries(
    account_set_id: int = Query(...),
    period_name: str = Query(None),
    voucher_type: str = Query(None),
    status: str = Query(None),
    search: str = Query(None),
    user: User = Depends(require_permission("accounting_view")),
):
    # 同 entries 查询逻辑但不分页，限制最大 10000 条
    query = VoucherEntry.filter(voucher__account_set_id=account_set_id)
    if period_name:
        query = query.filter(voucher__period_name=period_name)
    if voucher_type:
        query = query.filter(voucher__voucher_type=voucher_type)
    if status:
        query = query.filter(voucher__status=status)
    if search:
        query = query.filter(
            Q(summary__icontains=search) | Q(account__name__icontains=search) | Q(account__code__icontains=search)
        )
    entries = await query.limit(10000) \
        .select_related("voucher", "account", "aux_customer", "aux_supplier", "aux_employee", "aux_department") \
        .prefetch_related("voucher__creator", "voucher__approved_by", "voucher__posted_by") \
        .order_by("voucher__voucher_no", "line_no")
    # openpyxl 生成 Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "凭证分录"
    headers = ["日期", "期间", "凭证字", "凭证号", "摘要", "科目编码", "科目名称", "核算维度", "借方金额", "贷方金额", "制单人", "审核人", "过账人", "状态"]
    ws.append(headers)
    for e in entries:
        v = e.voucher
        aux_parts = []
        if e.aux_customer: aux_parts.append(f"客户:{e.aux_customer.name}")
        if e.aux_supplier: aux_parts.append(f"供应商:{e.aux_supplier.name}")
        if e.aux_employee: aux_parts.append(f"员工:{e.aux_employee.name}")
        if e.aux_department: aux_parts.append(f"部门:{e.aux_department.name}")
        ws.append([
            str(v.voucher_date), v.period_name, v.voucher_type,
            extract_sequence_no(v.voucher_no),
            e.summary, e.account.code, e.account.name,
            " | ".join(aux_parts) if aux_parts else "",
            float(e.debit_amount), float(e.credit_amount),
            v.creator.display_name if v.creator else "",
            v.approved_by.display_name if v.approved_by else "",
            v.posted_by.display_name if v.posted_by else "",
            v.status,
        ])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=voucher_entries.xlsx"},
    )
```

列标题：日期 | 期间 | 凭证字 | 凭证号 | 摘要 | 科目编码 | 科目名称 | 核算维度 | 借方金额 | 贷方金额 | 制单人 | 审核人 | 过账人 | 状态

- [ ] **Step 3: 前端 API 新增**

```javascript
export const getVoucherEntries = (params) => api.get('/vouchers/entries', { params })
export const exportVoucherEntries = (params) => api.get('/vouchers/entries/export', { params, responseType: 'blob' })
```

- [ ] **Step 4: 验证并提交**

```bash
cd /Users/lin/Desktop/ERP-4-main/backend && python3 -c "from app.routers.vouchers import router; print('OK')"
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
git add backend/app/routers/vouchers.py frontend/src/api/accounting.js
git commit -m "feat(A2): 分录列表 API + Excel 导出 API"
```

---

### Task 10: A2 前端 — 双视图 + 搜索 + 导出

**Files:**
- Modify: `frontend/src/components/business/VoucherPanel.vue` — 视图切换 + 搜索框 + 导出按钮
- Create: `frontend/src/components/business/VoucherEntryListView.vue` — 分录视图

- [ ] **Step 1: VoucherPanel 添加视图切换和搜索**

在 `#filters` 插槽中添加搜索框：
```html
<div class="toolbar-search-wrapper">
  <Search :size="14" class="toolbar-search-icon" />
  <input v-model="searchQuery" @input="debouncedSearch" class="toolbar-search" placeholder="搜索凭证号/摘要/科目...">
</div>
```

在 `#actions` 插槽中添加视图切换和导出按钮：
```html
<SegmentedControl v-model="viewMode" :options="[
  { value: 'voucher', label: '凭证视图' },
  { value: 'entry', label: '分录视图' }
]" />
<button class="btn btn-secondary btn-sm" @click="handleExport">
  <Download :size="14" /> 导出
</button>
```

- [ ] **Step 2: 创建 VoucherEntryListView.vue**

分录视图组件，每行一条 VoucherEntry：
- Props: `accountSetId`, `filters`
- 列：日期 | 期间 | 凭证字 | 凭证号 | 摘要 | 科目编码 | 科目名称 | 借方金额 | 贷方金额 | 制单 | 审核 | 过账 | 状态
- 调用 `getVoucherEntries` API
- 同一凭证的多行通过视觉分组区分（相邻行凭证号相同时不重复显示）
- 支持分页

- [ ] **Step 3: VoucherPanel 条件渲染两个视图**

```html
<VoucherListView v-if="viewMode === 'voucher'" ref="listViewRef"
  :account-set-id="accountSetId" :filters="currentFilters"
  @view-voucher="onViewVoucher" @create-voucher="onCreateVoucher" />
<VoucherEntryListView v-else-if="viewMode === 'entry'" ref="entryViewRef"
  :account-set-id="accountSetId" :filters="currentFilters" />
```

- [ ] **Step 4: 导出功能**

```javascript
async function handleExport() {
  try {
    const { data } = await exportVoucherEntries({
      account_set_id: accountSetId,
      period_name: filters.period || undefined,
      voucher_type: filters.voucher_type || undefined,
      status: filters.status || undefined,
      search: searchQuery.value || undefined,
    })
    downloadBlob(data, `凭证分录明细_${new Date().toISOString().slice(0,10)}.xlsx`)
  } catch (e) {
    appStore.showToast('导出失败', 'error')
  }
}
```

- [ ] **Step 5: 验证并提交**

```bash
cd /Users/lin/Desktop/ERP-4-main/frontend && npm run build
git add frontend/src/components/business/VoucherPanel.vue \
        frontend/src/components/business/VoucherEntryListView.vue
git commit -m "feat(A2): 凭证双视图切换 + 搜索筛选 + Excel 导出"
```

---

## 注意事项

1. **路由顺序关键**：FastAPI 按定义顺序匹配路由。`/next-number`、`/entries`、`/entries/export`、`/batch-submit`、`/batch-approve`、`/batch-post`、`/batch-pdf` 必须在 `/{id}` 之前定义
2. **VoucherPanel 拆分是 A2 的前置条件**：Task 5（拆分）必须在 Task 10（双视图）之前完成
3. **sequence_no 是显示用字段**：不存储到数据库，每次从 `voucher_no` 动态提取
4. **next-number 仅供预览**：前端显示预计凭证号，实际保存时后端在事务中重新分配
5. **openpyxl**：检查是否已安装，如未安装需 `pip install openpyxl`
6. **SearchableSelect**：项目已有此组件，确认 import 路径
7. **组件行数控制**：每个子组件不超过 300 行
8. **批量操作按钮启用逻辑**：可根据 selectedIds 中凭证的 status 动态启用/禁用对应按钮，但首版可以简化为选中就显示、后端校验不符合的
