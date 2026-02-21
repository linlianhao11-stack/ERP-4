<template>
  <div class="min-h-screen flex items-center justify-center p-4 bg-[#fbfbfd]">
    <div class="w-full max-w-[400px]">
      <!-- Logo & Brand -->
      <div class="text-center mb-10">
        <div class="w-14 h-14 bg-[#1d1d1f] rounded-[16px] mx-auto mb-5 flex items-center justify-center shadow-lg">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12l4 6-10 13L2 9z"/></svg>
        </div>
        <h1 class="text-[22px] font-semibold text-[#1d1d1f] tracking-tight">ERP System</h1>
        <p class="text-[13px] text-[#86868b] mt-1">企业资源管理平台</p>
      </div>

      <!-- Card -->
      <div class="bg-white rounded-[20px] border border-[#e8e8ed] shadow-sm p-8">
        <!-- 强制改密表单 -->
        <form v-if="showChangePwd" @submit.prevent="doChangePassword" class="space-y-5">
          <div class="flex items-start gap-3 p-3.5 bg-[#fff8e1] rounded-xl border border-[#ffe082]">
            <Lock :size="16" :stroke-width="1.5" class="text-[#ff9f0a] mt-0.5 shrink-0" />
            <span class="text-[13px] text-[#1d1d1f] leading-relaxed">首次登录，请修改默认密码后继续使用</span>
          </div>
          <div>
            <label class="label">新密码</label>
            <input v-model="pwdForm.new_password" type="password" class="input" placeholder="请输入新密码（至少6位）">
          </div>
          <div>
            <label class="label">确认新密码</label>
            <input v-model="pwdForm.confirm_password" type="password" class="input" placeholder="请再次输入新密码">
          </div>
          <button type="submit" class="btn btn-primary w-full h-11 text-[15px]" :disabled="loading">
            {{ loading ? '修改中...' : '修改密码并进入系统' }}
          </button>
        </form>

        <!-- 登录表单 -->
        <form v-else @submit.prevent="doLogin" class="space-y-5">
          <div>
            <label class="label">用户名</label>
            <input v-model="form.username" class="input" placeholder="请输入用户名" autofocus>
          </div>
          <div>
            <label class="label">密码</label>
            <input v-model="form.password" type="password" class="input" placeholder="请输入密码">
          </div>
          <button type="submit" class="btn btn-primary w-full h-11 text-[15px]" :disabled="loading">
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </form>
      </div>

      <!-- Footer -->
      <p class="text-center text-[11px] text-[#86868b] mt-8">&copy; {{ new Date().getFullYear() }} ERP System</p>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useAppStore } from '../stores/app'
import { login, changePassword } from '../api/auth'
import { Lock } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const form = reactive({ username: '', password: '' })
const pwdForm = reactive({ new_password: '', confirm_password: '' })
const loading = ref(false)
const showChangePwd = ref(false)
// 暂存登录时的原始密码，用于改密接口的 old_password
let tempOldPassword = ''

const doLogin = async () => {
  if (!form.username || !form.password) {
    appStore.showToast('请填写用户名和密码', 'error')
    return
  }
  loading.value = true
  try {
    const { data } = await login(form)
    authStore.setAuth(data.access_token, data.user)
    localStorage.setItem('erp_last_active', Date.now().toString())
    if (data.must_change_password) {
      tempOldPassword = form.password
      showChangePwd.value = true
      appStore.showToast('请先修改默认密码', 'warning')
    } else {
      router.push('/dashboard')
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '登录失败', 'error')
  } finally {
    loading.value = false
  }
}

const doChangePassword = async () => {
  if (!pwdForm.new_password || pwdForm.new_password.length < 6) {
    appStore.showToast('新密码长度不能少于6位', 'error')
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    appStore.showToast('两次输入的密码不一致', 'error')
    return
  }
  if (pwdForm.new_password === tempOldPassword) {
    appStore.showToast('新密码不能与原密码相同', 'error')
    return
  }
  loading.value = true
  try {
    await changePassword({ old_password: tempOldPassword, new_password: pwdForm.new_password })
    appStore.showToast('密码修改成功')
    showChangePwd.value = false
    tempOldPassword = ''
    router.push('/dashboard')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '密码修改失败', 'error')
  } finally {
    loading.value = false
  }
}
</script>
