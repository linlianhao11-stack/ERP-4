# 代采代发订单详情 + 物流跟踪 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为代采代发模块添加订单详情弹窗（含物流轨迹时间线）、发货时支持手机尾号、列表显示物流状态，并顺便拆分大组件提升代码质量。

**Architecture:** 新建 `DropshipOrderDetail.vue` 详情弹窗组件，从 `DropshipOrdersPanel.vue` 拆出发货/取消弹窗为独立组件。后端模型新增 `phone` 字段，列表 API 增加 `tracking_status`，新增物流刷新端点。共享快递公司常量。

**Tech Stack:** Vue 3 (Composition API) + Tailwind CSS 4 + FastAPI + Tortoise ORM + 快递100 API

---

### Task 1: 后端 — 模型新增 phone 字段 + 迁移

**Files:**
- Modify: `backend/app/models/dropship.py:44` (在 last_tracking_info 后加 phone)
- Modify: `backend/app/migrations.py` (末尾新增迁移函数)

**Step 1: 模型新增 phone 字段**

在 `backend/app/models/dropship.py` 的 `last_tracking_info` 字段后添加:

```python
    phone = fields.CharField(max_length=11, null=True)  # 收/寄件人手机号（顺丰/中通查询需要）
```

**Step 2: 新增迁移函数**

在 `backend/app/migrations.py` 末尾新增:

```python
async def migrate_dropship_phone():
    """代采代发订单新增 phone 字段（收/寄件人手机号，顺丰/中通查询需要）"""
    conn = connections.get("default")
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE dropship_orders ADD COLUMN phone VARCHAR(11);
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)
    logger.info("代采代发: phone 字段已添加")
```

**Step 3: 在 `_run_migrations_inner` 中注册调用**

找到 `await migrate_dropship_module()` 那一行，在其后添加:

```python
    await migrate_dropship_phone()
```

**Step 4: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && orb start && docker exec -i erp4-web python -c "from app.models.dropship import DropshipOrder; print('phone' in [f for f in DropshipOrder._meta.fields_map])" 2>/dev/null || echo "检查模型字段是否包含 phone"`

---

### Task 2: 后端 — Schema + 发货 API 支持 phone

**Files:**
- Modify: `backend/app/schemas/dropship.py:49-52` (DropshipShipRequest 加 phone)
- Modify: `backend/app/routers/dropship.py:615-635` (ship_order 传 phone)
- Modify: `backend/app/services/dropship_service.py:387-508` (ship_dropship_order 接收+存储+传递 phone)

**Step 1: Schema 新增 phone 字段**

在 `backend/app/schemas/dropship.py` 的 `DropshipShipRequest` 中添加:

```python
class DropshipShipRequest(BaseModel):
    carrier_code: str
    carrier_name: str
    tracking_no: str
    phone: Optional[str] = None  # 收/寄件人手机号（顺丰/中通需要）
```

**Step 2: 路由传递 phone**

修改 `backend/app/routers/dropship.py` 的 `ship_order` 函数:

```python
    order = await ship_dropship_order(
        order_id=order_id,
        carrier_code=data.carrier_code,
        carrier_name=data.carrier_name,
        tracking_no=data.tracking_no,
        phone=data.phone,
        user=user,
    )
```

**Step 3: 服务层接收 phone**

修改 `backend/app/services/dropship_service.py` 的 `ship_dropship_order` 函数签名:

```python
async def ship_dropship_order(
    order_id: int,
    carrier_code: str,
    carrier_name: str,
    tracking_no: str,
    user: User,
    phone: str = None,
) -> DropshipOrder:
```

在 "2. 更新物流信息" 部分添加:

```python
        order.carrier_code = carrier_code
        order.carrier_name = carrier_name
        order.tracking_no = tracking_no
        order.phone = phone  # 新增
```

修改快递100订阅调用（事务外部分）:

```python
    try:
        from app.services.logistics_service import subscribe_kd100
        await subscribe_kd100(carrier_code, tracking_no, order.id, phone=phone)
        order.kd100_subscribed = True
        await order.save()
