# 物料管理 Tab + 零库存 7 天隐藏规则 设计文档

## 概述

两个关联需求：

1. **采购模块新增"物料管理" Tab** — 统一管理所有商品（SKU）的基本信息，将商品增删改从库存页面迁移至此
2. **零库存显示规则优化** — 库存为 0 的物料不再立即隐藏，改为 7 天无任何库存变动后才隐藏，防止畅销品补货遗漏

## 需求背景

- 商品管理（新增/编辑）功能原先放在库存页面，职责混淆。采购模块是管理商品主数据的更合理位置
- 库存页面目前 quantity=0 立即隐藏，导致畅销品当天卖完后从列表消失，操作人员可能遗漏补货（尤其是设置了低库存提醒的商品）

---

## 第一部分：物料管理 Tab

### 位置

`PurchaseView.vue` 新增第四个 Tab：

```js
{ value: 'materials', label: '物料管理' }
```

Tab 顺序：采购订单 → 退货单 → 供应商管理 → 物料管理

### 新建文件

- `frontend/src/components/business/purchase/MaterialsTab.vue` — 物料管理面板

### 功能清单

| 功能 | 说明 |
|------|------|
| 商品列表 | 显示所有商品（含已停用），字段：SKU、名称、品牌、分类、零售价、成本价、单位、税率、状态 |
| 模糊搜索 | SKU/名称/品牌/分类关键词模糊匹配 |
| 品牌筛选 | 下拉选择品牌过滤 |
| 分类筛选 | 下拉选择分类过滤 |
| 新增商品 | 复用现有 `ProductFormModal.vue`，从 StockView 迁移至此 |
| 编辑商品 | 点击行弹出 ProductFormModal 编辑模式 |
| 停用/启用 | 切换 `is_active` 状态（软删除） |
| 分页 | 20 条/页，使用 `usePagination` |

### UI 规范

严格遵循项目现有 UI 模式：

- 工具栏：筛选下拉使用 `toolbar-select` 样式，搜索框使用 `toolbar-search-wrapper` + `toolbar-search`
- 桌面表格：`card hidden md:block` + `bg-elevated thead` + `px-3 py-2` 单元格
- 移动端：`md:hidden` 卡片列表
- 弹窗：`modal-backdrop` + `modal`（不用 modal-overlay）
- 成本价列受 `hasPermission('finance')` 权限控制

### 后端改动

修改 `GET /api/products` 接口：

- 新增 `include_inactive: bool = False` 参数
- 当 `include_inactive=True` 时，不过滤 `is_active`，返回所有商品（物料管理 Tab 使用）
- 默认 `False`，保持现有行为（库存页面等其他调用方）
- 新增 `brand` 筛选参数

### 不做的事

- 不新增 API 路由 — 复用现有 `/api/products` CRUD 接口
- 不做批量导入 — 留在库存页面（仓管使用）
- 不显示库存数量 — 物料管理只管商品基本信息

---

## 第二部分：StockView 简化

### 移除

- "新增商品"按钮及其 `openProductModal()` 调用
- 移动端卡片和桌面表格中的"编辑"商品按钮
- `ProductFormModal` 组件的 import 和相关状态变量（showProductModal、editingProduct 等）

### 保留

- Excel 批量导入（ImportModal + ImportPreviewModal）
- 补货（RestockModal）
- 调拨（TransferModal）
- 采购收货按钮
- 导出库存
- 所有筛选、搜索、排序、分页功能

### 定位转变

StockView 变为纯库存操作视图：看库存、补货、调拨、导入、导出。商品信息的增删改统一在 采购 > 物料管理。

---

## 第三部分：零库存 7 天隐藏规则

### 核心规则

```
显示条件：quantity > 0 OR (quantity = 0 AND last_activity_at > now() - 7天)
```

两个条件同时满足时才隐藏：
1. 库存为 0
2. 最后一次库存变动超过 7 天

### 后端改动

#### 1. WarehouseStock 模型新增字段

```python
last_activity_at = fields.DatetimeField(null=True)
```

#### 2. 数据库迁移

- 添加 `last_activity_at` 列
- 回填：用现有 `updated_at` 值初始化 `last_activity_at`

#### 3. 库存变动时更新 last_activity_at

所有创建 StockLog 的操作同步更新对应 WarehouseStock 的 `last_activity_at = now()`：

- 补货（restock）
- 销售出库
- 退货入库
- 调拨出/入
- 手动调整
- Excel 批量导入

#### 4. 修改 `GET /api/products` 库存过滤逻辑

```python
# 原来：
if s.quantity > 0:
    stock_details.append(...)

# 改为：
from datetime import timedelta
cutoff = now() - timedelta(days=7)
if s.quantity > 0 or (s.last_activity_at and s.last_activity_at > cutoff):
    stock_details.append(...)
```

#### 5. 修改导出接口

同步应用 7 天规则，替换原来的 `quantity__gt=0` 过滤。

### 前端改动

- 零库存但在 7 天窗口内的物料正常显示，数量显示为 `0`
- 零库存行使用 `text-muted` 样式弱化显示，提示操作人员关注补货

### 适用范围

- **受影响**：StockView（库存页面）、库存导出
- **不受影响**：物料管理 Tab（始终显示所有商品，不看库存状态）

### 不做的事

- 不做 7 天可配置 — 硬编码 7 天，需要时再加设置项
- 不做定时任务清理 — 查询时实时计算即可

---

## 涉及文件汇总

### 后端
| 文件 | 改动 |
|------|------|
| `backend/app/models/stock.py` | WarehouseStock 新增 `last_activity_at` 字段 |
| `backend/app/routers/products.py` | `list_products` 加 `include_inactive`/`brand` 参数 + 7天过滤逻辑 |
| `backend/app/routers/products.py` | `export_products` 同步7天过滤 |
| `backend/app/routers/stock.py` | 所有库存变动操作更新 `last_activity_at` |
| 迁移脚本 | 新增字段 + 回填 |

### 前端
| 文件 | 改动 |
|------|------|
| `frontend/src/views/PurchaseView.vue` | 新增 materials Tab + import MaterialsTab |
| `frontend/src/components/business/purchase/MaterialsTab.vue` | 新建：物料管理面板 |
| `frontend/src/views/StockView.vue` | 移除新增商品按钮、编辑按钮、ProductFormModal 引用 |
| `frontend/src/api/products.js` | 加 `include_inactive`/`brand` 参数支持 |
