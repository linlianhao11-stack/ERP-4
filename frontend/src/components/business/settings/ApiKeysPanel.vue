<template>
  <div class="space-y-4">
    <!-- 1. API 密钥 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.keys = !sections.keys">
        <h3 class="font-semibold flex items-center gap-2">
          <Key :size="16" />
          API 密钥
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.keys }" class="transition-transform" />
      </button>
      <div v-if="sections.keys" class="mt-4 space-y-4">
        <!-- DeepSeek -->
        <div class="space-y-3">
          <h4 class="text-sm font-medium text-secondary">DeepSeek</h4>
          <div class="grid md:grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-muted mb-1 block" for="ds-key">API Key</label>
              <input id="ds-key" v-model="keys['ai.deepseek.api_key']" type="password" class="input text-sm" placeholder="sk-..." />
            </div>
            <div>
              <label class="text-xs text-muted mb-1 block" for="ds-url">Base URL</label>
              <input id="ds-url" v-model="keys['ai.deepseek.base_url']" class="input text-sm" placeholder="https://api.deepseek.com" />
            </div>
            <div>
              <label class="text-xs text-muted mb-1 block" for="ds-model-sql">SQL 模型</label>
              <input id="ds-model-sql" v-model="keys['ai.deepseek.model_sql']" class="input text-sm" placeholder="deepseek-reasoner" />
            </div>
            <div>
              <label class="text-xs text-muted mb-1 block" for="ds-model-analysis">分析模型</label>
              <input id="ds-model-analysis" v-model="keys['ai.deepseek.model_analysis']" class="input text-sm" placeholder="deepseek-chat" />
            </div>
          </div>
          <button class="btn btn-secondary btn-sm" @click="handleTestDeepseek" :disabled="testing">
            {{ testing ? '测试中...' : '测试连接' }}
          </button>
        </div>
        <!-- KD100 -->
        <div class="border-t pt-4 space-y-3">
          <h4 class="text-sm font-medium text-secondary">快递100</h4>
          <div class="grid md:grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-muted mb-1 block" for="kd-key">Key</label>
              <input id="kd-key" v-model="keys['api.kd100.key']" type="password" class="input text-sm" />
            </div>
            <div>
              <label class="text-xs text-muted mb-1 block" for="kd-customer">Customer</label>
              <input id="kd-customer" v-model="keys['api.kd100.customer']" class="input text-sm" />
            </div>
          </div>
        </div>
        <div class="flex justify-end">
          <button class="btn btn-primary btn-sm" @click="handleSaveKeys" :disabled="saving">保存密钥</button>
        </div>
      </div>
    </div>

    <!-- 2. 提示词模板 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.prompts = !sections.prompts">
        <h3 class="font-semibold flex items-center gap-2">
          <FileText :size="16" />
          提示词模板
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.prompts }" class="transition-transform" />
      </button>
      <div v-if="sections.prompts" class="mt-4 space-y-4">
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-xs text-muted" for="prompt-sql">SQL 生成提示词</label>
            <button class="text-xs text-primary" @click="aiConfig['ai.prompt.system'] = null">重置默认</button>
          </div>
          <textarea id="prompt-sql" v-model="aiConfig['ai.prompt.system']" class="input text-sm font-mono" rows="8" placeholder="留空使用默认提示词..." />
        </div>
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-xs text-muted" for="prompt-analysis">数据分析提示词</label>
            <button class="text-xs text-primary" @click="aiConfig['ai.prompt.analysis'] = null">重置默认</button>
          </div>
          <textarea id="prompt-analysis" v-model="aiConfig['ai.prompt.analysis']" class="input text-sm font-mono" rows="6" placeholder="留空使用默认提示词..." />
        </div>
        <div class="flex justify-end">
          <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存提示词</button>
        </div>
      </div>
    </div>

    <!-- 3. 业务词典 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.dict = !sections.dict">
        <h3 class="font-semibold flex items-center gap-2">
          <BookOpen :size="16" />
          业务词典
          <span class="text-xs text-muted">({{ (aiConfig['ai.business_dict'] || []).length }})</span>
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.dict }" class="transition-transform" />
      </button>
      <div v-if="sections.dict" class="mt-4">
        <div class="space-y-2">
          <div v-for="(item, idx) in (aiConfig['ai.business_dict'] || [])" :key="idx" class="flex gap-2 items-start">
            <input v-model="item.term" class="input text-sm w-32" placeholder="术语" />
            <input v-model="item.meaning" class="input text-sm flex-1" placeholder="SQL 含义" />
            <button class="btn btn-danger btn-sm" @click="removeItem('ai.business_dict', idx)">
              <Trash2 :size="14" />
            </button>
          </div>
        </div>
        <div class="flex justify-between mt-3">
          <div class="flex gap-2">
            <button class="btn btn-secondary btn-sm" @click="addDictItem">添加术语</button>
            <button class="btn btn-secondary btn-sm" @click="exportJson('ai.business_dict', '业务词典')">
              <Download :size="14" class="mr-1" />导出
            </button>
            <label class="btn btn-secondary btn-sm cursor-pointer">
              <Upload :size="14" class="mr-1" />导入
              <input type="file" accept=".json" class="hidden" @change="e => importJson(e, 'ai.business_dict', '业务词典', validateDictImport)" />
            </label>
          </div>
          <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存词典</button>
        </div>
      </div>
    </div>

    <!-- 4. 示例问答库 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.shots = !sections.shots">
        <h3 class="font-semibold flex items-center gap-2">
          <MessageSquare :size="16" />
          示例问答库
          <span class="text-xs text-muted">({{ (aiConfig['ai.few_shots'] || []).length }})</span>
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.shots }" class="transition-transform" />
      </button>
      <div v-if="sections.shots" class="mt-4">
        <div class="space-y-3">
          <div v-for="(item, idx) in (aiConfig['ai.few_shots'] || [])" :key="idx" class="bg-elevated p-3 rounded-lg">
            <div class="flex justify-between items-start mb-2">
              <span class="text-xs px-1.5 py-0.5 rounded" :class="item.source === 'feedback' ? 'bg-success-subtle text-success-emphasis' : 'bg-primary-muted text-primary'">
                {{ item.source === 'feedback' ? '收藏' : '手动' }}
              </span>
              <button class="text-error text-xs" @click="removeItem('ai.few_shots', idx)">删除</button>
            </div>
            <input v-model="item.question" class="input text-sm mb-2" placeholder="用户问题" />
            <textarea v-model="item.sql" class="input text-sm font-mono" rows="2" placeholder="SQL" />
          </div>
        </div>
        <div class="flex justify-between mt-3">
          <div class="flex gap-2">
            <button class="btn btn-secondary btn-sm" @click="addShotItem">添加示例</button>
            <button class="btn btn-secondary btn-sm" @click="exportJson('ai.few_shots', '示例问答库')">
              <Download :size="14" class="mr-1" />导出
            </button>
            <label class="btn btn-secondary btn-sm cursor-pointer">
              <Upload :size="14" class="mr-1" />导入
              <input type="file" accept=".json" class="hidden" @change="e => importJson(e, 'ai.few_shots', '示例问答库', validateShotsImport)" />
            </label>
          </div>
          <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存示例</button>
        </div>
      </div>
    </div>

    <!-- 5. 快捷问题 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.presets = !sections.presets">
        <h3 class="font-semibold flex items-center gap-2">
          <Zap :size="16" />
          快捷问题
          <span class="text-xs text-muted">({{ (aiConfig['ai.preset_queries'] || []).length }})</span>
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.presets }" class="transition-transform" />
      </button>
      <div v-if="sections.presets" class="mt-4">
        <div class="space-y-2">
          <div v-for="(item, idx) in (aiConfig['ai.preset_queries'] || [])" :key="idx" class="flex gap-2 items-start">
            <input v-model="item.display" class="input text-sm w-40" placeholder="显示文字" />
            <input :value="(item.keywords || []).join(', ')" @change="item.keywords = $event.target.value.split(',').map(s => s.trim()).filter(Boolean)" class="input text-sm w-40" placeholder="关键词（逗号分隔）" />
            <input v-model="item.sql" class="input text-sm flex-1 font-mono" placeholder="预置 SQL" />
            <button class="btn btn-danger btn-sm" @click="removeItem('ai.preset_queries', idx)">
              <Trash2 :size="14" />
            </button>
          </div>
        </div>
        <div class="flex justify-between mt-3">
          <div class="flex gap-2">
            <button class="btn btn-secondary btn-sm" @click="addPresetItem">添加问题</button>
            <button class="btn btn-secondary btn-sm" @click="exportJson('ai.preset_queries', '快捷问题')">
              <Download :size="14" class="mr-1" />导出
            </button>
            <label class="btn btn-secondary btn-sm cursor-pointer">
              <Upload :size="14" class="mr-1" />导入
              <input type="file" accept=".json" class="hidden" @change="e => importJson(e, 'ai.preset_queries', '快捷问题', validatePresetsImport)" />
            </label>
          </div>
          <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存问题</button>
        </div>
      </div>
    </div>

    <!-- 6. 同义词映射 -->
    <div class="card p-4">
      <button class="flex items-center justify-between w-full text-left" @click="sections.synonyms = !sections.synonyms">
        <h3 class="font-semibold flex items-center gap-2">
          <ArrowLeftRight :size="16" />
          同义词映射
          <span class="text-xs text-muted">({{ synonymRows.length }})</span>
        </h3>
        <ChevronDown :size="16" :class="{ 'rotate-180': sections.synonyms }" class="transition-transform" />
      </button>
      <div v-if="sections.synonyms" class="mt-4">
        <p class="text-xs text-muted mb-3">将用户口语化表达映射到标准业务术语，提升 AI 理解准确度</p>
        <div class="space-y-2">
          <div v-for="(row, idx) in synonymRows" :key="idx" class="flex gap-2 items-start">
            <input
              :value="row.term"
              @change="renameSynonymKey(idx, $event.target.value)"
              class="input text-sm w-32"
              placeholder="标准词"
            />
            <input
              :value="row.alts"
              @change="updateSynonymAlts(idx, $event.target.value)"
              class="input text-sm flex-1"
              placeholder="同义词（逗号分隔）"
            />
            <button class="btn btn-danger btn-sm" @click="deleteSynonym(idx)">
              <Trash2 :size="14" />
            </button>
          </div>
        </div>
        <div class="flex justify-between mt-3">
          <div class="flex gap-2">
            <button class="btn btn-secondary btn-sm" @click="addSynonym">添加映射</button>
            <button class="btn btn-secondary btn-sm" @click="exportJson('ai.synonyms', '同义词映射')">
              <Download :size="14" class="mr-1" />导出
            </button>
            <label class="btn btn-secondary btn-sm cursor-pointer">
              <Upload :size="14" class="mr-1" />导入
              <input type="file" accept=".json" class="hidden" @change="e => importJson(e, 'ai.synonyms', '同义词映射', validateSynonymsImport)" />
            </label>
          </div>
          <button class="btn btn-primary btn-sm" @click="handleSaveConfig" :disabled="saving">保存映射</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Key, ChevronDown, FileText, BookOpen, MessageSquare, Zap, Trash2, ArrowLeftRight, Download, Upload } from 'lucide-vue-next'
