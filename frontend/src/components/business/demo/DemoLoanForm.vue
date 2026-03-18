<!--
  借出申请弹窗
  选择样机 + 借用类型 + 借用人 + 经办人 + 预计归还日期
-->
<template>
  <AppModal :visible="visible" title="借出申请" width="640px" @close="$emit('close')">
    <div class="space-y-4">

      <!-- 样机选择 -->
      <div class="relative">
        <label class="label" for="loan-unit-search">样机 *</label>
        <input
          id="loan-unit-search"
          v-model="unitSearch"
          @input="unitDropdown = true"
          @focus="unitDropdown = true"
          @blur="hideUnitDropdown"
          class="input text-sm"
          placeholder="输入样机编号或产品名称搜索..."
          autocomplete="off"
        >
        <div v-if="unitDropdown && filteredUnits.length" class="absolute z-50 left-0 right-0 bg-surface border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
          <div
            v-for="u in filteredUnits"
            :key="u.id"
            @mousedown.prevent="selectUnit(u)"
            class="px-2 py-2 hover:bg-info-subtle cursor-pointer text-sm"
          >
            {{ u.code }} - {{ u.product_name }}
            <span v-if="u.sn_code" class="text-muted text-xs ml-1">({{ u.sn_code }})</span>
          </div>
        </div>
      </div>

      <!-- 借用类型 -->
      <div>
        <label class="label" for="loan-type">借用类型 *</label>
        <select id="loan-type" v-model="form.loan_type" class="input text-sm">
          <option value="customer_trial">客户试用</option>
          <option value="salesperson">业务员携带</option>
          <option value="exhibition">展会</option>
        </select>
      </div>

      <!-- 借用人类型 -->
      <div>
        <label class="label">借用人类型</label>
        <div class="flex items-center gap-4 mt-1">
          <label class="flex items-center gap-1.5 cursor-pointer text-sm">
            <input type="radio" v-model="form.borrower_type" value="customer" class="w-4 h-4"> 客户
          </label>
          <label class="flex items-center gap-1.5 cursor-pointer text-sm">
            <input type="radio" v-model="form.borrower_type" value="employee" class="w-4 h-4"> 员工
          </label>
        </div>
      </div>

      <!-- 借用人选择 -->
      <div class="relative">
        <label class="label" for="loan-borrower-search">借用人 *</label>
        <input
          id="loan-borrower-search"
          v-model="borrowerSearch"
          @input="borrowerDropdown = true"
          @focus="borrowerDropdown = true"
          @blur="hideBorrowerDropdown"
          class="input text-sm"
          :placeholder="form.borrower_type === 'customer' ? '搜索客户名称...' : '搜索员工姓名...'"
          autocomplete="off"
        >
        <div v-if="borrowerDropdown && filteredBorrowers.length" class="absolute z-50 left-0 right-0 bg-surface border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
          <div
            v-for="b in filteredBorrowers"
            :key="b.id"
            @mousedown.prevent="selectBorrower(b)"
            class="px-2 py-2 hover:bg-info-subtle cursor-pointer text-sm"
          >
            {{ b.name }}
            <span v-if="b.contact_person" class="text-muted text-xs ml-1">({{ b.contact_person }})</span>
          </div>
        </div>
      </div>

      <!-- 经办人 -->
      <div class="relative">
        <label class="label" for="loan-handler-search">经办人 *</label>
        <input
          id="loan-handler-search"
          v-model="handlerSearch"
          @input="handlerDropdown = true"
          @focus="handlerDropdown = true"
          @blur="hideHandlerDropdown"
          class="input text-sm"
          placeholder="搜索经办人..."
          autocomplete="off"
        >
        <div v-if="handlerDropdown && filteredHandlers.length" class="absolute z-50 left-0 right-0 bg-surface border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
          <div
            v-for="h in filteredHandlers"
            :key="h.id"
            @mousedown.prevent="selectHandler(h)"
            class="px-2 py-2 hover:bg-info-subtle cursor-pointer text-sm"
          >
            {{ h.name }}
          </div>
        </div>
      </div>

      <!-- 预计归还日期 -->
      <div>
        <label class="label" for="loan-return-date">预计归还日期 *</label>
        <input
          id="loan-return-date"
          v-model="form.expected_return_date"
          type="date"
          class="input text-sm"
        >
      </div>

      <!-- 用途说明 -->
      <div>
        <label class="label" for="loan-purpose">用途说明</label>
        <textarea
          id="loan-purpose"
          v-model="form.purpose"
          class="input text-sm"
          rows="2"
          placeholder="可选"
        ></textarea>
      </div>

    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-3">
        <button type="button" class="btn btn-secondary btn-sm" @click="$emit('close')">取消</button>
        <button type="button" class="btn btn-primary btn-sm" :disabled="appStore.submitting" @click="handleSubmit">
          {{ appStore.submitting ? '提交中...' : '提交申请' }}
        </button>
      </div>
    </template>
  </AppModal>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import AppModal from '../../common/AppModal.vue'
import { useAppStore } from '../../../stores/app'
import { createDemoLoan, getDemoUnits } from '../../../api/demo'
import { getCustomers } from '../../../api/customers'
import { getEmployees } from '../../../api/employees'

const props = defineProps({
  visible: Boolean,
  preselectUnit: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])
