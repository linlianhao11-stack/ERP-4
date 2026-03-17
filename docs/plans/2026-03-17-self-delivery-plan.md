# 自配送选项 + 快递公司扩充 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在发货流程中新增"自配送"物流选项（提交后直接已签收/已送达），扩充快递公司列表至 29 项，并将快递选择下拉框改为可搜索。

**Architecture:** 复用现有 self_pickup 逻辑路径，新增 self_delivery carrier_code。后端提取 `NO_LOGISTICS_CARRIERS` 集合统一判断，前端用已有的 `SearchableSelect` 组件替换原生 `<select>`。

**Tech Stack:** FastAPI + Tortoise ORM（后端），Vue 3 Composition API + SearchableSelect 组件（前端）

---

### Task 1: 后端 — 扩充快递公司列表 + 提取无物流常量

**Files:**
- Modify: `backend/app/config.py:47-60`
- Modify: `backend/app/routers/logistics.py:12` (import)

**Step 1: 修改 `backend/app/config.py`**

将 `CARRIER_LIST` 替换为完整的 29 项，并新增 `NO_LOGISTICS_CARRIERS` 常量：

```python
# 快递公司列表
CARRIER_LIST = [
    {"code": "self_pickup", "name": "上门自提"},
    {"code": "self_delivery", "name": "自配送"},
    {"code": "shunfeng", "name": "顺丰速运"},
    {"code": "shunfengkuaiyun", "name": "顺丰快运"},
    {"code": "yuantong", "name": "圆通速递"},
    {"code": "zhongtong", "name": "中通快递"},
    {"code": "zhongtongkuaiyun", "name": "中通快运"},
    {"code": "yunda", "name": "韵达快递"},
    {"code": "yundakuaiyun", "name": "韵达快运"},
    {"code": "shentong", "name": "申通快递"},
    {"code": "ems", "name": "EMS"},
    {"code": "jd", "name": "京东物流"},
    {"code": "jtexpress", "name": "极兔速递"},
    {"code": "debangkuaidi", "name": "德邦快递"},
    {"code": "huitongkuaidi", "name": "百世快递"},
    {"code": "tiantian", "name": "天天快递"},
    {"code": "youzhengguonei", "name": "中国邮政"},
    {"code": "youzhengbk", "name": "邮政标准快递"},
    {"code": "kuayue", "name": "跨越速运"},
    {"code": "fengwang", "name": "丰网速运"},
    {"code": "annengwuliu", "name": "安能快运"},
    {"code": "yimidida", "name": "壹米滴答"},
    {"code": "ztky", "name": "中铁快运"},
    {"code": "zhaijisong", "name": "宅急送"},
    {"code": "guotongkuaidi", "name": "国通快递"},
    {"code": "jiayunmeiwuliu", "name": "加运美"},
    {"code": "xinfengwuliu", "name": "信丰物流"},
    {"code": "jinguangsudikuaijian", "name": "京广速递"},
]

# 无需物流跟踪的配送方式（自提/自配送）
NO_LOGISTICS_CARRIERS = {"self_pickup", "self_delivery"}
```

**Step 2: 修改 `backend/app/routers/logistics.py` import**

在第 12 行的 import 中加入 `NO_LOGISTICS_CARRIERS`：

```python
from app.config import CARRIER_LIST, NO_LOGISTICS_CARRIERS, KD100_KEY, KD100_CUSTOMER
```

**Step 3: 验证**

Run: `cd /Users/lin/Desktop/erp-4 && python -c "from app.config import CARRIER_LIST, NO_LOGISTICS_CARRIERS; print(len(CARRIER_LIST), NO_LOGISTICS_CARRIERS)"`
Expected: `28 {'self_pickup', 'self_delivery'}` （28 项因为列表实际 28 条）

---

### Task 2: 后端 — 修改 3 个端点的自提/自配送判断逻辑

**Files:**
- Modify: `backend/app/routers/logistics.py:300-314` (ship_order_items)
- Modify: `backend/app/routers/logistics.py:487-501` (ship_order_items 物流跟踪+返回消息)
- Modify: `backend/app/routers/logistics.py:516-547` (add_shipment)
- Modify: `backend/app/routers/logistics.py:556-587` (ship_order / edit)

