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
              <th class="px-2 py-2 text-left w-28">SKU</th>
              <th class="px-2 py-2 text-left">商品名称</th>
              <th class="px-2 py-2 text-left w-24">品牌</th>
              <th class="px-2 py-2 text-left w-20">分类</th>
              <th class="px-2 py-2 text-left w-16">单位</th>
              <th class="px-2 py-2 text-right w-24">零售价</th>
              <th v-if="hasPermission('finance')" class="px-2 py-2 text-right w-24">成本价</th>
              <th class="px-2 py-2 text-right w-16">税率</th>
              <th class="px-2 py-2 text-center w-16">状态</th>
              <th class="px-2 py-2 text-center w-28">操作</th>
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
              <td class="px-2 py-2 font-mono text-xs">{{ p.sku }}</td>
              <td class="px-2 py-2">
                <span :class="{ 'line-through': !p.is_active }">{{ p.name }}</span>
              </td>
              <td class="px-2 py-2 text-secondary text-xs">{{ p.brand || '-' }}</td>
              <td class="px-2 py-2 text-secondary text-xs">{{ p.category || '-' }}</td>
              <td class="px-2 py-2 text-secondary text-xs">{{ p.unit }}</td>
              <td class="px-2 py-2 text-right">{{ p.retail_price }}</td>
              <td v-if="hasPermission('finance')" class="px-2 py-2 text-right">{{ p.cost_price }}</td>
              <td class="px-2 py-2 text-right text-xs text-secondary">{{ p.tax_rate }}%</td>
              <td class="px-2 py-2 text-center">
                <span :class="p.is_active ? 'badge badge-blue' : 'badge badge-muted'">{{ p.is_active ? '启用' : '停用' }}</span>
              </td>
              <td class="px-2 py-2 text-center" @click.stop>
                <div class="flex gap-1 justify-center">
                  <button @click="openEdit(p)" class="px-2 py-0.5 rounded-md text-[12px] font-medium bg-info-subtle text-info-emphasis transition-colors">编辑</button>
                  <button v-if="hasPermission('stock_edit')" @click="toggleActive(p)" class="px-2 py-0.5 rounded-md text-[12px] font-medium transition-colors" :class="p.is_active ? 'bg-error-subtle text-error-emphasis' : 'bg-success-subtle text-success-emphasis'">
                    {{ p.is_active ? '停用' : '启用' }}
                  </button>
                </div>
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
import { getProducts, updateProduct, getCategories } from '../../../api/products'
import { getProductBrands } from '../../../api/brands'
import PageToolbar from '../../common/PageToolbar.vue'
import ProductFormModal from '../stock/ProductFormModal.vue'

const appStore = useAppStore()
const { hasPermission } = usePermission()
const { page, total, totalPages, hasPagination, paginationParams, visiblePages, pageItemCount, resetPage, prevPage, nextPage, goToPage } = usePagination(20)

const products = ref([])
const brands = ref([])
const categories = ref([])
const filters = reactive({ brand: '', category: '' })
const searchQuery = ref('')

const showProductModal = ref(false)
const editingProduct = ref(null)

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

let _timer = null
const debouncedSearch = () => {
  clearTimeout(_timer)
  resetPage()
  _timer = setTimeout(loadList, 300)
}
onUnmounted(() => clearTimeout(_timer))

const onFilterChange = () => {
  resetPage()
  loadList()
}

const loadFilters = async () => {
  try {
    const [brandsRes, catsRes] = await Promise.all([getProductBrands(), getCategories()])
    const bd = brandsRes.data; brands.value = bd.items || bd || []
    const cd = catsRes.data; categories.value = cd.items || cd || []
  } catch (e) {
    console.error(e)
  }
}

const openCreate = () => {
  editingProduct.value = null
  showProductModal.value = true
}

const openEdit = (product) => {
  editingProduct.value = product
  showProductModal.value = true
}

const onProductSaved = () => {
  loadList()
  loadFilters()
}

const toggleActive = async (product) => {
  const action = product.is_active ? '停用' : '启用'
  if (!await appStore.customConfirm(`${action}确认`, `确定${action}「${product.name}」？`)) return
  try {
    await updateProduct(product.id, { is_active: !product.is_active })
    appStore.showToast(`${action}成功`)
    loadList()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || `${action}失败`, 'error')
  }
}

onMounted(() => {
  loadList()
  loadFilters()
})
</script>
