# 样机明细弹窗 + SN码搜索修复 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为样机台账添加点击查看明细弹窗（含时间线 + 借还表格），并修复 SN 码搜索无法匹配的问题。

**Architecture:** 新增 `DemoUnitDetailModal.vue` 全屏弹窗组件，复用现有 `modal-overlay` / `modal-content` 样式体系。后端无需新 API，`GET /api/demo/units/{id}` 已返回 loans + disposals。搜索修复只需在后端 Q 表达式中追加 SN 字段。

**Tech Stack:** Vue 3 (Composition API) + Tailwind CSS 4 + FastAPI + Tortoise ORM

---

### Task 1: 后端 — SN 码搜索修复

**Files:**
- Modify: `backend/app/routers/demo.py:300-303`

**Step 1: 修改搜索过滤逻辑**

在 `backend/app/routers/demo.py` 第 302 行，给 Q 表达式增加 SN 码匹配：

```python
# 修改前（第 302 行）:
q = Q(code__icontains=search) | Q(product__name__icontains=search) | Q(product__sku__icontains=search)

# 修改后:
q = Q(code__icontains=search) | Q(product__name__icontains=search) | Q(product__sku__icontains=search) | Q(sn_code__code__icontains=search)
```

注意: `sn_code` 是 DemoUnit 到 SnCode 的 FK 字段名，SnCode 模型中实际存储 SN 值的字段名是 `sn_code`（即 `code` 属性名），所以 Tortoise ORM 的跨关联查询写法是 `sn_code__code__icontains`。但需要验证 SnCode 模型的字段名 — 如果字段名是 `sn_code` 则写 `sn_code__sn_code__icontains`。

**Step 2: 验证 SnCode 模型字段名**

检查 `backend/app/models/sn.py` 中 SnCode 模型的字段名。根据序列化代码 `u.sn_code.sn_code`（demo.py:95），SnCode 的 SN 值字段名是 `sn_code`，所以正确写法是：

```python
q = Q(code__icontains=search) | Q(product__name__icontains=search) | Q(product__sku__icontains=search) | Q(sn_code__sn_code__icontains=search)
```

**Step 3: 重启后端验证**

Run: 在样机管理页面的搜索框中输入一个已知的 SN 码，确认能搜到对应样机。

**Step 4: Commit**

```bash
git add backend/app/routers/demo.py
git commit -m "fix: 样机搜索支持SN码匹配"
```

---

### Task 2: 前端 — 新建 DemoUnitDetailModal 组件

**Files:**
- Create: `frontend/src/components/business/demo/DemoUnitDetailModal.vue`

**Step 1: 创建组件文件**

组件结构参照 `FinanceOrderDetailModal.vue` 的模式：`modal-overlay` + `modal-content`，`props: { visible, unitId }`，`emit: ['update:visible']`。