**核心逻辑：** 将所有 `== "self_pickup"` 判断替换为 `in NO_LOGISTICS_CARRIERS`，状态文本根据 carrier_code 区分。

**辅助函数**（加在 `_shipment_to_dict` 函数之后）：

```python
def _no_logistics_status_text(carrier_code: str) -> str:
    """无物流配送方式的状态文本"""
    return "已送达" if carrier_code == "self_delivery" else "已自提"

def _no_logistics_message(carrier_code: str) -> str:
    """无物流配送方式的返回消息"""
    return "已标记送达" if carrier_code == "self_delivery" else "已标记自提完成"
```

**Step 1: 修改 `ship_order_items`（POST /{order_id}/ship）**

第 300 行：
```python
# 旧
is_self_pickup = data.is_self_pickup or data.carrier_code == "self_pickup"
# 新
is_no_logistics = data.is_self_pickup or data.carrier_code in NO_LOGISTICS_CARRIERS
```

第 301-302 行：
```python
# 旧
if not is_self_pickup and not data.tracking_no:
# 新
if not is_no_logistics and not data.tracking_no:
```

第 313-314 行：
```python
# 旧
status="signed" if is_self_pickup else "shipped",
status_text="已自提" if is_self_pickup else "已发货"
# 新
status="signed" if is_no_logistics else "shipped",
status_text=_no_logistics_status_text(data.carrier_code) if is_no_logistics else "已发货"
```

第 487 行：
```python
# 旧
if not is_self_pickup and data.tracking_no:
# 新
if not is_no_logistics and data.tracking_no:
```

第 501 行：
```python
# 旧
"message": "已标记自提完成" if is_self_pickup else "发货成功",
# 新
"message": _no_logistics_message(data.carrier_code) if is_no_logistics else "发货成功",
```

**Step 2: 修改 `add_shipment`（POST /{order_id}/add）**

第 516 行：
```python
# 旧
is_self_pickup = data.carrier_code == "self_pickup"
# 新
is_no_logistics = data.carrier_code in NO_LOGISTICS_CARRIERS
```

第 526-527 行：
```python
# 旧
status="signed" if is_self_pickup else "shipped",
status_text="已自提" if is_self_pickup else "已发货"
# 新
status="signed" if is_no_logistics else "shipped",
status_text=_no_logistics_status_text(data.carrier_code) if is_no_logistics else "已发货"
```

第 534 行：
```python
# 旧
if not is_self_pickup and data.tracking_no:
# 新
if not is_no_logistics and data.tracking_no:
```

第 547 行：
```python
# 旧
return {"message": "已标记自提完成" if is_self_pickup else "物流单已添加", ...}
# 新
return {"message": _no_logistics_message(data.carrier_code) if is_no_logistics else "物流单已添加", ...}
```

**Step 3: 修改 `ship_order`（PUT /shipment/{shipment_id}/ship）**

第 556 行：
```python
# 旧
is_self_pickup = data.carrier_code == "self_pickup"
# 新
is_no_logistics = data.carrier_code in NO_LOGISTICS_CARRIERS
```

第 564-565 行：
```python
# 旧
shipment.status = "signed" if is_self_pickup else "shipped"
shipment.status_text = "已自提" if is_self_pickup else "已发货"
# 新
shipment.status = "signed" if is_no_logistics else "shipped"
shipment.status_text = _no_logistics_status_text(data.carrier_code) if is_no_logistics else "已发货"
```

第 574 行：
```python
# 旧
if not is_self_pickup and data.tracking_no and tracking_changed:
# 新
if not is_no_logistics and data.tracking_no and tracking_changed:
```

第 587 行：
```python
# 旧
return {"message": "已标记自提完成" if is_self_pickup else "发货信息已保存", ...}
# 新
return {"message": _no_logistics_message(data.carrier_code) if is_no_logistics else "发货信息已保存", ...}
```

