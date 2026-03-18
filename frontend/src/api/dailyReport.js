import api from './index'

export const getDailyReportConfig = () => api.get('/daily-report/config')
export const updateDailyReportConfig = (data) => api.put('/daily-report/config', data)
export const testDailyReportEmail = () => api.post('/daily-report/test')
export const sendDailyReportNow = () => api.post('/daily-report/send-now')