const appStore = useAppStore()

// 可选样机列表（仅在库的）
const availableUnits = ref([])
const unitSearch = ref('')
const unitDropdown = ref(false)

// 借用人列表
const customers = ref([])
const employees = ref([])
const borrowerSearch = ref('')
const borrowerDropdown = ref(false)

// 经办人列表
const handlerSearch = ref('')
const handlerDropdown = ref(false)

// 下拉定时器
let _blurTimer = null
const hideUnitDropdown = () => {
  clearTimeout(_blurTimer)
  _blurTimer = setTimeout(() => { unitDropdown.value = false }, 200)
}
const hideBorrowerDropdown = () => {
  clearTimeout(_blurTimer)
  _blurTimer = setTimeout(() => { borrowerDropdown.value = false }, 200)
}
const hideHandlerDropdown = () => {
  clearTimeout(_blurTimer)
  _blurTimer = setTimeout(() => { handlerDropdown.value = false }, 200)
}
onUnmounted(() => clearTimeout(_blurTimer))

// 表单
const form = reactive({
  demo_unit_id: null,
  loan_type: 'customer_trial',
  borrower_type: 'customer',
  borrower_id: null,
  handler_id: null,
  expected_return_date: '',
  purpose: '',
})

// 搜索过滤
const filteredUnits = computed(() => {
  const q = unitSearch.value.trim().toLowerCase()
  if (!q) return availableUnits.value.slice(0, 20)
  return availableUnits.value.filter(u =>
    u.code.toLowerCase().includes(q) ||
    (u.product_name && u.product_name.toLowerCase().includes(q)) ||
    (u.sn_code && u.sn_code.toLowerCase().includes(q))
  ).slice(0, 20)
})

const filteredBorrowers = computed(() => {
  const q = borrowerSearch.value.trim().toLowerCase()
  const list = form.borrower_type === 'customer' ? customers.value : employees.value
  if (!q) return list.slice(0, 20)
  return list.filter(b =>
    b.name.toLowerCase().includes(q) ||
    (b.contact_person && b.contact_person.toLowerCase().includes(q))
  ).slice(0, 20)
})

const filteredHandlers = computed(() => {
  const q = handlerSearch.value.trim().toLowerCase()
  if (!q) return employees.value.slice(0, 20)
  return employees.value.filter(h => h.name.toLowerCase().includes(q)).slice(0, 20)
})

// 选择操作
const selectUnit = (u) => {
  form.demo_unit_id = u.id
  unitSearch.value = `${u.code} - ${u.product_name}`
  unitDropdown.value = false
}

const selectBorrower = (b) => {
  form.borrower_id = b.id
  borrowerSearch.value = b.name
  borrowerDropdown.value = false
}

const selectHandler = (h) => {
  form.handler_id = h.id
  handlerSearch.value = h.name
  handlerDropdown.value = false
}

// 加载数据
const loadAvailableUnits = async () => {
  try {
    const { data } = await getDemoUnits({ status: 'in_stock', page_size: 200 })
    availableUnits.value = data.items || []
  } catch (e) {
    console.error('加载可借样机失败:', e)
  }
}

const loadCustomers = async () => {
  try {
    const { data } = await getCustomers()
    customers.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载客户失败:', e)
  }
}

const loadEmployees = async () => {
  try {
    const { data } = await getEmployees()
    employees.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    console.error('加载员工失败:', e)
  }
}

// 重置表单
const resetForm = () => {
  Object.assign(form, {
    demo_unit_id: null,
    loan_type: 'customer_trial',
    borrower_type: 'customer',
    borrower_id: null,
    handler_id: null,
    expected_return_date: '',
    purpose: '',
  })
  unitSearch.value = ''
  borrowerSearch.value = ''
  handlerSearch.value = ''
}

// 切换借用人类型时清除已选
watch(() => form.borrower_type, () => {
  form.borrower_id = null
  borrowerSearch.value = ''
})

// 弹窗打开时重置/预填
watch(() => props.visible, (val) => {
  if (val) {
    resetForm()
    loadAvailableUnits()
    if (props.preselectUnit) {
      form.demo_unit_id = props.preselectUnit.id
      unitSearch.value = `${props.preselectUnit.code} - ${props.preselectUnit.product_name}`
    }
  }
})

// 校验
const validate = () => {
  if (!form.demo_unit_id) {
    appStore.showToast('请选择样机', 'error')
    return false
  }
  if (!form.borrower_id) {
    appStore.showToast('请选择借用人', 'error')
    return false
  }
  if (!form.handler_id) {
    appStore.showToast('请选择经办人', 'error')
    return false
  }
  if (!form.expected_return_date) {
    appStore.showToast('请选择预计归还日期', 'error')
    return false
  }
  return true
}

// 提交
const handleSubmit = async () => {
  if (!validate()) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await createDemoLoan({
      demo_unit_id: form.demo_unit_id,
      loan_type: form.loan_type,
      borrower_type: form.borrower_type,
      borrower_id: form.borrower_id,
      handler_id: form.handler_id,
      expected_return_date: form.expected_return_date,
      purpose: form.purpose || null,
    })
    appStore.showToast('借出申请已提交')
    emit('saved')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '提交失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

onMounted(() => {
  loadCustomers()
  loadEmployees()
})
</script>
