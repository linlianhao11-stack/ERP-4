# 物料管理 Tab + 零库存 7 天隐藏规则 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在采购模块新增物料管理 Tab 统一商品 CRUD，简化库存页面为纯库存操作，并将零库存隐藏规则从"立即隐藏"改为"7 天无活动后隐藏"。

**Architecture:** 后端通过 PostgreSQL 触发器自动维护 `last_activity_at` 字段，零改动覆盖所有库存操作路径。前端新建 MaterialsTab 复用现有 ProductFormModal，StockView 移除商品管理功能。API 层扩展 `list_products` 支持 `include_inactive` 和 `brand` 筛选。

**Tech Stack:** FastAPI + Tortoise ORM + PostgreSQL 16 / Vue 3 (Composition API) + Tailwind CSS 4

---

## Chunk 1: 后端改动

### Task 1: WarehouseStock 模型新增 last_activity_at 字段

**Files:**
- Modify: `backend/app/models/stock.py:4-13`

- [ ] **Step 1: 在 WarehouseStock 模型添加 last_activity_at 字段**

在 `updated_at` 字段之后（第 13 行之后）添加：

```python
last_activity_at = fields.DatetimeField(null=True)
```

完整的字段顺序：
```python
class WarehouseStock(models.Model):
    id = fields.IntField(pk=True)
    warehouse = fields.ForeignKeyField("models.Warehouse", related_name="stocks", on_delete=fields.RESTRICT)
    product = fields.ForeignKeyField("models.Product", related_name="warehouse_stocks", on_delete=fields.RESTRICT)
    location = fields.ForeignKeyField("models.Location", related_name="stocks", null=True, on_delete=fields.SET_NULL)
    quantity = fields.IntField(default=0)
    reserved_qty = fields.IntField(default=0)
    weighted_cost = fields.DecimalField(max_digits=12, decimal_places=2, default=0)
    weighted_entry_date = fields.DatetimeField(null=True)
    updated_at = fields.DatetimeField(auto_now=True)
    last_activity_at = fields.DatetimeField(null=True)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/models/stock.py
git commit -m "feat(stock): WarehouseStock 新增 last_activity_at 字段"
```

---

### Task 2: 数据库迁移 + PostgreSQL 触发器

**Files:**
- Modify: `backend/app/migrations.py` — 在文件末尾添加迁移函数，在 `run_migrations()` 中注册

- [ ] **Step 1: 在 migrations.py 末尾添加 migrate_stock_last_activity 函数**

在文件最后（`migrate_ai_readonly_user` 函数之后）追加：

```python
async def migrate_stock_last_activity():
    """新增 last_activity_at 字段 + 触发器自动维护"""
    conn = connections.get("default")
    # 1. 添加字段
    await conn.execute_query(
        "ALTER TABLE warehouse_stocks ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ"
    )
    # 2. 回填：用 updated_at 初始化
    await conn.execute_query(
        "UPDATE warehouse_stocks SET last_activity_at = updated_at WHERE last_activity_at IS NULL"
    )
    # 3. 创建触发器函数
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
    await conn.execute_query(
        "DROP TRIGGER IF EXISTS trg_stock_last_activity_update ON warehouse_stocks"
    )
    await conn.execute_query("""
        CREATE TRIGGER trg_stock_last_activity_update
        BEFORE UPDATE ON warehouse_stocks
        FOR EACH ROW
        WHEN (OLD.quantity IS DISTINCT FROM NEW.quantity
              OR OLD.reserved_qty IS DISTINCT FROM NEW.reserved_qty)
        EXECUTE FUNCTION trg_update_last_activity()
    """)
    # 5. INSERT 触发器
    await conn.execute_query(
        "DROP TRIGGER IF EXISTS trg_stock_last_activity_insert ON warehouse_stocks"
    )
    await conn.execute_query("""
        CREATE TRIGGER trg_stock_last_activity_insert
        BEFORE INSERT ON warehouse_stocks
        FOR EACH ROW
        EXECUTE FUNCTION trg_update_last_activity()
    """)
```

- [ ] **Step 2: 在 run_migrations() 中注册新迁移**

在 `run_migrations()` 函数内的 DDL 迁移区块末尾（第 26 行 `await migrate_ai_readonly_user()` 之后、第 28 行数据初始化代码之前）添加：

