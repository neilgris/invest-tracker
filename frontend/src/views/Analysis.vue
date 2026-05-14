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
                <p>L2: ~90个行业板块 | L3: 概念板块 | L4: ETF | L5: 个股</p>
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
                      <span>{{ row.code }}</span>
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

      <!-- Tab 2: 相关性分析 -->
      <el-tab-pane label="相关性分析" name="correlation">
        <!-- 全局日期范围设置 -->
        <el-card shadow="hover" style="margin-bottom: 20px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>分析时间范围</span>
              <div>
                <el-radio-group v-model="globalDateRange.preset" size="small" @change="onDatePresetChange">
                  <el-radio-button label="1y">近1年</el-radio-button>
                  <el-radio-button label="3y">近3年</el-radio-button>
                  <el-radio-button label="5y">近5年</el-radio-button>
                  <el-radio-button label="10y">近10年</el-radio-button>
                  <el-radio-button label="custom">自定义</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </template>
          <el-form :inline="true">
            <el-form-item label="起始日期">
              <el-date-picker v-model="globalDateRange.start" type="date" placeholder="起始日期" format="YYYY-MM-DD" value-format="YYYY-MM-DD" :disabled="globalDateRange.preset !== 'custom'" />
            </el-form-item>
            <el-form-item label="结束日期">
              <el-date-picker v-model="globalDateRange.end" type="date" placeholder="结束日期" format="YYYY-MM-DD" value-format="YYYY-MM-DD" :disabled="globalDateRange.preset !== 'custom'" />
            </el-form-item>
            <el-form-item>
              <el-tag v-if="globalDateRange.start && globalDateRange.end" type="info" size="small">
                {{ globalDateRange.start }} ~ {{ globalDateRange.end }}
              </el-tag>
            </el-form-item>
          </el-form>
        </el-card>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-card shadow="hover" style="margin-bottom: 20px">
              <template #header><span>两两相关性 (Pearson)</span></template>
              <el-form label-width="80px">
                <el-form-item label="资产A">
                  <el-input v-model="pearsonForm.code_a" placeholder="000001" />
                </el-form-item>
                <el-form-item label="资产B">
                  <el-input v-model="pearsonForm.code_b" placeholder="399001" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="calcPearson" :loading="loading.pearson">计算</el-button>
                </el-form-item>
              </el-form>
              <div v-if="pearsonResult.ok" class="result-box">
                <p>相关系数: <strong :class="pearsonResult.correlation > 0 ? 'profit' : 'loss'">{{ pearsonResult.correlation?.toFixed(4) }}</strong></p>
                <p>P值: {{ pearsonResult.p_value?.toExponential(2) }}</p>
                <p>样本数: {{ pearsonResult.n }}</p>
              </div>
            </el-card>

            <el-card shadow="hover">
              <template #header><span>领先滞后分析 (CCF)</span></template>
              <el-form label-width="80px">
                <el-form-item label="资产A">
                  <el-input v-model="ccfForm.code_a" placeholder="000300" />
                </el-form-item>
                <el-form-item label="资产B">
                  <el-input v-model="ccfForm.code_b" placeholder="399006" />
                </el-form-item>
                <el-form-item label="最大滞后">
                  <el-input-number v-model="ccfForm.max_lag" :min="1" :max="30" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="calcCCF" :loading="loading.ccf">计算</el-button>
                </el-form-item>
              </el-form>
              <div v-if="ccfResult.ok" class="result-box">
                <p>{{ ccfResult.interpretation }}</p>
                <p>最佳滞后: {{ ccfResult.best_lag }} 期</p>
                <p>最佳相关: {{ ccfResult.best_corr?.toFixed(4) }}</p>
              </div>
            </el-card>
          </el-col>

          <el-col :span="16">
            <el-card shadow="hover" style="margin-bottom: 20px">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>相关矩阵</span>
                  <el-button type="primary" size="small" @click="calcMatrix" :loading="loading.matrix">计算</el-button>
                </div>
              </template>
              <el-form :inline="true">
                <el-form-item label="资产列表">
                  <el-select-v2
                    v-model="matrixForm.codes"
                    :options="cacheAssetOptions"
                    placeholder="选择资产"
                    multiple
                    clearable
                    style="width: 400px"
                  />
                </el-form-item>
              </el-form>
              <div v-if="matrixResult.ok">
                <el-table :data="matrixTableData" size="small" border>
                  <el-table-column prop="code" label="代码" width="100" fixed />
                  <el-table-column v-for="c in (matrixResult.codes || [])" :key="c" :prop="c" :label="c" width="90">
                    <template #default="{ row }">
                      <span :class="row[c] > 0 ? 'profit' : row[c] < 0 ? 'loss' : ''">{{ row[c]?.toFixed(2) }}</span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </el-card>

            <el-card shadow="hover">
              <template #header><span>CCF 交叉相关图</span></template>
              <v-chart v-if="ccfResult.ok" :option="ccfChartOption" style="height: 300px" autoresize />
              <el-empty v-else description="请先计算CCF" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- Tab 3: 特征规律挖掘 -->
      <el-tab-pane label="规律挖掘" name="pattern">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-card shadow="hover" style="margin-bottom: 20px">
              <template #header><span>季节效应分析</span></template>
              <el-form label-width="80px">
                <el-form-item label="资产代码">
                  <el-input v-model="seasonForm.code" placeholder="000001" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="calcSeasonality" :loading="loading.season">分析</el-button>
                </el-form-item>
              </el-form>
            </el-card>

            <el-card shadow="hover" style="margin-bottom: 20px">
              <template #header><span>动量反转分析</span></template>
              <el-form label-width="100px">
                <el-form-item label="资产代码">
                  <el-input v-model="momentumForm.code" placeholder="000001" />
                </el-form-item>
                <el-form-item label="回看天数">
                  <el-input-number v-model="momentumForm.lookback" :min="5" :max="60" />
                </el-form-item>
                <el-form-item label="持有天数">
                  <el-input-number v-model="momentumForm.hold" :min="1" :max="20" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="calcMomentum" :loading="loading.momentum">分析</el-button>
                </el-form-item>
              </el-form>
              <div v-if="momentumResult.ok" class="result-box">
                <p>效应: <el-tag :type="momentumResult.effect === '动量效应' ? 'danger' : 'success'">{{ momentumResult.effect }}</el-tag></p>
                <p>相关系数: {{ momentumResult.correlation?.toFixed(4) }}</p>
              </div>
            </el-card>

            <el-card shadow="hover">
              <template #header><span>均值回归分析</span></template>
              <el-form label-width="80px">
                <el-form-item label="资产代码">
                  <el-input v-model="revertForm.code" placeholder="000001" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="calcReversion" :loading="loading.revert">分析</el-button>
                </el-form-item>
              </el-form>
              <div v-if="revertResult.ok" class="result-box">
                <p>当前Z值: <strong>{{ revertResult.current_zscore?.toFixed(2) }}</strong></p>
                <p>超买次数: {{ revertResult.overbought_count }} | 超卖次数: {{ revertResult.oversold_count }}</p>
              </div>
            </el-card>
          </el-col>

          <el-col :span="16">
            <el-card shadow="hover" style="margin-bottom: 20px">
              <template #header><span>月度季节效应</span></template>
              <v-chart v-if="seasonResult.ok" :option="seasonChartOption" style="height: 300px" autoresize />
              <el-empty v-else description="请先选择资产进行分析" />
            </el-card>

            <el-card shadow="hover">
              <template #header><span>快速综合报告</span></template>
              <el-form :inline="true">
                <el-form-item label="资产代码">
                  <el-input v-model="reportForm.code" placeholder="000001" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="loadReport" :loading="loading.report">生成报告</el-button>
                </el-form-item>
              </el-form>
              <div v-if="reportResult.ok">
                <el-descriptions :column="3" border size="small">
                  <el-descriptions-item label="数据范围">{{ reportResult.basic?.start_date?.slice(0,10) }} ~ {{ reportResult.basic?.end_date?.slice(0,10) }}</el-descriptions-item>
                  <el-descriptions-item label="总收益">{{ reportResult.basic?.total_return_pct?.toFixed(2) }}%</el-descriptions-item>
                  <el-descriptions-item label="年化收益">{{ reportResult.basic?.annualized_return_pct?.toFixed(2) }}%</el-descriptions-item>
                  <el-descriptions-item label="年化波动">{{ reportResult.basic?.annualized_volatility_pct?.toFixed(2) }}%</el-descriptions-item>
                  <el-descriptions-item label="最大回撤">{{ reportResult.basic?.max_drawdown_pct?.toFixed(2) }}%</el-descriptions-item>
                  <el-descriptions-item label="夏普比率">{{ reportResult.basic?.sharpe_ratio?.toFixed(2) }}</el-descriptions-item>
                </el-descriptions>
              </div>
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
  analysisCacheSyncL1, analysisCacheSyncL2,
  analysisPearson, analysisCorrMatrix, analysisCCF, analysisGranger,
  analysisSeasonality, analysisMomentumReversal, analysisMeanReversion, analysisQuickReport,
  analysisDataOHLCV, analysisDataDistribution, analysisVolumeAnalysis, analysisDataStats
} from '../api'