```

**Step 4: 详情 API 返回 phone**

修改 `backend/app/routers/dropship.py` 的 `get_dropship_order` 函数返回字典，在 `last_tracking_info` 后添加:

```python
        "phone": order.phone,
```

---

### Task 3: 后端 — 列表 API 增加 tracking_status + 物流刷新端点

**Files:**
- Modify: `backend/app/routers/dropship.py:322-393` (list 增加 tracking_status)
- Modify: `backend/app/routers/dropship.py` (新增物流刷新端点)

**Step 1: 列表 API 返回 tracking_status**

在 `list_dropship_orders` 函数中，为每条记录解析 `last_tracking_info` 提取物流状态。在返回 items 列表的字典推导中添加:

```python
                "carrier_name": o.carrier_name,
                "tracking_status": _parse_tracking_status(o.last_tracking_info, o.status),
```

在文件顶部（router 定义之前）添加辅助函数:

```python
import json

def _parse_tracking_status(last_tracking_info: str | None, order_status: str) -> str | None:
    """从 last_tracking_info JSON 解析最新物流状态文本"""
    if not last_tracking_info:
        if order_status == "shipped":
            return "待查询"
        return None
    try:
        data = json.loads(last_tracking_info)
        if isinstance(data, dict):
            # 快递100格式: {state: "0", ischeck: "0", ...}
            if str(data.get("ischeck")) == "1":
                return "已签收"
            from app.config import KD100_STATE_MAP
            state = str(data.get("state", ""))
            if state in KD100_STATE_MAP:
                return KD100_STATE_MAP[state][1]
        return "运输中"
    except (json.JSONDecodeError, TypeError, KeyError):
        return None