```python
    await migrate_stock_last_activity()
```

注：`run_migrations()` 分为两个区块：DDL 迁移（第 13-26 行）和数据初始化（第 28 行起）。新迁移是 DDL（ALTER TABLE + CREATE TRIGGER），必须放在 DDL 区块。

- [ ] **Step 3: Commit**

```bash
git add backend/app/migrations.py
git commit -m "feat(migration): 新增 last_activity_at 字段 + PostgreSQL 触发器"
```

---

### Task 3: ProductUpdate Schema 新增 is_active 字段

**Files:**
- Modify: `backend/app/schemas/product.py:15-21`

- [ ] **Step 1: 在 ProductUpdate 类中添加 is_active 字段**

在 `unit` 字段之后添加：

```python
    is_active: Optional[bool] = Field(default=None)
```

完整的 ProductUpdate：
```python
class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    brand: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    retail_price: Optional[Decimal] = Field(default=None, ge=0, le=99999999)
    cost_price: Optional[Decimal] = Field(default=None, ge=0, le=99999999)
    unit: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = Field(default=None)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/product.py
git commit -m "feat(schema): ProductUpdate 新增 is_active 字段支持停用/启用"
```

---

### Task 4: list_products API 扩展（include_inactive + brand + 响应字段 + 7天过滤）

**Files:**
- Modify: `backend/app/routers/products.py:33-101`

- [ ] **Step 1: 修改 list_products 函数签名，新增 include_inactive 和 brand 参数**

将函数签名（第 33-37 行）改为：

```python
@router.get("")
async def list_products(keyword: Optional[str] = None, category: Optional[str] = None,
                        brand: Optional[str] = None,
                        warehouse_id: Optional[int] = None,
                        include_inactive: bool = False,
                        offset: int = 0, limit: int = 200,
                        user: User = Depends(get_current_user)):
```

- [ ] **Step 2: 修改查询逻辑，支持 include_inactive 和 brand 过滤**

将第 39 行 `query = Product.filter(is_active=True)` 改为：

```python
    query = Product.all() if include_inactive else Product.filter(is_active=True)
```

在 `if category:` 过滤之后（第 44 行之后）添加品牌过滤：

```python
    if brand:
        query = query.filter(brand=brand)
```

- [ ] **Step 3: 修改库存过滤逻辑，应用 7 天规则**

在 `for p in products:` 循环之前（第 62 行之前）添加 cutoff 计算：

```python
    cutoff = now() - timedelta(days=7)
```

然后将第 77-78 行：

```python
        for s in stocks:
            if s.quantity > 0:
```

改为：

```python
        for s in stocks:
            if s.quantity > 0 or (s.last_activity_at and to_naive(s.last_activity_at) > to_naive(cutoff)):
```

注：`timedelta` 已在文件顶部 import（第 5 行），`now` 和 `to_naive` 也已导入（第 17 行）。`cutoff` 在外层循环之前计算一次，避免重复计算。

- [ ] **Step 4: 扩展响应对象，新增 tax_rate、is_active 字段**

将响应构建（第 91-99 行）改为：

```python
        item = {
            "id": p.id, "sku": p.sku, "name": p.name, "brand": p.brand,
            "category": p.category, "retail_price": float(p.retail_price),
            "unit": p.unit, "tax_rate": float(p.tax_rate),
            "is_active": p.is_active,
            "total_stock": total_qty, "age_days": age_days,
            "stocks": stock_details
        }
        if has_finance:
            item["cost_price"] = float(p.cost_price)
        result.append(item)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/products.py
git commit -m "feat(api): list_products 扩展 include_inactive/brand 参数 + 7天过滤"
```

---

### Task 5: export_products 同步 7 天过滤

**Files:**
- Modify: `backend/app/routers/products.py:110-148`

- [ ] **Step 1: 修改 export_products 的库存查询**

将第 122 行：

```python
    all_stocks = await WarehouseStock.filter(product_id__in=product_ids, quantity__gt=0).select_related("warehouse") if product_ids else []
```

改为：

```python
    all_stocks = await WarehouseStock.filter(product_id__in=product_ids).select_related("warehouse") if product_ids else []
```

- [ ] **Step 2: 在汇总库存时应用 7 天规则**

将第 129-130 行的库存汇总：

