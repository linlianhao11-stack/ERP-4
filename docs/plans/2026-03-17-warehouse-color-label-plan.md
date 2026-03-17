# 仓库颜色标记 — 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为仓库增加颜色标记字段，让库存页面和销售页面的仓位标签按仓库颜色显示，方便区分售后仓等特殊仓库。

**Architecture:** Warehouse 模型新增 `color` 字段（默认 `"blue"`），通过已有的 `select_related("warehouse")` 零成本透传到商品库存列表 API，前端用 `badge-${color}` 动态渲染。设置页面仓库编辑弹窗增加 7 色圆形选择器。

**Tech Stack:** FastAPI + Tortoise ORM（后端），Vue 3 Composition API + Tailwind CSS 4（前端）

---

### Task 1: 后端模型 + Schema + 迁移

**Files:**
- Modify: `backend/app/models/warehouse.py:4-12`
- Modify: `backend/app/schemas/warehouse.py`
- Modify: `backend/app/migrations.py`

**Step 1: Warehouse 模型加 color 字段**

在 `backend/app/models/warehouse.py` 的 `Warehouse` 类中，`is_active` 字段之后添加：

```python
color = fields.CharField(max_length=20, default="blue")
```

**Step 2: Schema 加 color 校验**

在 `backend/app/schemas/warehouse.py` 中：

1. 顶部添加 `Literal` 导入：
```python
from typing import Optional, Literal
```

2. 定义合法颜色类型（放在 import 之后、class 之前）：
```python
WarehouseColor = Literal["blue", "green", "red", "yellow", "purple", "gray", "orange"]
```

3. `WarehouseCreate` 加字段：
```python
color: WarehouseColor = "blue"
```

4. `WarehouseUpdate` 加字段：
```python
color: Optional[WarehouseColor] = None
```

**Step 3: 数据库迁移函数**

在 `backend/app/migrations.py` 中：

1. 在 `_run_migrations_inner()` 函数末尾（`migrate_tracking_refresh_fields()` 之后）添加调用：
```python
await migrate_warehouse_color()
```

2. 在文件末尾添加迁移函数：
```python
async def migrate_warehouse_color():
    """v4.17: 仓库颜色标记字段"""
    conn = connections.get("default")
    cols = [r["column_name"] for r in (await conn.execute_query(
        "SELECT column_name FROM information_schema.columns WHERE table_name='warehouses'"
    ))[1]]
    if "color" not in cols:
        await conn.execute_query(
            "ALTER TABLE warehouses ADD COLUMN color VARCHAR(20) DEFAULT 'blue'"
        )
        logger.info("迁移完成: warehouses.color")
```

**Step 4: 验证后端启动无报错**

Run: `cd ~/Desktop/erp-4 && docker compose up -d && docker compose logs backend --tail=30`
Expected: 无报错，可以看到迁移日志 `迁移完成: warehouses.color`

**Step 5: Commit**

```bash
git add backend/app/models/warehouse.py backend/app/schemas/warehouse.py backend/app/migrations.py
git commit -m "feat: 仓库模型增加 color 字段 + 数据库迁移"
```

---

### Task 2: 后端 API — 仓库列表/创建/更新透传 color

**Files:**
- Modify: `backend/app/routers/warehouses.py:33-39` (list_warehouses 返回值)
- Modify: `backend/app/routers/warehouses.py:51` (create_warehouse create_kwargs)

**Step 1: 仓库列表 API 返回 color**

在 `backend/app/routers/warehouses.py` 的 `list_warehouses` 函数中，`result.append({...})` 字典里加上 `color` 字段。

原来（第 33-39 行）：
```python
result.append({
    "id": w.id, "name": w.name, "is_default": w.is_default,
    "is_virtual": w.is_virtual, "customer_id": w.customer_id,
    "account_set_id": w.account_set_id,
    "account_set_name": as_map.get(w.account_set_id) if w.account_set_id else None,
    "locations": [{"id": loc.id, "code": loc.code, "name": loc.name} for loc in locs]
})
```