import { getApiKeys, updateApiKeys, testDeepseek, getAiConfig, updateAiConfig } from '../../../api/ai'
import { useAppStore } from '../../../stores/app'

const appStore = useAppStore()

const sections = reactive({ keys: true, prompts: false, dict: false, shots: false, presets: false, synonyms: false })
const keys = reactive({})
const aiConfig = reactive({})
const saving = ref(false)
const testing = ref(false)

// ===== 同义词：对象 <-> 行列表转换 =====

const synonymRows = computed(() => {
  const obj = aiConfig['ai.synonyms'] || {}
  return Object.entries(obj).map(([term, alts]) => ({
    term,
    alts: alts.join(', ')
  }))
})

const addSynonym = () => {
  if (!aiConfig['ai.synonyms']) aiConfig['ai.synonyms'] = {}
  // 生成一个不重复的临时 key
  let key = ''
  let i = 1
  do { key = `新术语${i++}` } while (aiConfig['ai.synonyms'][key] !== undefined)
  aiConfig['ai.synonyms'][key] = []
}

const renameSynonymKey = (idx, newKey) => {
  const trimmed = newKey.trim()
  if (!trimmed) return
  const obj = aiConfig['ai.synonyms'] || {}
  const entries = Object.entries(obj)
  if (idx < 0 || idx >= entries.length) return
  const [oldKey, alts] = entries[idx]
  if (oldKey === trimmed) return
  // 如果新 key 已存在且不是自身，阻止
  if (obj[trimmed] !== undefined) {
    appStore.showToast(`标准词 "${trimmed}" 已存在`, 'error')
    return
  }
  // 构建新对象以保持顺序
  const newObj = {}
  for (const [k, v] of entries) {
    if (k === oldKey) {
      newObj[trimmed] = alts
    } else {
      newObj[k] = v
    }
  }
  aiConfig['ai.synonyms'] = newObj
}