const activeTab = ref('cache')

// 加载状态
const loading = ref({
  cache: false, syncL1: false, syncL2: false, syncSingle: false,
  pearson: false, matrix: false, ccf: false, granger: false,
  season: false, momentum: false, revert: false, report: false
})

// 缓存状态
const cacheStatus = ref({})
const cacheAssets = ref([])

// 同步进度
const syncProgress = ref({ active: false, task: '', current: 0, total: 0, current_code: '', message: '空闲' })
let progressTimer = null

// 同步表单
const syncForm = ref({ code: '', asset_type: 'index' })

// 全局日期范围（相关性分析页面共用）
const globalDateRange = ref({
  preset: '5y',
  start: '',
  end: ''
})

// 根据预设计算日期范围
const calcDateRange = (preset) => {
  const end = new Date()
  const endStr = end.toISOString().split('T')[0]
  let startStr = ''
  switch (preset) {
    case '1y':
      startStr = new Date(end.getFullYear() - 1, end.getMonth(), end.getDate()).toISOString().split('T')[0]
      break
    case '3y':
      startStr = new Date(end.getFullYear() - 3, end.getMonth(), end.getDate()).toISOString().split('T')[0]
      break
    case '5y':
      startStr = new Date(end.getFullYear() - 5, end.getMonth(), end.getDate()).toISOString().split('T')[0]
      break
    case '10y':
      startStr = new Date(end.getFullYear() - 10, end.getMonth(), end.getDate()).toISOString().split('T')[0]
      break
    case 'custom':
      return { start: globalDateRange.value.start, end: globalDateRange.value.end }
    default:
      return { start: null, end: endStr }
  }
  return { start: startStr, end: endStr }
}