```

**Step 2: 新增代采代发物流刷新端点**

在 `complete_order` 之前添加:

```python
@router.post("/{order_id}/refresh-tracking")
async def refresh_tracking(
    order_id: int,
    user: User = Depends(require_permission("dropship")),
):
    """刷新代采代发订单的物流信息（查询快递100）"""
    order = await DropshipOrder.filter(id=order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if not order.tracking_no or not order.carrier_code:
        raise HTTPException(status_code=400, detail="该订单没有物流信息")

    try:
        from app.services.logistics_service import query_kd100
        resp = await query_kd100(order.carrier_code, order.tracking_no, phone=order.phone)

        if resp.get("message") == "ok" and resp.get("data"):
            tracking_data = resp["data"]
            order.last_tracking_info = json.dumps(resp, ensure_ascii=False)

            # 检查是否已签收
            if str(resp.get("ischeck")) == "1":
                if order.status == "shipped":
                    order.status = "completed"
                    logger.info(f"快递已签收，自动完成: {order.ds_no}")
            await order.save()

            return {
                "id": order.id,
                "ds_no": order.ds_no,
                "status": order.status,
                "last_tracking_info": order.last_tracking_info,
                "tracking_status": _parse_tracking_status(order.last_tracking_info, order.status),
            }
        else:
            return {
                "id": order.id,
                "message": resp.get("message", "查询无结果"),
            }
    except Exception as e:
        logger.warning(f"物流刷新失败: {order.ds_no}, 错误: {e}")
        raise HTTPException(status_code=500, detail=f"物流查询失败: {str(e)}")
```

---

### Task 4: 前端 — 提取共享常量 + API 函数

**Files:**
- Create: `frontend/src/constants/carriers.js`
- Modify: `frontend/src/api/dropship.js` (添加 refreshDropshipTracking)

**Step 1: 创建快递公司常量文件**

```javascript
/**
 * 快递公司列表（与快递100 carrier_code 对应）
 */
export const CARRIERS = [
  { code: 'shunfeng', name: '顺丰速运' },
  { code: 'zhongtong', name: '中通快递' },
  { code: 'yuantong', name: '圆通速递' },
  { code: 'shentong', name: '申通快递' },
  { code: 'yunda', name: '韵达快递' },
  { code: 'jd', name: '京东物流' },
  { code: 'debangkuaidi', name: '德邦快递' },
  { code: 'ems', name: 'EMS' },
]

/** 需要手机号后四位才能查询物流的快递公司 */
export const PHONE_REQUIRED_CARRIERS = new Set(['shunfeng', 'shunfengkuaiyun', 'zhongtong'])
```

**Step 2: 添加物流刷新 API**

在 `frontend/src/api/dropship.js` 中添加:

```javascript
// 物流
export const refreshDropshipTracking = (id) => api.post('/dropship/' + id + '/refresh-tracking')
```

---

### Task 5: 前端 — 拆分发货弹窗为独立组件（含 phone 支持）

**Files:**
- Create: `frontend/src/components/business/dropship/DropshipShipModal.vue`
- Modify: `frontend/src/components/business/DropshipOrdersPanel.vue` (移除内联发货弹窗，改用新组件)

**Step 1: 创建 DropshipShipModal.vue**

```vue
<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('update:visible', false)">
    <div class="modal-content" style="max-width:520px">
      <div class="modal-header">
        <h3 class="modal-title">确认发货</h3>
        <button @click="$emit('update:visible', false)" class="modal-close">&times;</button>
      </div>
      <div class="modal-body">
        <div class="space-y-4">
          <!-- 订单摘要 -->
          <div class="bg-elevated rounded-lg p-3 text-sm">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-mono font-semibold">{{ order?.ds_no }}</span>
            </div>
            <div class="text-muted">{{ order?.product_name }}</div>
            <div class="text-muted text-xs mt-1">
              {{ order?.supplier_name }} → {{ order?.customer_name }}
            </div>
          </div>
          <!-- 快递公司 -->
          <div>
            <label class="label" for="ship-carrier">快递公司 *</label>
            <select id="ship-carrier" v-model="form.carrier_code" class="input">
              <option value="" disabled>请选择快递公司</option>
              <option v-for="c in CARRIERS" :key="c.code" :value="c.code">{{ c.name }}</option>
            </select>
          </div>
          <!-- 快递单号 -->
          <div>
            <label class="label" for="ship-tracking">快递单号 *</label>
            <input id="ship-tracking" v-model="form.tracking_no" class="input" placeholder="输入快递单号">
          </div>
          <!-- 手机号（顺丰/中通需要） -->
          <div v-if="needPhone">
            <label class="label" for="ship-phone">手机号后四位</label>
            <input id="ship-phone" v-model="form.phone" class="input" placeholder="收/寄件人手机号后四位（用于物流查询）" maxlength="4">
            <p class="text-xs text-muted mt-1">{{ carrierName }}查询物流需要手机号后四位</p>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" @click="$emit('update:visible', false)" class="btn btn-sm btn-secondary">取消</button>
        <button type="button" @click="handleShip" class="btn btn-sm btn-primary"
          :disabled="submitting || !form.carrier_code || !form.tracking_no.trim()">
          {{ submitting ? '发货中...' : '确认发货' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, computed, watch } from 'vue'
import { CARRIERS, PHONE_REQUIRED_CARRIERS } from '../../../constants/carriers'
import { shipDropshipOrder } from '../../../api/dropship'
import { useAppStore } from '../../../stores/app'

const props = defineProps({
  visible: Boolean,
  order: Object,
})
const emit = defineEmits(['update:visible', 'shipped'])

const appStore = useAppStore()
const submitting = computed(() => appStore.submitting)

const form = reactive({
  carrier_code: '',
  tracking_no: '',
  phone: '',
})

const needPhone = computed(() => PHONE_REQUIRED_CARRIERS.has(form.carrier_code))
const carrierName = computed(() => CARRIERS.find(c => c.code === form.carrier_code)?.name || '')

// 弹窗打开时重置表单
watch(() => props.visible, (v) => {
  if (v) {
    form.carrier_code = ''
    form.tracking_no = ''
    form.phone = ''
  }
})

const handleShip = async () => {
  if (!form.carrier_code || !form.tracking_no.trim()) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const selectedCarrier = CARRIERS.find(c => c.code === form.carrier_code)
    await shipDropshipOrder(props.order.id, {
      carrier_code: form.carrier_code,
      carrier_name: selectedCarrier?.name || '',
      tracking_no: form.tracking_no.trim(),
      phone: form.phone.trim() || null,
    })
    appStore.showToast('发货成功')
    emit('update:visible', false)
    emit('shipped')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '发货失败', 'error')
  } finally {
    appStore.submitting = false
  }
}
</script>
```

**Step 2: 修改 DropshipOrdersPanel.vue**

- 移除内联发货弹窗 HTML（第 226-267 行的 `<!-- 发货弹窗 -->` 整块）
- 移除 script 中的发货相关变量和函数（第 422-553 行的 carriers、shipForm、shipOrder、showShipModal、openShipModal、handleShip）
- 导入新组件，在 `DropshipOrderForm` 后添加:

```vue
    <DropshipShipModal
      :visible="showShipModal"
      :order="shipOrder"
      @update:visible="showShipModal = $event"
      @shipped="loadData"
    />