const updateSynonymAlts = (idx, value) => {
  const obj = aiConfig['ai.synonyms'] || {}
  const entries = Object.entries(obj)
  if (idx < 0 || idx >= entries.length) return
  const [key] = entries[idx]
  obj[key] = value.split(',').map(s => s.trim()).filter(Boolean)
}

const deleteSynonym = (idx) => {
  const obj = aiConfig['ai.synonyms'] || {}
  const entries = Object.entries(obj)
  if (idx < 0 || idx >= entries.length) return
  const [key] = entries[idx]
  delete obj[key]
  // 触发响应式更新
  aiConfig['ai.synonyms'] = { ...obj }
}

// ===== 数据加载 =====

const loadKeys = async () => {
  try {
    const { data } = await getApiKeys()
    Object.assign(keys, data)
  } catch (e) {
    appStore.showToast('加载 API 密钥失败', 'error')
  }
}

const loadConfig = async () => {
  try {
    const { data } = await getAiConfig()
    Object.assign(aiConfig, data)
  } catch (e) {
    appStore.showToast('加载 AI 配置失败', 'error')
  }
}

// ===== 保存/测试 =====

const handleSaveKeys = async () => {
  if (saving.value) return
  saving.value = true
  try {
    await updateApiKeys(keys)
    appStore.showToast('密钥已保存')
    await loadKeys()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

const handleTestDeepseek = async () => {
  testing.value = true
  try {
    const { data } = await testDeepseek()
    appStore.showToast(data.message, data.success ? 'success' : 'error')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '测试失败', 'error')
  } finally {
    testing.value = false
  }
}

const handleSaveConfig = async () => {
  if (saving.value) return
  saving.value = true
  try {
    await updateAiConfig(aiConfig)
    appStore.showToast('配置已保存')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

// ===== 列表项增删 =====

const addDictItem = () => {
  if (!aiConfig['ai.business_dict']) aiConfig['ai.business_dict'] = []
  aiConfig['ai.business_dict'].push({ term: '', meaning: '' })
}

const addShotItem = () => {
  if (!aiConfig['ai.few_shots']) aiConfig['ai.few_shots'] = []
  aiConfig['ai.few_shots'].push({ question: '', sql: '', source: 'manual' })
}

const addPresetItem = () => {
  if (!aiConfig['ai.preset_queries']) aiConfig['ai.preset_queries'] = []
  aiConfig['ai.preset_queries'].push({ display: '', keywords: [], sql: '' })
}

const removeItem = (key, idx) => {
  if (aiConfig[key]) aiConfig[key].splice(idx, 1)
}

// ===== JSON 导入/导出 =====

const exportJson = (configKey, label) => {
  const data = aiConfig[configKey]
  if (!data) {
    appStore.showToast(`${label}为空，无内容可导出`, 'error')
    return
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${configKey.replace(/\./g, '_')}.json`
  a.click()
  URL.revokeObjectURL(url)
  appStore.showToast(`${label}已导出`)
}

const importJson = (event, configKey, label, validator) => {
  const file = event.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const parsed = JSON.parse(e.target.result)
      const error = validator(parsed)
      if (error) {
        appStore.showToast(`${label}导入失败: ${error}`, 'error')
        return
      }
      aiConfig[configKey] = parsed
      appStore.showToast(`${label}已导入，请点击保存以生效`)
    } catch {
      appStore.showToast(`${label}导入失败: JSON 格式无效`, 'error')
    }
  }
  reader.readAsText(file)
  // 重置 file input 以允许重复导入同一文件
  event.target.value = ''
}

// ===== 格式校验 =====

const validateDictImport = (data) => {
  if (!Array.isArray(data)) return '数据必须是数组格式'
  for (let i = 0; i < data.length; i++) {
    const item = data[i]
    if (typeof item !== 'object' || item === null) return `第 ${i + 1} 项不是对象`
    if (typeof item.term !== 'string') return `第 ${i + 1} 项缺少 term 字段`
    if (typeof item.meaning !== 'string') return `第 ${i + 1} 项缺少 meaning 字段`
  }
  return null
}

const validateShotsImport = (data) => {
  if (!Array.isArray(data)) return '数据必须是数组格式'
  for (let i = 0; i < data.length; i++) {
    const item = data[i]
    if (typeof item !== 'object' || item === null) return `第 ${i + 1} 项不是对象`
    if (typeof item.question !== 'string') return `第 ${i + 1} 项缺少 question 字段`
    if (typeof item.sql !== 'string') return `第 ${i + 1} 项缺少 sql 字段`
  }
  return null
}

const validatePresetsImport = (data) => {
  if (!Array.isArray(data)) return '数据必须是数组格式'
  for (let i = 0; i < data.length; i++) {
    const item = data[i]
    if (typeof item !== 'object' || item === null) return `第 ${i + 1} 项不是对象`
    if (typeof item.display !== 'string') return `第 ${i + 1} 项缺少 display 字段`
    if (typeof item.sql !== 'string') return `第 ${i + 1} 项缺少 sql 字段`
  }
  return null
}

const validateSynonymsImport = (data) => {
  if (typeof data !== 'object' || data === null || Array.isArray(data)) return '数据必须是对象格式 { "标准词": ["同义词1", ...] }'
  for (const [key, val] of Object.entries(data)) {
    if (!Array.isArray(val)) return `"${key}" 的值必须是数组`
    for (let i = 0; i < val.length; i++) {
      if (typeof val[i] !== 'string') return `"${key}" 的第 ${i + 1} 个同义词必须是字符串`
    }
  }
  return null
}

onMounted(() => {
  loadKeys()
  loadConfig()
})
</script>
