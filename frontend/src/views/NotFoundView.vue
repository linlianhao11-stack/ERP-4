<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-[var(--bg)]">
    <div class="text-center space-y-4">
      <h1 class="text-6xl font-bold text-[var(--text-muted)] tracking-tight">404</h1>
      <p class="text-lg text-[var(--text-secondary)]">页面不存在</p>
      <button class="btn btn-primary" @click="router.push('/dashboard')">
        返回首页
      </button>
    </div>
  </div>
</template>