```

- 保留 `showShipModal` 和 `shipOrder` ref 给 handleAction 使用
- `openShipModal` 简化为设置 ref:

```javascript
const showShipModal = ref(false)
const shipOrder = ref(null)
const openShipModal = (order) => {
  shipOrder.value = order
  showShipModal.value = true
}
```

- 移除 `shipDropshipOrder` 的导入（已在新组件内导入）
- 移除 `carriers` 硬编码数组

---

### Task 6: 前端 — 拆分取消弹窗为独立组件

**Files:**
- Create: `frontend/src/components/business/dropship/DropshipCancelModal.vue`
- Modify: `frontend/src/components/business/DropshipOrdersPanel.vue`

**Step 1: 创建 DropshipCancelModal.vue**

```vue
<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('update:visible', false)">
    <div class="modal-content" style="max-width:480px">
      <div class="modal-header">
        <h3 class="modal-title">取消订单</h3>
        <button @click="$emit('update:visible', false)" class="modal-close">&times;</button>
      </div>
      <div class="modal-body">
        <div class="space-y-4">
          <div class="bg-elevated rounded-lg p-3 text-sm">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-mono font-semibold">{{ order?.ds_no }}</span>
              <StatusBadge type="dropshipStatus" :status="order?.status" />
            </div>
            <div class="text-muted">{{ order?.product_name }}</div>
            <div class="text-muted text-xs mt-1">
              {{ order?.supplier_name }} → {{ order?.customer_name }}
            </div>
          </div>
          <div>
            <label class="label" for="cancel-reason">取消原因（可选）</label>
            <textarea id="cancel-reason" v-model="reason" class="input" rows="3" placeholder="请输入取消原因..."></textarea>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" @click="$emit('update:visible', false)" class="btn btn-sm btn-secondary">返回</button>
        <button type="button" @click="handleCancel" class="btn btn-sm btn-danger" :disabled="submitting">
          {{ submitting ? '取消中...' : '确认取消' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import StatusBadge from '../../common/StatusBadge.vue'
import { cancelDropshipOrder } from '../../../api/dropship'
import { useAppStore } from '../../../stores/app'

const props = defineProps({
  visible: Boolean,
  order: Object,
})
const emit = defineEmits(['update:visible', 'cancelled'])

const appStore = useAppStore()
const submitting = computed(() => appStore.submitting)
const reason = ref('')

watch(() => props.visible, (v) => {
  if (v) reason.value = ''
})

const handleCancel = async () => {
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await cancelDropshipOrder(props.order.id, {
      reason: reason.value.trim() || null,
    })
    appStore.showToast('订单已取消')
    emit('update:visible', false)
    emit('cancelled')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '取消失败', 'error')
  } finally {
    appStore.submitting = false
  }
}
</script>
```

**Step 2: 修改 DropshipOrdersPanel.vue**

- 移除内联取消弹窗 HTML（第 269-303 行）
- 移除 script 中的取消相关变量和函数（cancelOrder, cancelReason, showCancelModal, openCancelModal, handleCancel）
- 导入新组件并使用:

```vue
    <DropshipCancelModal
      :visible="showCancelModal"
      :order="cancelOrder"
      @update:visible="showCancelModal = $event"
      @cancelled="loadData"
    />
