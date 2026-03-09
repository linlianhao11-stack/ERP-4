<template>
  <div class="login-page">
    <!-- 左侧品牌区（背景图 + 文案） -->
    <div class="login-brand">
      <div class="login-brand-content">
        <div class="brand-mark">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12l4 6-10 13L2 9z"/></svg>
        </div>
        <h1 class="brand-headline">精准掌控<br>每一笔账</h1>
        <p class="brand-tagline">面向中小贸易企业的一体化资源管理平台。销售、库存、财务、会计，一处搞定。</p>
        <div class="brand-stats">
          <div><div class="stat-val">38</div><div class="stat-label">核心数据表</div></div>
          <div><div class="stat-val">12</div><div class="stat-label">业务模块</div></div>
          <div><div class="stat-val">5</div><div class="stat-label">财务报表</div></div>
        </div>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="login-form-panel">
      <div class="login-form-inner">
        <img src="/logo.png" alt="CHEERIN 启领科技" class="login-logo">
        <h2 class="form-greeting">欢迎回来</h2>
        <p class="form-subtitle">登录以继续访问您的工作台</p>

        <!-- 强制改密表单 -->
        <form v-if="showChangePwd" @submit.prevent="doChangePassword" class="space-y-4">
          <div class="flex items-start gap-3 p-3.5 bg-warning-subtle rounded-xl border border-warning">
            <Lock :size="16" :stroke-width="1.5" class="text-warning mt-0.5 shrink-0" />
            <span class="text-[13px] text-foreground leading-relaxed">首次登录，请修改默认密码后继续使用</span>
          </div>
          <div>
            <label class="label" for="new-pwd">新密码</label>
            <div class="input-with-icon">
              <Lock :size="16" :stroke-width="1.5" class="input-icon-el" />
              <input id="new-pwd" v-model="pwdForm.new_password" type="password" class="input input-icon-pad" placeholder="请输入新密码（至少6位）">
            </div>
          </div>
          <div>
            <label class="label" for="confirm-pwd">确认新密码</label>
            <div class="input-with-icon">
              <Lock :size="16" :stroke-width="1.5" class="input-icon-el" />
              <input id="confirm-pwd" v-model="pwdForm.confirm_password" type="password" class="input input-icon-pad" placeholder="请再次输入新密码">
            </div>
          </div>
          <button type="submit" class="login-btn" :disabled="loading">
            {{ loading ? '修改中...' : '修改密码并进入系统' }}
          </button>
        </form>

        <!-- 登录表单 -->
        <form v-else @submit.prevent="doLogin" class="space-y-4">
          <div>
            <label class="label" for="username">用户名</label>
            <div class="input-with-icon">
              <User :size="16" :stroke-width="1.5" class="input-icon-el" />
              <input id="username" v-model="form.username" class="input input-icon-pad" placeholder="请输入用户名" autofocus>
            </div>
          </div>
          <div>
            <label class="label" for="password">密码</label>
            <div class="input-with-icon">
              <Lock :size="16" :stroke-width="1.5" class="input-icon-el" />
              <input id="password" v-model="form.password" type="password" class="input input-icon-pad" placeholder="请输入密码">
            </div>
          </div>
          <button type="submit" class="login-btn" :disabled="loading">
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </form>

        <div class="login-footer-text">&copy; {{ new Date().getFullYear() }} 启领科技 · ERP System</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useAppStore } from '../stores/app'
import { login, changePassword } from '../api/auth'
import { Lock, User } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()

const form = reactive({ username: '', password: '' })
const pwdForm = reactive({ new_password: '', confirm_password: '' })
const loading = ref(false)
const showChangePwd = ref(false)
// 暂存登录时的原始密码，用于改密接口的 old_password
let tempOldPassword = ''

onUnmounted(() => { tempOldPassword = '' })