// 预设变化时自动更新日期
const onDatePresetChange = (preset) => {
  if (preset !== 'custom') {
    const { start, end } = calcDateRange(preset)
    globalDateRange.value.start = start
    globalDateRange.value.end = end
  }
}

// 初始化默认日期范围
onMounted(() => {
  const { start, end } = calcDateRange('5y')
  globalDateRange.value.start = start
  globalDateRange.value.end = end
})

// 获取当前日期范围参数
const getGlobalDateParams = () => {
  const { start, end } = calcDateRange(globalDateRange.value.preset)
  return {
    start_date: start,
    end_date: end
  }
}

const pearsonForm = ref({ code_a: '000001', code_b: '399001' })
const pearsonResult = ref({})

const matrixForm = ref({ codes: ['000001', '399001', '000300', '399006'] })
const matrixResult = ref({})

const ccfForm = ref({ code_a: '000300', code_b: '399006', max_lag: 10 })
const ccfResult = ref({})

// 规律挖掘表单
const seasonForm = ref({ code: '000001' })
const seasonResult = ref({})

const momentumForm = ref({ code: '000001', lookback: 20, hold: 5 })

// 数据查看
const dataViewForm = ref({ code: '', assetType: 'all' })
const dataStats = ref({ exists: false })
const klineData = ref([])
const distData = ref({ bins: [], freq: [] })
const volumeData = ref([])
const momentumResult = ref({})