```

- 保留 `showCancelModal`、`cancelOrder` ref 和简化的 `openCancelModal`:

```javascript
const showCancelModal = ref(false)
const cancelOrder = ref(null)
const openCancelModal = (order) => {
  cancelOrder.value = order
  showCancelModal.value = true
}
```

- 移除 `cancelDropshipOrder` 的导入

---

### Task 7: 前端 — 列表增加物流状态列 + 单号可点击

**Files:**
- Modify: `frontend/src/composables/useDropshipOrder.js` (增加 tracking_status 列)
- Modify: `frontend/src/components/business/DropshipOrdersPanel.vue` (单号可点击 + 物流状态列)

**Step 1: composable 增加列定义**

在 `useDropshipOrder.js` 的 `dropshipColumnDefs` 中，`tracking_no` 后添加:

```javascript
  tracking_status: { label: '物流状态', defaultVisible: true },
```

**Step 2: DropshipOrdersPanel — 表头增加物流状态列**

在 `tracking_no` 的 th 后添加:

```html
              <th v-if="isColumnVisible('tracking_status')" class="px-2 py-2 text-center">物流状态</th>
```

**Step 3: 表体增加物流状态列**

在 `tracking_no` 的 td 后添加:

```html
              <td v-if="isColumnVisible('tracking_status')" class="px-2 py-2 text-center">
                <span v-if="o.tracking_status" class="text-xs px-1.5 py-0.5 rounded-md"
                  :class="{
                    'bg-success/10 text-success': o.tracking_status === '已签收',
                    'bg-primary/10 text-primary': o.tracking_status === '运输中' || o.tracking_status === '待查询',
                    'bg-warning/10 text-warning': o.tracking_status === '待揽收',
                    'bg-elevated text-secondary': !['已签收','运输中','待查询','待揽收'].includes(o.tracking_status),
                  }">
                  {{ o.tracking_status }}
                </span>
                <span v-else class="text-muted">-</span>
              </td>
```

**Step 4: tfoot 增加物流状态列占位**

```html
              <td v-if="isColumnVisible('tracking_status')" class="px-2 py-2"></td>
```

**Step 5: 单号做成可点击链接**

修改 ds_no 的 td:

```html
              <td v-if="isColumnVisible('ds_no')" class="px-2 py-2 font-mono text-sm">
                <span v-if="['pending_payment','paid_pending_ship'].includes(o.status)" class="todo-dot mr-1.5"></span>
                <button type="button" class="text-primary hover:underline cursor-pointer" @click="openDetail(o)">
                  {{ o.ds_no }}
                </button>
                <span v-if="o.urged_at" class="badge badge-orange text-[10px] ml-1">催</span>
              </td>
```

移动端卡片的单号也做成可点击:

```html
            <button type="button" class="font-medium text-sm font-mono text-primary hover:underline" @click="openDetail(o)">
              <span v-if="['pending_payment','paid_pending_ship'].includes(o.status)" class="todo-dot mr-1"></span>
              {{ o.ds_no }}
              <span v-if="o.urged_at" class="badge badge-orange text-[10px] ml-1">催</span>
            </button>
```

**Step 6: 添加详情弹窗的状态和引用**

在 script 中添加:

```javascript
// 详情弹窗
const showDetailModal = ref(false)
const detailOrderId = ref(null)

const openDetail = (order) => {
  detailOrderId.value = order.id
  showDetailModal.value = true
}
```

在 template 中 DropshipOrderForm 后添加:

```vue
    <DropshipOrderDetail
      :visible="showDetailModal"
      :orderId="detailOrderId"
      @update:visible="showDetailModal = $event"
      @status-changed="loadData"
    />
