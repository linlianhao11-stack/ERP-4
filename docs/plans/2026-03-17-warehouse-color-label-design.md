# 仓库颜色标记功能设计

> 日期：2026-03-17
> 状态：已确认

## 背景

库存页面所有仓位标签统一显示蓝色 badge，无法直观区分特殊仓库（如售后仓）。需要在仓库级别增加颜色标记，让用户一目了然地识别不同仓库的库存。

## 设计决策

| 决策项 | 结论 |
|--------|------|
| 颜色粒度 | 仓库级别，仓位继承 |
| 颜色选择方式 | 7 种预设颜色（复用现有 badge 体系） |
| 默认颜色 | blue，向后兼容 |
| 展示范围 | 全局一致（StockView + ProductSelector） |
| 实现方案 | Warehouse 模型加 color 字段，API 透传 |

## 预设颜色

复用 `base.css` 已有的 7 种 badge 颜色：

| 值 | 颜色 | 典型用途 |
|----|------|----------|
| `blue` | 蓝色 | 默认 |
| `green` | 绿色 | - |
| `red` | 红色 | 售后仓等需警示的 |
| `yellow` | 黄色 | - |
| `purple` | 紫色 | - |
| `gray` | 灰色 | - |
| `orange` | 橙色 | - |

> 注：寄售库存始终显示紫色 + "寄售"文字，不受仓库颜色影响。

## 数据层

### Warehouse 模型

新增字段：

```python
color = fields.CharField(max_length=20, default="blue")
```

### Schema

- `WarehouseCreate`：加 `color: str = "blue"`，校验值在 7 种之内
- `WarehouseUpdate`：加 `color: Optional[str] = None`，同样校验

### 库存 API 透传

库存查询结果每行增加 `warehouse_color` 字段，从已有的 Warehouse JOIN 中取，零额外查询开销。

### 数据库迁移

```sql
ALTER TABLE warehouse ADD COLUMN color VARCHAR(20) DEFAULT 'blue';
```

现有仓库自动获得 `"blue"` 默认值。

## 设置页面 UI

### WarehouseSettings.vue

仓库创建/编辑表单中，名称输入框旁增加一排 7 个圆形色块：

- 点击选中，选中态加边框/勾号
- 创建时默认选中蓝色
- 编辑时显示当前颜色为选中态
- 仓库列表中仓库名称旁显示小色点

无需新组件，直接在现有表单中添加。

## 库存页面 & 销售页面渲染

### StockView.vue

```html
<!-- 原来 -->
<span :class="s.is_virtual ? 'badge badge-purple' : 'badge badge-blue'">

<!-- 改为 -->
<span :class="s.is_virtual ? 'badge badge-purple' : `badge badge-${s.warehouse_color || 'blue'}`">
```

移动端和桌面端两处均修改。

### ProductSelector.vue

```html
<!-- 原来 -->
<span v-else-if="p.location_code" class="badge badge-blue text-xs">

<!-- 改为 -->
<span v-else-if="p.location_code" :class="`badge badge-${p.warehouse_color || 'blue'} text-xs`">
```

### 寄售优先级

寄售库存（`is_virtual`）始终显示 `badge-purple` + "寄售"文字，不受仓库颜色设置影响。

## 涉及文件

| 文件 | 变更 |
|------|------|
| `backend/app/models/warehouse.py` | Warehouse 加 color 字段 |
| `backend/app/schemas/warehouse.py` | Create/Update schema 加 color |
| `backend/app/routers/warehouses.py` | 创建/更新时处理 color |
| `backend/app/routers/stock.py`（或库存查询处） | 透传 warehouse_color |
| `frontend/src/components/business/settings/WarehouseSettings.vue` | 颜色选择器 UI |
| `frontend/src/views/StockView.vue` | badge 动态颜色 |
| `frontend/src/components/business/sales/ProductSelector.vue` | badge 动态颜色 |