const revertForm = ref({ code: '000001' })
const revertResult = ref({})

const reportForm = ref({ code: '000001' })
const reportResult = ref({})

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

// 相关矩阵表格数据
const matrixTableData = computed(() => {
  if (!matrixResult.value.ok) return []
  const codes = matrixResult.value.codes || []
  const matrix = matrixResult.value.matrix || []
  return codes.map((code, i) => {
    const row = { code }
    codes.forEach((c, j) => { row[c] = matrix[i]?.[j] })
    return row
  })
})

// CCF图表配置
const ccfChartOption = computed(() => {
  if (!ccfResult.value.ok) return {}
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ccfResult.value.lags, name: '滞后' },
    yAxis: { type: 'value', name: '相关系数' },
    series: [{
      type: 'bar',
      data: ccfResult.value.values,
      itemStyle: {
        color: (p) => p.value > 0 ? '#f56c6c' : '#67c23a'
      }
    }],
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
  }
})

// 季节效应图表
const seasonChartOption = computed(() => {
  if (!seasonResult.value.ok) return {}
  const months = seasonResult.value.monthly || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['月均涨跌%', '胜率%'] },
    xAxis: { type: 'category', data: months.map(m => m.month + '月') },
    yAxis: [
      { type: 'value', name: '涨跌%', position: 'left' },
      { type: 'value', name: '胜率%', position: 'right', max: 100 }
    ],
    series: [
      {
        name: '月均涨跌%',
        type: 'bar',
        data: months.map(m => (m.avg_pct * 100).toFixed(2)),
        itemStyle: { color: (p) => parseFloat(p.value) > 0 ? '#f56c6c' : '#67c23a' }
      },
      {
        name: '胜率%',
        type: 'line',
        yAxisIndex: 1,
        data: months.map(m => (m.win_rate * 100).toFixed(1)),
        smooth: true
      }
    ],
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
  }
})

// 辅助函数
const assetTypeTag = (type) => {
  const map = { index: 'primary', sector_industry: 'success', sector_concept: 'warning', etf: 'info', stock: '' }
  return map[type] || ''
}
const assetTypeLabel = (type) => {
  const map = { index: '指数', sector_industry: '行业', sector_concept: '概念', etf: 'ETF', stock: '个股' }
  return map[type] || type
}
const sourceLabel = (source) => {
  const map = { sw: '申万', em: '东财', csindex: '中证', wind: 'Wind', ths: '同花顺' }
  return map[source] || source
}