```vue
<script setup>
import { ref, watch, computed } from 'vue'
import { getDemoUnit } from '../../../api/demo'
import { useFormat } from '../../../composables/useFormat'
import { Maximize2, Minimize2 } from 'lucide-vue-next'

const props = defineProps({
  unitId: { type: Number, default: null },
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['update:visible'])

const { fmtDate } = useFormat()
const isExpanded = ref(false)
const detail = ref(null)
const loading = ref(false)

const close = () => emit('update:visible', false)

// 加载明细数据
watch(() => [props.visible, props.unitId], async ([vis, id]) => {
  if (!vis || !id) return
  loading.value = true
  try {
    const { data } = await getDemoUnit(id)
    detail.value = data
  } catch (e) {
    console.error('加载样机明细失败:', e)
  } finally {
    loading.value = false
  }
}, { immediate: true })

// 状态 / 成色 / 借出类型 映射
const STATUS_MAP = {
  in_stock: { label: '在库', cls: 'badge badge-green' },
  lent_out: { label: '借出中', cls: 'badge badge-blue' },
  repairing: { label: '维修中', cls: 'badge badge-yellow' },
  sold: { label: '已售', cls: 'badge badge-gray' },
  scrapped: { label: '已报废', cls: 'badge badge-red' },
  lost: { label: '已丢失', cls: 'badge badge-red' },
  converted: { label: '已转良品', cls: 'badge badge-purple' },
}
const CONDITION_MAP = { new: '全新', good: '良好', fair: '一般', poor: '较差' }
const LOAN_TYPE_MAP = { customer_trial: '客户试用', salesperson: '业务员携带', exhibition: '展会' }
const LOAN_STATUS_MAP = {
  pending_approval: '待审批', approved: '已审批', rejected: '已拒绝',
  lent_out: '借出中', returned: '已归还', closed: '已关闭',
}
const DISPOSAL_TYPE_MAP = { sale: '转销售', scrap: '报废', loss_compensation: '丢失赔偿', conversion: '转良品' }

const statusLabel = (s) => STATUS_MAP[s]?.label || s
const statusClass = (s) => STATUS_MAP[s]?.cls || 'badge badge-gray'

// 时间线：合并 loans + disposals，按时间倒序
const timeline = computed(() => {
  if (!detail.value) return []
  const events = []

  // 创建事件
  if (detail.value.created_at) {
    events.push({
      time: detail.value.created_at,
      type: 'create',
      label: '创建入库',
      desc: `样机 ${detail.value.code} 入库`,
    })
  }

  // 借还事件
  for (const loan of (detail.value.loans || [])) {
    if (loan.created_at) {
      events.push({
        time: loan.created_at,
        type: 'loan_create',
        label: '借出申请',
        desc: `${loan.loan_type_label} · ${loan.borrower_name || '未知'}`,
        loan,
      })
    }
    if (loan.loan_date) {
      events.push({
        time: loan.loan_date,
        type: 'loan_lend',
        label: '确认出库',
        desc: `经手人: ${loan.handler_name || '-'}`,
        loan,
        isOverdue: loan.is_overdue,
      })
    }
    if (loan.actual_return_date) {
      events.push({
        time: loan.actual_return_date,
        type: 'loan_return',
        label: '归还',
        desc: `归还成色: ${CONDITION_MAP[loan.condition_on_return] || '-'}`,
        loan,
      })
    }
    if (loan.status === 'rejected') {
      events.push({
        time: loan.created_at,
        type: 'loan_reject',
        label: '审批拒绝',
        desc: '',
        loan,
      })
    }
    if (loan.status === 'closed' && !loan.actual_return_date) {
      events.push({
        time: loan.created_at,
        type: 'loan_close',
        label: '借出关闭',
        desc: loan.return_notes || '',
        loan,
      })
    }
  }

  // 处置事件
  for (const d of (detail.value.disposals || [])) {
    events.push({
      time: d.created_at,
      type: 'disposal',
      label: DISPOSAL_TYPE_MAP[d.disposal_type] || d.disposal_type,
      desc: d.reason || (d.amount != null ? `金额: ¥${d.amount}` : ''),
    })
  }

  // 按时间倒序
  events.sort((a, b) => (b.time || '').localeCompare(a.time || ''))
  return events
})

// 时间线节点颜色
const timelineDotClass = (ev) => {
  if (ev.isOverdue) return 'bg-error'
  const map = {
    create: 'bg-primary',
    loan_create: 'bg-blue-400',
    loan_lend: 'bg-warning',
    loan_return: 'bg-success',
    loan_reject: 'bg-error',
    loan_close: 'bg-gray-400',
    disposal: 'bg-error',
  }
  return map[ev.type] || 'bg-gray-400'
}
</script>

<template>
  <div v-if="visible" class="modal-overlay" @click.self="close()">
    <div class="modal-content" :class="{ 'modal-expanded': isExpanded }" style="max-width:920px">
      <!-- 头部 -->
      <div class="modal-header">
        <div class="flex items-center gap-2">
          <h3 class="font-semibold">样机明细</h3>
          <span v-if="detail" :class="statusClass(detail.status)">{{ statusLabel(detail.status) }}</span>
        </div>
        <div class="flex items-center gap-1">
          <button @click="isExpanded = !isExpanded" class="modal-expand-btn hidden md:inline-flex" :aria-label="isExpanded ? '收起弹窗' : '展开弹窗'">
            <Minimize2 v-if="isExpanded" :size="16" />
            <Maximize2 v-else :size="16" />
          </button>
          <button @click="close()" class="modal-close">&times;</button>
        </div>
      </div>

      <!-- 内容 -->
      <div class="modal-body" v-if="detail">
        <!-- 基本信息卡片 -->
        <div class="mb-5 p-4 bg-elevated rounded-xl">
          <div class="text-[15px] font-bold font-mono mb-2">{{ detail.code }}</div>
          <div class="grid grid-cols-2 gap-1.5 gap-x-4 text-[13px]">
            <div><span class="text-muted">产品:</span> {{ detail.product_name || '-' }}</div>
            <div><span class="text-muted">SKU:</span> {{ detail.product_sku || '-' }}</div>
            <div><span class="text-muted">SN码:</span> <span class="font-mono">{{ detail.sn_code || '-' }}</span></div>
            <div><span class="text-muted">仓库:</span> {{ detail.warehouse_name || '-' }}<span v-if="detail.location_code" class="text-muted"> / {{ detail.location_code }}</span></div>
            <div><span class="text-muted">成色:</span> {{ CONDITION_MAP[detail.condition] || '-' }}</div>
            <div><span class="text-muted">成本价:</span> <span class="font-mono">¥{{ detail.cost_price?.toFixed(2) }}</span></div>
            <div v-if="detail.holder_name"><span class="text-muted">当前持有人:</span> {{ detail.holder_name }}</div>
            <div><span class="text-muted">累计借出:</span> {{ detail.total_loan_count || 0 }} 次 / {{ detail.total_loan_days || 0 }} 天</div>
            <div class="col-span-2"><span class="text-muted">创建时间:</span> {{ fmtDate(detail.created_at) }}</div>
            <div v-if="detail.notes" class="col-span-2"><span class="text-muted">备注:</span> {{ detail.notes }}</div>
          </div>
        </div>

        <!-- 时间线 -->
        <div class="mb-5">
          <h4 class="text-sm font-semibold mb-3">生命周期</h4>
          <div v-if="timeline.length" class="relative pl-5">
            <div class="absolute left-[7px] top-1.5 bottom-1.5 w-px bg-border"></div>
            <div v-for="(ev, i) in timeline" :key="i" class="relative pb-4 last:pb-0">
              <div class="absolute left-[-13px] top-1 w-2.5 h-2.5 rounded-full border-2 border-surface" :class="timelineDotClass(ev)"></div>
              <div class="text-[13px]">
                <span class="font-medium" :class="{ 'text-error': ev.isOverdue }">{{ ev.label }}</span>
                <span class="text-muted ml-2 text-xs">{{ fmtDate(ev.time) }}</span>
              </div>
              <div v-if="ev.desc" class="text-xs text-secondary mt-0.5">{{ ev.desc }}</div>
            </div>
          </div>
          <div v-else class="text-sm text-muted">暂无记录</div>
        </div>

        <!-- 借还记录表格 -->
        <div class="mb-5">
          <h4 class="text-sm font-semibold mb-3">借还记录</h4>
          <div v-if="detail.loans?.length" class="overflow-x-auto">
            <table class="w-full text-[13px]">
              <thead>
                <tr class="border-b border-border text-left text-muted">
                  <th class="px-2 py-1.5 font-medium">单号</th>
                  <th class="px-2 py-1.5 font-medium">类型</th>
                  <th class="px-2 py-1.5 font-medium">借用人</th>
                  <th class="px-2 py-1.5 font-medium">经手人</th>
                  <th class="px-2 py-1.5 font-medium">借出日期</th>
                  <th class="px-2 py-1.5 font-medium">预期归还</th>
                  <th class="px-2 py-1.5 font-medium">实际归还</th>
                  <th class="px-2 py-1.5 font-medium">状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="loan in detail.loans" :key="loan.id" class="border-b border-border-light" :class="{ 'text-error': loan.is_overdue }">
                  <td class="px-2 py-1.5 font-mono">{{ loan.loan_no }}</td>
                  <td class="px-2 py-1.5">{{ loan.loan_type_label }}</td>
                  <td class="px-2 py-1.5">{{ loan.borrower_name || '-' }}</td>
                  <td class="px-2 py-1.5">{{ loan.handler_name || '-' }}</td>
                  <td class="px-2 py-1.5">{{ fmtDate(loan.loan_date) }}</td>
                  <td class="px-2 py-1.5" :class="{ 'text-error font-medium': loan.is_overdue }">{{ fmtDate(loan.expected_return_date) }}</td>
                  <td class="px-2 py-1.5">{{ fmtDate(loan.actual_return_date) }}</td>
                  <td class="px-2 py-1.5">
                    <span class="text-xs" :class="{
                      'text-warning': loan.status === 'pending_approval',
                      'text-primary': loan.status === 'approved' || loan.status === 'lent_out',
                      'text-success': loan.status === 'returned',
                      'text-error': loan.status === 'rejected',
                      'text-muted': loan.status === 'closed',
                    }">{{ loan.status_label }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="text-sm text-muted">暂无借还记录</div>
        </div>

        <!-- 处置记录 -->
        <div v-if="detail.disposals?.length" class="mb-5">
          <h4 class="text-sm font-semibold mb-3">处置记录</h4>
          <div class="overflow-x-auto">
            <table class="w-full text-[13px]">
              <thead>
                <tr class="border-b border-border text-left text-muted">
                  <th class="px-2 py-1.5 font-medium">处置类型</th>
                  <th class="px-2 py-1.5 font-medium">金额</th>
                  <th class="px-2 py-1.5 font-medium">翻新费</th>
                  <th class="px-2 py-1.5 font-medium">原因</th>
                  <th class="px-2 py-1.5 font-medium">时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="d in detail.disposals" :key="d.id" class="border-b border-border-light">
                  <td class="px-2 py-1.5">{{ DISPOSAL_TYPE_MAP[d.disposal_type] || d.disposal_type }}</td>
                  <td class="px-2 py-1.5 font-mono">{{ d.amount != null ? '¥' + d.amount.toFixed(2) : '-' }}</td>
                  <td class="px-2 py-1.5 font-mono">{{ d.refurbish_cost != null ? '¥' + d.refurbish_cost.toFixed(2) : '-' }}</td>
                  <td class="px-2 py-1.5">{{ d.reason || '-' }}</td>
                  <td class="px-2 py-1.5">{{ fmtDate(d.created_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-else-if="loading" class="modal-body flex items-center justify-center py-12">
        <span class="text-muted text-sm">加载中...</span>
      </div>
    </div>
  </div>
</template>
```