**Step 4: 验证后端可正常导入**

Run: `cd /Users/lin/Desktop/erp-4 && python -c "from app.routers.logistics import router; print('OK')"`
Expected: `OK`

**Step 5: 提交后端改动**

```bash
git add backend/app/config.py backend/app/routers/logistics.py
git commit -m "feat: 新增自配送选项 + 扩充快递公司列表至28家"
```

---

### Task 3: 前端 — 替换快递公司下拉框为 SearchableSelect + 支持自配送

**Files:**
- Modify: `frontend/src/components/business/logistics/ShipmentDetailModal.vue`

**关键信息：**
- `SearchableSelect` 组件路径：`../../common/SearchableSelect.vue`（相对于 ShipmentDetailModal）
- 接口：`options=[{id, label}]`，`v-model` 绑定选中的 `id`
- 选中时 emit `update:modelValue`，需手动触发 carrier_name 同步
- 不支持 `@change` 事件，用 `watch` 代替

**Step 1: 添加 import**

在 `<script setup>` 的 import 区域（第 262 行附近）添加：

```javascript
import SearchableSelect from '../../common/SearchableSelect.vue'
```

**Step 2: 添加 carrierOptions computed**

在辅助函数区域（第 326 行附近）添加：

```javascript
/** 快递公司列表转 SearchableSelect 格式 */
const carrierOptions = computed(() =>
  (props.carriers || []).map(c => ({ id: c.code, label: c.name }))
)

/** 判断是否为无物流配送方式 */
const isNoLogistics = (code) => code === 'self_pickup' || code === 'self_delivery'

/** 无物流配送的提示文案 */
const noLogisticsHint = (code) =>
  code === 'self_delivery' ? '自配送（无需快递单号）' : '客户上门自提'

/** 发货按钮文案 */
const shipBtnText = (code) => {
  if (code === 'self_pickup') return '确认自提'
  if (code === 'self_delivery') return '确认送达'
  return '确认发货'
}

/** legacy 表单保存按钮文案 */
const legacySaveBtnText = (code, isEditing) => {
  if (code === 'self_pickup') return '确认自提'
  if (code === 'self_delivery') return '确认送达'
  return isEditing ? '保存修改' : '添加'
}
```

**Step 3: 用 watch 替代 @change 同步 carrier_name**

修改 `onShipCarrierChange` 和 `onCarrierChange`，改为 watch：

```javascript
/** 发货表单快递公司选择变化 — 自动同步 carrier_name */
watch(() => shipForm.carrier_code, (code) => {
  const c = props.carriers?.find(x => x.code === code)
  if (c) shipForm.carrier_name = c.name
})

/** 编辑表单快递公司选择变化 — 自动同步 carrier_name */
watch(() => shipmentForm.carrier_code, (code) => {
  const c = props.carriers?.find(x => x.code === code)
  if (c) shipmentForm.carrier_name = c.name
})
```

删除原来的 `onShipCarrierChange` 函数（第 412-415 行）和 `onCarrierChange` 函数（第 515-518 行）。

**Step 4: 修改发货表单模板（第 169-202 行）**

替换快递信息区域：

```html
<!-- 快递信息 -->
<div class="grid grid-cols-2 gap-2">
  <div>
    <label class="label text-xs">快递公司</label>
    <SearchableSelect
      v-model="shipForm.carrier_code"
      :options="carrierOptions"
      placeholder="请选择快递公司"
      search-placeholder="搜索快递公司..."
    />
  </div>
  <div v-if="isNoLogistics(shipForm.carrier_code)" class="flex items-end pb-1">
    <span class="text-sm text-success font-semibold">{{ noLogisticsHint(shipForm.carrier_code) }}</span>
  </div>
  <div v-else>
    <label class="label text-xs">快递单号</label>
    <input v-model="shipForm.tracking_no" class="input text-sm py-1" placeholder="输入快递单号">
  </div>
  <div
    v-if="!isNoLogistics(shipForm.carrier_code) && ['shunfeng', 'shunfengkuaiyun', 'zhongtong'].includes(shipForm.carrier_code)"
    class="col-span-2"
  >
    <label class="label text-xs">
      手机号后四位
      <span class="text-warning font-normal">
        （{{ carriers.find(c => c.code === shipForm.carrier_code)?.name }}必填）
      </span>
    </label>
    <input v-model="shipForm.phone" class="input text-sm py-1" placeholder="收/寄件人手机号后四位" maxlength="11">
  </div>
</div>
<div class="flex gap-2 pt-2">
  <button @click="submitShip" class="btn btn-primary btn-sm flex-1">
    {{ shipBtnText(shipForm.carrier_code) }}
  </button>
  <button @click="showShipForm = false" class="btn btn-secondary btn-sm flex-1">取消</button>
</div>
```