// API调用
const loadCacheStatus = async () => {
  console.log('loadCacheStatus called')
  loading.value.cache = true
  try {
    const res = await analysisCacheStatus()
    console.log('analysisCacheStatus returned')
    console.log('Full res:', res)
    console.log('res.data:', res.data)
    console.log('res.data?.date_ranges:', res.data?.date_ranges)
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
    stopProgressPolling()
    loading.value.syncL2 = false
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

const calcPearson = async () => {
  loading.value.pearson = true
  pearsonResult.value = {}  // 清空旧结果
  try {
    const { start_date, end_date } = getGlobalDateParams()
    const params = {
      code_a: pearsonForm.value.code_a,
      code_b: pearsonForm.value.code_b,
      start_date,
      end_date
    }
    pearsonResult.value = (await analysisPearson(params)).data
  } catch (e) {
    ElMessage.error('计算失败')
  } finally {
    loading.value.pearson = false
  }
}

const calcMatrix = async () => {
  if (matrixForm.value.codes.length < 2) return ElMessage.warning('至少选择2个资产')
  loading.value.matrix = true
  matrixResult.value = {}  // 清空旧结果
  try {
    const { start_date, end_date } = getGlobalDateParams()
    const params = {
      codes: matrixForm.value.codes,
      start_date,
      end_date
    }
    matrixResult.value = (await analysisCorrMatrix(params)).data
  } catch (e) {
    ElMessage.error('计算失败')
  } finally {
    loading.value.matrix = false
  }
}

const calcCCF = async () => {
  loading.value.ccf = true
  try {
    ccfResult.value = (await analysisCCF(ccfForm.value)).data
  } catch (e) {
    ElMessage.error('计算失败')
  } finally {
    loading.value.ccf = false
  }
}

const calcSeasonality = async () => {
  loading.value.season = true
  try {
    seasonResult.value = (await analysisSeasonality(seasonForm.value)).data
  } catch (e) {
    ElMessage.error('分析失败')
  } finally {
    loading.value.season = false
  }
}

const calcMomentum = async () => {
  loading.value.momentum = true
  try {
    momentumResult.value = (await analysisMomentumReversal(momentumForm.value)).data
  } catch (e) {
    ElMessage.error('分析失败')
  } finally {
    loading.value.momentum = false
  }
}

const calcReversion = async () => {
  loading.value.revert = true
  try {
    revertResult.value = (await analysisMeanReversion(revertForm.value)).data
  } catch (e) {
    ElMessage.error('分析失败')
  } finally {
    loading.value.revert = false
  }
}

const loadReport = async () => {
  loading.value.report = true
  try {
    reportResult.value = (await analysisQuickReport(reportForm.value)).data
  } catch (e) {
    ElMessage.error('生成报告失败')
  } finally {
    loading.value.report = false
  }
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

// K线图配置（与成交量融合显示）
const klineOption = computed(() => {
  if (!klineData.value.length) return {}
  const dates = klineData.value.map(d => d.date)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: [
      { left: '10%', right: '10%', top: '10%', height: '55%' },
      { left: '10%', right: '10%', top: '70%', height: '20%' }
    ],
    xAxis: [
      { type: 'category', data: dates, scale: true, boundaryGap: false, axisLine: { onZero: false }, splitLine: { show: false }, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, scale: true, boundaryGap: false, axisLine: { onZero: false }, axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: true } }
    ],
    yAxis: [
      { scale: true, splitArea: { show: true } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 50, end: 100, bottom: '5%' }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: klineData.value.map(d => [d.open, d.close, d.low, d.high]),
        itemStyle: { color: '#f56c6c', color0: '#67c23a', borderColor: '#f56c6c', borderColor0: '#67c23a' }
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: klineData.value.map(d => d.volume),
        itemStyle: { color: (params) => klineData.value[params.dataIndex]?.close >= klineData.value[params.dataIndex]?.open ? '#f56c6c' : '#67c23a' }
      }
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
  console.log('onMounted, calling loadCacheStatus')
  loadCacheStatus()
})

// 切换到数据查看Tab时自动加载缓存状态
watch(activeTab, (tab) => {
  console.log('activeTab changed to:', tab)
  if (tab === 'dataview') {
    console.log('calling loadCacheStatus from watch')
    loadCacheStatus()
  }
})

const handleTabClick = () => {
  console.log('Tab clicked, activeTab:', activeTab.value)
  if (activeTab.value === 'dataview') {
    console.log('Tab dataview active, calling loadCacheStatus')
    loadCacheStatus()
  }
}
</script>

<style scoped>
.stat-box { text-align: center; padding: 20px; }
.stat-num { font-size: 32px; font-weight: bold; color: #409eff; }
.stat-label { color: #909399; font-size: 14px; margin-top: 8px; }
.result-box { background: #f5f7fa; padding: 15px; border-radius: 4px; margin-top: 10px; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