const doLogin = async () => {
  if (!form.username || !form.password) {
    appStore.showToast('请填写用户名和密码', 'error')
    return
  }
  loading.value = true
  try {
    const { data } = await login(form)
    if (data.must_change_password) {
      // 仅将 token 存入 localStorage 供改密接口使用，不设置 authStore.user
      // 原因：一旦 authStore.user 非空，App.vue 会切换模板分支，销毁当前组件实例，
      // 导致 showChangePwd 状态丢失，改密表单无法显示
      localStorage.setItem('erp_token', data.access_token)
      localStorage.setItem('erp_last_active', Date.now().toString())
      tempOldPassword = form.password
      showChangePwd.value = true
      appStore.showToast('请先修改默认密码', 'warning')
    } else {
      authStore.setAuth(data.access_token, data.user)
      localStorage.setItem('erp_last_active', Date.now().toString())
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
    const { data } = await changePassword({ old_password: tempOldPassword, new_password: pwdForm.new_password })
    appStore.showToast('密码修改成功')
    tempOldPassword = ''
    // 后端改密后会使旧 token 失效并返回新 token，用新 token 完成登录
    authStore.setAuth(data.access_token, data.user)
    localStorage.setItem('erp_last_active', Date.now().toString())
    router.push('/dashboard')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '密码修改失败', 'error')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
}

/* === 左侧品牌区 === */
.login-brand {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: oklch(0.10 0.02 250);
  display: none;
}
@media (min-width: 768px) {
  .login-brand { display: flex; }
}
.login-brand::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image: url("https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1400&q=85");
  background-size: cover;
  background-position: center 40%;
  filter: saturate(0.3) brightness(0.9);
}
.login-brand::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to right,
    oklch(0.06 0.03 250 / 0.70) 0%,
    oklch(0.08 0.02 250 / 0.45) 40%,
    oklch(0.06 0.02 250 / 0.60) 70%,
    oklch(0.05 0.02 250 / 0.85) 100%
  );
}
.login-brand-content {
  position: relative;
  z-index: 1;
  padding: 48px 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 480px;
}
.brand-mark {
  width: 40px; height: 40px;
  border: 2px solid oklch(0.93 0 0 / 0.3);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 32px;
  color: oklch(0.95 0 0);
  backdrop-filter: blur(8px);
  background: oklch(1 0 0 / 0.08);
}
.brand-headline {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.04em;
  line-height: 1.1;
  margin-bottom: 12px;
  color: oklch(0.97 0 0);
  text-shadow: 0 2px 16px oklch(0 0 0 / 0.3);
}
.brand-tagline {
  font-size: 14px;
  color: oklch(0.70 0.008 250);
  line-height: 1.6;
  max-width: 280px;
}
.brand-stats {
  display: flex;
  gap: 32px;
  margin-top: 40px;
  padding-top: 24px;
  border-top: 1px solid oklch(0.95 0 0 / 0.12);
}
.stat-val {
  font-size: 20px;
  font-weight: 700;
  font-family: var(--font-mono, 'Geist Mono', monospace);
  color: var(--primary);
  letter-spacing: -0.02em;
}
.stat-label {
  font-size: 11px;
  color: oklch(0.55 0.008 250);
  margin-top: 2px;
}

/* === 右侧表单区 === */
.login-form-panel {
  width: 100%;
  max-width: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 32px;
  background: var(--surface);
  box-shadow: -8px 0 32px oklch(0 0 0 / 0.08);
}
@media (max-width: 767px) {
  .login-form-panel {
    max-width: 100%;
    box-shadow: none;
  }
}
.login-form-inner {
  width: 100%;
  max-width: 340px;
}
.login-logo {
  height: 36px;
  width: auto;
  object-fit: contain;
  display: block;
  margin-bottom: 20px;
}
.form-greeting {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.03em;
  margin-bottom: 4px;
  text-align: left;
}
.form-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 28px;
  text-align: left;
}

/* 带图标的输入框 */
.input-with-icon {
  position: relative;
}
.input-icon-el {
  position: absolute;
  left: 13px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}
.input-icon-pad {
  padding-left: 40px !important;
}

/* 登录按钮 */
.login-btn {
  width: 100%;
  height: 46px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 12px;
  border: none;
  background: var(--primary);
  color: var(--on-primary);
  cursor: pointer;
  font-family: inherit;
  letter-spacing: -0.01em;
  transition: all 0.2s var(--ease-out-expo, cubic-bezier(0.16, 1, 0.3, 1));
  margin-top: 8px;
}
.login-btn:hover {
  background: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px var(--primary-ring);
}
.login-btn:active {
  transform: translateY(0) scale(0.98);
}
.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.login-footer-text {
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}
</style>