```python
    for p in products:
        stocks = stocks_by_product.get(p.id, [])
        total_qty = sum(s.quantity for s in stocks if not s.warehouse.is_virtual)
```

改为（在 `for p in products:` 之前加 cutoff 计算）：

```python
    cutoff = now() - timedelta(days=7)
    for p in products:
        raw_stocks = stocks_by_product.get(p.id, [])
        stocks = [s for s in raw_stocks if s.quantity > 0 or (s.last_activity_at and to_naive(s.last_activity_at) > to_naive(cutoff))]
        total_qty = sum(s.quantity for s in stocks if not s.warehouse.is_virtual)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/products.py
git commit -m "feat(api): export_products 同步7天零库存过滤规则"
```

---

## Chunk 2: 前端改动

### Task 6: 前端 API 层扩展

**Files:**
- Modify: `frontend/src/api/products.js`

- [ ] **Step 1: 添加 deleteProduct 函数**

在文件末尾追加：

```javascript
export const deleteProduct = (id) => api.delete('/products/' + id)
export const getCategories = () => api.get('/products/categories/list')
```

完整的 `products.js`：
```javascript
import api from './index'

export const getProducts = (params) => api.get('/products', { params })
export const getNextSku = () => api.get('/products/next-sku')
export const createProduct = (data) => api.post('/products', data)
export const updateProduct = (id, data) => api.put('/products/' + id, data)
export const deleteProduct = (id) => api.delete('/products/' + id)
export const getCategories = () => api.get('/products/categories/list')
export const getTemplate = () => api.get('/products/template', { responseType: 'blob' })
export const previewImport = (formData) => api.post('/products/import/preview', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
export const importProducts = (formData) => api.post('/products/import', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/products.js
git commit -m "feat(api): 新增 deleteProduct + getCategories 导出"
```

---

### Task 7: MaterialsTab.vue — 物料管理面板

**Files:**
- Create: `frontend/src/components/business/purchase/MaterialsTab.vue`

- [ ] **Step 1: 创建 MaterialsTab.vue 完整组件**

参考 `PurchaseReturnTab.vue` 的 UI 模式（PageToolbar + 表格 + 分页 + 移动端卡片），复用 `ProductFormModal`。

