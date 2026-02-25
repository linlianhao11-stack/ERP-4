import api from './index'

export const login = (data) => api.post('/auth/login', data)
export const getMe = () => api.get('/auth/me')
export const changePassword = (data) => api.post('/auth/change-password', data)
export const logoutApi = () => api.post('/auth/logout')