**Step 2: 构建验证**

Run: `cd frontend && npm run build`
Expected: 编译通过，无错误。

**Step 3: Commit**

```bash
git add frontend/src/components/business/demo/DemoUnitDetailModal.vue
git commit -m "feat: 新增样机明细弹窗组件（时间线+借还表格+处置记录）"
```

---

### Task 3: 前端 — DemoUnitList 集成明细弹窗

**Files:**
- Modify: `frontend/src/components/business/demo/DemoUnitList.vue`

**Step 1: 导入组件并添加状态**

在 `DemoUnitList.vue` 的 `<script setup>` 中：

1. 添加 import（在 `DemoDisposalModal` import 后面）：
```javascript
import DemoUnitDetailModal from './DemoUnitDetailModal.vue'
```

2. 添加状态变量（在 `disposalType` ref 后面）：
```javascript
const showDetailModal = ref(false)
const detailUnitId = ref(null)

const openDetail = (u) => {
  detailUnitId.value = u.id
  showDetailModal.value = true
}
```

**Step 2: 桌面端表格行添加点击事件**

修改桌面表格的 `<tr>`（约第 80-84 行），添加 `@click` 和 `cursor-pointer`：

```html
<!-- 修改前 -->
<tr
  v-for="u in sortedUnits"
  :key="u.id"
  class="hover:bg-elevated"
  :class="{ 'text-error': u.is_overdue }"
>

<!-- 修改后 -->
<tr
  v-for="u in sortedUnits"
  :key="u.id"
  class="hover:bg-elevated cursor-pointer"
  :class="{ 'text-error': u.is_overdue }"
  @click="openDetail(u)"
>
```