```

---

### Task 8: 前端 — 创建订单详情弹窗组件

**Files:**
- Create: `frontend/src/components/business/dropship/DropshipOrderDetail.vue`

**Step 1: 创建完整组件**

这是最核心的新组件，包含 6 个信息区块 + 物流时间线。

```vue
<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal-content" style="max-width:680px; max-height:90vh; display:flex; flex-direction:column">
        <div class="modal-header">
          <div class="flex items-center gap-2">
            <h3 class="modal-title">订单详情</h3>
            <StatusBadge v-if="detail" type="dropshipStatus" :status="detail.status" />
          </div>
          <button @click="close" class="modal-close">&times;</button>
        </div>

        <div v-if="loading" class="modal-body flex items-center justify-center py-12">
          <span class="text-muted">加载中...</span>
        </div>

        <div v-else-if="detail" class="modal-body overflow-y-auto" style="flex:1; min-height:0">
          <div class="space-y-5">

            <!-- 顶部摘要 -->
            <div class="flex items-center justify-between">
              <div>
                <div class="font-mono text-lg font-semibold">{{ detail.ds_no }}</div>
                <div class="text-xs text-muted mt-0.5">{{ fmtDate(detail.created_at) }} · {{ detail.creator_name || '-' }}</div>
              </div>
              <div class="text-right">
                <div class="text-xs text-muted">毛利</div>
                <div class="text-lg font-bold font-mono"
                  :class="Number(detail.gross_profit) >= 0 ? 'text-success' : 'text-error'">
                  ¥{{ fmt(detail.gross_profit) }}
                  <span class="text-xs font-normal text-muted ml-1">{{ Number(detail.gross_margin).toFixed(1) }}%</span>
                </div>
              </div>
            </div>

            <!-- 采购信息 -->
            <section>
              <h4 class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">采购信息</h4>
              <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <div><span class="text-muted">供应商</span><span class="float-right">{{ detail.supplier_name }}</span></div>
                <div><span class="text-muted">商品</span><span class="float-right">{{ detail.product_name }}</span></div>
                <div><span class="text-muted">采购单价</span><span class="float-right font-mono">¥{{ fmt(detail.purchase_price) }}</span></div>
                <div><span class="text-muted">数量</span><span class="float-right">{{ detail.quantity }}</span></div>
                <div><span class="text-muted">采购总额</span><span class="float-right font-mono font-semibold">¥{{ fmt(detail.purchase_total) }}</span></div>
                <div><span class="text-muted">发票类型</span><span class="float-right">{{ detail.invoice_type === 'special' ? '专票' : '普票' }}</span></div>
                <div><span class="text-muted">采购税率</span><span class="float-right">{{ detail.purchase_tax_rate }}%</span></div>
              </div>
            </section>

            <!-- 销售信息 -->
            <section>
              <h4 class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">销售信息</h4>
              <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <div><span class="text-muted">客户</span><span class="float-right">{{ detail.customer_name }}</span></div>
                <div><span class="text-muted">平台订单号</span><span class="float-right font-mono text-xs">{{ detail.platform_order_no || '-' }}</span></div>
                <div><span class="text-muted">销售单价</span><span class="float-right font-mono">¥{{ fmt(detail.sale_price) }}</span></div>
                <div><span class="text-muted">销售总额</span><span class="float-right font-mono font-semibold">¥{{ fmt(detail.sale_total) }}</span></div>
                <div><span class="text-muted">销售税率</span><span class="float-right">{{ detail.sale_tax_rate }}%</span></div>
                <div><span class="text-muted">结算方式</span><span class="float-right">{{ detail.settlement_type === 'prepaid' ? '先款后货' : '赊销' }}</span></div>
              </div>
            </section>

            <!-- 物流信息 -->
            <section v-if="detail.tracking_no">
              <div class="flex items-center justify-between mb-2">
                <h4 class="text-xs font-semibold text-muted uppercase tracking-wider">物流信息</h4>
                <button type="button" @click="handleRefreshTracking" class="text-xs text-primary hover:underline"
                  :disabled="refreshing">
                  {{ refreshing ? '刷新中...' : '刷新物流' }}
                </button>
              </div>
              <div class="bg-elevated rounded-lg p-3 text-sm space-y-2">
                <div class="flex items-center justify-between">
                  <span>{{ detail.carrier_name || detail.carrier_code }}</span>
                  <span class="font-mono text-xs">{{ detail.tracking_no }}</span>
                </div>
                <!-- 物流摘要（最后一条） -->
                <div v-if="latestTracking" class="text-xs text-secondary">
                  {{ latestTracking.time }} — {{ latestTracking.desc }}
                </div>
                <!-- 展开完整时间线 -->
                <button v-if="trackingItems.length > 1" type="button"
                  @click="showFullTracking = !showFullTracking"
                  class="text-xs text-primary hover:underline">
                  {{ showFullTracking ? '收起' : `查看全部 ${trackingItems.length} 条` }}
                </button>
                <div v-if="showFullTracking && trackingItems.length" class="max-h-48 overflow-y-auto mt-2">
                  <div v-for="(item, i) in trackingItems" :key="i" class="flex gap-2 text-xs">
                    <div class="flex flex-col items-center">
                      <div class="w-2 h-2 rounded-full shrink-0 mt-1"
                        :class="i === 0 ? 'bg-success' : 'bg-line-strong'"></div>
                      <div v-if="i < trackingItems.length - 1" class="w-0.5 h-5 bg-line"></div>
                    </div>
                    <div class="pb-2">
                      <div class="text-muted">{{ item.time }}</div>
                      <div class="text-text">{{ item.desc }}</div>
                    </div>
                  </div>
                </div>
                <div v-if="!trackingItems.length" class="text-xs text-muted">暂无物流轨迹，请点击刷新获取</div>
              </div>
            </section>

            <!-- 财务单据 -->
            <section v-if="detail.payable_bill_no || detail.disbursement_bill_id || detail.receivable_bill_id">
              <h4 class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">财务单据</h4>
              <div class="text-sm space-y-1">
                <div v-if="detail.payable_bill_no" class="flex justify-between">
                  <span class="text-muted">应付单</span>
                  <span class="font-mono text-xs">{{ detail.payable_bill_no }}</span>
                </div>
                <div v-if="detail.disbursement_bill_id" class="flex justify-between">
                  <span class="text-muted">付款方式</span>
                  <span>{{ detail.payment_method === 'employee_advance' ? '冲减借支' : '银行转账' }}{{ detail.payment_employee_name ? ` · ${detail.payment_employee_name}` : '' }}</span>
                </div>
                <div v-if="detail.receivable_bill_id" class="flex justify-between">
                  <span class="text-muted">应收单</span>
                  <span class="font-mono text-xs">已创建</span>
                </div>
              </div>
            </section>

            <!-- 操作日志（时间线） -->
            <section>
              <h4 class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">操作记录</h4>
              <div class="text-xs space-y-1 text-secondary">
                <div>{{ fmtDate(detail.created_at) }} — 创建订单</div>
                <div v-if="detail.payable_bill_no">提交订单 → 待付款</div>
                <div v-if="detail.disbursement_bill_id">付款完成 → 已付待发</div>
                <div v-if="detail.urged_at">{{ fmtDate(detail.urged_at) }} — 催付款</div>
                <div v-if="detail.shipped_at">{{ fmtDate(detail.shipped_at) }} — 已发货</div>
                <div v-if="detail.status === 'completed'">订单完成</div>
                <div v-if="detail.status === 'cancelled'">
                  订单取消{{ detail.cancel_reason ? `：${detail.cancel_reason}` : '' }}
                </div>
              </div>
            </section>

            <!-- 备注 -->
            <section v-if="detail.note">
              <h4 class="text-xs font-semibold text-muted uppercase tracking-wider mb-2">备注</h4>
              <div class="text-sm text-secondary">{{ detail.note }}</div>
            </section>

          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import StatusBadge from '../../common/StatusBadge.vue'