改为：
```python
result.append({
    "id": w.id, "name": w.name, "is_default": w.is_default,
    "is_virtual": w.is_virtual, "customer_id": w.customer_id,
    "account_set_id": w.account_set_id,
    "account_set_name": as_map.get(w.account_set_id) if w.account_set_id else None,
    "color": w.color or "blue",
    "locations": [{"id": loc.id, "code": loc.code, "name": loc.name} for loc in locs]
})
```

**Step 2: 创建仓库时写入 color**

在 `create_warehouse` 函数中，`create_kwargs` 构造处（第 51 行附近）：

原来：
```python
create_kwargs = dict(name=data.name, is_default=data.is_default)
```

改为：
```python
create_kwargs = dict(name=data.name, is_default=data.is_default, color=data.color)
```

**Step 3: 更新仓库无需额外改动**

`update_warehouse` 函数中已使用 `data.model_dump(exclude_unset=True)` 自动处理所有字段，`color` 会自动包含在 `update_data` 中，无需修改。

**Step 4: 验证 API**

Run: `curl -s http://localhost:8000/api/warehouses -H "Authorization: Bearer <token>" | python3 -m json.tool | head -20`
Expected: 每个仓库对象中包含 `"color": "blue"`

**Step 5: Commit**

```bash
git add backend/app/routers/warehouses.py
git commit -m "feat: 仓库列表/创建 API 透传 color 字段"
```

---

### Task 3: 后端 API — 商品库存列表透传 warehouse_color

**Files:**
- Modify: `backend/app/routers/products.py:92-101` (stock_details 序列化)

**Step 1: 库存详情加 warehouse_color**

在 `backend/app/routers/products.py` 的商品列表端点中，`stock_details.append({...})` 字典（约第 92-101 行）加上 `warehouse_color`：

原来：
```python
stock_details.append({
    "warehouse_id": s.warehouse_id,
    "warehouse_name": s.warehouse.name,
    "location_id": s.location_id,
    "location_code": s.location.code if s.location else None,
    "quantity": s.quantity,
    "reserved_qty": reserved,
    "available_qty": s.quantity - reserved,
    "is_virtual": s.warehouse.is_virtual
})
```

改为：
```python
stock_details.append({
    "warehouse_id": s.warehouse_id,
    "warehouse_name": s.warehouse.name,
    "warehouse_color": s.warehouse.color or "blue",
    "location_id": s.location_id,
    "location_code": s.location.code if s.location else None,
    "quantity": s.quantity,
    "reserved_qty": reserved,
    "available_qty": s.quantity - reserved,
    "is_virtual": s.warehouse.is_virtual
})
```

> 注意：`select_related("warehouse")` 已经在第 64 行做了，不需要额外查询。

**Step 2: 检查商品详情端点是否也需要修改**

在同一文件中搜索其他返回 stock 详情的地方（约第 146 行附近的详情端点），如果也有 `stock_details` 序列化，同样加上 `"warehouse_color": s.warehouse.color or "blue"`。

**Step 3: Commit**

```bash
git add backend/app/routers/products.py
git commit -m "feat: 商品库存 API 透传 warehouse_color"
```

---

### Task 4: 前端 — 设置页面颜色选择器

**Files:**
- Modify: `frontend/src/components/business/settings/WarehouseSettings.vue`

**Step 1: 仓库列表标题行加色点**

在 `WarehouseSettings.vue` 模板中，仓库名称 `<span class="font-medium text-sm">{{ w.name }}</span>` 之前加一个色点：

```html
<span class="inline-block w-2.5 h-2.5 rounded-full" :style="`background: var(--${colorCssVar(w.color || 'blue')})`"></span>
```

**Step 2: 仓库编辑弹窗加颜色选择器**

在仓库弹窗 `modal-body` 中，"仓库名称"字段之后、"设为默认仓库"之前，添加颜色选择行：

