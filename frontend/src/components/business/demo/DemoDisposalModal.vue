<!--
  处置通用弹窗
  根据 type 切换：转销售 / 翻新转良品 / 报废 / 登记丢失
-->
<template>
  <AppModal :visible="visible" :title="modalTitle" width="600px" @close="$emit('close')">
    <div class="space-y-4">

      <!-- 样机信息 -->
      <div v-if="unit" class="card p-3 space-y-1 text-sm">
        <div class="flex justify-between">
          <span class="text-muted">样机编号</span>
          <span class="font-mono">{{ unit.code }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-muted">产品</span>
          <span>{{ unit.product_name }}</span>
        </div>
        <div v-if="unit.sn_code" class="flex justify-between">
          <span class="text-muted">SN码</span>
          <span class="font-mono">{{ unit.sn_code }}</span>
        </div>
      </div>

      <!-- ===== 转销售 ===== -->
      <template v-if="type === 'sale'">
        <!-- 客户 -->
        <div class="relative">
          <label class="label" for="disposal-customer">客户 *</label>
          <input
            id="disposal-customer"
            v-model="customerSearch"
            @input="customerDropdown = true"
            @focus="customerDropdown = true"
            @blur="hideCustomerDropdown"
            class="input text-sm"
            placeholder="输入客户名称搜索..."
            autocomplete="off"
          >
          <div v-if="customerDropdown && filteredCustomers.length" class="absolute z-50 left-0 right-0 bg-surface border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
            <div
              v-for="c in filteredCustomers"
              :key="c.id"
              @mousedown.prevent="selectCustomer(c)"
              class="px-2 py-2 hover:bg-info-subtle cursor-pointer text-sm"
            >
              {{ c.name }}
              <span v-if="c.contact_person" class="text-muted text-xs ml-1">({{ c.contact_person }})</span>
            </div>
          </div>
        </div>

        <!-- 销售价 -->
        <div>
          <label class="label" for="disposal-sale-price">销售价 *</label>
          <input
            id="disposal-sale-price"
            v-model.number="form.sale_price"
            type="number"
            step="0.01"
            min="0"
            class="input text-sm"
            placeholder="0.00"
          >
        </div>

        <!-- 账套 -->
        <div v-if="accountSets.length">
          <label class="label" for="disposal-account-set">财务账套</label>
          <select id="disposal-account-set" v-model="form.account_set_id" class="input text-sm">
            <option :value="null">不指定</option>
            <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>

        <!-- 经办人 -->
        <div class="relative">
          <label class="label" for="disposal-employee">经办人</label>
          <input
            id="disposal-employee"
            v-model="employeeSearch"
            @input="employeeDropdown = true"
            @focus="employeeDropdown = true"
            @blur="hideEmployeeDropdown"
            class="input text-sm"
            placeholder="搜索经办人..."
            autocomplete="off"
          >
          <div v-if="employeeDropdown && filteredEmployees.length" class="absolute z-50 left-0 right-0 bg-surface border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
            <div
              v-for="e in filteredEmployees"
              :key="e.id"
              @mousedown.prevent="selectEmployee(e)"
              class="px-2 py-2 hover:bg-info-subtle cursor-pointer text-sm"
            >
              {{ e.name }}
            </div>
          </div>
        </div>

        <!-- 备注 -->
        <div>
          <label class="label" for="disposal-sale-remark">备注</label>
          <textarea id="disposal-sale-remark" v-model="form.remark" class="input text-sm" rows="2" placeholder="可选"></textarea>
        </div>
      </template>

      <!-- ===== 翻新转良品 ===== -->
      <template v-else-if="type === 'conversion'">
        <!-- 目标仓库 -->
        <div>
          <label class="label" for="disposal-conv-wh">目标仓库 *</label>
          <select id="disposal-conv-wh" v-model="form.target_warehouse_id" class="input text-sm">
            <option :value="null">请选择仓库</option>
            <option v-for="w in warehouses" :key="w.id" :value="w.id">{{ w.name }}</option>
          </select>
        </div>

        <!-- 目标仓位 -->
        <div>
          <label class="label" for="disposal-conv-loc">目标仓位</label>
          <select id="disposal-conv-loc" v-model="form.target_location_id" class="input text-sm">
            <option :value="null">默认仓位</option>
            <option v-for="loc in filteredLocations" :key="loc.id" :value="loc.id">{{ loc.code }} - {{ loc.name }}</option>
          </select>
        </div>

        <!-- 翻新费用 -->
        <div>
          <label class="label" for="disposal-conv-cost">翻新费用</label>
          <input
            id="disposal-conv-cost"
            v-model.number="form.refurbish_cost"
            type="number"
            step="0.01"
            min="0"
            class="input text-sm"
            placeholder="0.00"
          >
        </div>
      </template>

      <!-- ===== 报废 ===== -->
      <template v-else-if="type === 'scrap'">
        <div>
          <label class="label" for="disposal-scrap-reason">报废原因 *</label>
          <textarea id="disposal-scrap-reason" v-model="form.reason" class="input text-sm" rows="3" placeholder="请说明报废原因"></textarea>
        </div>

        <div>
          <label class="label" for="disposal-scrap-residual">残值</label>
          <input
            id="disposal-scrap-residual"
            v-model.number="form.residual_value"
            type="number"
            step="0.01"
            min="0"
            class="input text-sm"
            placeholder="0.00"
          >
        </div>

        <div v-if="accountSets.length">
          <label class="label" for="disposal-scrap-acct">财务账套</label>
          <select id="disposal-scrap-acct" v-model="form.account_set_id" class="input text-sm">
            <option :value="null">不指定</option>
            <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
      </template>

      <!-- ===== 登记丢失 ===== -->
      <template v-else-if="type === 'loss'">
        <div>
          <label class="label" for="disposal-loss-desc">丢失说明 *</label>
          <textarea id="disposal-loss-desc" v-model="form.description" class="input text-sm" rows="3" placeholder="请描述丢失情况"></textarea>
        </div>

        <div>
          <label class="label" for="disposal-loss-comp">赔偿金额</label>
          <input
            id="disposal-loss-comp"
            v-model.number="form.compensation_amount"
            type="number"
            step="0.01"
            min="0"
            class="input text-sm"
            placeholder="0.00"
          >
        </div>

        <div v-if="accountSets.length">
          <label class="label" for="disposal-loss-acct">财务账套</label>
          <select id="disposal-loss-acct" v-model="form.account_set_id" class="input text-sm">
            <option :value="null">不指定</option>
            <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
      </template>

    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-3">
        <button type="button" class="btn btn-secondary btn-sm" @click="$emit('close')">取消</button>
        <button
          type="button"
          :class="type === 'scrap' || type === 'loss' ? 'btn btn-danger btn-sm' : 'btn btn-primary btn-sm'"
          :disabled="appStore.submitting"
          @click="handleSubmit"
        >
          {{ appStore.submitting ? '提交中...' : '确认' }}
        </button>
      </div>
    </template>
  </AppModal>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import AppModal from '../../common/AppModal.vue'
import { useAppStore } from '../../../stores/app'
import { sellDemoUnit, convertDemoUnit, scrapDemoUnit, reportLossDemoUnit } from '../../../api/demo'
import { getCustomers } from '../../../api/customers'
import { getEmployees } from '../../../api/employees'
import { getAccountSets } from '../../../api/accounting'
import { getWarehouses, getLocations } from '../../../api/warehouses'

const props = defineProps({
  visible: Boolean,
  unit: { type: Object, default: null },
  type: { type: String, default: 'sale' }, // sale | conversion | scrap | loss
})
const emit = defineEmits(['close', 'saved'])
const appStore = useAppStore()

// 标题
const TITLE_MAP = { sale: '转销售', conversion: '翻新转良品', scrap: '报废', loss: '登记丢失' }
const modalTitle = computed(() => TITLE_MAP[props.type] || '处置')

// 引用数据
const customers = ref([])
const employees = ref([])
const accountSets = ref([])
const warehouses = ref([])
const locations = ref([])

// 搜索/下拉状态
const customerSearch = ref('')
const customerDropdown = ref(false)
const employeeSearch = ref('')
const employeeDropdown = ref(false)

let _blurTimer = null
const hideCustomerDropdown = () => {
  clearTimeout(_blurTimer)
  _blurTimer = setTimeout(() => { customerDropdown.value = false }, 200)
}
const hideEmployeeDropdown = () => {
  clearTimeout(_blurTimer)
  _blurTimer = setTimeout(() => { employeeDropdown.value = false }, 200)
}
onUnmounted(() => clearTimeout(_blurTimer))

// 表单
const form = reactive({
  // 转销售
  customer_id: null,
  sale_price: null,
  account_set_id: null,
  employee_id: null,
  remark: '',
  // 翻新
  target_warehouse_id: null,
  target_location_id: null,
  refurbish_cost: null,
  // 报废
  reason: '',
  residual_value: null,
  // 丢失
  description: '',
  compensation_amount: null,
})

// 搜索过滤
const filteredCustomers = computed(() => {
  const q = customerSearch.value.trim().toLowerCase()
  if (!q) return customers.value.slice(0, 20)
  return customers.value.filter(c =>
    c.name.toLowerCase().includes(q) ||
    (c.contact_person && c.contact_person.toLowerCase().includes(q))
  ).slice(0, 20)
})

const filteredEmployees = computed(() => {
  const q = employeeSearch.value.trim().toLowerCase()
  if (!q) return employees.value.slice(0, 20)
  return employees.value.filter(e => e.name.toLowerCase().includes(q)).slice(0, 20)
})

const filteredLocations = computed(() => {
  if (!form.target_warehouse_id) return []
  return locations.value.filter(l => l.warehouse_id === form.target_warehouse_id)
})

// 选择
const selectCustomer = (c) => {
  form.customer_id = c.id
  customerSearch.value = c.name
  customerDropdown.value = false
}

const selectEmployee = (e) => {
  form.employee_id = e.id
  employeeSearch.value = e.name
  employeeDropdown.value = false
}

// 加载数据
const loadRefData = async () => {
  try {
    const [custRes, empRes, acctRes, whRes, locRes] = await Promise.all([
      getCustomers(),
      getEmployees(),
      getAccountSets(),
      getWarehouses(),
      getLocations(),
    ])
    customers.value = Array.isArray(custRes.data) ? custRes.data : (custRes.data.items || [])
    employees.value = Array.isArray(empRes.data) ? empRes.data : (empRes.data.items || [])
    accountSets.value = Array.isArray(acctRes.data) ? acctRes.data : (acctRes.data.items || [])
    warehouses.value = Array.isArray(whRes.data) ? whRes.data : (whRes.data.items || [])
    locations.value = Array.isArray(locRes.data) ? locRes.data : (locRes.data.items || [])
  } catch (e) {
    console.error('加载引用数据失败:', e)
  }
}

// 重置表单
const resetForm = () => {
  Object.assign(form, {
    customer_id: null,
    sale_price: null,
    account_set_id: null,
    employee_id: null,
    remark: '',
    target_warehouse_id: null,
    target_location_id: null,
    refurbish_cost: null,
    reason: '',
    residual_value: null,
    description: '',
    compensation_amount: null,
  })
  customerSearch.value = ''
  employeeSearch.value = ''
}

watch(() => props.visible, (val) => {
  if (val) resetForm()
})

// 校验
const validate = () => {
  if (props.type === 'sale') {
    if (!form.customer_id) { appStore.showToast('请选择客户', 'error'); return false }
    if (!form.sale_price || form.sale_price <= 0) { appStore.showToast('请输入销售价', 'error'); return false }
  } else if (props.type === 'conversion') {
    if (!form.target_warehouse_id) { appStore.showToast('请选择目标仓库', 'error'); return false }
  } else if (props.type === 'scrap') {
    if (!form.reason?.trim()) { appStore.showToast('请填写报废原因', 'error'); return false }
  } else if (props.type === 'loss') {
    if (!form.description?.trim()) { appStore.showToast('请填写丢失说明', 'error'); return false }
  }
  return true
}

// 提交
const handleSubmit = async () => {
  if (!validate()) return
  if (!props.unit?.id) return
  if (appStore.submitting) return
  appStore.submitting = true

  try {
    const id = props.unit.id
    if (props.type === 'sale') {
      await sellDemoUnit(id, {
        customer_id: form.customer_id,
        sale_price: form.sale_price,
        account_set_id: form.account_set_id || null,
        employee_id: form.employee_id || null,
        remark: form.remark || null,
      })
      appStore.showToast('转销售成功')
    } else if (props.type === 'conversion') {
      await convertDemoUnit(id, {
        target_warehouse_id: form.target_warehouse_id,
        target_location_id: form.target_location_id || null,
        refurbish_cost: form.refurbish_cost || null,
      })
      appStore.showToast('翻新转良品成功')
    } else if (props.type === 'scrap') {
      await scrapDemoUnit(id, {
        reason: form.reason,
        residual_value: form.residual_value || null,
        account_set_id: form.account_set_id || null,
      })
      appStore.showToast('报废成功')
    } else if (props.type === 'loss') {
      await reportLossDemoUnit(id, {
        description: form.description,
        compensation_amount: form.compensation_amount || null,
        account_set_id: form.account_set_id || null,
      })
      appStore.showToast('丢失登记成功')
    }
    emit('saved')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

onMounted(() => loadRefData())
</script>
