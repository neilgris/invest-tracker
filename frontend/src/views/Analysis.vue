<template>
  <div>
    <el-tabs v-model="activeTab" type="border-card" @tab-click="handleTabClick">
      <!-- Tab 1: 数据缓存管理 -->
      <el-tab-pane label="数据缓存" name="cache">
        <el-row :gutter="20">
          <el-col :span="16">
            <el-card shadow="hover" style="margin-bottom: 20px">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>缓存概览</span>
                  <el-button type="primary" size="small" @click="loadCacheStatus" :loading="loading.cache">刷新</el-button>
                </div>
              </template>
              <el-row :gutter="20">
                <el-col :span="6">
                  <div class="stat-box">
                    <div class="stat-num">{{ cacheStatus.total_assets || 0 }}</div>
                    <div class="stat-label">资产总数</div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="stat-box">
                    <div class="stat-num">{{ cacheStatus.cached_assets || 0 }}</div>
                    <div class="stat-label">已缓存</div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="stat-box">
                    <div class="stat-num">{{ cacheStatus.total_quotes?.toLocaleString() || 0 }}</div>
                    <div class="stat-label">行情条数</div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div class="stat-box">
                    <div class="stat-num">{{ Object.keys(cacheStatus.date_ranges || {}).length }}</div>
                    <div class="stat-label">资产种类</div>
                  </div>
                </el-col>
              </el-row>
            </el-card>

            <el-card shadow="hover">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>数据同步</span>
                  <div>
                    <el-button type="primary" size="small" @click="syncL1" :loading="loading.syncL1">同步L1宽基</el-button>
                    <el-button type="success" size="small" @click="syncL2" :loading="loading.syncL2">同步L2行业</el-button>
                    <el-button type="info" size="small" @click="syncL3Theme" :loading="loading.syncL3Theme">同步L3主题指数</el-button>
                    <el-button type="warning" size="small" @click="syncL6" :loading="loading.syncL6">同步L6国际大宗</el-button>
                    <el-button type="danger" size="small" @click="syncL6C" :loading="loading.syncL6C">同步L6C国内大宗</el-button>
                  </div>
                </div>
              </template>
              <el-form :inline="true">
                <el-form-item label="资产代码">
                  <el-input v-model="syncForm.code" placeholder="如: 000300" style="width: 120px" />
                </el-form-item>
                <el-form-item label="类型">
                  <el-select v-model="syncForm.asset_type" style="width: 140px">
                    <el-option label="指数" value="index" />
                    <el-option label="行业板块" value="sector_industry" />
                    <el-option label="概念板块" value="sector_concept" />
                    <el-option label="ETF" value="etf" />
                    <el-option label="个股" value="stock" />
                    <el-option label="大宗商品" value="commodity" />
                  </el-select>
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="syncSingle" :loading="loading.syncSingle">同步</el-button>
                </el-form-item>
              </el-form>
              <el-divider />
              <!-- 同步进度显示 -->
              <div v-if="syncProgress.active" style="margin-bottom: 15px">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px">
                  <span style="font-size: 13px; color: #409eff; font-weight: bold">{{ syncProgress.task }}</span>
                  <span style="font-size: 12px; color: #909399">{{ syncProgress.current }}/{{ syncProgress.total }}</span>
                </div>
                <el-progress :percentage="Math.round((syncProgress.current / syncProgress.total) * 100)" :stroke-width="8" />
                <div style="font-size: 12px; color: #606266; margin-top: 5px">{{ syncProgress.message }}</div>
              </div>
              <div style="color: #909399; font-size: 12px">
                <p>L1: 7个宽基指数(上证/深证/沪深300/中证500/中证1000/创业板/科创50)</p>
                <p>L2: ~90个行业板块 | L3主题: 持仓关联指数 | L3概念: 概念板块 | L4: ETF | L5: 个股 | L6: 国际大宗商品</p>
              </div>
            </el-card>
          </el-col>

          <el-col :span="8">
            <el-card shadow="hover">
              <template #header><span>缓存资产列表</span></template>
              <el-table :data="cacheAssets" size="small" height="400" v-loading="loading.cache">
                <el-table-column prop="code" label="代码" width="100" show-overflow-tooltip>
                  <template #default="{ row }">
                    <el-tooltip :content="`${row.start || '-'} ~ ${row.end || '-'}`" placement="top">
                      <el-link type="primary" @click="goToDataView(row)">{{ row.code }}</el-link>
                    </el-tooltip>
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="名称" show-overflow-tooltip />
                <el-table-column prop="asset_type" label="类型" width="80">
                  <template #default="{ row }">
                    <el-tag size="small" :type="assetTypeTag(row.asset_type)">{{ assetTypeLabel(row.asset_type) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="source" label="来源" width="70">
                  <template #default="{ row }">
                    <el-tag v-if="row.source" size="small" type="info">{{ sourceLabel(row.source) }}</el-tag>
                    <span v-else style="color: #909399; font-size: 12px">-</span>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 4: 基础数据查看 -->
      <el-tab-pane label="数据查看" name="dataview">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-card shadow="hover">
              <template #header>
                <span>选择资产</span>
              </template>
              <!-- 一级筛选：资产类型 -->
              <el-select v-model="dataViewForm.assetType" placeholder="选择类型" style="width: 100%; margin-bottom: 10px" @change="onAssetTypeChange">
                <el-option label="全部" value="all" />
                <el-option label="指数" value="index" />
                <el-option label="行业板块" value="sector_industry" />
                <el-option label="概念板块" value="sector_concept" />
                <el-option label="ETF" value="etf" />
                <el-option label="个股" value="stock" />
                <el-option label="大宗商品" value="commodity" />
              </el-select>
              <!-- 二级选择：具体资产 + 左右切换 -->
              <div style="display: flex; align-items: center; gap: 8px">
                <el-button size="small" @click="prevAsset" :disabled="!canPrevAsset">
                  <el-icon><Arrow-Left /></el-icon>
                </el-button>
                <el-select-v2
                  v-model="dataViewForm.code"
                  :options="filteredAssetOptions"
                  placeholder="选择资产"
                  style="flex: 1"
                  @change="loadDataView"
                />
                <el-button size="small" @click="nextAsset" :disabled="!canNextAsset">
                  <el-icon><Arrow-Right /></el-icon>
                </el-button>
              </div>
              <el-divider />
              <div v-if="dataStats.exists" style="font-size: 13px; color: #606266">
                <p><strong>统计概览</strong></p>
                <p>数据天数: {{ dataStats.total_days }}</p>
                <p>总收益: {{ dataStats.returns?.total }}%</p>
                <p>日均收益: {{ dataStats.returns?.avg_daily }}%</p>
                <p>波动率: {{ dataStats.returns?.volatility }}</p>
                <p>最大单日: {{ dataStats.returns?.max }}%</p>
                <p>最小单日: {{ dataStats.returns?.min }}%</p>
              </div>
            </el-card>
          </el-col>
          <el-col :span="18">
            <el-card shadow="hover">
              <template #header>
                <span>K线图</span>
              </template>
              <v-chart v-if="klineData.length" :option="klineOption" style="height: 450px" />
              <el-empty v-else description="选择资产查看K线" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 5: 主题指数 -->
      <el-tab-pane label="主题指数" name="theme">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-card shadow="hover">
              <template #header>
                <span>主题列表</span>
              </template>
              <el-input
                v-model="themeSearch"
                placeholder="搜索名称或代码"
                clearable
                size="small"
                style="margin-bottom: 10px"
              />
              <el-table
                :data="filteredThemeAssets"
                size="small"
                height="460"
                highlight-current-row
                @row-click="onThemeSelect"
                style="cursor: pointer"
              >
                <el-table-column prop="code" label="代码" width="90" show-overflow-tooltip />
                <el-table-column prop="name" label="名称" show-overflow-tooltip />
              </el-table>
              <div style="font-size: 12px; color: #909399; margin-top: 8px">
                共 {{ filteredThemeAssets.length }} / {{ themeAssets.length }} 个
              </div>
            </el-card>
          </el-col>
          <el-col :span="18">
            <el-card shadow="hover">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <div style="display: flex; align-items: center; gap: 8px">
                    <span>{{ selectedTheme?.name || '选择主题查看走势' }}</span>
                    <el-tag v-if="selectedTheme" size="small" type="warning">{{ selectedTheme.code }}</el-tag>
                  </div>
                  <el-radio-group v-model="themeChartMode" size="small">
                    <el-radio-button label="收盘价" value="close" />
                    <el-radio-button label="K线" value="kline" />
                  </el-radio-group>
                </div>
              </template>
              <div v-if="loading.themeChart" style="height: 500px; display: flex; align-items: center; justify-content: center">
                <el-text type="info">加载中...</el-text>
              </div>
              <v-chart v-else-if="themeChartData.length" :option="themeChartOption" style="height: 500px" autoresize />
              <el-empty v-else-if="selectedTheme" description="暂无数据，请在「数据缓存」中同步 L3 主题指数" />
              <el-empty v-else description="点击左侧主题查看走势图" />
            </el-card>
          </el-col>
        </el-row>
        <el-row :gutter="20" style="margin-top: 16px">
          <el-col :span="6">
            <el-card shadow="hover">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>最新指标</span>
                  <el-radio-group v-model="themePeView" size="small">
                    <el-radio-button label="市盈率" value="pe" />
                    <el-radio-button label="股息率" value="dy" />
                  </el-radio-group>
                </div>
              </template>
              <template v-if="themePeView === 'pe'">
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item label="静态PE">
                    <span style="font-weight: bold; color: #409EFF">{{ themePeLatest?.pe1?.toFixed(2) ?? '-' }}</span>
                  </el-descriptions-item>
                  <el-descriptions-item label="TTM PE">
                    <span style="font-weight: bold; color: #F56C6C">{{ themePeLatest?.pe2?.toFixed(2) ?? '-' }}</span>
                  </el-descriptions-item>
                  <el-descriptions-item label="数据日期">
                    <span style="color: #909399; font-size: 12px">{{ themePeLatest?.date ?? '-' }}</span>
                  </el-descriptions-item>
                </el-descriptions>
              </template>
              <template v-else>
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item label="静态股息率">
                    <span style="font-weight: bold; color: #67C23A">{{ themePeLatest?.dividend_yield1?.toFixed(2) ?? '-' }}%</span>
                  </el-descriptions-item>
                  <el-descriptions-item label="TTM股息率">
                    <span style="font-weight: bold; color: #E6A23C">{{ themePeLatest?.dividend_yield2?.toFixed(2) ?? '-' }}%</span>
                  </el-descriptions-item>
                  <el-descriptions-item label="数据日期">
                    <span style="color: #909399; font-size: 12px">{{ themePeLatest?.date ?? '-' }}</span>
                  </el-descriptions-item>
                </el-descriptions>
              </template>
            </el-card>
          </el-col>
          <el-col :span="18">
            <el-card shadow="hover">
              <template #header>
                <span>{{ themePeView === 'pe' ? '市盈率走势' : '股息率走势' }}</span>
              </template>
              <v-chart v-if="themePeData.length" :option="themePeChartOption" style="height: 220px" autoresize />
              <el-empty v-else description="暂无 PE 数据" :image-size="60" style="padding: 20px 0" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 6: 大宗商品 -->
      <el-tab-pane label="大宗商品" name="commodity">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-card shadow="hover">
              <template #header>
                <span>品种列表</span>
              </template>
              <el-table
                :data="commodityAssets"
                size="small"
                height="500"
                highlight-current-row
                @row-click="onCommoditySelect"
                style="cursor: pointer"
              >
                <el-table-column prop="code" label="代码" width="80" />
                <el-table-column prop="name" label="名称" />
                <el-table-column prop="source" label="来源" width="70">
                  <template #default="{ row }">
                    <el-tag size="small" type="info">{{ sourceLabel(row.source) }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="18">
            <el-card shadow="hover">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>{{ selectedCommodity?.name || '选择品种查看走势' }}</span>
                  <el-tag v-if="selectedCommodity" size="small" type="info">{{ selectedCommodity.code }}</el-tag>
                </div>
              </template>
              <v-chart v-if="commodityChartData.length" :option="commodityChartOption" style="height: 500px" autoresize />
              <el-empty v-else description="点击左侧品种查看走势图" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>


    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import {
  analysisCacheStatus, analysisCacheSync, analysisCacheSyncBatch, analysisCacheProgress,
  analysisCacheSyncL1, analysisCacheSyncL2, analysisCacheSyncL6, analysisCacheSyncL6C, analysisCacheSyncL3Theme,

  analysisDataOHLCV, analysisDataDistribution, analysisVolumeAnalysis, analysisDataStats,
  getIndexPeData
} from '../api'

const activeTab = ref('cache')


const PARAM_DESC = {
  stop_loss_pct:        '兜底止损：浮亏达此%强制卖出，无论使用哪种退出模式都生效。宽基ETF建议10-20%；过小频繁止损，过大单次亏损过重。',
  max_hold_days:        '时间止损：持仓超过此天数无论盈亏强制平仓，防止资金长期被套。0=不限制。常设365天（1年）或730天（2年）。',
  take_profit_pct:      '止盈线：浮盈涨到此%时卖出锁利。过低会频繁止盈、错失后续上涨；建议参考标的历史平均涨幅周期设定。',
  pmax_drawdown_pct:    '回撤容忍度：从持仓最高点回落超过此%触发卖出。宽基ETF日均波幅~1%，10%≈约10个交易日正常波动，可视个人风险偏好适度放宽。',
  profit_trigger_pct:   '激活阈值：浮盈须先达到此%，保护机制才生效。激活前只有兜底止损保护，建议设在你认为"已有可观盈利"的水平（如ETF涨幅15-30%）。',
  profit_retention_pct: '浮盈保留比（0～1）：激活后，止损线 = 历史最高浮盈 × 此比例。0.5=保留50%浮盈，0.8=保留80%（保护更激进，但容易提前触发）。',
  cost_trigger_pct:     '激活阈值：浮盈须先达到此%后保本保护才生效。建议至少5-10%，给策略一定获利空间再锁仓位。',
  cost_floor_pct:       '保护底线：激活后止损线 = 成本价×(1+此值/100)。0=保本，2=成本+2%，-1=允许亏1%才触发（负值通常不推荐）。',
  reentry_cooldown:     '冷静期（日历天）：止损/止盈后等待此天数再重新入场，避免震荡市频繁进出被"锯齿"消耗。宽基ETF建议20-30天。',
  whipsaw_window:       'Whipsaw判定窗口（交易日）：止损卖出后，若此日内价格反弹超过止损价则判为假止损。此参数只影响统计分析，不影响实际交易逻辑。',
}

// 加载状态
const loading = ref({
  cache: false, syncL1: false, syncL2: false, syncL6: false, syncL6C: false, syncL3Theme: false, syncSingle: false,
  themeChart: false
})

// 缓存状态
const cacheStatus = ref({})
const cacheAssets = ref([])

// 同步进度
const syncProgress = ref({ active: false, task: '', current: 0, total: 0, current_code: '', message: '空闲' })
let progressTimer = null

// 同步表单
const syncForm = ref({ code: '', asset_type: 'index' })

// 数据查看
const dataViewForm = ref({ code: '', assetType: 'all' })
const dataStats = ref({ exists: false })
const klineData = ref([])
const distData = ref({ bins: [], freq: [] })
const volumeData = ref([])
// 主题指数
const themeAssets = ref([])
const themeSearch = ref('')
const selectedTheme = ref(null)
const themeChartData = ref([])
const themeChartMode = ref('close')
const themePeData = ref([])
const themePeView = ref('pe')

const filteredThemeAssets = computed(() => {
  const q = themeSearch.value.trim()
  if (!q) return themeAssets.value
  return themeAssets.value.filter(a => a.name.includes(q) || a.code.includes(q))
})

const loadThemeAssets = () => {
  themeAssets.value = cacheAssets.value.filter(a => a.category === '主题指数')
  if (themeAssets.value.length > 0 && !selectedTheme.value) {
    const first = themeAssets.value[0]
    selectedTheme.value = first
    loadThemeChart(first.code)
  }
}

const onThemeSelect = (row) => {
  selectedTheme.value = row
  loadThemeChart(row.code)
  loadThemePe(row.code)
}

const loadThemePe = async (code) => {
  themePeData.value = []
  try {
    const res = await getIndexPeData(code)
    themePeData.value = res.data.data || []
  } catch (e) {
    // PE数据缺失不影响主流程
  }
}

const loadThemeChart = async (code) => {
  if (!code) return
  loading.value.themeChart = true
  themeChartData.value = []
  try {
    const res = await analysisDataOHLCV(code, 5000)
    themeChartData.value = res.data.data || []
  } catch (e) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value.themeChart = false
  }
}

// 大宗商品
const commodityAssets = ref([])
const selectedCommodity = ref(null)
const commodityChartData = ref([])

// 筛选大宗商品资产
const loadCommodityAssets = () => {
  commodityAssets.value = cacheAssets.value.filter(a => a.asset_type === 'commodity')
  // 默认选中第一个并加载数据
  if (commodityAssets.value.length > 0 && !selectedCommodity.value) {
    const first = commodityAssets.value[0]
    selectedCommodity.value = first
    loadCommodityChart(first.code)
  }
}

// 大宗商品选择
const onCommoditySelect = (row) => {
  selectedCommodity.value = row
  loadCommodityChart(row.code)
}

// 加载大宗商品走势图数据
const loadCommodityChart = async (code) => {
  if (!code) return
  try {
    const ohlcvRes = await analysisDataOHLCV(code, 5000)
    commodityChartData.value = ohlcvRes.data.data || []
  } catch (e) {
    ElMessage.error('加载数据失败')
  }
}

// 资产选项（从缓存状态生成）
const cacheAssetOptions = computed(() => {
  if (!Array.isArray(cacheAssets.value)) return []
  return cacheAssets.value.map(a => ({ label: `${a.name || assetTypeLabel(a.asset_type)} (${a.code})`, value: a.code, assetType: a.asset_type }))
})

// 根据类型筛选后的资产选项
const filteredAssetOptions = computed(() => {
  if (dataViewForm.value.assetType === 'all') return cacheAssetOptions.value
  return cacheAssetOptions.value.filter(a => a.assetType === dataViewForm.value.assetType)
})

// 当前资产索引
const currentAssetIndex = computed(() => {
  return filteredAssetOptions.value.findIndex(a => a.value === dataViewForm.value.code)
})

// 是否可以切换
const canPrevAsset = computed(() => currentAssetIndex.value > 0)
const canNextAsset = computed(() => currentAssetIndex.value >= 0 && currentAssetIndex.value < filteredAssetOptions.value.length - 1)

// 切换资产
const prevAsset = () => {
  const idx = currentAssetIndex.value
  if (idx > 0) {
    dataViewForm.value.code = filteredAssetOptions.value[idx - 1].value
    loadDataView()
  }
}
const nextAsset = () => {
  const idx = currentAssetIndex.value
  if (idx >= 0 && idx < filteredAssetOptions.value.length - 1) {
    dataViewForm.value.code = filteredAssetOptions.value[idx + 1].value
    loadDataView()
  }
}

// 资产类型改变时重置选择
const onAssetTypeChange = () => {
  dataViewForm.value.code = ''
  dataStats.value = { exists: false }
  klineData.value = []
}

// 辅助函数
const assetTypeTag = (type) => {
  const map = { index: 'primary', sector_industry: 'success', sector_concept: 'warning', etf: 'info', stock: '', commodity: 'danger' }
  return map[type] || ''
}
const assetTypeLabel = (type) => {
  const map = { index: '指数', sector_industry: '行业', sector_concept: '概念', etf: 'ETF', stock: '个股', commodity: '大宗商品' }
  return map[type] || type
}
const sourceLabel = (source) => {
  const map = { sw: '申万', em: '东财', csindex: '中证', wind: 'Wind', ths: '同花顺', global: '国际' }
  return map[source] || source
}

// API调用
const loadCacheStatus = async () => {
  loading.value.cache = true
  try {
    const res = await analysisCacheStatus()
    cacheStatus.value = res.data || res
    // 合并 date_ranges 和 by_type 信息
    const typeMap = {}
    ;(res.data.by_type || []).forEach(t => {
      typeMap[t.asset_type] = t
    })
    // 使用后端返回的 assets 列表（含名称和数据范围）
    cacheAssets.value = res.data.assets || []
  } catch (e) {
    console.error('loadCacheStatus error:', e)
    ElMessage.error('加载缓存状态失败: ' + e.message)
  } finally {
    loading.value.cache = false
  }
}

// 进度轮询
const startProgressPolling = () => {
  if (progressTimer) clearInterval(progressTimer)
  progressTimer = setInterval(async () => {
    try {
      const res = await analysisCacheProgress()
      syncProgress.value = res.data
    } catch (e) {
      // ignore
    }
  }, 2000)
}

const stopProgressPolling = () => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

// 等待进度完成后再停止轮询（最长等 10 分钟，L3/L6 同步较慢）
const waitProgressComplete = async (timeoutMs = 600000) => {
  const startTime = Date.now()
  while (Date.now() - startTime < timeoutMs) {
    try {
      const res = await analysisCacheProgress()
      syncProgress.value = res.data
      if (!res.data.active) {
        // 任务已完成，再显示2秒后清除
        await new Promise(r => setTimeout(r, 2000))
        return
      }
    } catch (e) {
      // ignore
    }
    await new Promise(r => setTimeout(r, 1000))
  }
}

const syncL1 = async () => {
  loading.value.syncL1 = true
  startProgressPolling()
  try {
    const res = await analysisCacheSyncL1()
    if (res.data.results) {
      const success = res.data.results.filter(r => r.ok).length
      ElMessage.success(`L1同步完成: ${success}/${res.data.total} 个指数`)
    } else {
      ElMessage.success('L1同步完成')
    }
    loadCacheStatus()
  } catch (e) {
    ElMessage.error('L1同步失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    await waitProgressComplete()
    stopProgressPolling()
    loading.value.syncL1 = false
    syncProgress.value = { active: false, task: '', current: 0, total: 0, current_code: '', message: '空闲' }
  }
}

const syncL2 = async () => {
  loading.value.syncL2 = true
  startProgressPolling()
  try {
    const res = await analysisCacheSyncL2()
    if (res.data.ok === false) {
      ElMessage.error(res.data.message || 'L2同步失败')
      // 错误时保持进度显示2秒让用户看到错误信息
      await new Promise(r => setTimeout(r, 2000))
      return
    }
    if (res.data.results) {
      const success = res.data.results.filter(r => r.ok).length
      ElMessage.success(`L2同步完成: ${success}/${res.data.total} 个板块`)
    } else {
      ElMessage.success('L2同步完成')
    }
    loadCacheStatus()
  } catch (e) {
    ElMessage.error('L2同步失败: ' + (e.response?.data?.detail || e.message))
    // 错误时保持进度显示2秒
    await new Promise(r => setTimeout(r, 2000))
  } finally {
    await waitProgressComplete()
    stopProgressPolling()
    loading.value.syncL2 = false
    syncProgress.value = { active: false, task: '', current: 0, total: 0, current_code: '', message: '空闲' }
  }
}

const syncL6 = async () => {
  loading.value.syncL6 = true
  startProgressPolling()
  try {
    const res = await analysisCacheSyncL6()
    if (res.data.ok === false) {
      ElMessage.error(res.data.message || 'L6同步失败')
      await new Promise(r => setTimeout(r, 2000))
      return
    }
    ElMessage.success(`L6同步完成: ${res.data.success}/${res.data.total} 个品种, ${res.data.saved}条数据`)
    loadCacheStatus()
  } catch (e) {
    ElMessage.error('L6同步失败: ' + (e.response?.data?.detail || e.message))
    await new Promise(r => setTimeout(r, 2000))
  } finally {
    await waitProgressComplete()
    stopProgressPolling()
    loading.value.syncL6 = false
    syncProgress.value = { active: false, task: '', current: 0, total: 0, current_code: '', message: '空闲' }
  }
}

const syncL6C = async () => {
  loading.value.syncL6C = true
  startProgressPolling()
  try {
    const res = await analysisCacheSyncL6C()
    if (res.data.ok === false) {
      ElMessage.error(res.data.message || 'L6C同步失败')
      await new Promise(r => setTimeout(r, 2000))
      return
    }
    ElMessage.success(`L6C同步完成: ${res.data.success}/${res.data.total} 个品种, ${res.data.saved}条数据`)
    loadCacheStatus()
  } catch (e) {
    ElMessage.error('L6C同步失败: ' + (e.response?.data?.detail || e.message))
    await new Promise(r => setTimeout(r, 2000))
  } finally {
    await waitProgressComplete()
    stopProgressPolling()
    loading.value.syncL6C = false
    syncProgress.value = { active: false, task: '', current: 0, total: 0, current_code: '', message: '空闲' }
  }
}

const syncL3Theme = async () => {
  loading.value.syncL3Theme = true
  startProgressPolling()
  try {
    const res = await analysisCacheSyncL3Theme()
    if (res.data.ok === false) {
      ElMessage.error(res.data.message || 'L3主题指数同步失败')
      await new Promise(r => setTimeout(r, 2000))
      return
    }
    ElMessage.success(`L3主题指数同步完成: ${res.data.success}/${res.data.total} 个指数, ${res.data.saved}条数据`)
    loadCacheStatus()
  } catch (e) {
    ElMessage.error('L3主题指数同步失败: ' + (e.response?.data?.detail || e.message))
    await new Promise(r => setTimeout(r, 2000))
  } finally {
    await waitProgressComplete()
    stopProgressPolling()
    loading.value.syncL3Theme = false
    syncProgress.value = { active: false, task: '', current: 0, total: 0, current_code: '', message: '空闲' }
  }
}

const syncSingle = async () => {
  if (!syncForm.value.code) return ElMessage.warning('请输入资产代码')
  loading.value.syncSingle = true
  try {
    const res = await analysisCacheSync(syncForm.value)
    ElMessage.success(`同步完成: ${res.data.saved}条数据`)
    loadCacheStatus()
  } catch (e) {
    ElMessage.error('同步失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value.syncSingle = false
  }
}

// 跳转到数据查看Tab
const goToDataView = (row) => {
  activeTab.value = 'dataview'
  dataViewForm.value.code = row.code
  // 如果row有asset_type，也设置类型筛选
  if (row.asset_type) {
    dataViewForm.value.assetType = row.asset_type
  }
  loadDataView()
}

// 数据查看
const loadDataView = async () => {
  const code = dataViewForm.value.code
  if (!code) return
  
  try {
    // 加载统计数据
    const statsRes = await analysisDataStats(code)
    dataStats.value = statsRes.data
    
    // 加载K线数据（所有历史数据）
    const ohlcvRes = await analysisDataOHLCV(code, 5000)
    klineData.value = ohlcvRes.data.data || []
    

  } catch (e) {
    ElMessage.error('加载数据失败')
  }
}

// K线图配置（与大宗商品Tab一致）
const klineOption = computed(() => {
  if (!klineData.value.length) return {}
  const dates = klineData.value.map(d => d.date)
  const range = calculateSixMonthRange(dates)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: { left: '10%', right: '10%', top: '10%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: dates,
      scale: true,
      boundaryGap: false,
      axisLine: { onZero: false, lineStyle: { color: '#909399' } },
      axisTick: { show: true, alignWithLabel: true },
      splitLine: { show: false },
      axisLabel: { show: true, interval: 'auto', rotate: 0, fontSize: 11, color: '#606266' }
    },
    yAxis: { scale: true, splitArea: { show: true }, name: '价格' },
    dataZoom: [
      { type: 'inside', start: range.start, end: range.end },
      {
        type: 'slider',
        start: range.start,
        end: range.end,
        bottom: '2%',
        height: 24,
        handleStyle: {
          color: '#409EFF',
          borderColor: '#409EFF',
          borderWidth: 2,
          shadowBlur: 4,
          shadowColor: 'rgba(64, 158, 255, 0.5)'
        },
        textStyle: {
          color: '#303133',
          fontWeight: 'bold',
          fontSize: 12
        },
        borderColor: '#DCDFE6',
        fillerColor: 'rgba(64, 158, 255, 0.15)',
        backgroundColor: '#F5F7FA',
        dataBackground: {
          lineStyle: { color: '#C0C4CC', width: 1 },
          areaStyle: { color: '#EBEEF5' }
        },
        selectedDataBackground: {
          lineStyle: { color: '#409EFF', width: 2 },
          areaStyle: { color: 'rgba(64, 158, 255, 0.2)' }
        },
        brushSelect: false
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: klineData.value.map(d => [d.open, d.close, d.low, d.high]),
        itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' }
      }
    ]
  }
})

// 计算近6个月的dataZoom范围（约120个交易日）
const calculateSixMonthRange = (dates) => {
  if (!dates || dates.length === 0) return { start: 0, end: 100 }
  const total = dates.length
  const sixMonthDays = 120
  if (total <= sixMonthDays) return { start: 0, end: 100 }
  const startPercent = ((total - sixMonthDays) / total) * 100
  return { start: startPercent, end: 100 }
}

// 大宗商品走势图配置
const commodityChartOption = computed(() => {
  if (!commodityChartData.value.length) return {}
  const dates = commodityChartData.value.map(d => d.date)
  const range = calculateSixMonthRange(dates)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: { left: '10%', right: '10%', top: '10%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: dates,
      scale: true,
      boundaryGap: false,
      axisLine: { onZero: false, lineStyle: { color: '#909399' } },
      axisTick: { show: true, alignWithLabel: true },
      splitLine: { show: false },
      axisLabel: { show: true, interval: 'auto', rotate: 0, fontSize: 11, color: '#606266' }
    },
    yAxis: { scale: true, splitArea: { show: true }, name: '价格' },
    dataZoom: [
      { type: 'inside', start: range.start, end: range.end },
      {
        type: 'slider',
        start: range.start,
        end: range.end,
        bottom: '2%',
        height: 24,
        handleStyle: {
          color: '#409EFF',
          borderColor: '#409EFF',
          borderWidth: 2,
          shadowBlur: 4,
          shadowColor: 'rgba(64, 158, 255, 0.5)'
        },
        textStyle: {
          color: '#303133',
          fontWeight: 'bold',
          fontSize: 12
        },
        borderColor: '#DCDFE6',
        fillerColor: 'rgba(64, 158, 255, 0.15)',
        backgroundColor: '#F5F7FA',
        dataBackground: {
          lineStyle: { color: '#C0C4CC', width: 1 },
          areaStyle: { color: '#EBEEF5' }
        },
        selectedDataBackground: {
          lineStyle: { color: '#409EFF', width: 2 },
          areaStyle: { color: 'rgba(64, 158, 255, 0.2)' }
        },
        brushSelect: false
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: commodityChartData.value.map(d => [d.open, d.close, d.low, d.high]),
        itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' }
      }
    ]
  }
})

// 主题指数走势图配置
const themeChartOption = computed(() => {
  if (!themeChartData.value.length) return {}
  const dates = themeChartData.value.map(d => d.date)
  const range = calculateSixMonthRange(dates)
  const isClose = themeChartMode.value === 'close'
  const dataZoom = [
    { type: 'inside', start: range.start, end: range.end },
    {
      type: 'slider',
      start: range.start,
      end: range.end,
      bottom: '2%',
      height: 24,
      handleStyle: { color: '#409EFF', borderColor: '#409EFF', borderWidth: 2, shadowBlur: 4, shadowColor: 'rgba(64, 158, 255, 0.5)' },
      textStyle: { color: '#303133', fontWeight: 'bold', fontSize: 12 },
      borderColor: '#DCDFE6',
      fillerColor: 'rgba(64, 158, 255, 0.15)',
      backgroundColor: '#F5F7FA',
      dataBackground: { lineStyle: { color: '#C0C4CC', width: 1 }, areaStyle: { color: '#EBEEF5' } },
      selectedDataBackground: { lineStyle: { color: '#409EFF', width: 2 }, areaStyle: { color: 'rgba(64, 158, 255, 0.2)' } },
      brushSelect: false
    }
  ]
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: { left: '10%', right: '10%', top: '10%', bottom: '15%' },
    xAxis: {
      type: 'category',
      data: dates,
      scale: true,
      boundaryGap: isClose ? false : true,
      axisLine: { onZero: false, lineStyle: { color: '#909399' } },
      axisTick: { show: true, alignWithLabel: true },
      splitLine: { show: false },
      axisLabel: { show: true, interval: 'auto', rotate: 0, fontSize: 11, color: '#606266' }
    },
    yAxis: { scale: true, splitArea: { show: true }, name: '指数' },
    dataZoom,
    series: isClose
      ? [{
          name: '收盘价',
          type: 'line',
          data: themeChartData.value.map(d => d.close),
          smooth: false,
          symbol: 'none',
          lineStyle: { color: '#409EFF', width: 2 },
          areaStyle: { color: 'rgba(64, 158, 255, 0.08)' }
        }]
      : [{
          name: 'K线',
          type: 'candlestick',
          data: themeChartData.value.map(d => [d.open, d.close, d.low, d.high]),
          itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' }
        }]
  }
})

// 主题指数 PE 最新值
const themePeLatest = computed(() => {
  if (!themePeData.value.length) return null
  return themePeData.value[themePeData.value.length - 1]
})

// 主题指数 PE / 股息率图表配置
const themePeChartOption = computed(() => {
  if (!themePeData.value.length) return {}
  const sorted = [...themePeData.value].sort((a, b) => new Date(a.date) - new Date(b.date))
  const dates = sorted.map(p => p.date)
  const isPe = themePeView.value === 'pe'

  const v1 = sorted.map(p => isPe ? p.pe1 : p.dividend_yield1)
  const v2 = sorted.map(p => isPe ? p.pe2 : p.dividend_yield2)
  const s1Name = isPe ? '静态PE' : '静态股息率'
  const s2Name = isPe ? 'TTM PE' : 'TTM股息率'
  const yName  = isPe ? 'PE' : '股息率(%)'
  const fmt    = isPe ? (v => v?.toFixed(2)) : (v => v?.toFixed(2) + '%')

  const all = [...v1, ...v2].filter(v => v != null)
  const vMin = Math.min(...all), vMax = Math.max(...all)
  const vRange = vMax - vMin || 1

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        let html = `<div style="font-weight:bold;margin-bottom:4px">${params[0].axisValue}</div>`
        params.forEach(p => {
          const val = p.value != null ? (isPe ? p.value.toFixed(2) : p.value.toFixed(2) + '%') : '-'
          html += `<div>${p.marker} ${p.seriesName}: <b>${val}</b></div>`
        })
        return html
      }
    },
    legend: { data: [s1Name, s2Name], top: 4 },
    grid: { left: '8%', right: '4%', top: '14%', bottom: '8%' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { fontSize: 11, color: '#606266' }
    },
    yAxis: {
      type: 'value',
      name: yName,
      min: Math.max(0, vMin - vRange * 0.1),
      max: vMax + vRange * 0.1,
      axisLabel: { formatter: fmt }
    },
    series: [
      { name: s1Name, type: 'line', data: v1, smooth: true, symbol: 'circle', symbolSize: 4, lineStyle: { color: '#409EFF', width: 2 }, itemStyle: { color: '#409EFF' } },
      { name: s2Name, type: 'line', data: v2, smooth: true, symbol: 'circle', symbolSize: 4, lineStyle: { color: '#F56C6C', width: 2 }, itemStyle: { color: '#F56C6C' } }
    ]
  }
})

