<!--
  仓库与仓位管理组件
  功能：仓库列表展开/折叠、仓库新建/改名/删除/设为默认、
        仓位新增/编辑/删除（含颜色标记）、仓库关联账套、SN码管理配置
  从 SettingsView.vue 常规设置标签页提取
-->
<template>
  <div class="contents">
    <!-- 仓库与仓位管理卡片 -->
    <div class="card p-4 md:col-span-2">
      <h3 class="font-semibold mb-3 text-sm">仓库与仓位管理</h3>
      <!-- 仓库列表（手风琴） -->
      <div class="space-y-3 mb-3">
        <div v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" class="border rounded-lg overflow-hidden">
          <!-- 仓库标题行 -->
          <div class="flex justify-between items-center p-3 bg-elevated cursor-pointer" @click="toggleExpandWarehouse(w.id)">
            <div class="flex items-center gap-2">
              <span class="text-xs text-muted">{{ expandedWarehouse === w.id ? '▼' : '▶' }}</span>
              <span class="font-medium text-sm">{{ w.name }}</span>
              <span v-if="w.is_default" class="text-xs text-primary bg-info-subtle px-1.5 py-0.5 rounded">(默认)</span>
              <span v-if="w.account_set_name" class="text-xs text-white bg-primary px-1.5 py-0.5 rounded">{{ w.account_set_name }}</span>
              <span v-else-if="accountSets.length" class="text-xs text-muted bg-elevated px-1.5 py-0.5 rounded border border-dashed">未关联账套</span>
              <span class="text-xs text-muted">{{ (w.locations || []).length }} 个仓位</span>
            </div>
            <div class="flex gap-2" @click.stop>
              <button v-if="!w.is_default" @click="handleSetDefaultWarehouse(w.id)" class="text-success-emphasis text-xs">设为默认</button>
              <button @click="editWarehouse(w)" class="text-primary text-xs">编辑</button>
              <button v-if="!w.is_default" @click="handleDeleteWarehouse(w.id)" class="text-error text-xs">删除</button>
            </div>
          </div>
          <!-- 仓位列表（展开后显示） -->
          <div v-if="expandedWarehouse === w.id" class="p-3 border-t bg-surface">
            <div class="space-y-1.5 mb-3 max-h-48 overflow-y-auto">
              <div v-for="loc in (w.locations || [])" :key="loc.id" class="flex justify-between items-center px-3 py-1.5 bg-elevated rounded text-sm">
                <div class="flex items-center gap-2">
                  <span class="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0" :style="`background-color: var(--${colorCssVarMap[loc.color || DEFAULT_LOCATION_COLOR] || 'info-emphasis'})`"></span>
                  <span>{{ loc.code }} <span v-if="loc.name" class="text-xs text-muted">{{ loc.name }}</span></span>
                </div>
                <div>
                  <button @click="editLocation(loc, w.id)" class="text-primary text-xs mr-2">编辑</button>
                  <button @click="handleDeleteLocation(loc.id)" class="text-error text-xs">删除</button>
                </div>
              </div>
              <div v-if="!(w.locations || []).length" class="text-muted text-center py-2 text-xs">暂无仓位</div>
            </div>
            <!-- 新增仓位表单 -->
            <form @submit.prevent="handleCreateLocation(w.id)" class="flex gap-2 items-end">
              <input v-model="getLocationInput(w.id).code" class="input flex-1 text-sm" placeholder="仓位编号(如 A-01-02)">
              <input v-model="getLocationInput(w.id).name" class="input flex-1 text-sm" placeholder="名称(可选)">
              <div class="flex gap-1 flex-shrink-0">
                <button
                  v-for="c in colorOptions"
                  :key="c.value"
                  type="button"
                  @click="getLocationInput(w.id).color = c.value"
                  class="w-5 h-5 rounded-full border-2 flex-shrink-0"
                  :class="(getLocationInput(w.id).color || DEFAULT_LOCATION_COLOR) === c.value ? 'border-foreground scale-110' : 'border-transparent opacity-50 hover:opacity-100'"
                  :style="`background-color: var(--${c.cssVar})`"
                  :title="c.label"
                ></button>
              </div>
              <button type="submit" class="btn btn-primary btn-sm">添加</button>
            </form>
          </div>
        </div>
      </div>
      <!-- 新增仓库按钮 -->
      <button @click="openCreateWarehouse" class="btn btn-primary btn-sm">添加仓库</button>
    </div>

    <!-- SN码管理配置卡片 -->
    <div class="card p-4">
      <h3 class="font-semibold mb-3 text-sm">SN码管理配置</h3>
      <div class="text-xs text-muted mb-3">配置需要SN码追踪的"仓库+品牌"组合，启用后入库必填SN码</div>
      <div class="space-y-2 mb-3 max-h-48 overflow-y-auto">
        <div v-for="c in snConfigs" :key="c.id" class="flex justify-between items-center p-2 bg-elevated rounded text-sm">
          <span>{{ c.warehouse_name }} <span class="text-primary font-medium">{{ c.brand }}</span></span>
          <button @click="handleDeleteSnConfig(c.id)" class="text-error text-xs">删除</button>
        </div>
        <div v-if="!snConfigs.length" class="text-muted text-center py-2 text-sm">暂无配置</div>
      </div>
      <div class="flex gap-2">
        <select v-model="newSnConfigWarehouse" class="input flex-1 text-sm">
          <option value="">选择仓库</option>
          <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
        </select>
        <select v-model="newSnConfigBrand" class="input flex-1 text-sm">
          <option value="">选择品牌</option>
          <option v-for="b in productBrands" :key="b" :value="b">{{ b }}</option>
        </select>
        <button @click="handleCreateSnConfig" class="btn btn-primary btn-sm">添加</button>
      </div>
    </div>

    <!-- 仓库改名弹窗 -->
    <div v-if="showWarehouseModal" class="modal-overlay active" @click.self="showWarehouseModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">{{ warehouseForm.id ? '编辑仓库 - ' + warehouseForm.name : '新建仓库' }}</h3>
          <button @click="showWarehouseModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body"><div class="space-y-3">
          <div><label class="label">仓库名称 *</label><input v-model="warehouseForm.name" class="input" required placeholder="请输入新名称"></div>
          <div><label class="flex items-center"><input type="checkbox" v-model="warehouseForm.is_default" class="mr-2">设为默认仓库</label></div>
          <div v-if="accountSets.length">
            <label class="label">关联账套</label>
            <select v-model="warehouseForm.account_set_id" class="input">
              <option :value="null">不关联</option>
              <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
        </div></div>
        <div class="modal-footer">
          <button type="button" @click="showWarehouseModal = false" class="btn btn-sm btn-secondary">取消</button>
          <button type="button" @click="saveWarehouse()" class="btn btn-sm btn-primary">保存</button>
        </div>
      </div>
    </div>

    <!-- 仓位编辑弹窗 -->
    <div v-if="showLocationModal" class="modal-overlay active" @click.self="showLocationModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">编辑仓位 - {{ locationForm.code }}</h3>
          <button @click="showLocationModal = false" class="modal-close">&times;</button>
        </div>
        <div class="modal-body"><div class="space-y-3">
          <div><label class="label">仓位编号 *</label><input v-model="locationForm.code" class="input" required placeholder="如 A-01-02"></div>
          <div><label class="label">仓位名称</label><input v-model="locationForm.name" class="input" placeholder="可选，如：主通道左侧"></div>
          <div>
            <label class="label">标记颜色</label>
            <div class="flex gap-2 mt-1">
              <button
                v-for="c in colorOptions"
                :key="c.value"
                type="button"
                @click="locationForm.color = c.value"
                class="w-7 h-7 rounded-full border-2 transition-all flex items-center justify-center"
                :class="locationForm.color === c.value ? 'border-foreground scale-110' : 'border-transparent opacity-60 hover:opacity-100'"
                :style="`background-color: var(--${c.cssVar})`"
                :title="c.label"
              >
                <svg v-if="locationForm.color === c.value" class="w-3 h-3 text-white" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>
              </button>
            </div>
          </div>
        </div></div>
        <div class="modal-footer">
          <button type="button" @click="showLocationModal = false" class="btn btn-sm btn-secondary">取消</button>
          <button type="button" @click="saveLocation()" class="btn btn-sm btn-primary">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * 仓库与仓位管理 + SN码配置
 * 包含：仓库CRUD、仓位CRUD（含颜色标记）、账套关联、SN配置CRUD
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { useWarehousesStore } from '../../../stores/warehouses'
import { useSettingsStore } from '../../../stores/settings'
import {
  createWarehouse, updateWarehouse, deleteWarehouse as deleteWarehouseApi,
  createLocation, updateLocation, deleteLocation as deleteLocationApi
} from '../../../api/warehouses'
import { createSnConfig, deleteSnConfig as deleteSnConfigApi } from '../../../api/sn'
import { getAccountSets } from '../../../api/accounting'
import { LOCATION_COLORS, DEFAULT_LOCATION_COLOR, locationColorCssVarMap } from '../../../utils/constants'

