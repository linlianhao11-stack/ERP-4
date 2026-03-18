<template>
  <div class="card p-4 mt-4">
    <h3 class="font-semibold mb-3 text-sm">日报邮件</h3>
    <div class="space-y-3">
      <!-- 启用开关 -->
      <label class="flex items-center gap-2 cursor-pointer text-sm" for="dr-enabled">
        <input id="dr-enabled" type="checkbox" v-model="form.enabled" class="w-4 h-4" @change="save">
        <span>启用每日自动发送</span>
      </label>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="label text-xs" for="dr-time">发送时间</label>
          <input id="dr-time" type="time" v-model="form.send_time" class="input text-sm" @change="save">
        </div>
        <div>
          <label class="label text-xs" for="dr-from-name">发件人名称</label>
          <input id="dr-from-name" v-model="form.from_name" class="input text-sm" placeholder="ERP系统" @change="save">
        </div>
      </div>

      <div>
        <label class="label text-xs" for="dr-recipients">收件人（每行一个邮箱）</label>
        <textarea id="dr-recipients" v-model="recipientsText" class="input text-sm" rows="3" placeholder="admin@company.com" @change="saveRecipients"></textarea>
      </div>

      <!-- SMTP 配置 -->
      <details class="border rounded-lg">
        <summary class="px-3 py-2 text-xs font-medium text-secondary cursor-pointer bg-elevated rounded-lg">SMTP 配置</summary>
        <div class="p-3 space-y-2">
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="label text-xs" for="dr-smtp-host">SMTP 服务器</label>
              <input id="dr-smtp-host" v-model="form.smtp_host" class="input text-sm" placeholder="smtp.company.com" @change="save">
            </div>
            <div>
              <label class="label text-xs" for="dr-smtp-port">端口</label>
              <input id="dr-smtp-port" type="number" v-model.number="form.smtp_port" class="input text-sm" placeholder="465" @change="save">
            </div>
          </div>
          <div>
            <label class="label text-xs" for="dr-smtp-user">用户名</label>
            <input id="dr-smtp-user" v-model="form.smtp_user" class="input text-sm" @change="save">
          </div>
          <div>
            <label class="label text-xs" for="dr-smtp-pwd">密码</label>
            <input id="dr-smtp-pwd" type="password" v-model="form.smtp_password" class="input text-sm" :placeholder="passwordSet ? '已设置（留空不修改）' : '请输入'" @change="save">
          </div>
          <div>
            <label class="label text-xs" for="dr-from-email">发件邮箱</label>
            <input id="dr-from-email" v-model="form.from_email" class="input text-sm" placeholder="noreply@company.com" @change="save">
          </div>
        </div>
      </details>

      <!-- 操作按钮 -->
      <div class="flex gap-2 pt-2">
        <button @click="testSend" :disabled="testing" class="btn btn-secondary btn-sm text-xs">
          {{ testing ? '发送中...' : '测试发送' }}
        </button>
        <button @click="sendNow" :disabled="sending" class="btn btn-primary btn-sm text-xs">
          {{ sending ? '生成中...' : '立即发送日报' }}
        </button>
        <span v-if="lastSentDate" class="text-xs text-muted self-center ml-2">上次发送: {{ lastSentDate }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../../../stores/app'
import { getDailyReportConfig, updateDailyReportConfig, testDailyReportEmail, sendDailyReportNow } from '../../../api/dailyReport'

const appStore = useAppStore()

const form = ref({
  enabled: false,
  send_time: '21:00',
  recipients: [],
  smtp_host: '',
  smtp_port: 465,
  smtp_user: '',
  smtp_password: null,
  from_email: '',
  from_name: 'ERP系统',
})
const recipientsText = ref('')
const passwordSet = ref(false)
const lastSentDate = ref('')
const testing = ref(false)
const sending = ref(false)

const load = async () => {
  try {
    const { data } = await getDailyReportConfig()
    form.value = { ...data, smtp_password: null }
    recipientsText.value = (data.recipients || []).join('\n')
    passwordSet.value = data.smtp_password_set
    lastSentDate.value = data.last_sent_date || ''
  } catch {}
}

const save = async () => {
  try {
    const payload = { ...form.value }
    if (!payload.smtp_password) payload.smtp_password = null
    await updateDailyReportConfig(payload)
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  }
}

const saveRecipients = async () => {
  form.value.recipients = recipientsText.value.split('\n').map(s => s.trim()).filter(Boolean)
  await save()
}

const testSend = async () => {
  testing.value = true
  try {
    const { data } = await testDailyReportEmail()
    appStore.showToast(data.message || '测试邮件已发送')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '发送失败', 'error')
  } finally {
    testing.value = false
  }
}

const sendNow = async () => {
  sending.value = true
  try {
    const { data } = await sendDailyReportNow()
    appStore.showToast(data.message || '日报已发送')
    await load()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '发送失败', 'error')
  } finally {
    sending.value = false
  }
}

onMounted(load)
</script>