// 分布图配置
const distOption = computed(() => {
  if (!distData.value.freq?.length) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '15%', right: '10%', bottom: '15%' },
    xAxis: { 
      type: 'category', 
      data: distData.value.bins.map(b => b.toFixed(2)),
      name: '涨跌幅%'
    },
    yAxis: { type: 'value', name: '频次' },
    series: [{
      type: 'bar',
      data: distData.value.freq,
      itemStyle: { color: '#409eff' }
    }]
  }
})

// 成交量图配置
const volumeOption = computed(() => {
  if (!volumeData.value.length) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '10%', right: '10%', bottom: '15%' },
    xAxis: { type: 'category', data: volumeData.value.map(d => d.date) },
    yAxis: [
      { type: 'value', name: '成交量' },
      { type: 'value', name: '收盘价', position: 'right' }
    ],
    dataZoom: [{ type: 'inside' }],
    series: [
      {
        type: 'bar',
        data: volumeData.value.map(d => d.volume),
        itemStyle: { color: '#909399' },
        name: '成交量'
      },
      {
        type: 'line',
        data: volumeData.value.map(d => d.close),
        yAxisIndex: 1,
        itemStyle: { color: '#409eff' },
        name: '收盘价'
      }
    ]
  }
})


onMounted(() => {
  loadCacheStatus()
})