const colorOptions = LOCATION_COLORS
const colorCssVarMap = locationColorCssVarMap

const emit = defineEmits(['data-changed'])

const appStore = useAppStore()
const warehousesStore = useWarehousesStore()
const settingsStore = useSettingsStore()
const warehouses = computed(() => warehousesStore.warehouses)
const snConfigs = computed(() => settingsStore.snConfigs)
const productBrands = computed(() => settingsStore.productBrands)

// 账套列表（用于仓库关联）
const accountSets = ref([])

// 仓库相关状态
const showWarehouseModal = ref(false)
const warehouseForm = reactive({ id: null, name: '', is_default: false, account_set_id: null })
const expandedWarehouse = ref(null)

// 仓位相关状态
const newLocationInputs = ref({})
const getLocationInput = (whId) => {
  if (!newLocationInputs.value[whId]) {
    newLocationInputs.value[whId] = { code: '', name: '', color: DEFAULT_LOCATION_COLOR }
  }
  return newLocationInputs.value[whId]
}
const showLocationModal = ref(false)
const locationForm = reactive({ id: null, code: '', name: '', color: DEFAULT_LOCATION_COLOR })

// SN配置状态
const newSnConfigWarehouse = ref('')
const newSnConfigBrand = ref('')

// 展开/折叠仓库
const toggleExpandWarehouse = (id) => {
  expandedWarehouse.value = expandedWarehouse.value === id ? null : id
}

