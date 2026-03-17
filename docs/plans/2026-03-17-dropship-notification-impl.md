# 代采代发通知待办机制 — 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将代采代发模块接入现有 todo-counts 通知待办系统，统一 UI 风格，在仪表盘和侧边栏展示待办数量。

**Architecture:** 扩展 `dashboard.py` 的 `get_todo_counts` 端点新增 3 条 SQL 查询；前端在 DashboardView 待办面板、Sidebar badge 映射中添加对应条目；DropshipOrdersPanel 去掉催字 badge，改为 todo-dot 红点。

**Tech Stack:** FastAPI + PostgreSQL (原生 SQL) / Vue 3 + Pinia + Tailwind CSS 4

---

### Task 1: 后端 — 扩展 todo-counts 端点

**Files:**
- Modify: `backend/app/routers/dashboard.py:128-194`

**Step 1: 添加 3 条代采代发查询**

在 `get_todo_counts` 函数的 `return counts` 之前（第 193 行之前），添加以下代码：

```python
    # 代采代发待付款（dropship 权限）
    if is_admin or "dropship" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM dropship_orders WHERE status = 'pending_payment'"
        )
        counts["ds_pending_payment"] = int(r[0]["c"]) if r else 0

    # 代采代发已付待发（dropship 权限）
    if is_admin or "dropship" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM dropship_orders WHERE status = 'paid_pending_ship'"
        )
        counts["ds_paid_pending_ship"] = int(r[0]["c"]) if r else 0

    # 代采代发催付未处理（dropship 权限）
    if is_admin or "dropship" in perms:
        r = await conn.execute_query_dict(
            "SELECT COUNT(*) as c FROM dropship_orders WHERE status = 'pending_payment' AND urged_at IS NOT NULL"
        )
        counts["ds_urged_unpaid"] = int(r[0]["c"]) if r else 0
```

**Step 2: 验证后端**

Run: `cd ~/Desktop/erp-4/backend && python -c "from app.routers.dashboard import router; print('import ok')"`
Expected: `import ok`

**Step 3: Commit**

```bash
git add backend/app/routers/dashboard.py
git commit -m "feat: 代采代发模块接入 todo-counts 待办统计"
```

---

### Task 2: 前端 — 仪表盘待办面板添加 3 项

**Files:**
- Modify: `frontend/src/views/DashboardView.vue:254-289`

**Step 1: 添加 Repeat 图标导入**

在 DashboardView.vue 的 lucide-vue-next import 中添加 `Repeat`：

```javascript
import {
  TrendingUp, CircleDollarSign, Package, Receipt,
  Truck, ClipboardCheck, PackageSearch, CreditCard, AlertTriangle, FileText,
  Wallet, ChevronRight, CheckCircle, Repeat
} from 'lucide-vue-next'
```

**Step 2: 在 todoItemDefs 数组末尾添加 3 项**

在 `pending_receivable` 那一行之后、`]` 之前添加：

```javascript
  { key: 'ds_pending_payment', label: '代采代发待付款', route: '/dropship', perm: 'dropship', icon: Repeat, iconBg: 'bg-warning-subtle', iconColor: 'text-warning' },
  { key: 'ds_paid_pending_ship', label: '代采代发待发货', route: '/dropship', perm: 'dropship', icon: Repeat, iconBg: 'bg-info-subtle', iconColor: 'text-info' },
  { key: 'ds_urged_unpaid', label: '代采代发催付未处理', route: '/dropship', perm: 'dropship', icon: Repeat, iconBg: 'bg-error-subtle', iconColor: 'text-error' },
```

**Step 3: 构建验证**

Run: `cd ~/Desktop/erp-4/frontend && npm run build`
Expected: 构建成功，无错误

**Step 4: Commit**

```bash
git add frontend/src/views/DashboardView.vue
git commit -m "feat: 仪表盘待办面板添加代采代发三类待办项"
```

---