**Step 5: 修改 legacy 表单模板（第 208-245 行）**

替换快递信息区域：

```html
<div class="grid grid-cols-2 gap-2">
  <div>
    <label class="label text-xs">快递公司</label>
    <SearchableSelect
      v-model="shipmentForm.carrier_code"
      :options="carrierOptions"
      placeholder="请选择快递公司"
      search-placeholder="搜索快递公司..."
    />
  </div>
  <div v-if="isNoLogistics(shipmentForm.carrier_code)" class="flex items-end pb-1">
    <span class="text-sm text-success font-semibold">{{ noLogisticsHint(shipmentForm.carrier_code) }}</span>
  </div>
  <div v-else>
    <label class="label text-xs">快递单号</label>
    <input v-model="shipmentForm.tracking_no" class="input text-sm py-1" placeholder="输入快递单号">
  </div>
  <div
    v-if="!isNoLogistics(shipmentForm.carrier_code) && ['shunfeng', 'shunfengkuaiyun', 'zhongtong'].includes(shipmentForm.carrier_code)"
    class="col-span-2"
  >
    <label class="label text-xs">
      手机号后四位
      <span class="text-warning font-normal">
        （{{ carriers.find(c => c.code === shipmentForm.carrier_code)?.name }}必填）
      </span>
    </label>
    <input v-model="shipmentForm.phone" class="input text-sm py-1" placeholder="收/寄件人手机号后四位" maxlength="11">
  </div>
  <div class="col-span-2">
    <label class="label text-xs">SN码 <span class="text-muted font-normal">(选填，多个用逗号/空格/换行分隔)</span></label>
    <textarea v-model="shipmentForm.sn_code" class="input text-sm py-1" rows="2" placeholder="输入SN码"></textarea>
  </div>
</div>
<div class="flex gap-2 pt-2">
  <button @click="saveShipment(shipmentDetail.order.id)" class="btn btn-primary btn-sm flex-1">
    {{ legacySaveBtnText(shipmentForm.carrier_code, editingShipmentId) }}
  </button>
  <button @click="resetShipmentForm" class="btn btn-secondary btn-sm flex-1">取消</button>
</div>
```

**Step 6: 修改 `submitShip` 中的 self_pickup 判断（第 424-428 行）**

```javascript
// 旧
const isSelfPickup = shipForm.carrier_code === 'self_pickup'
if (!isSelfPickup && !shipForm.tracking_no) {
// 新
const noLogistics = isNoLogistics(shipForm.carrier_code)
if (!noLogistics && !shipForm.tracking_no) {
```

第 449 行：
```javascript
// 旧
is_self_pickup: isSelfPickup,
// 新
is_self_pickup: noLogistics,
```

**Step 7: 修改 `saveShipment` 中的 self_pickup 判断（第 526 行）**

```javascript
// 旧
if (shipmentForm.carrier_code !== 'self_pickup' && !shipmentForm.tracking_no) {
// 新
if (!isNoLogistics(shipmentForm.carrier_code) && !shipmentForm.tracking_no) {
```

**Step 8: 验证前端构建**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`
Expected: 构建成功，无错误

**Step 9: 提交前端改动**

```bash
git add frontend/src/components/business/logistics/ShipmentDetailModal.vue
git commit -m "feat: 快递公司下拉框改为可搜索 + 支持自配送选项"
```
