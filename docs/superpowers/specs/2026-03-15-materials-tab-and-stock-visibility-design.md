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
| 品牌筛选 | 下拉选择品牌过滤，使用现有 `getProductBrands()` API（`frontend/src/api/brands.js`） |
| 分类筛选 | 下拉选择分类过滤，使用现有 `GET /api/products/categories/list` |
| 新增商品 | 复用现有 `ProductFormModal.vue`，从 StockView 迁移至此 |
| 编辑商品 | 点击行弹出 ProductFormModal 编辑模式 |
| 停用/启用 | 通过 `updateProduct(id, { is_active: false/true })` 切换状态 |
| 分页 | 20 条/页，使用 `usePagination` |

### UI 规范

严格遵循项目现有 UI 模式：

- 工具栏：筛选下拉使用 `toolbar-select` 样式，搜索框使用 `toolbar-search-wrapper` + `toolbar-search`
- 桌面表格：`card hidden md:block` + `bg-elevated thead` + `px-3 py-2` 单元格
- 移动端：`md:hidden` 卡片列表
- 弹窗：`modal-backdrop` + `modal`（不用 modal-overlay）
- 成本价列受 `hasPermission('finance')` 权限控制
- 已停用商品行使用 `text-muted` + 删除线样式标识

### 后端改动

#### `GET /api/products` 接口扩展

- 新增 `include_inactive: bool = False` 参数 — 物料管理传 `True` 显示所有商品
- 新增 `brand: str` 筛选参数
- 响应数据新增 `tax_rate`、`is_active`、`unit` 字段（现有响应缺少这些字段）

#### `ProductUpdate` Schema 扩展

- 新增 `is_active: Optional[bool]` 字段，用于停用/启用商品

#### `frontend/src/api/products.js` 扩展

- 新增 `deleteProduct(id)` — 调用 `DELETE /api/products/{id}`（软删除）

### 不做的事

- 不新增 API 路由 — 复用现有 `/api/products` CRUD 接口
- 不做批量导入 — 留在库存页面（仓管使用）
- 不显示库存数量 — 物料管理只管商品基本信息
- 不动 `PurchaseOrderForm.vue` 中的内联商品创建 — 那是采购开单时的便捷入口，保留

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

#### 2. 数据库迁移 + 触发器

在 `backend/app/migrations.py` 中新增迁移函数，并在 `run_migrations()` 中调用：

```python
async def migrate_stock_last_activity():
    conn = connections.get("default")
    # 1. 添加字段
    await conn.execute_query(
        "ALTER TABLE warehouse_stocks ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ"
    )
    # 2. 回填：用 updated_at 初始化
    await conn.execute_query(
        "UPDATE warehouse_stocks SET last_activity_at = updated_at WHERE last_activity_at IS NULL"
    )
    # 3. 创建触发器函数：quantity 或 reserved_qty 变化时自动更新 last_activity_at
    await conn.execute_query("""
        CREATE OR REPLACE FUNCTION trg_update_last_activity()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.last_activity_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    # 4. UPDATE 触发器：仅在 quantity 或 reserved_qty 变化时触发
    await conn.execute_query("""
        DROP TRIGGER IF EXISTS trg_stock_last_activity_update ON warehouse_stocks
    """)
    await conn.execute_query("""
        CREATE TRIGGER trg_stock_last_activity_update
        BEFORE UPDATE ON warehouse_stocks
        FOR EACH ROW
        WHEN (OLD.quantity IS DISTINCT FROM NEW.quantity
              OR OLD.reserved_qty IS DISTINCT FROM NEW.reserved_qty)
        EXECUTE FUNCTION trg_update_last_activity()
    """)
    # 5. INSERT 触发器：新记录自动设置 last_activity_at
    await conn.execute_query("""
        DROP TRIGGER IF EXISTS trg_stock_last_activity_insert ON warehouse_stocks
    """)
    await conn.execute_query("""
        CREATE TRIGGER trg_stock_last_activity_insert
        BEFORE INSERT ON warehouse_stocks
        FOR EACH ROW
        EXECUTE FUNCTION trg_update_last_activity()
    """)
```

#### 3. last_activity_at 更新策略：数据库触发器

**核心策略**：使用 PostgreSQL 触发器自动维护 `last_activity_at`，而非在应用层逐个修改。

**原因**：库存变动分散在多个文件（`stock.py`、`logistics.py`、`purchase_orders.py`、`consignment.py`、`order_service.py`、`products.py` 导入），且很多操作直接使用 `WarehouseStock.filter().update()` 绕过 ORM 的 `save()` 方法。逐个修改容易遗漏，而数据库触发器能保证 100% 覆盖。

**触发条件**：
- `INSERT` — 新建库存记录时自动设置
- `UPDATE` — 仅当 `quantity` 或 `reserved_qty` 发生变化时触发（避免非库存变动的更新误触）

**应用层改动**：无需修改任何现有的库存操作代码。零改动 = 零遗漏风险。

#### 4. 修改 `GET /api/products` 库存过滤逻辑

```python
# 原来（products.py:78）：
if s.quantity > 0:
    stock_details.append(...)

# 改为：
cutoff = now() - timedelta(days=7)
if s.quantity > 0 or (s.last_activity_at and to_naive(s.last_activity_at) > to_naive(cutoff)):
    stock_details.append(...)
```

#### 5. 修改导出接口

**`products.py` 导出**（`export_products`）：将 `quantity__gt=0` 过滤替换为同样的 7 天规则，改为加载所有库存再在 Python 层过滤。

**`stock.py` 导出**（`export_stock`）：当前不过滤零库存，保持现状不改（导出是完整数据备份场景）。

### 前端改动

- 零库存但在 7 天窗口内的物料正常显示，数量显示为 `0`
- 零库存行整行使用 `text-muted` 样式弱化显示，提示操作人员关注补货

### 适用范围

- **受影响**：StockView（库存页面）、`products.py` 商品导出
- **不受影响**：物料管理 Tab（始终显示所有商品，不看库存状态）、`stock.py` 库存导出

### 不做的事

- 不做 7 天可配置 — 硬编码 7 天，需要时再加设置项
- 不做定时任务清理 — 查询时实时计算即可

---

## 涉及文件汇总

### 后端
| 文件 | 改动 |
|------|------|
| `backend/app/models/stock.py` | WarehouseStock 新增 `last_activity_at` 字段 |
| `backend/app/migrations.py` | 新增 `migrate_stock_last_activity()` — 字段 + 触发器 |
| `backend/app/routers/products.py` | `list_products` 加 `include_inactive`/`brand` 参数 + 响应加 `tax_rate`/`is_active`/`unit` + 7天过滤 |
| `backend/app/routers/products.py` | `export_products` 同步7天过滤 |
| `backend/app/schemas/product.py` | `ProductUpdate` 新增 `is_active` 字段 |

### 前端
| 文件 | 改动 |
|------|------|
| `frontend/src/views/PurchaseView.vue` | 新增 materials Tab + import MaterialsTab |
| `frontend/src/components/business/purchase/MaterialsTab.vue` | 新建：物料管理面板（列表+筛选+搜索+CRUD） |
| `frontend/src/views/StockView.vue` | 移除新增商品按钮、编辑按钮、ProductFormModal 引用 |
| `frontend/src/api/products.js` | 加 `include_inactive`/`brand` 参数 + `deleteProduct()` 函数 |