watch(activeTab, (tab) => {
  if (tab === 'dataview') loadCacheStatus()
  if (tab === 'theme') loadThemeAssets()
  if (tab === 'commodity') loadCommodityAssets()
})

const handleTabClick = () => {
  if (activeTab.value === 'dataview') loadCacheStatus()
  if (activeTab.value === 'theme') loadThemeAssets()
  if (activeTab.value === 'commodity') loadCommodityAssets()
}
</script>

<style scoped>
.stat-box { text-align: center; padding: 20px; }
.stat-num { font-size: 32px; font-weight: bold; color: #409eff; }
.stat-label { color: #909399; font-size: 14px; margin-top: 8px; }
.result-box { background: #f5f7fa; padding: 15px; border-radius: 4px; margin-top: 10px; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
.col-tip    { cursor: help; border-bottom: 1px dashed #909399; }
.best-metric { cursor: help; border-bottom: 1px dashed #67c23a; }
.mode-desc-box { background:#f0f9eb; border-left:3px solid #67c23a; border-radius:4px; padding:8px 10px; font-size:12px; color:#606266; line-height:1.7; margin-bottom:12px; white-space:pre-line; }
.param-desc    { font-size:11px; color:#909399; line-height:1.6; margin-top:3px; }
:deep(.grid-best-row)  { background: #f0f9eb !important; font-weight: bold; }
:deep(.oos-row-good)   { background: #f0f9eb !important; }
:deep(.oos-row-warn)   { background: #fdf6ec !important; }
:deep(.oos-row-bad)    { background: #fef0f0 !important; }
</style>