**Step 3: 操作按钮阻止冒泡**

操作列的按钮需要 `@click.stop` 防止点击按钮时也打开明细弹窗。修改所有操作按钮（约第 104-116 行），给每个 `@click` 加 `.stop` 修饰符：

```html
<template v-if="u.status === 'in_stock'">
  <button class="btn btn-primary btn-sm text-xs" @click.stop="openLoan(u)">借出</button>
  <button class="btn btn-secondary btn-sm text-xs" @click.stop="openDisposal(u, 'sale')">转销售</button>
  <button class="btn btn-secondary btn-sm text-xs" @click.stop="openDisposal(u, 'conversion')">翻新</button>
  <button class="btn btn-error btn-sm text-xs" @click.stop="openDisposal(u, 'scrap')">报废</button>
</template>
<template v-else-if="u.status === 'lent_out'">
  <button class="btn btn-primary btn-sm text-xs" @click.stop="openReturn(u)">归还</button>
  <button class="btn btn-secondary btn-sm text-xs" @click.stop="openDisposal(u, 'sale')">转销售</button>
  <button class="btn btn-error btn-sm text-xs" @click.stop="openDisposal(u, 'loss')">登记丢失</button>
</template>
<template v-else-if="u.status === 'repairing'">
  <button class="btn btn-error btn-sm text-xs" @click.stop="openDisposal(u, 'scrap')">报废</button>
</template>
```