import { getDropshipOrder, refreshDropshipTracking } from '../../../api/dropship'
import { useFormat } from '../../../composables/useFormat'
import { useAppStore } from '../../../stores/app'

const props = defineProps({
  visible: Boolean,
  orderId: Number,
})
const emit = defineEmits(['update:visible', 'status-changed'])

const { fmt, fmtDate } = useFormat()
const appStore = useAppStore()

const detail = ref(null)
const loading = ref(false)
const refreshing = ref(false)
const showFullTracking = ref(false)

const close = () => emit('update:visible', false)

// 解析物流轨迹
const trackingItems = computed(() => {
  if (!detail.value?.last_tracking_info) return []
  try {
    const data = JSON.parse(detail.value.last_tracking_info)
    const items = data?.data || []
    return items.map(item => ({
      time: item.ftime || item.time || '',
      desc: item.context || item.desc || '',
    }))
  } catch {
    return []
  }
})

const latestTracking = computed(() => trackingItems.value[0] || null)

// 加载详情
const loadDetail = async () => {
  if (!props.orderId) return
  loading.value = true
  showFullTracking.value = false
  try {
    const { data } = await getDropshipOrder(props.orderId)
    detail.value = data
  } catch (e) {
    appStore.showToast('加载订单详情失败', 'error')
    close()
  } finally {
    loading.value = false
  }
}