```vue
<template>
  <div>
    <!-- 移动端卡片列表 -->
    <div class="md:hidden space-y-2">
      <div class="flex flex-wrap items-center gap-2 mb-2">
        <select v-model="filters.brand" @change="onFilterChange" class="toolbar-select flex-1">
          <option value="">全部品牌</option>
          <option v-for="b in brands" :key="b" :value="b">{{ b }}</option>
        </select>
        <div class="toolbar-search-wrapper flex-1" style="max-width:none">
          <Search :size="14" class="toolbar-search-icon" />
          <input v-model="searchQuery" @input="debouncedSearch" class="toolbar-search" placeholder="搜索SKU/名称/品牌...">
        </div>
      </div>
      <div v-for="p in products" :key="p.id" class="card p-3" :class="{ 'opacity-50': !p.is_active }" @click="openEdit(p)">
        <div class="flex justify-between items-start mb-1">
          <div class="flex-1 min-w-0 mr-2">
            <div class="font-medium text-sm truncate" :class="{ 'line-through': !p.is_active }">{{ p.name }}</div>
            <div class="text-xs text-muted font-mono">
              {{ p.sku }}
              <span v-if="p.brand" class="ml-1">· {{ p.brand }}</span>
            </div>
          </div>
          <div class="text-right flex-shrink-0">
            <div class="text-sm font-semibold">¥{{ p.retail_price }}</div>
            <div v-if="hasPermission('finance')" class="text-xs text-muted">成本 ¥{{ p.cost_price }}</div>
          </div>
        </div>
        <div class="flex justify-between items-center text-xs">
          <div class="text-muted">{{ p.category || '-' }} · {{ p.unit }}</div>
          <span :class="p.is_active ? 'badge badge-blue' : 'badge badge-muted'">{{ p.is_active ? '启用' : '停用' }}</span>
        </div>
      </div>
      <div v-if="!products.length" class="p-8 text-center text-muted text-sm">暂无商品数据</div>
    </div>

    <!-- 桌面端表格 -->
    <div class="card hidden md:block" style="overflow: visible">
      <PageToolbar>
        <template #filters>
          <select v-model="filters.brand" @change="onFilterChange" class="toolbar-select">
            <option value="">全部品牌</option>
            <option v-for="b in brands" :key="b" :value="b">{{ b }}</option>
          </select>
          <select v-model="filters.category" @change="onFilterChange" class="toolbar-select">
            <option value="">全部分类</option>
            <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
          </select>
          <div class="toolbar-search-wrapper">
            <Search :size="14" class="toolbar-search-icon" />
            <input v-model="searchQuery" @input="debouncedSearch" class="toolbar-search" placeholder="搜索SKU/名称/品牌...">
          </div>
        </template>
        <template #actions>
          <button @click="openCreate" class="btn btn-primary btn-sm" v-if="hasPermission('stock_edit')">新增商品</button>
        </template>
      </PageToolbar>
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-elevated">
            <tr>
              <th class="px-3 py-2 text-left w-28">SKU</th>
              <th class="px-3 py-2 text-left">商品名称</th>
              <th class="px-3 py-2 text-left w-24">品牌</th>
              <th class="px-3 py-2 text-left w-20">分类</th>
              <th class="px-3 py-2 text-left w-16">单位</th>
              <th class="px-3 py-2 text-right w-24">零售价</th>
              <th v-if="hasPermission('finance')" class="px-3 py-2 text-right w-24">成本价</th>
              <th class="px-3 py-2 text-right w-16">税率</th>
              <th class="px-3 py-2 text-center w-16">状态</th>
              <th class="px-3 py-2 text-center w-28">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-if="!products.length">
              <td :colspan="hasPermission('finance') ? 10 : 9">
                <div class="text-center py-12 text-muted">
                  <p class="text-sm font-medium mb-1">暂无商品数据</p>
                  <p class="text-xs">点击「新增商品」添加第一个商品</p>
                </div>
              </td>
            </tr>
            <tr v-for="p in products" :key="p.id" class="hover:bg-elevated" :class="{ 'text-muted': !p.is_active }">
              <td class="px-3 py-2 font-mono text-xs">{{ p.sku }}</td>
              <td class="px-3 py-2">
                <span :class="{ 'line-through': !p.is_active }">{{ p.name }}</span>
              </td>
              <td class="px-3 py-2 text-secondary text-xs">{{ p.brand || '-' }}</td>
              <td class="px-3 py-2 text-secondary text-xs">{{ p.category || '-' }}</td>
              <td class="px-3 py-2 text-secondary text-xs">{{ p.unit }}</td>
              <td class="px-3 py-2 text-right">{{ p.retail_price }}</td>
              <td v-if="hasPermission('finance')" class="px-3 py-2 text-right">{{ p.cost_price }}</td>
              <td class="px-3 py-2 text-right text-xs text-secondary">{{ p.tax_rate }}%</td>
              <td class="px-3 py-2 text-center">
                <span :class="p.is_active ? 'badge badge-blue' : 'badge badge-muted'">{{ p.is_active ? '启用' : '停用' }}</span>
              </td>
              <td class="px-3 py-2 text-center" @click.stop>
                <button @click="openEdit(p)" class="text-primary text-xs mr-2">编辑</button>
                <button v-if="hasPermission('stock_edit')" @click="toggleActive(p)" class="text-xs" :class="p.is_active ? 'text-error' : 'text-success'">
                  {{ p.is_active ? '停用' : '启用' }}
                </button>
              </td>
            </tr>
          </tbody>
          <tfoot v-if="hasPagination" class="bg-elevated text-sm">
            <tr>
              <td :colspan="100" class="px-3.5 py-2.5">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-muted">共 {{ pageItemCount }} 条</span>
                  <div class="flex items-center gap-1">
                    <button @click="prevPage(); loadList()" :disabled="page <= 1" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">‹</button>
                    <template v-for="(pg, i) in visiblePages" :key="i">
                      <span v-if="pg === '…'" class="w-7 h-7 flex items-center justify-center text-xs text-muted cursor-default">…</span>
                      <button v-else @click="goToPage(pg); loadList()" :class="pg === page ? 'bg-primary text-white font-medium' : 'text-muted hover:bg-surface-hover hover:text-text'" class="w-7 h-7 flex items-center justify-center rounded-md text-xs">{{ pg }}</button>
                    </template>
                    <button @click="nextPage(); loadList()" :disabled="page >= totalPages" class="w-7 h-7 flex items-center justify-center rounded-md text-xs text-muted hover:bg-surface-hover disabled:opacity-30 disabled:cursor-not-allowed">›</button>
                  </div>
                  <span class="text-xs text-muted w-16"></span>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>

    <!-- 商品新增/编辑弹窗 -->
    <ProductFormModal
      v-model:visible="showProductModal"
      :product="editingProduct"
      @saved="onProductSaved"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Search } from 'lucide-vue-next'
import { useAppStore } from '../../../stores/app'
import { usePermission } from '../../../composables/usePermission'
import { usePagination } from '../../../composables/usePagination'
import { getProducts, updateProduct } from '../../../api/products'
import { getProductBrands } from '../../../api/brands'
import { getCategories } from '../../../api/products'
import PageToolbar from '../../common/PageToolbar.vue'
import ProductFormModal from '../stock/ProductFormModal.vue'

const appStore = useAppStore()
const { hasPermission } = usePermission()
const { page, pageSize, total, totalPages, hasPagination, paginationParams, visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage } = usePagination(20)

const products = ref([])
const brands = ref([])
const categories = ref([])
const filters = reactive({ brand: '', category: '' })
const searchQuery = ref('')

// 弹窗状态
const showProductModal = ref(false)
const editingProduct = ref(null)

// 加载商品列表
const loadList = async () => {
  try {
    const params = { ...paginationParams.value, include_inactive: true }
    if (filters.brand) params.brand = filters.brand
    if (filters.category) params.category = filters.category
    if (searchQuery.value) params.keyword = searchQuery.value
    const { data } = await getProducts(params)
    products.value = data.items || data
    total.value = data.total ?? 0
  } catch (e) {
    console.error(e)
  }
}

// 搜索防抖
let _timer = null
const debouncedSearch = () => {
  clearTimeout(_timer)
  resetPage()
  _timer = setTimeout(loadList, 300)
}
onUnmounted(() => clearTimeout(_timer))

// 筛选变化
const onFilterChange = () => {
  resetPage()
  loadList()
}

// 加载品牌和分类列表
const loadFilters = async () => {
  try {
    const [brandsRes, catsRes] = await Promise.all([getProductBrands(), getCategories()])
    brands.value = brandsRes.data || []
    categories.value = catsRes.data || []
  } catch (e) {
    console.error(e)
  }
}

// 新增商品
const openCreate = () => {
  editingProduct.value = null
  showProductModal.value = true
}

// 编辑商品
const openEdit = (product) => {
  editingProduct.value = product
  showProductModal.value = true
}

// 保存后刷新
const onProductSaved = () => {
  loadList()
  loadFilters()
}

// 停用/启用
const toggleActive = async (product) => {
  const action = product.is_active ? '停用' : '启用'
  if (!confirm(`确定${action}「${product.name}」？`)) return
  try {
    await updateProduct(product.id, { is_active: !product.is_active })
    appStore.showToast(`${action}成功`)
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || `${action}失败`, 'error')
  }
}

// 初始化
onMounted(() => {
  loadList()
  loadFilters()
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/business/purchase/MaterialsTab.vue
git commit -m "feat(MaterialsTab): 新建物料管理面板 — 列表/搜索/筛选/CRUD"
```