### Task 3: 前端 — 侧边栏 badge 映射

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.vue:86-92`

**Step 1: 在 badgeMap 中添加 dropship 映射**

在 `Sidebar.vue` 第 86-92 行的 `badgeMap` 对象中添加 dropship 条目：

```javascript
const badgeMap = {
  logistics: ['pending_shipment'],
  purchase: ['pending_review', 'in_transit'],
  finance: ['pending_collection', 'pending_payment'],
  stock: ['low_stock'],
  accounting: ['pending_receivable'],
  dropship: ['ds_pending_payment', 'ds_paid_pending_ship', 'ds_urged_unpaid']
}
```

**Step 2: 构建验证**

Run: `cd ~/Desktop/erp-4/frontend && npm run build`
Expected: 构建成功，无错误

**Step 3: Commit**

```bash
git add frontend/src/components/layout/Sidebar.vue
git commit -m "feat: 侧边栏代采代发模块添加待办 badge"
```

---

### Task 4: 前端 — 订单列表 UI 调整（去催字 badge，统一红点）

**Files:**
- Modify: `frontend/src/components/business/DropshipOrdersPanel.vue:25-27,134-139`

**Step 1: 修改移动端卡片（第 25-27 行）**

将移动端的订单号区域：
```html
<span v-if="['pending_payment','paid_pending_ship'].includes(o.status)" class="todo-dot mr-1"></span>
{{ o.ds_no }}
<span v-if="o.urged_at" class="badge badge-orange text-[10px] ml-1">催</span>
```

改为（去掉催字 badge）：
```html
<span v-if="['pending_payment','paid_pending_ship'].includes(o.status)" class="todo-dot mr-1"></span>
{{ o.ds_no }}
```

**Step 2: 修改桌面端表格（第 134-139 行）**

将桌面端的单号列：
```html
<td v-if="isColumnVisible('ds_no')" class="px-2 py-2 font-mono text-sm">
  <span v-if="['pending_payment','paid_pending_ship'].includes(o.status)" class="todo-dot mr-1.5"></span>
  <button type="button" class="text-primary hover:underline cursor-pointer" @click="openDetail(o)">
    {{ o.ds_no }}
  </button>
  <span v-if="o.urged_at" class="badge badge-orange text-[10px] ml-1">催</span>
</td>
```

改为（去掉催字 badge）：
```html
<td v-if="isColumnVisible('ds_no')" class="px-2 py-2 font-mono text-sm">
  <span v-if="['pending_payment','paid_pending_ship'].includes(o.status)" class="todo-dot mr-1.5"></span>
  <button type="button" class="text-primary hover:underline cursor-pointer" @click="openDetail(o)">
    {{ o.ds_no }}
  </button>
</td>
```

**Step 3: 构建验证**

Run: `cd ~/Desktop/erp-4/frontend && npm run build`
Expected: 构建成功，无错误

**Step 4: Commit**

```bash
git add frontend/src/components/business/DropshipOrdersPanel.vue
git commit -m "fix: 代采代发订单列表去掉催字 badge，统一使用 todo-dot 红点"
```

---

### Task 5: 端到端验证

**Step 1: 启动后端和前端开发服务器**

确保 PostgreSQL 运行，然后启动后端：
```bash
cd ~/Desktop/erp-4/backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

**Step 2: 验证 todo-counts API**

```bash
# 登录获取 token 后：
curl -s http://localhost:8000/api/todo-counts -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: 返回的 JSON 中包含 `ds_pending_payment`、`ds_paid_pending_ship`、`ds_urged_unpaid` 三个字段

**Step 3: 前端构建并检查**

Run: `cd ~/Desktop/erp-4/frontend && npm run build`
Expected: 构建成功

**Step 4: 运行现有后端测试**

Run: `cd ~/Desktop/erp-4/backend && python -m pytest tests/ -v --timeout=60`
Expected: 84 个测试全部通过（未引入回归）