// 刷新物流
const handleRefreshTracking = async () => {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const { data } = await refreshDropshipTracking(props.orderId)
    if (data.last_tracking_info) {
      detail.value.last_tracking_info = data.last_tracking_info
    }
    if (data.status && data.status !== detail.value.status) {
      detail.value.status = data.status
      emit('status-changed')
    }
    appStore.showToast('物流信息已更新')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '物流刷新失败', 'error')
  } finally {
    refreshing.value = false
  }
}

watch(() => props.visible, (v) => {
  if (v) loadDetail()
})
</script>
```

---

### Task 9: 整合 + 清理 DropshipOrdersPanel.vue

**Files:**
- Modify: `frontend/src/components/business/DropshipOrdersPanel.vue`

**Step 1: 清理导入**

最终的 import 块应该是:

```javascript
import { ref, computed, onMounted } from 'vue'
import { Search, Plus, Upload, Download } from 'lucide-vue-next'
import ColumnMenu from '../common/ColumnMenu.vue'
import StatusBadge from '../common/StatusBadge.vue'
import PageToolbar from '../common/PageToolbar.vue'
import DateRangePicker from '../common/DateRangePicker.vue'
import DropshipOrderForm from './dropship/DropshipOrderForm.vue'
import DropshipOrderDetail from './dropship/DropshipOrderDetail.vue'
import DropshipShipModal from './dropship/DropshipShipModal.vue'
import DropshipCancelModal from './dropship/DropshipCancelModal.vue'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import { useDropshipOrder } from '../../composables/useDropshipOrder'
import { useAppStore } from '../../stores/app'
import {
  submitDropshipOrder, urgeDropshipOrder, completeDropshipOrder,
  importSuppliers, downloadSupplierTemplate
} from '../../api/dropship'
```

注意移除了 `reactive`（不再需要 shipForm）、`shipDropshipOrder`、`cancelDropshipOrder`。

**Step 2: 确认移除的代码块**

从 script 中移除:
- `carriers` 数组（已迁移到 constants/carriers.js）
- `shipForm` reactive 对象
- `handleShip` 函数
- `cancelReason` ref
- `handleCancel` 函数

从 template 中移除:
- 内联发货弹窗（原 `<div v-if="showShipModal">` 块）
- 内联取消弹窗（原 `<div v-if="showCancelModal">` 块）

**Step 3: build 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

---

### Task 10: 端到端验证 + 提交

**Step 1: 后端启动验证**

确认迁移正常、API 端点可用。

**Step 2: 前端 build 验证**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`
Expected: 编译成功，无错误

**Step 3: 功能验证（preview）**

- 启动开发服务器
- 访问代采代发页面
- 验证: 单号可点击 → 弹出详情弹窗
- 验证: 详情弹窗各区块信息展示
- 验证: 物流状态列正常显示
- 验证: 发货弹窗手机号字段（选择顺丰时出现）

**Step 4: 提交**

```bash
git add frontend/src/constants/carriers.js \
  frontend/src/components/business/dropship/DropshipShipModal.vue \
  frontend/src/components/business/dropship/DropshipCancelModal.vue \
  frontend/src/components/business/dropship/DropshipOrderDetail.vue \
  frontend/src/components/business/DropshipOrdersPanel.vue \
  frontend/src/composables/useDropshipOrder.js \
  frontend/src/api/dropship.js \
  backend/app/models/dropship.py \
  backend/app/schemas/dropship.py \
  backend/app/routers/dropship.py \
  backend/app/services/dropship_service.py \
  backend/app/migrations.py
git commit -m "feat(代采代发): 订单详情弹窗+物流跟踪+组件拆分"
```