```html
<div>
  <label class="label">标记颜色</label>
  <div class="flex gap-2 mt-1">
    <button
      v-for="c in colorOptions"
      :key="c.value"
      type="button"
      @click="warehouseForm.color = c.value"
      class="w-7 h-7 rounded-full border-2 transition-all flex items-center justify-center"
      :class="warehouseForm.color === c.value ? 'border-foreground scale-110' : 'border-transparent opacity-60 hover:opacity-100'"
      :style="`background: var(--${c.cssVar})`"
      :title="c.label"
    >
      <svg v-if="warehouseForm.color === c.value" class="w-3 h-3 text-white" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
    </button>
  </div>
</div>
```

**Step 3: Script 中添加颜色常量和辅助函数**

在 `<script setup>` 中添加：

```javascript
// 预设颜色选项
const colorOptions = [
  { value: 'blue', label: '蓝色', cssVar: 'info-emphasis' },
  { value: 'green', label: '绿色', cssVar: 'success-emphasis' },
  { value: 'red', label: '红色', cssVar: 'error-emphasis' },
  { value: 'yellow', label: '黄色', cssVar: 'warning-emphasis' },
  { value: 'purple', label: '紫色', cssVar: 'purple-emphasis' },
  { value: 'gray', label: '灰色', cssVar: 'gray-emphasis' },
  { value: 'orange', label: '橙色', cssVar: 'orange-emphasis' },
]

const colorCssVar = (color) => {
  const map = { blue: 'info-emphasis', green: 'success-emphasis', red: 'error-emphasis', yellow: 'warning-emphasis', purple: 'purple-emphasis', gray: 'gray-emphasis', orange: 'orange-emphasis' }
  return map[color] || 'info-emphasis'
}
```

**Step 4: warehouseForm 初始化加 color**

1. `warehouseForm` reactive 初始值加 `color: 'blue'`：
```javascript
const warehouseForm = reactive({ id: null, name: '', is_default: false, account_set_id: null, color: 'blue' })
```

2. `openCreateWarehouse` 的 Object.assign 加 `color: 'blue'`：
```javascript
Object.assign(warehouseForm, { id: null, name: '', is_default: false, account_set_id: null, color: 'blue' })
```

3. `editWarehouse` 的 Object.assign 加 `color: w.color || 'blue'`：
```javascript
Object.assign(warehouseForm, { id: w.id, name: w.name, is_default: w.is_default, account_set_id: w.account_set_id || null, color: w.color || 'blue' })
```

**Step 5: saveWarehouse 传 color 给 API**

在 `saveWarehouse` 函数中，`createWarehouse` 和 `updateWarehouse` 调用的 payload 中加上 `color`。

创建时（原第 200 行）：
```javascript
await createWarehouse({ name: warehouseForm.name.trim(), is_default: warehouseForm.is_default, account_set_id: warehouseForm.account_set_id || null, color: warehouseForm.color })
```

更新时（原第 198 行）：
```javascript
await updateWarehouse(warehouseForm.id, { name: warehouseForm.name.trim(), is_default: warehouseForm.is_default, account_set_id: warehouseForm.account_set_id || null, color: warehouseForm.color })
```

**Step 6: 构建验证**

Run: `cd ~/Desktop/erp-4/frontend && npm run build`
Expected: 编译通过，无错误

**Step 7: Commit**

```bash
git add frontend/src/components/business/settings/WarehouseSettings.vue
git commit -m "feat: 仓库设置增加颜色选择器"
```

---

### Task 5: 前端 — StockView 动态颜色渲染

**Files:**
- Modify: `frontend/src/views/StockView.vue:62,130`

**Step 1: 移动端卡片标签（第 62 行）**

原来：
```html
<span :class="s.is_virtual ? 'badge badge-purple' : 'badge badge-blue'">{{ s.is_virtual ? '寄售' : (s.location_code || '-') }}</span>
```

