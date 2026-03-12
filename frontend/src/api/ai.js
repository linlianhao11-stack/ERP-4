import api from './index'

// AI 聊天
export const aiChat = (data) => api.post('/ai/chat', data, { timeout: 180000 })

// AI 状态检查
export const getAiStatus = () => api.get('/ai/status')

// 导出 Excel
export const aiExport = (data) => api.post('/ai/chat/export', data, { responseType: 'blob' })

// 反馈
export const aiFeedback = (data) => api.post('/ai/chat/feedback', data)

// API 密钥管理
export const getApiKeys = () => api.get('/api-keys')
export const updateApiKeys = (data) => api.put('/api-keys', data)
export const testDeepseek = () => api.post('/api-keys/test-deepseek')

// AI 配置管理
export const getAiConfig = () => api.get('/api-keys/ai-config')
export const updateAiConfig = (data) => api.put('/api-keys/ai-config', data)