// === 仓库操作 ===
const openCreateWarehouse = () => {
  Object.assign(warehouseForm, { id: null, name: '', is_default: false, account_set_id: null })
  showWarehouseModal.value = true
}

const editWarehouse = (w) => {
  Object.assign(warehouseForm, { id: w.id, name: w.name, is_default: w.is_default, account_set_id: w.account_set_id || null })
  showWarehouseModal.value = true
}

const saveWarehouse = async () => {
  if (!warehouseForm.name || !warehouseForm.name.trim()) {
    appStore.showToast('请输入仓库名称', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    if (warehouseForm.id) {
      await updateWarehouse(warehouseForm.id, { name: warehouseForm.name.trim(), is_default: warehouseForm.is_default, account_set_id: warehouseForm.account_set_id || null })
    } else {
      await createWarehouse({ name: warehouseForm.name.trim(), is_default: warehouseForm.is_default, account_set_id: warehouseForm.account_set_id || null })
    }
    appStore.showToast(warehouseForm.id ? '保存成功' : '创建成功')
    showWarehouseModal.value = false
    warehousesStore.loadWarehouses()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleDeleteWarehouse = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该仓库？')) return
  try {
    await deleteWarehouseApi(id)
    appStore.showToast('已删除')
    warehousesStore.loadWarehouses()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

const handleSetDefaultWarehouse = async (id) => {
  try {
    await updateWarehouse(id, { is_default: true })
    appStore.showToast('默认仓库已切换')
    warehousesStore.loadWarehouses()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

// === 仓位操作 ===
const editLocation = (loc, warehouseId) => {
  Object.assign(locationForm, { id: loc.id, code: loc.code, name: loc.name || '', color: loc.color || DEFAULT_LOCATION_COLOR })
  showLocationModal.value = true
}

const saveLocation = async () => {
  if (!locationForm.code || !locationForm.code.trim()) {
    appStore.showToast('请输入仓位编号', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await updateLocation(locationForm.id, { code: locationForm.code.trim(), name: locationForm.name || null, color: locationForm.color })
    appStore.showToast('保存成功')
    showLocationModal.value = false
    warehousesStore.loadWarehouses()
    warehousesStore.loadLocations()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleCreateLocation = async (warehouseId) => {
  const input = getLocationInput(warehouseId)
  if (!input.code || !input.code.trim()) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await createLocation({ warehouse_id: warehouseId, code: input.code.trim(), name: input.name.trim() || null, color: input.color || DEFAULT_LOCATION_COLOR })
    appStore.showToast('创建成功')
    input.code = ''
    input.name = ''
    input.color = DEFAULT_LOCATION_COLOR
    warehousesStore.loadWarehouses()
    warehousesStore.loadLocations()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleDeleteLocation = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该仓位？')) return
  try {
    await deleteLocationApi(id)
    appStore.showToast('已删除')
    warehousesStore.loadWarehouses()
    warehousesStore.loadLocations()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// === SN配置操作 ===
const handleCreateSnConfig = async () => {
  if (!newSnConfigWarehouse.value || !newSnConfigBrand.value) {
    appStore.showToast('请选择仓库和品牌', 'error')
    return
  }
  try {
    await createSnConfig({ warehouse_id: parseInt(newSnConfigWarehouse.value), brand: newSnConfigBrand.value })
    appStore.showToast('配置已添加')
    newSnConfigWarehouse.value = ''
    newSnConfigBrand.value = ''
    settingsStore.loadSnConfigs()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '添加失败', 'error')
  }
}

const handleDeleteSnConfig = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该SN配置？')) return
  try {
    await deleteSnConfigApi(id)
    appStore.showToast('已删除')
    settingsStore.loadSnConfigs()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// 组件挂载时加载账套数据
onMounted(async () => {
  warehousesStore.loadWarehouses()
  warehousesStore.loadLocations()
  settingsStore.loadSnConfigs()
  settingsStore.loadProductBrands()
  try {
    const { data } = await getAccountSets()
    accountSets.value = data.items || data
  } catch (e) { /* ignore */ }
})
</script>