改为：
```html
<span :class="s.is_virtual ? 'badge badge-purple' : `badge badge-${s.warehouse_color || 'blue'}`">{{ s.is_virtual ? '寄售' : (s.location_code || '-') }}</span>
```

**Step 2: 桌面表格标签（第 130 行）**

原来：
```html
<span :class="row.s.is_virtual ? 'badge badge-purple' : 'badge badge-blue'">{{ row.s.is_virtual ? '寄售' : (row.s.location_code || '-') }}</span>
```

改为：
```html
<span :class="row.s.is_virtual ? 'badge badge-purple' : `badge badge-${row.s.warehouse_color || 'blue'}`">{{ row.s.is_virtual ? '寄售' : (row.s.location_code || '-') }}</span>
```

**Step 3: 构建验证**

Run: `cd ~/Desktop/erp-4/frontend && npm run build`
Expected: 编译通过

**Step 4: Commit**

```bash
git add frontend/src/views/StockView.vue
git commit -m "feat: 库存页面仓位标签按仓库颜色渲染"
```

---

### Task 6: 前端 — ProductSelector 动态颜色渲染

**Files:**
- Modify: `frontend/src/components/business/sales/ProductSelector.vue:90,238-243`

**Step 1: 商品表格仓位标签（第 90 行）**

原来：
```html
<span v-else-if="p.location_code" class="badge badge-blue text-xs">{{ p.location_code }}</span>
```

改为：
```html
<span v-else-if="p.location_code" :class="`badge badge-${p.warehouse_color || 'blue'} text-xs`">{{ p.location_code }}</span>
```

**Step 2: displayProducts 计算属性透传 warehouse_color**

在 `displayProducts` computed 中，普通模式下 `result.push({...})` 的展开对象（约第 235-244 行）已经有 `...p`（展开了 product），但 `warehouse_color` 来自 stock `s` 对象，需要显式添加：

原来：
```javascript
result.push({
  ...p,
  location_code: s.location_code,
  stock_key: s.warehouse_id + '-' + s.location_id,
  display_stock: s.available_qty ?? s.quantity,
  warehouse_id: s.warehouse_id,
  location_id: s.location_id,
  is_virtual_stock: !!s.is_virtual,
  virtual_warehouse_name: s.warehouse_name || ''
})
```

改为：
```javascript
result.push({
  ...p,
  location_code: s.location_code,
  stock_key: s.warehouse_id + '-' + s.location_id,
  display_stock: s.available_qty ?? s.quantity,
  warehouse_id: s.warehouse_id,
  location_id: s.location_id,
  is_virtual_stock: !!s.is_virtual,
  virtual_warehouse_name: s.warehouse_name || '',
  warehouse_color: s.warehouse_color || 'blue'
})
```

同样，退货模式的 `result.push({...})` 块（约第 199-208 行）也要加上 `warehouse_color: s.warehouse_color || 'blue'`。

**Step 3: 构建验证**

Run: `cd ~/Desktop/erp-4/frontend && npm run build`
Expected: 编译通过

**Step 4: Commit**

```bash
git add frontend/src/components/business/sales/ProductSelector.vue
git commit -m "feat: 销售页面商品选择器按仓库颜色渲染"
```

---

### Task 7: 端到端验证

**Step 1: 启动服务**

Run: `cd ~/Desktop/erp-4 && docker compose up -d --build`

**Step 2: 验证设置页面**

1. 打开设置 → 仓库与仓位管理
2. 编辑一个仓库（如售后仓），将颜色改为红色，保存
3. 验证仓库列表中该仓库名前出现红色色点

**Step 3: 验证库存页面**

1. 打开库存页面
2. 验证售后仓的仓位标签显示红色，其他仓库仍为蓝色
3. 验证寄售库存仍为紫色 + "寄售"文字

**Step 4: 验证销售页面**

1. 新建销售订单，在商品选择器中验证仓位标签颜色正确

**Step 5: 最终 Commit**

如有修复则提交，否则跳过。