---

### Task 8: PurchaseView 注册物料管理 Tab

**Files:**
- Modify: `frontend/src/views/PurchaseView.vue`

- [ ] **Step 1: 在 AppTabs 中添加第四个 Tab**

将第 4-8 行的 tabs 数组改为：

```vue
    <AppTabs v-model="purchaseTab" :tabs="[
      { value: 'orders', label: '采购订单' },
      { value: 'returns', label: '退货单' },
      { value: 'suppliers', label: '供应商管理' },
      { value: 'materials', label: '物料管理' }
    ]" container-class="mb-4" />
```

- [ ] **Step 2: 在 Transition 中添加 MaterialsTab 面板**

在 `PurchaseSuppliersPanel` 之后（第 28 行之前）添加：

```vue
      <MaterialsTab
        v-else-if="purchaseTab === 'materials'"
        key="materials"
      />
```

- [ ] **Step 3: 添加 import 语句**

在第 39 行（PurchaseReturnTab import）之后添加：

```javascript
import MaterialsTab from '../components/business/purchase/MaterialsTab.vue'
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/PurchaseView.vue
git commit -m "feat(PurchaseView): 注册物料管理 Tab"
```

---

### Task 9: StockView 移除商品管理功能

**Files:**
- Modify: `frontend/src/views/StockView.vue`