**Step 4: 移动端卡片添加点击事件**

修改移动端卡片的外层 div（约第 33-37 行），添加点击事件：

```html
<!-- 修改前 -->
<div
  v-for="u in sortedUnits"
  :key="u.id"
  class="card p-3"
  :class="{ 'border-error': u.is_overdue }"
>

<!-- 修改后 -->
<div
  v-for="u in sortedUnits"
  :key="u.id"
  class="card p-3 cursor-pointer"
  :class="{ 'border-error': u.is_overdue }"
  @click="openDetail(u)"
>
```

同样给移动端的操作按钮加 `.stop`（约第 59-64 行）：

```html
<template v-if="u.status === 'in_stock'">
  <button class="text-primary" @click.stop="openLoan(u)">借出</button>
  <button class="text-success" @click.stop="openDisposal(u, 'sale')">转销售</button>
</template>
<template v-else-if="u.status === 'lent_out'">
  <button class="text-primary" @click.stop="openReturn(u)">归还</button>
</template>
```

**Step 5: 在模板中添加弹窗组件**

在 `DemoDisposalModal` 后面（约第 164 行之后）添加：

```html
<DemoUnitDetailModal
  :visible="showDetailModal"
  :unit-id="detailUnitId"
  @update:visible="showDetailModal = $event"
/>
```

**Step 6: 构建验证**

Run: `cd frontend && npm run build`
Expected: 编译通过。

**Step 7: Commit**

```bash
git add frontend/src/components/business/demo/DemoUnitList.vue
git commit -m "feat: 样机台账列表支持点击行查看明细弹窗"
```

---

### Task 4: 验证

**Step 1: 启动前后端**

确保后端和前端 dev server 都在运行。

**Step 2: 验证 SN 码搜索**

1. 打开样机管理页面
2. 在搜索框输入一个已知的 SN 码
3. 确认能搜到对应样机

**Step 3: 验证明细弹窗**

1. 点击样机台账列表的某一行
2. 确认弹窗打开，显示基本信息、时间线、借还记录
3. 点击操作按钮（借出、转销售等），确认不会触发弹窗打开
4. 移动端视图同样点击卡片测试

**Step 4: 最终 Commit（如有微调）**

```bash
git add -A
git commit -m "fix: 样机明细弹窗和SN搜索微调"
```
