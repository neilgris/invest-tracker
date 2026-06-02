import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 长耗时同步操作专用实例，不设超时
const syncApi = axios.create({
  baseURL: '/api',
  timeout: 0,
})

// --- 交易 ---
export const getTrades = (params) => api.get('/trades', { params })
export const createTrade = (data) => api.post('/trades', data)
export const updateTrade = (id, data) => api.put(`/trades/${id}`, data)
export const deleteTrade = (id) => api.delete(`/trades/${id}`)

// --- 持仓 ---
export const getPositions = () => api.get('/positions')
export const getOverview = () => api.get('/positions/overview')
export const getPositionDetail = (code) => api.get(`/positions/${code}`)
export const getPositionChart = (code, period = 'daily', baselineCode = '') => api.get(`/positions/${code}/chart`, { params: { period, baseline: baselineCode || undefined } })
export const updatePositionCategory = (code, category) => api.patch(`/positions/${code}/category`, { category })
export const updatePositionLinkedCode = (code, linkedCode, linkedName = null, linkedShortName = null) => api.patch(`/positions/${code}/linked-code`, {
  linked_code: linkedCode,
  linked_name: linkedName,
  linked_short_name: linkedShortName
})
export const suggestLinkedEtf = (code) => api.get(`/positions/${code}/suggest-linked`)
export const getCategoryStats = () => api.get('/positions/categories/stats')
export const getClosedPositions = () => api.get('/positions/closed-positions')

export const validateCode = (code) => api.get(`/quotes/validate/${code}`)
export const getFundInfo = (code, date) => api.get(`/quotes/fund-info/${code}`, { params: { date } })

// --- 行情同步 ---
export const syncQuotes = () => syncApi.post('/quotes/sync')
export const getSyncProgress = (taskId) => api.get(`/quotes/sync-progress/${taskId}`)
export const getLastSync = () => api.get('/quotes/last-sync')

// --- 分红 ---
export const detectDividends = (code) => api.get('/quotes/dividends', { params: { code } })
export const confirmDividends = (dividends) => api.post('/quotes/dividends/confirm', dividends)

// --- PE数据 ---
export const getEtfPeData = (etfCode) => api.get(`/quotes/pe/${etfCode}`)
export const getIndexPeData = (indexCode) => api.get(`/quotes/pe/index/${indexCode}`)

// --- 统计 ---
export const getMonthlyStats = (year) => api.get('/stats/monthly', { params: { year } })
export const getYearlyStats = () => api.get('/stats/yearly')
export const getMonthlyPositionDetails = (year, month) => api.get(`/stats/monthly/${year}/${month}/positions`)
export const getYearlyPositionDetails = (year) => api.get(`/stats/yearly/${year}/positions`)

export default api

// --- 历史行情分析（数据缓存 & 查看）---
export const analysisCacheSync = (data) => syncApi.post('/analysis/cache/sync', data)
export const analysisCacheSyncBatch = (data) => syncApi.post('/analysis/cache/sync-batch', data)
export const analysisCacheSyncL1 = () => syncApi.post('/analysis/cache/sync-l1')
export const analysisCacheSyncL2 = () => syncApi.post('/analysis/cache/sync-l2')
export const analysisCacheSyncL6 = () => syncApi.post('/analysis/cache/sync-l6')
export const analysisCacheSyncL6C = () => syncApi.post('/analysis/cache/sync-l6c')
export const analysisCacheSyncL3Theme = () => syncApi.post('/analysis/cache/sync-l3-theme')
export const analysisCacheStatus = () => api.get('/analysis/cache/status')
export const analysisCacheProgress = () => syncApi.get('/analysis/cache/progress')  // 同步期间后端忙，不设超时
export const analysisDataOHLCV = (code, limit = 100) => api.get('/analysis/data/ohlcv', { params: { code, limit } })
export const analysisDataStats = (code) => api.get('/analysis/data/stats', { params: { code } })

// --- 参数寻优 ---
export const analysisGridSearch = (data) => syncApi.post('/analysis/backtest/grid-search', data)

// --- 回测历史记录 ---
export const saveBacktestRecord = (data) => api.post('/backtest-records', data)
export const listBacktestRecords = (code) => api.get('/backtest-records', { params: code ? { code } : {} })
export const listBacktestCodes = () => api.get('/backtest-records/codes')
export const updateBacktestNotes = (id, notes) => api.patch(`/backtest-records/${id}/notes`, { notes })
export const deleteBacktestRecord = (id) => api.delete(`/backtest-records/${id}`)