- [ ] **Step 1: 移除"新增商品"按钮**

删除第 26 行：

```vue
      <button @click="openProductModal()" class="btn btn-secondary btn-sm" v-if="hasPermission('stock_edit')">新增商品</button>
```

- [ ] **Step 2: 移除移动端"编辑"按钮**

将第 68-69 行：

```vue
              <template v-if="!s.is_virtual">
                <button @click="openProductModal(p)" class="text-primary">编辑</button>
                <button v-if="hasPermission('stock_edit')" @click="openTransferModal(p, s)" class="text-success">调拨</button>
              </template>
```

改为（移除编辑按钮，保留调拨）：

```vue
              <template v-if="!s.is_virtual">
                <button v-if="hasPermission('stock_edit')" @click="openTransferModal(p, s)" class="text-success">调拨</button>
              </template>
```

- [ ] **Step 3: 移除桌面端"编辑"按钮**

将第 144-148 行：

```vue
                <template v-if="!row.s.is_virtual">
                  <button @click="openProductModal(row.p)" class="text-primary text-xs mr-2">编辑</button>
                  <button v-if="hasPermission('stock_edit')" @click="openTransferModal(row.p, row.s)" class="text-success text-xs">调拨</button>
                </template>
```

改为：

```vue
                <template v-if="!row.s.is_virtual">
                  <button v-if="hasPermission('stock_edit')" @click="openTransferModal(row.p, row.s)" class="text-success text-xs">调拨</button>
                </template>
```

- [ ] **Step 4: 移除 ProductFormModal 组件及其模板使用**

删除第 176-181 行（ProductFormModal 模板）：

```vue
    <!-- 商品新增/编辑弹窗 -->
    <ProductFormModal
      v-model:visible="showProductModal"
      :product="editingProduct"
      @saved="loadProductsData"
    />
```

- [ ] **Step 5: 移除 ProductFormModal import**

删除第 229 行：

```javascript
import ProductFormModal from '../components/business/stock/ProductFormModal.vue'
```

- [ ] **Step 6: 移除相关状态变量和函数**

删除第 252 行：
```javascript
const showProductModal = ref(false)
```

删除第 260 行：
```javascript
const editingProduct = ref(null)
```

删除第 278-282 行（openProductModal 函数）：
```javascript
/** 打开商品弹窗（新增或编辑） */
const openProductModal = (product = null) => {
  editingProduct.value = product
  showProductModal.value = true
}
```

- [ ] **Step 7: 为零库存行添加 text-muted 样式**

在桌面表格的 `<tr>` 行（第 118-122 行），添加零库存样式条件：

将：
```vue
            <tr
              v-for="(row, idx) in sortedStockRows"
              :key="row.p.id + '-' + idx"
              class="hover:bg-elevated"
              :class="{ 'bg-purple-subtle': row.s.is_virtual }"
            >
```

改为：
```vue
            <tr
              v-for="(row, idx) in sortedStockRows"
              :key="row.p.id + '-' + idx"
              class="hover:bg-elevated"
              :class="{ 'bg-purple-subtle': row.s.is_virtual, 'text-muted': row.s.quantity === 0 }"
            >
```

同样对移动端卡片（第 42-43 行），添加零库存样式：

将：
```vue
          class="card p-3"
          :class="{ 'bg-purple-subtle': s.is_virtual }"
```

改为：
```vue
          class="card p-3"
          :class="{ 'bg-purple-subtle': s.is_virtual, 'text-muted': s.quantity === 0 }"
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/StockView.vue
git commit -m "refactor(StockView): 移除商品管理功能 + 零库存行弱化样式"
```

---

### Task 10: Build 验证

- [ ] **Step 1: 运行前端构建**

```bash
cd frontend && npm run build
```

Expected: 编译成功，无错误。

- [ ] **Step 2: 修复可能的构建错误**

如有 import 错误或未使用变量，修复后重新构建。

- [ ] **Step 3: Commit 修复（如有）**

```bash
git add -A
git commit -m "fix: 修复构建错误"
```
