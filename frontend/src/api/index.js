import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
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
export const getPositionChart = (code, period = 'daily') => api.get(`/positions/${code}/chart`, { params: { period } })
export const getBaselineComparison = (code, baselineCode, period = 'daily') => api.get(`/positions/${code}/baseline`, { params: { baseline_code: baselineCode, period } })
export const updatePositionCategory = (code, category) => api.patch(`/positions/${code}/category`, { category })
export const updatePositionLinkedCode = (code, linkedCode) => api.patch(`/positions/${code}/linked-code`, { linked_code: linkedCode })
export const suggestLinkedEtf = (code) => api.get(`/positions/${code}/suggest-linked`)
export const getCategoryStats = () => api.get('/positions/categories/stats')
export const getClosedPositions = () => api.get('/positions/closed-positions')

// --- 基线配置 ---
export const addBaselineConfig = (data) => api.post('/positions/baseline-config', data)
export const getBaselineConfig = (etfCode) => api.get(`/positions/baseline-config/${etfCode}`)

export const validateCode = (code) => api.get(`/quotes/validate/${code}`)
export const getFundInfo = (code, date) => api.get(`/quotes/fund-info/${code}`, { params: { date } })

// --- 行情同步 ---
export const syncQuotes = () => api.post('/quotes/sync')
export const getSyncProgress = (taskId) => api.get(`/quotes/sync-progress/${taskId}`)
export const getLastSync = () => api.get('/quotes/last-sync')

// --- 分红 ---
export const detectDividends = (code) => api.get('/quotes/dividends', { params: { code } })
export const confirmDividends = (dividends) => api.post('/quotes/dividends/confirm', dividends)

// --- 统计 ---
export const getMonthlyStats = (year) => api.get('/stats/monthly', { params: { year } })
export const getYearlyStats = () => api.get('/stats/yearly')
export const getMonthlyPositionDetails = (year, month) => api.get(`/stats/monthly/${year}/${month}/positions`)
export const getYearlyPositionDetails = (year) => api.get(`/stats/yearly/${year}/positions`)

export default api

// --- 历史行情分析 ---
export const analysisCacheSync = (data) => api.post('/analysis/cache/sync', data)
export const analysisCacheSyncBatch = (data) => api.post('/analysis/cache/sync-batch', data)
export const analysisCacheSyncL1 = () => api.post('/analysis/cache/sync-l1')
export const analysisCacheSyncL2 = () => api.post('/analysis/cache/sync-l2')
export const analysisCacheStatus = () => api.get('/analysis/cache/status')
export const analysisCacheProgress = () => api.get('/analysis/cache/progress')
export const analysisPearson = (data) => api.post('/analysis/correlation/pearson', data)
export const analysisCorrMatrix = (data) => api.post('/analysis/correlation/matrix', data)
export const analysisCCF = (data) => api.post('/analysis/correlation/ccf', data)
export const analysisGranger = (data) => api.post('/analysis/correlation/granger', data)
export const analysisSeasonality = (data) => api.post('/analysis/pattern/seasonality', data)
export const analysisMomentumReversal = (data) => api.post('/analysis/pattern/momentum-reversal', data)
export const analysisMeanReversion = (data) => api.post('/analysis/pattern/mean-reversion', data)
export const analysisQuickReport = (data) => api.post('/analysis/report/quick', data)

// --- 基础数据查看 ---
export const analysisDataOHLCV = (code, limit = 100) => api.get('/analysis/data/ohlcv', { params: { code, limit } })
export const analysisDataDistribution = (code, field = 'pct_change', bins = 20) => api.get('/analysis/data/distribution', { params: { code, field, bins } })
export const analysisVolumeAnalysis = (code, limit = 100) => api.get('/analysis/data/volume-analysis', { params: { code, limit } })
export const analysisDataStats = (code) => api.get('/analysis/data/stats', { params: { code } })
