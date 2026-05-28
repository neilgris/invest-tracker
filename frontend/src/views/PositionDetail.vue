<template>
  <div>
    <!-- 顶部导航：左右箭头 + Select 切换 -->
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px">
      <el-button circle size="small" @click="goPrev" :disabled="!canGoPrev">
        <el-icon><Arrow-Left /></el-icon>
      </el-button>
      
      <el-select 
        v-model="selectedCode" 
        filterable 
        style="width: 280px"
        @change="onCodeChange"
      >
        <el-option 
          v-for="pos in allPositions" 
          :key="pos.code" 
          :label="`${pos.linked_short_name || pos.name} (${pos.code})`" 
          :value="pos.code" 
        />
      </el-select>
      
      <el-button circle size="small" @click="goNext" :disabled="!canGoNext">
        <el-icon><Arrow-Right /></el-icon>
      </el-button>
      
      <el-button text @click="$router.push('/')">返回总览</el-button>
    </div>

    <!-- 持仓统计与价格走势合并 -->
    <el-card shadow="hover" style="margin-bottom: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px">
          <div style="display: flex; align-items: center; gap: 16px">
            <span style="font-weight: 500; font-size: 15px">{{ detail.code }} {{ detail.linked_short_name || detail.name }}</span>
            <el-radio-group v-model="period" size="small" @change="onPeriodChange">
              <el-radio-button value="daily">日K</el-radio-button>
              <el-radio-button value="weekly">周K</el-radio-button>
              <el-radio-button value="monthly">月K</el-radio-button>
            </el-radio-group>
          </div>
          <div style="display: flex; align-items: center; gap: 10px">
            <el-radio-group v-model="chartMode" size="small" @change="onChartModeChangeWithSave">
              <el-radio-button value="price">净值</el-radio-button>
              <el-radio-button value="trend">趋势</el-radio-button>
              <el-radio-button value="compare">对比</el-radio-button>
            </el-radio-group>
            <template v-if="chartMode === 'trend'">
              <el-radio-group v-model="trendIndicator" size="small" @change="onTrendIndicatorChange">
                <el-radio-button value="ma">MA</el-radio-button>
                <el-radio-button value="adx">ADX</el-radio-button>
              </el-radio-group>
            </template>
            <template v-if="chartMode === 'compare'">
              <span style="font-size: 14px; color: #909399">基线:</span>
              <el-select v-model="baselineCode" size="small" style="width: 160px" @change="onBaselineChange">
                <el-option label="沪深300" value="000300" />
                <el-option label="中证500" value="000905" />
                <el-option label="中证1000" value="000852" />
                <el-option label="上证50" value="000016" />
              </el-select>
            </template>
          </div>
        </div>
      </template>
      <!-- 持仓统计与关联ETF信息 -->
      <div style="margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #ebeef5">
        <el-row :gutter="20">
          <el-col :span="4">
            <div class="stat-label">持仓数量</div>
            <div class="stat-value">{{ detail.quantity?.toFixed(2) }}</div>
          </el-col>
          <el-col :span="4">
            <div class="stat-label">平均成本</div>
            <div class="stat-value">{{ detail.avg_cost?.toFixed(4) }}</div>
          </el-col>
          <el-col :span="4">
            <div class="stat-label">总收益</div>
            <div class="stat-value" :class="detail.total_pnl >= 0 ? 'profit' : 'loss'">
              {{ detail.total_pnl >= 0 ? '+' : '' }}¥{{ detail.total_pnl?.toLocaleString() }}
            </div>
          </el-col>
          <el-col :span="4">
            <div class="stat-label">收益率</div>
            <div class="stat-value" :class="detail.total_pnl_pct >= 0 ? 'profit' : 'loss'">
              {{ detail.total_pnl_pct >= 0 ? '+' : '' }}{{ detail.total_pnl_pct }}%
            </div>
          </el-col>
          <el-col :span="4">
            <div class="stat-label">利润状态</div>
            <div class="stat-value">
              <el-tooltip v-if="profitStatus" placement="top" :show-after="200">
                <template #content>
                  <div style="max-width: 320px; line-height: 1.6;">
                    <div style="font-weight: bold; margin-bottom: 4px;">📊 当前状态匹配</div>
                    <div style="margin-bottom: 8px; padding: 6px; background: rgba(255,255,255,0.1); border-radius: 4px;">
                      <div>档位: <b>{{ profitStatus.code }} {{ profitStatus.status }}</b></div>
                      <div>条件: {{ profitStatus.matchCondition }}</div>
                      <div style="margin-top: 4px; font-size: 11px; color: #ccc;">
                        峰值浮盈 {{ profitStatus.pnlPeak > 0 ? '+' : '' }}{{ profitStatus.pnlPeak }}% / 
                        当前浮盈 {{ profitStatus.pnlNow > 0 ? '+' : '' }}{{ profitStatus.pnlNow }}% / 
                        持仓 {{ profitStatus.holdDays }}天
                      </div>
                    </div>
                    <div v-if="profitStatus.stopLossStrategy" style="font-weight: bold; margin-bottom: 4px;">🎯 止盈策略</div>
                    <div v-if="profitStatus.stopLossStrategy" style="padding: 6px; background: rgba(255,255,255,0.1); border-radius: 4px;">
                      <div>策略: {{ profitStatus.stopLossStrategy.name }}</div>
                      <div>减半仓线: <b>{{ profitStatus.stopLossStrategy.halfLine }}</b></div>
                      <div>清仓线: <b>{{ profitStatus.stopLossStrategy.clearLine }}</b></div>
                      <div style="margin-top: 4px; font-size: 11px; color: #ccc;">{{ profitStatus.stopLossStrategy.desc }}</div>
                    </div>
                    <div v-else style="color: #ccc; font-size: 11px;">当前档位不设止盈线</div>
                  </div>
                </template>
                <el-tag :type="profitStatus.type" size="small" effect="dark" style="font-size: 12px; cursor: pointer;">
                  {{ profitStatus.code }} {{ profitStatus.status }}
                </el-tag>
              </el-tooltip>
              <span v-else style="color: #909399">-</span>
            </div>
            <div v-if="profitStatus" style="font-size: 11px; color: #909399; margin-top: 2px">
              峰值 {{ profitStatus.pnlPeak > 0 ? '+' : '' }}{{ profitStatus.pnlPeak }}% / 当前 {{ profitStatus.pnlNow > 0 ? '+' : '' }}{{ profitStatus.pnlNow }}% / 持仓 {{ profitStatus.holdDays }}天
            </div>
          </el-col>
          <el-col :span="4" style="text-align: right; display: flex; align-items: center; justify-content: flex-end;">
            <div v-if="detail.linked_info" style="font-size: 13px">
              <span style="color: #909399">关联: {{ detail.linked_info.code }} {{ detail.linked_info.name }}</span>
              <el-button size="small" type="danger" text @click="clearLinked" style="margin-left: 8px;">取消关联</el-button>
            </div>
            <div v-else-if="!isEtf" style="font-size: 13px">
              <span style="color: #909399">未关联场内ETF</span>
              <el-button size="small" type="primary" @click="showLinkDialog = true" style="margin-left: 8px;">关联</el-button>
            </div>
          </el-col>
        </el-row>
      </div>
      <v-chart :option="chartOption" style="height: 400px" autoresize @dataZoom="onDataZoom" @legendselectchanged="onLegendSelectChanged" />
    </el-card>

    <!-- 关联ETF对话框 -->
    <el-dialog v-model="showLinkDialog" title="关联场内ETF" width="600px">
      <div style="margin-bottom: 16px">
        <el-button size="small" type="primary" @click="loadSuggestions" :loading="suggestLoading">获取推荐</el-button>
      </div>
      <div v-if="suggestions.length" style="margin-bottom: 16px">
        <div style="color: #909399; font-size: 13px; margin-bottom: 8px">推荐的场内ETF：</div>
        <el-table :data="suggestions" size="small" @row-click="selectSuggestion" highlight-current-row>
          <el-table-column prop="code" label="代码" width="100" />
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="score" label="匹配度" width="80">
            <template #default="{ row }">{{ (row.score * 100).toFixed(0) }}%</template>
          </el-table-column>
        </el-table>
      </div>
      <el-form label-width="80px">
        <el-form-item label="ETF代码">
          <el-input v-model="linkCode" placeholder="输入场内ETF代码，如518880" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showLinkDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmLink" :disabled="!linkCode">确认关联</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { getPositionDetail, getPositionChart, updatePositionLinkedCode, suggestLinkedEtf, getPositions } from '../api'
import axios from 'axios'

const route = useRoute()
const router = useRouter()
const code = computed(() => route.params.code)
const selectedCode = ref(route.params.code)
const allPositions = ref([])
const detail = ref({})
const chartData = ref({ prices: [], markers: [], baseline: [] })
const period = ref('daily')
const baselineCode = ref('000300')
const chartMode = ref('price')  // 'price' = 净值模式, 'trend' = 趋势模式, 'compare' = 对比模式
const trendIndicator = ref('ma')  // 'ma' = MA指标, 'adx' = ADX指标（仅在趋势模式下有效）

// 当前图表视图范围（响应dataZoom事件）
const viewRange = ref({ start: 0, end: 100 })

// 图例选择状态（持久化到 sessionStorage）
const legendSelected = ref({})

// 显示的K线数量（用于切换标的时保持相对范围）
const visibleBarCount = ref(null)

// sessionStorage key
const STORAGE_KEY_VIEW_RANGE = 'position_detail_view_range'
const STORAGE_KEY_LEGEND_SELECTED = 'position_detail_legend_selected'
const STORAGE_KEY_CHART_MODE = 'position_detail_chart_mode'
const STORAGE_KEY_VISIBLE_BAR_COUNT = 'position_detail_visible_bar_count'

// 从 sessionStorage 加载状态
const loadPersistedState = () => {
  try {
    const savedViewRange = sessionStorage.getItem(STORAGE_KEY_VIEW_RANGE)
    if (savedViewRange) {
      viewRange.value = JSON.parse(savedViewRange)
    }
    const savedLegendSelected = sessionStorage.getItem(STORAGE_KEY_LEGEND_SELECTED)
    if (savedLegendSelected) {
      legendSelected.value = JSON.parse(savedLegendSelected)
    }
    const savedChartMode = sessionStorage.getItem(STORAGE_KEY_CHART_MODE)
    if (savedChartMode) {
      chartMode.value = savedChartMode
    }
    const savedBarCount = sessionStorage.getItem(STORAGE_KEY_VISIBLE_BAR_COUNT)
    if (savedBarCount) {
      visibleBarCount.value = parseInt(savedBarCount, 10)
    }
  } catch (e) {
    console.error('加载持久化状态失败', e)
  }
}

// 保存状态到 sessionStorage
const saveViewRange = () => {
  try {
    sessionStorage.setItem(STORAGE_KEY_VIEW_RANGE, JSON.stringify(viewRange.value))
  } catch (e) {
    console.error('保存视图范围失败', e)
  }
}

const saveVisibleBarCount = () => {
  try {
    if (visibleBarCount.value !== null) {
      sessionStorage.setItem(STORAGE_KEY_VISIBLE_BAR_COUNT, visibleBarCount.value.toString())
    }
  } catch (e) {
    console.error('保存K线数量失败', e)
  }
}

const saveLegendSelected = () => {
  try {
    sessionStorage.setItem(STORAGE_KEY_LEGEND_SELECTED, JSON.stringify(legendSelected.value))
  } catch (e) {
    console.error('保存图例选择失败', e)
  }
}

const saveChartMode = () => {
  try {
    sessionStorage.setItem(STORAGE_KEY_CHART_MODE, chartMode.value)
  } catch (e) {
    console.error('保存图表模式失败', e)
  }
}

// 趋势指标切换
const onTrendIndicatorChange = () => {
  // 切换指标时重置图例选择，让新指标默认显示
  legendSelected.value = {}
  saveLegendSelected()
}

// 关联ETF相关状态
const showLinkDialog = ref(false)
const linkCode = ref('')
const linkName = ref('')
const suggestions = ref([])
const suggestLoading = ref(false)

// 配置
const stopLossConfigs = ref([])
const profitLevels = ref([])

const isEtf = computed(() => code.value?.startsWith('5') || code.value?.startsWith('15'))

// 利润状态计算（从配置读取）
const profitStatus = computed(() => {
  const prices = chartData.value.prices
  const markers = chartData.value.markers
  const avgCost = detail.value.avg_cost || 0

  if (!prices.length || avgCost <= 0) return null

  // 找到第一个买入日期
  const buyMarkers = markers.filter(m => m.direction === 'buy')
  if (buyMarkers.length === 0) return null

  const firstBuyDate = buyMarkers.sort((a, b) => a.date.localeCompare(b.date))[0].date
  const firstBuyIdx = prices.findIndex(p => p.date >= firstBuyDate)
  if (firstBuyIdx < 0) return null

  // 持仓期间最高净值
  const histPrices = prices.slice(firstBuyIdx).map(p => p.close)
  const pMax = Math.max(...histPrices)
  const pNow = prices[prices.length - 1]?.close || 0

  // 计算浮盈率
  const pnlPeak = (pMax - avgCost) / avgCost * 100  // 历史峰值浮盈率
  const pnlNow = (pNow - avgCost) / avgCost * 100   // 当前浮盈率

  // 计算持仓天数（从第一个买入日期到今天）
  const today = new Date()
  const firstBuy = new Date(firstBuyDate)
  const holdDays = Math.floor((today - firstBuy) / (1000 * 60 * 60 * 24))

  // 从配置匹配利润等级
  const levels = profitLevels.value
  if (!levels || levels.length === 0) {
    // 配置未加载时使用默认规则
    return getDefaultProfitStatus(pnlPeak, pnlNow, holdDays)
  }

  // 按优先级排序后匹配（范围匹配：threshold_min <= value < threshold_max）
  // 特殊处理：L1/L2 共用 -10%~0% 区间，根据 hold_days 区分
  const sortedLevels = [...levels].sort((a, b) => a.sort_order - b.sort_order)
  for (const level of sortedLevels) {
    const thresholdMin = level.pnl_threshold
    const thresholdMax = level.pnl_threshold_max !== null && level.pnl_threshold_max !== undefined
      ? level.pnl_threshold_max
      : Infinity
    const value = level.use_peak_pnl ? pnlPeak : pnlNow

    // 检查是否在阈值范围内
    if (value >= thresholdMin && value < thresholdMax) {
      // 持仓天数判断: hold_days_min <= hold_days < hold_days_max
      // null/undefined 表示无限制
      if (level.hold_days_min !== null && level.hold_days_min !== undefined && holdDays < level.hold_days_min) {
        continue  // 不满足最小天数要求
      }
      if (level.hold_days_max !== null && level.hold_days_max !== undefined && holdDays >= level.hold_days_max) {
        continue  // 超过最大天数限制
      }

      // 构建匹配条件描述
      const valueLabel = level.use_peak_pnl ? '峰值浮盈率' : '当前浮盈率'
      const valueNum = level.use_peak_pnl ? pnlPeak : pnlNow
      let matchCondition = `${valueLabel} ${valueNum.toFixed(1)}% 满足 `
      if (thresholdMax === Infinity || thresholdMax === null) {
        matchCondition += `≥ ${thresholdMin}%`
      } else {
        matchCondition += `${thresholdMin}% ≤ ${valueLabel} < ${thresholdMax}%`
      }
      // 持仓天数条件描述
      if (level.hold_days_min !== null && level.hold_days_min !== undefined && level.hold_days_max !== null && level.hold_days_max !== undefined) {
        matchCondition += `, 且 ${level.hold_days_min} ≤ 持仓 < ${level.hold_days_max}天`
      } else if (level.hold_days_min !== null && level.hold_days_min !== undefined) {
        matchCondition += `, 且持仓 ≥ ${level.hold_days_min}天`
      } else if (level.hold_days_max !== null && level.hold_days_max !== undefined) {
        matchCondition += `, 且持仓 < ${level.hold_days_max}天`
      }

      // 查找对应的止盈策略
      const stopLossConfig = stopLossConfigs.value.find(c => c.profit_level_key === level.level_key)
      let stopLossStrategy = null
      if (stopLossConfig) {
        const avgCost = detail.value.avg_cost || 0
        const calcMode = stopLossConfig.calculation_mode
        
        if (calcMode === 'profit_retention') {
          // 基于 Profit_max 保留比例 (F1.1, F2)
          const retentionHalf = stopLossConfig.profit_retention_half || 0
          const retentionClear = stopLossConfig.profit_retention_clear || 0
          const halfPrice = avgCost + (pMax - avgCost) * retentionHalf
          const clearPrice = avgCost + (pMax - avgCost) * retentionClear
          stopLossStrategy = {
            name: 'Profit_max保留比例',
            halfLine: `¥${halfPrice.toFixed(3)} (保留${(retentionHalf*100).toFixed(0)}%浮盈)`,
            clearLine: `¥${clearPrice.toFixed(3)} (保留${(retentionClear*100).toFixed(0)}%浮盈)`,
            desc: `以持仓后最高点¥${pMax.toFixed(3)}为基准，保留相应比例浮盈`
          }
        } else if (calcMode === 'cost_protection') {
          // 基于成本保护 (F3, L1, L2)
          const halfRatio = stopLossConfig.half_position_ratio
          const clearRatio = stopLossConfig.clear_position_ratio
          const halfPrice = avgCost * halfRatio
          const clearPrice = avgCost * clearRatio
          const halfDrop = (1 - halfRatio) * 100
          const clearDrop = (1 - clearRatio) * 100
          stopLossStrategy = {
            name: '成本保护策略',
            halfLine: `¥${halfPrice.toFixed(3)} (跌破${halfDrop.toFixed(0)}%)`,
            clearLine: `¥${clearPrice.toFixed(3)} (跌破${clearDrop.toFixed(0)}%)`,
            desc: `以成本价¥${avgCost.toFixed(3)}为基准，跌破相应比例触发`
          }
        } else if (calcMode === 'pmax_drawdown' && stopLossConfig.half_position_ratio && stopLossConfig.clear_position_ratio) {
          // 基于 Pmax 回撤 (F1.3, F1.2)
          const halfRatio = stopLossConfig.half_position_ratio
          const clearRatio = stopLossConfig.clear_position_ratio
          const halfPrice = pMax * halfRatio
          const clearPrice = pMax * clearRatio
          const halfDrawdown = (1 - halfRatio) * 100
          const clearDrawdown = (1 - clearRatio) * 100
          stopLossStrategy = {
            name: 'Pmax回撤策略',
            halfLine: `¥${halfPrice.toFixed(3)} (回撤${halfDrawdown.toFixed(0)}%)`,
            clearLine: `¥${clearPrice.toFixed(3)} (回撤${clearDrawdown.toFixed(0)}%)`,
            desc: `以持仓后最高点¥${pMax.toFixed(3)}为基准，回撤相应比例触发`
          }
        } else {
          stopLossStrategy = null
        }
      }

      return {
        status: level.level_name,
        code: level.level_code,
        levelKey: level.level_key,
        type: level.display_color,
        color: level.display_color === 'success' ? '#67c23a' : level.display_color === 'warning' ? '#e6a23c' : '#f56c6c',
        pnlPeak: pnlPeak.toFixed(1),
        pnlNow: pnlNow.toFixed(1),
        holdDays: holdDays,
        matchCondition,
        stopLossStrategy
      }
    }
  }

  // 默认返回最后一个
  const lastLevel = sortedLevels[sortedLevels.length - 1]
  return {
    status: lastLevel?.level_name || '未知',
    code: lastLevel?.level_code || '',
    levelKey: lastLevel?.level_key || '',
    type: lastLevel?.display_color || 'info',
    color: '#909399',
    pnlPeak: pnlPeak.toFixed(1),
    pnlNow: pnlNow.toFixed(1),
    holdDays: holdDays,
    matchCondition: '未匹配到任何档位',
    stopLossStrategy: null
  }
})

// 默认利润状态（配置未加载时）
// 档位规则：
// F1.3: PnL_peak ≥ 200%, 极厚利润
// F1.2: PnL_peak ≥ 100%, 中厚利润
// F1.1: PnL_peak ≥ 50%, 浅厚利润
// F2: PnL_peak ≥ 25%, 中利润
// F3: PnL_now ≥ 0, 薄利润
// L1: PnL_now ≥ -10% 且 Hold_days < 60, 新建仓宽容
// L2: PnL_now ≥ -10% 且 Hold_days ≥ 60, 薄亏损观察
// L3: PnL_now ≥ -30%, 中亏损决策
// L4: PnL_now ≥ -100%, 厚亏损清仓
const getDefaultProfitStatus = (pnlPeak, pnlNow, holdDays = 0) => {
  let status = '', code = '', type = '', color = ''

  if (pnlPeak >= 200) {
    status = '极厚利润'; code = 'F1.3'; type = 'success'; color = '#67c23a'
  } else if (pnlPeak >= 100) {
    status = '中厚利润'; code = 'F1.2'; type = 'success'; color = '#67c23a'
  } else if (pnlPeak >= 50) {
    status = '浅厚利润'; code = 'F1.1'; type = 'success'; color = '#67c23a'
  } else if (pnlPeak >= 25) {
    status = '中利润'; code = 'F2'; type = 'success'; color = '#67c23a'
  } else if (pnlNow >= 0) {
    status = '薄利润'; code = 'F3'; type = 'warning'; color = '#e6a23c'
  } else if (pnlNow >= -10) {
    // L1/L2 根据 hold_days 区分
    if (holdDays < 60) {
      status = '新建仓宽容'; code = 'L1'; type = 'warning'; color = '#e6a23c'
    } else {
      status = '薄亏损观察'; code = 'L2'; type = 'warning'; color = '#e6a23c'
    }
  } else if (pnlNow >= -30) {
    status = '中亏损决策'; code = 'L3'; type = 'danger'; color = '#f56c6c'
  } else {
    status = '厚亏损清仓'; code = 'L4'; type = 'danger'; color = '#f56c6c'
  }

  return { status, code, type, color, pnlPeak: pnlPeak.toFixed(1), pnlNow: pnlNow.toFixed(1), holdDays }
}

// 计算 dataZoom 初始范围：日视图默认显示近1年，周/月视图全部显示
// 注意：此函数只用于初始化 viewRange，不应在 computed 中修改 ref
const calculateInitialRange = () => {
  const prices = chartData.value.prices
  const len = prices.length
  if (len === 0) return { start: 0, end: 100 }

  if (period.value === 'daily') {
    // 日视图：默认显示近1年
    const oneYearAgo = new Date()
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1)
    const oneYearStr = oneYearAgo.toISOString().slice(0, 10)
    const idx = prices.findIndex(p => p.date >= oneYearStr)
    if (idx <= 0) return { start: 0, end: 100 }  // 全部数据都在1年内
    const startPercent = Math.round(idx / len * 100)
    return { start: startPercent, end: 100 }
  }

  // 周/月视图：全部显示
  return { start: 0, end: 100 }
}

// 净值模式图表配置
const buildPriceModeChart = (dates, closes, markers, safeStartIdx, safeEndIdx) => {
  const etfName = detail.value.short_name || detail.value.name || code.value

  // 找到第一个买入日期
  const buyMarkers = markers.filter(m => m.direction === 'buy')
  let firstBuyDate = null
  if (buyMarkers.length > 0) {
    firstBuyDate = buyMarkers.sort((a, b) => a.date.localeCompare(b.date))[0].date
  }

  // 找到第一个买入点在dates中的索引
  let firstBuyIdx = 0
  if (firstBuyDate) {
    firstBuyIdx = dates.findIndex(d => d >= firstBuyDate)
    if (firstBuyIdx < 0) firstBuyIdx = 0
  }

  // 成本价
  const avgCost = detail.value.avg_cost || 0

  // 计算Pmax（持仓后第一个买入点之后的最高净值）
  const histPrices = closes.slice(firstBuyIdx, safeEndIdx + 1)
  const pmax = histPrices.length > 0 ? Math.max(...histPrices) : 0

  // 使用 profitStatus 判断是否有止盈线配置（L3/L4厚亏损档位不显示止盈线）
  const currentProfitStatus = profitStatus.value
  const hasStopLoss = currentProfitStatus && currentProfitStatus.stopLossStrategy !== null && currentProfitStatus.stopLossStrategy !== undefined

  // 计算Profit_max（最高浮盈金额）
  const profitMax = pmax - avgCost
  const pnlPeak = avgCost > 0 ? ((pmax - avgCost) / avgCost * 100) : 0

  // 根据利润厚度计算止盈线价格（使用后端配置）
  let halfPositionPrice = 0
  let clearPositionPrice = 0
  let profitLevel = currentProfitStatus ? currentProfitStatus.status : '' // 用于tooltip显示利润层级

  if (hasStopLoss && avgCost > 0) {
    // 从 profitStatus 获取对应的止盈配置
    const stopLossConfig = stopLossConfigs.value.find(c => c.profit_level_key === currentProfitStatus.levelKey)
    
    if (stopLossConfig) {
      const calcMode = stopLossConfig.calculation_mode
      if (calcMode === 'profit_retention') {
        // F1.1/F2: 基于Profit_max保留比例计算
        const retentionHalf = stopLossConfig.profit_retention_half !== null ? stopLossConfig.profit_retention_half : 0.5
        const retentionClear = stopLossConfig.profit_retention_clear !== null ? stopLossConfig.profit_retention_clear : 0.3
        halfPositionPrice = avgCost + profitMax * retentionHalf
        clearPositionPrice = avgCost + profitMax * retentionClear
      } else if (calcMode === 'cost_protection') {
        // F3/L1/L2: 薄利润/亏损观察，成本保护，基于avg_cost
        halfPositionPrice = avgCost * (stopLossConfig.half_position_ratio || 0.97)
        clearPositionPrice = avgCost * (stopLossConfig.clear_position_ratio || 0.92)
      } else {
        // F1.3/F1.2: 厚利润，基于Pmax回撤 (pmax_drawdown或其他)
        halfPositionPrice = pmax * (stopLossConfig.half_position_ratio || 1.0)
        clearPositionPrice = pmax * (stopLossConfig.clear_position_ratio || 1.0)
      }
    }
  }

  // 计算Y轴范围（包含成本价和止盈线）
  const viewValues = closes.slice(safeStartIdx, safeEndIdx + 1)
  const viewMinPrice = Math.min(...viewValues)
  const viewMaxPrice = Math.max(...viewValues)
  let allMin = Math.min(viewMinPrice, avgCost > 0 ? avgCost : Infinity)
  let allMax = Math.max(viewMaxPrice, avgCost > 0 ? avgCost : 0)
  // 有止盈线配置时包含止盈线
  if (hasStopLoss) {
    allMin = Math.min(allMin, clearPositionPrice)
    allMax = Math.max(allMax, halfPositionPrice)
  }
  const priceRange = allMax - allMin || 1
  const yMin = allMin - priceRange * 0.05
  const yMax = allMax + priceRange * 0.05

  // 日期索引映射
  const dateToIdx = new Map(dates.map((d, i) => [d, i]))
  const findClosestIdx = (markerDate) => {
    if (dateToIdx.has(markerDate)) return dateToIdx.get(markerDate)
    for (let i = dates.length - 1; i >= 0; i--) {
      if (dates[i] <= markerDate) return i
    }
    return 0
  }

  // 预计算持仓期间最高点（前缀最大值数组）- 用于优化tooltip性能
  const histMaxArray = new Array(closes.length).fill(0)
  let runningMax = 0
  for (let i = 0; i < closes.length; i++) {
    if (i >= firstBuyIdx) {
      runningMax = Math.max(runningMax, closes[i])
    }
    histMaxArray[i] = runningMax
  }

  // 标记点（只显示在视图范围内）
  const buyMarkerPoints = markers.filter(m => m.direction === 'buy').map(m => {
    const idx = findClosestIdx(m.date)
    if (idx < safeStartIdx || idx > safeEndIdx) return null
    return {
      coord: [dates[idx], closes[idx]],
      symbol: 'triangle',
      symbolSize: 12,
      itemStyle: { color: '#67c23a' },
      label: { show: false },
    }
  }).filter(m => m !== null)
  const sellMarkerPoints = markers.filter(m => m.direction === 'sell').map(m => {
    const idx = findClosestIdx(m.date)
    if (idx < safeStartIdx || idx > safeEndIdx) return null
    return {
      coord: [dates[idx], closes[idx]],
      symbol: 'triangle',
      symbolRotate: 180,
      symbolSize: 12,
      itemStyle: { color: '#f56c6c' },
      label: { show: false },
    }
  }).filter(m => m !== null)
  const divMarkerPoints = markers.filter(m => m.direction === 'dividend').map(m => {
    const idx = findClosestIdx(m.date)
    if (idx < safeStartIdx || idx > safeEndIdx) return null
    return {
      coord: [dates[idx], closes[idx]],
      symbol: 'diamond',
      symbolSize: 10,
      itemStyle: { color: '#e6a23c' },
      label: { show: false },
    }
  }).filter(m => m !== null)

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const date = params[0].axisValue
        const price = params[0].value
        // 找到当前日期索引
        const dateIdx = dates.indexOf(date)
        // 使用预计算的持仓期间最高点数组（O(1)查询，替代O(n)切片+展开）
        const histMax = dateIdx >= 0 ? histMaxArray[dateIdx] : price
        const drawdown = histMax > 0 ? ((histMax - price) / histMax * 100).toFixed(2) : '0.00'
        // 计算相对于成本价的盈亏
        const pnlPct = avgCost > 0 ? ((price - avgCost) / avgCost * 100).toFixed(2) : '0.00'

        let html = `<div style="font-weight:bold;margin-bottom:5px">${date}</div>`
        html += `<div>${params[0].marker} ${etfName}: <b>¥${price?.toFixed(3) || '-'}</b></div>`
        html += `<div style="margin-top:5px;color:#909399;font-size:11px">`
        html += `持仓最高: ¥${histMax.toFixed(3)} | 回撤: ${drawdown}% | 成本: ¥${avgCost.toFixed(3)}(${pnlPct > 0 ? '+' : ''}${pnlPct}%)`
        // 满足止盈条件时显示止盈线信息
        if (hasStopLoss) {
          if (pnlPeak < 25) {
            // 薄利润：成本保护，显示跌破成本的百分比
            const dropHalf = ((avgCost - halfPositionPrice) / avgCost * 100).toFixed(1)
            const dropClear = ((avgCost - clearPositionPrice) / avgCost * 100).toFixed(1)
            html += `<br/>[${profitLevel}] 减半仓线: ¥${halfPositionPrice.toFixed(3)}(跌破${dropHalf}%) | 清仓线: ¥${clearPositionPrice.toFixed(3)}(跌破${dropClear}%)`
          } else {
            // 中利润及以上：基于Pmax回撤
            const drawdownHalf = ((pmax - halfPositionPrice) / pmax * 100).toFixed(1)
            const drawdownClear = ((pmax - clearPositionPrice) / pmax * 100).toFixed(1)
            html += `<br/>[${profitLevel}] 减半仓线: ¥${halfPositionPrice.toFixed(3)}(回撤${drawdownHalf}%) | 清仓线: ¥${clearPositionPrice.toFixed(3)}(回撤${drawdownClear}%)`
          }
        }
        html += `</div>`
        return html
      }
    },
    legend: { data: hasStopLoss ? [etfName, '成本价', '减半仓线', '清仓线'] : [etfName, '成本价'], top: 10, selected: legendSelected.value },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        rotate: dates.length > 30 ? 30 : 0,
        fontSize: 11,
      },
    },
    yAxis: {
      type: 'value',
      name: '净值',
      min: yMin,
      max: yMax,
      axisLabel: { formatter: (v) => '¥' + v.toFixed(2) },
    },
    dataZoom: [
      {
        type: 'inside',
        start: viewRange.value.start,
        end: viewRange.value.end,
      },
      {
        type: 'slider',
        start: viewRange.value.start,
        end: viewRange.value.end,
        height: 20,
        bottom: 5,
      },
    ],
    series: [
      {
        name: etfName,
        type: 'line',
        data: closes,
        smooth: true,
        lineStyle: { width: 2 },
        markPoint: { data: [...buyMarkerPoints, ...sellMarkerPoints, ...divMarkerPoints] },
      },
      ...(avgCost > 0 ? [{
        name: '成本价',
        type: 'line',
        data: dates.map(() => avgCost),
        smooth: false,
        lineStyle: { type: 'dotted', width: 2, color: '#409eff' },
        symbol: 'none',
        silent: true,
      }] : []),
      // 有止盈线配置时显示
      ...(hasStopLoss ? [
        {
          name: '减半仓线',
          type: 'line',
          data: dates.map(() => halfPositionPrice),
          smooth: false,
          lineStyle: { type: 'dashed', width: 2, color: '#e6a23c' },
          symbol: 'none',
          silent: true,
        },
        {
          name: '清仓线',
          type: 'line',
          data: dates.map(() => clearPositionPrice),
          smooth: false,
          lineStyle: { type: 'dashed', width: 2, color: '#f56c6c' },
          symbol: 'none',
          silent: true,
        }
      ] : []),
    ],
    grid: { left: '3%', right: '4%', top: 60, bottom: 60, containLabel: true },
  }
}

// 计算移动平均线
const calculateMA = (data, period) => {
  const ma = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      ma.push(null) // 数据不足时返回null
    } else {
      let sum = 0
      for (let j = 0; j < period; j++) {
        sum += data[i - j]
      }
      ma.push(sum / period)
    }
  }
  return ma
}

// 计算 ADX（平均趋向指数）
const calculateADX = (highs, lows, closes, period = 14) => {
  const len = closes.length
  if (len < period + 1) return { adx: new Array(len).fill(null), plusDI: new Array(len).fill(null), minusDI: new Array(len).fill(null) }

  const tr = new Array(len).fill(0)  // True Range
  const plusDM = new Array(len).fill(0)  // +DM
  const minusDM = new Array(len).fill(0)  // -DM

  // 计算 TR, +DM, -DM
  for (let i = 1; i < len; i++) {
    const highDiff = highs[i] - highs[i - 1]
    const lowDiff = lows[i - 1] - lows[i]

    // True Range
    const tr1 = highs[i] - lows[i]
    const tr2 = Math.abs(highs[i] - closes[i - 1])
    const tr3 = Math.abs(lows[i] - closes[i - 1])
    tr[i] = Math.max(tr1, tr2, tr3)

    // +DM 和 -DM
    if (highDiff > lowDiff && highDiff > 0) {
      plusDM[i] = highDiff
    } else {
      plusDM[i] = 0
    }

    if (lowDiff > highDiff && lowDiff > 0) {
      minusDM[i] = lowDiff
    } else {
      minusDM[i] = 0
    }
  }

  // 计算平滑后的 TR, +DM, -DM
  const atr = new Array(len).fill(null)
  const smoothPlusDM = new Array(len).fill(null)
  const smoothMinusDM = new Array(len).fill(null)

  // 第一个平滑值用简单平均
  let sumTR = 0, sumPlusDM = 0, sumMinusDM = 0
  for (let i = 1; i <= period; i++) {
    sumTR += tr[i]
    sumPlusDM += plusDM[i]
    sumMinusDM += minusDM[i]
  }
  atr[period] = sumTR / period
  smoothPlusDM[period] = sumPlusDM / period
  smoothMinusDM[period] = sumMinusDM / period

  // 后续使用平滑公式
  for (let i = period + 1; i < len; i++) {
    atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    smoothPlusDM[i] = (smoothPlusDM[i - 1] * (period - 1) + plusDM[i]) / period
    smoothMinusDM[i] = (smoothMinusDM[i - 1] * (period - 1) + minusDM[i]) / period
  }

  // 计算 +DI 和 -DI
  const plusDI = new Array(len).fill(null)
  const minusDI = new Array(len).fill(null)
  for (let i = period; i < len; i++) {
    if (atr[i] > 0) {
      plusDI[i] = (smoothPlusDM[i] / atr[i]) * 100
      minusDI[i] = (smoothMinusDM[i] / atr[i]) * 100
    }
  }

  // 计算 DX 和 ADX
  const dx = new Array(len).fill(null)
  for (let i = period; i < len; i++) {
    const diSum = plusDI[i] + minusDI[i]
    if (diSum > 0) {
      dx[i] = (Math.abs(plusDI[i] - minusDI[i]) / diSum) * 100
    }
  }

  const adx = new Array(len).fill(null)
  // 第一个 ADX 用 DX 的简单平均
  let sumDX = 0
  let dxCount = 0
  for (let i = period; i < period + period && i < len; i++) {
    if (dx[i] !== null) {
      sumDX += dx[i]
      dxCount++
    }
  }
  if (dxCount > 0) {
    adx[period + period - 1] = sumDX / dxCount
  }

  // 后续使用平滑公式
  for (let i = period + period; i < len; i++) {
    adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period
  }

  return { adx, plusDI, minusDI }
}

// 趋势模式：显示主指标线 + MA5/MA20/MA60/MA120 + ADX
const buildTrendModeChart = (dates, closes, highs, lows, markers, safeStartIdx, safeEndIdx) => {
  const etfName = detail.value.short_name || detail.value.name || code.value

  // 计算各周期均线
  const ma5 = calculateMA(closes, 5)
  const ma20 = calculateMA(closes, 20)
  const ma60 = calculateMA(closes, 60)
  const ma120 = calculateMA(closes, 120)

  // 计算 ADX
  const { adx, plusDI, minusDI } = calculateADX(highs, lows, closes, 14)

  // 买卖标记点
  const dateToIdx = new Map(dates.map((d, i) => [d, i]))
  const findClosestIdx = (markerDate) => {
    if (dateToIdx.has(markerDate)) return dateToIdx.get(markerDate)
    for (let i = dates.length - 1; i >= 0; i--) {
      if (dates[i] <= markerDate) return i
    }
    return 0
  }

  const buyMarkerPoints = markers.filter(m => m.direction === 'buy').map(m => {
    const idx = findClosestIdx(m.date)
    if (idx < safeStartIdx || idx > safeEndIdx) return null
    return {
      coord: [dates[idx], closes[idx]],
      symbol: 'triangle',
      symbolSize: 12,
      itemStyle: { color: '#67c23a' },
      label: { show: false },
    }
  }).filter(m => m !== null)

  const sellMarkerPoints = markers.filter(m => m.direction === 'sell').map(m => {
    const idx = findClosestIdx(m.date)
    if (idx < safeStartIdx || idx > safeEndIdx) return null
    return {
      coord: [dates[idx], closes[idx]],
      symbol: 'triangle',
      symbolRotate: 180,
      symbolSize: 12,
      itemStyle: { color: '#f56c6c' },
      label: { show: false },
    }
  }).filter(m => m !== null)

  const divMarkerPoints = markers.filter(m => m.direction === 'dividend').map(m => {
    const idx = findClosestIdx(m.date)
    if (idx < safeStartIdx || idx > safeEndIdx) return null
    return {
      coord: [dates[idx], closes[idx]],
      symbol: 'diamond',
      symbolSize: 10,
      itemStyle: { color: '#e6a23c' },
      label: { show: false },
    }
  }).filter(m => m !== null)

  // 计算Y轴范围
  const viewPrices = closes.slice(safeStartIdx, safeEndIdx + 1)
  const priceMin = Math.min(...viewPrices)
  const priceMax = Math.max(...viewPrices)
  const priceRange = priceMax - priceMin || 1
  const yMin = priceMin - priceRange * 0.05
  const yMax = priceMax + priceRange * 0.05

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const date = params[0].axisValue
        let html = `<div style="font-weight:bold;margin-bottom:5px">${date}</div>`
        params.forEach(p => {
          const val = p.value?.toFixed(3) || '-'
          if (p.seriesName === 'ADX' || p.seriesName === '+DI' || p.seriesName === '-DI') {
            html += `<div>${p.marker} ${p.seriesName}: <b>${val}</b></div>`
          } else {
            html += `<div>${p.marker} ${p.seriesName}: <b>¥${val}</b></div>`
          }
        })
        return html
      }
    },
    legend: { 
      data: trendIndicator.value === 'ma' 
        ? [etfName, 'MA5', 'MA20', 'MA60', 'MA120']
        : [etfName, 'ADX', '+DI', '-DI'], 
      top: 10, 
      selected: legendSelected.value 
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        rotate: dates.length > 30 ? 30 : 0,
        fontSize: 11,
      },
    },
    yAxis: trendIndicator.value === 'ma'
      ? [
          {
            type: 'value',
            name: '净值',
            min: yMin,
            max: yMax,
            axisLabel: { formatter: (v) => '¥' + v.toFixed(2) },
          },
        ]
      : [
          {
            type: 'value',
            name: '净值',
            min: yMin,
            max: yMax,
            axisLabel: { formatter: (v) => '¥' + v.toFixed(2) },
          },
          {
            type: 'value',
            name: 'ADX',
            min: 0,
            max: 100,
            position: 'right',
            axisLabel: { formatter: (v) => v.toFixed(0) },
            splitLine: { show: false },
          },
        ],
    dataZoom: [
      {
        type: 'inside',
        start: viewRange.value.start,
        end: viewRange.value.end,
      },
      {
        type: 'slider',
        start: viewRange.value.start,
        end: viewRange.value.end,
        height: 20,
        bottom: 5,
      },
    ],
    series: trendIndicator.value === 'ma'
      ? [
          {
            name: etfName,
            type: 'line',
            data: closes,
            smooth: true,
            lineStyle: { width: 2 },
            markPoint: { data: [...buyMarkerPoints, ...sellMarkerPoints, ...divMarkerPoints] },
          },
          {
            name: 'MA5',
            type: 'line',
            data: ma5,
            smooth: true,
            lineStyle: { width: 1.5, color: '#e6a23c' },
            itemStyle: { color: '#e6a23c' },
            symbol: 'none',
          },
          {
            name: 'MA20',
            type: 'line',
            data: ma20,
            smooth: true,
            lineStyle: { width: 1.5, color: '#9b59b6' },
            itemStyle: { color: '#9b59b6' },
            symbol: 'none',
          },
          {
            name: 'MA60',
            type: 'line',
            data: ma60,
            smooth: true,
            lineStyle: { width: 1.5, color: '#409eff' },
            itemStyle: { color: '#409eff' },
            symbol: 'none',
          },
          {
            name: 'MA120',
            type: 'line',
            data: ma120,
            smooth: true,
            lineStyle: { width: 1.5, color: '#67c23a' },
            itemStyle: { color: '#67c23a' },
            symbol: 'none',
          },
        ]
      : [
          {
            name: etfName,
            type: 'line',
            data: closes,
            smooth: true,
            lineStyle: { width: 2 },
            markPoint: { data: [...buyMarkerPoints, ...sellMarkerPoints, ...divMarkerPoints] },
          },
          {
            name: 'ADX',
            type: 'line',
            data: adx,
            smooth: true,
            lineStyle: { width: 1.5, color: '#f56c6c' },
            itemStyle: { color: '#f56c6c' },
            symbol: 'none',
            yAxisIndex: 1,
          },
          {
            name: '+DI',
            type: 'line',
            data: plusDI,
            smooth: true,
            lineStyle: { width: 1, color: '#67c23a', type: 'dashed' },
            itemStyle: { color: '#67c23a' },
            symbol: 'none',
            yAxisIndex: 1,
          },
          {
            name: '-DI',
            type: 'line',
            data: minusDI,
            smooth: true,
            lineStyle: { width: 1, color: '#f56c6c', type: 'dashed' },
            itemStyle: { color: '#f56c6c' },
            symbol: 'none',
            yAxisIndex: 1,
          },
        ],
    grid: { left: '3%', right: trendIndicator.value === 'ma' ? '3%' : '8%', top: 60, bottom: 60, containLabel: true },
  }
}

const chartOption = computed(() => {
  const prices = chartData.value.prices
  const markers = chartData.value.markers
  const baseline = chartData.value.baseline || []

  if (!prices.length) return {}

  const dates = prices.map(p => p.date)
  const closes = prices.map(p => p.close)

  // 基线数据映射
  const baseMap = Object.fromEntries((baseline || []).map(d => [d.date, d.value]))

  // 获取当前视图的数据范围
  const zoom = viewRange.value
  const viewStartIdx = Math.floor(dates.length * zoom.start / 100)
  const viewEndIdx = Math.ceil(dates.length * zoom.end / 100) - 1
  const safeStartIdx = Math.max(0, Math.min(viewStartIdx, dates.length - 1))
  const safeEndIdx = Math.max(safeStartIdx, Math.min(viewEndIdx, dates.length - 1))

  // 净值模式：显示原始价格
  if (chartMode.value === 'price') {
    return buildPriceModeChart(dates, closes, markers, safeStartIdx, safeEndIdx)
  }

  // 趋势模式：显示主指标线 + MA5/MA20/MA60/MA120 + ADX
  if (chartMode.value === 'trend') {
    const highs = prices.map(p => p.high || p.close)
    const lows = prices.map(p => p.low || p.close)
    return buildTrendModeChart(dates, closes, highs, lows, markers, safeStartIdx, safeEndIdx)
  }

  // 对比模式：以视图第一天为基准，计算归一化百分比 (基准=100)
  const etfStartPrice = closes[safeStartIdx]
  const etfNormalized = closes.map(p => (p / etfStartPrice) * 100)

  // 基线归一化
  let baseNormalized = []
  let baseStartValue = null
  for (let i = safeStartIdx; i <= safeEndIdx; i++) {
    if (baseMap[dates[i]] !== undefined && baseMap[dates[i]] !== null) {
      baseStartValue = baseMap[dates[i]]
      break
    }
  }
  if (baseStartValue) {
    baseNormalized = dates.map(d => {
      const v = baseMap[d]
      return v !== undefined && v !== null ? (v / baseStartValue) * 100 : null
    })
  }

  // 计算Y轴范围（基于归一化后的数据）
  const viewEtfValues = etfNormalized.slice(safeStartIdx, safeEndIdx + 1)
  const etfMin = Math.min(...viewEtfValues)
  const etfMax = Math.max(...viewEtfValues)
  const etfRange = etfMax - etfMin || 1

  let baseMin, baseMax, baseRange
  if (baseStartValue) {
    const viewBaseValues = baseNormalized.slice(safeStartIdx, safeEndIdx + 1).filter(v => v !== null)
    if (viewBaseValues.length > 0) {
      baseMin = Math.min(...viewBaseValues)
      baseMax = Math.max(...viewBaseValues)
      baseRange = baseMax - baseMin || 1
    }
  }

  // 统一Y轴范围：取两者并集，加边距
  const allMin = Math.min(etfMin, baseMin || etfMin)
  const allMax = Math.max(etfMax, baseMax || etfMax)
  const allRange = allMax - allMin || 1
  const yMin = allMin - allRange * 0.05
  const yMax = allMax + allRange * 0.05

  // 买卖标记：周/月视图需要将精确日期映射到聚合后的日期
  const dateToIdx = new Map(dates.map((d, i) => [d, i]))

  // 对于周/月视图，找到最接近的 x 轴日期索引
  const findClosestIdx = (markerDate) => {
    // 精确匹配
    if (dateToIdx.has(markerDate)) return dateToIdx.get(markerDate)
    // 找包含该日期的区间（周/月聚合日期是区间末日）
    for (let i = dates.length - 1; i >= 0; i--) {
      if (dates[i] <= markerDate) return i
    }
    return 0
  }

  // 标记点坐标需要转换为归一化后的百分比值
  // 只显示在当前视图范围内的标记点
  const buyMarkers = markers.filter(m => m.direction === 'buy').map(m => {
    const idx = findClosestIdx(m.date)
    // 过滤：只保留在当前视图范围内的标记
    if (idx < safeStartIdx || idx > safeEndIdx) return null
    const normalizedPrice = etfNormalized[idx]
    return {
      coord: [dates[idx], normalizedPrice],
      symbol: 'triangle',
      symbolSize: 12,
      itemStyle: { color: '#67c23a' },
      label: { show: false },
    }
  }).filter(m => m !== null)
  const sellMarkers = markers.filter(m => m.direction === 'sell').map(m => {
    const idx = findClosestIdx(m.date)
    if (idx < safeStartIdx || idx > safeEndIdx) return null
    const normalizedPrice = etfNormalized[idx]
    return {
      coord: [dates[idx], normalizedPrice],
      symbol: 'triangle',
      symbolRotate: 180,
      symbolSize: 12,
      itemStyle: { color: '#f56c6c' },
      label: { show: false },
    }
  }).filter(m => m !== null)
  const divMarkers = markers.filter(m => m.direction === 'dividend').map(m => {
    const idx = findClosestIdx(m.date)
    if (idx < safeStartIdx || idx > safeEndIdx) return null
    const normalizedPrice = etfNormalized[idx]
    return {
      coord: [dates[idx], normalizedPrice],
      symbol: 'diamond',
      symbolSize: 10,
      itemStyle: { color: '#e6a23c' },
      label: { show: false },
    }
  }).filter(m => m !== null)

  const etfName = detail.value.short_name || detail.value.name || code.value

  // 为tooltip准备原始价格映射
  const priceMap = Object.fromEntries(prices.map((p, i) => [dates[i], p.close]))
  const basePriceMap = Object.fromEntries(baseline.map(b => [b.date, b.value]))

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const date = params[0].axisValue
        let html = `<div style="font-weight:bold;margin-bottom:5px">${date}</div>`
        params.forEach(p => {
          const normalizedVal = p.value
          const changePct = normalizedVal ? (normalizedVal - 100).toFixed(2) : '0.00'
          if (p.seriesName === etfName) {
            const originalPrice = priceMap[date]
            html += `<div>${p.marker} ${p.seriesName}: <b>${normalizedVal?.toFixed(2) || '-'}%</b> (${changePct}%)<br/><span style="color:#999;font-size:11px">原始价格: ¥${originalPrice?.toFixed(3) || '-'}</span></div>`
          } else {
            const basePrice = basePriceMap[date]
            html += `<div>${p.marker} ${p.seriesName}: <b>${normalizedVal?.toFixed(2) || '-'}%</b> (${changePct}%)<br/><span style="color:#999;font-size:11px">原始点位: ${basePrice?.toFixed(2) || '-'}</span></div>`
          }
        })
        return html
      }
    },
    legend: { data: [etfName, '基线'], top: 10, selected: legendSelected.value },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        rotate: dates.length > 30 ? 30 : 0,
        fontSize: 11,
      },
    },
    yAxis: {
      type: 'value',
      name: '相对涨幅(%)',
      min: yMin,
      max: yMax,
      axisLabel: { formatter: (v) => v.toFixed(1) + '%' },
    },
    dataZoom: [
      {
        type: 'inside',
        start: viewRange.value.start,
        end: viewRange.value.end,
      },
      {
        type: 'slider',
        start: viewRange.value.start,
        end: viewRange.value.end,
        height: 20,
        bottom: 5,
      },
    ],
    series: [
      {
        name: etfName,
        type: 'line',
        data: etfNormalized,
        smooth: true,
        lineStyle: { width: 2 },
        markPoint: { data: [...buyMarkers, ...sellMarkers, ...divMarkers] },
      },
      {
        name: '基线',
        type: 'line',
        data: baseNormalized,
        smooth: true,
        connectNulls: true,
        lineStyle: { type: 'dashed', width: 2 },
        symbol: 'none',
      },
    ],
    grid: { left: '3%', right: '4%', top: 60, bottom: 60, containLabel: true },
  }
})

const loadData = async () => {
  const [dRes, cRes] = await Promise.all([
    getPositionDetail(code.value),
    getPositionChart(code.value, period.value, baselineCode.value),
  ])
  detail.value = dRes.data
  // 映射后端字段到前端字段：data -> prices, trades -> markers
  chartData.value = {
    prices: cRes.data.data || [],
    markers: cRes.data.trades || [],
    baseline: cRes.data.baseline || [],
    avg_cost: cRes.data.avg_cost
  }
  
  // 数据加载完成后，计算 viewRange
  const prices = chartData.value.prices
  if (prices && prices.length > 0 && visibleBarCount.value !== null) {
    // 如果有保存的K线数量，按相对数量计算视图范围（显示最近N根K线）
    const count = Math.min(visibleBarCount.value, prices.length)
    const end = 100
    const start = Math.max(0, 100 - (count / prices.length) * 100)
    viewRange.value = { start, end }
  } else {
    // 没有保存的K线数量，使用默认初始范围
    viewRange.value = calculateInitialRange()
  }
}

const loadAllPositions = async () => {
  const res = await getPositions()
  // 按收益率从高到低排序
  allPositions.value = (res.data || []).sort((a, b) => (b.total_pnl_pct || 0) - (a.total_pnl_pct || 0))
}

const currentIndex = computed(() => {
  return allPositions.value.findIndex(p => p.code === code.value)
})

const canGoPrev = computed(() => currentIndex.value > 0)
const canGoNext = computed(() => currentIndex.value >= 0 && currentIndex.value < allPositions.value.length - 1)

const goPrev = () => {
  if (canGoPrev.value) {
    const prevCode = allPositions.value[currentIndex.value - 1].code
    router.push(`/position/${prevCode}`)
  }
}

const goNext = () => {
  if (canGoNext.value) {
    const nextCode = allPositions.value[currentIndex.value + 1].code
    router.push(`/position/${nextCode}`)
  }
}

const onCodeChange = (newCode) => {
  if (newCode && newCode !== code.value) {
    router.push(`/position/${newCode}`)
  }
}

// 监听路由参数变化，重新加载数据
watch(() => route.params.code, (newCode) => {
  if (newCode) {
    selectedCode.value = newCode
    loadData()
  }
})

const onPeriodChange = async () => {
  await loadData()
}

const onBaselineChange = async () => {
  const cRes = await getPositionChart(code.value, period.value, baselineCode.value)
  chartData.value = {
    prices: cRes.data.data || [],
    markers: cRes.data.trades || [],
    baseline: cRes.data.baseline || [],
    avg_cost: cRes.data.avg_cost
  }
}

const onChartModeChange = async () => {
  // 切换模式时保持当前日期范围不变
  // 如果切换到对比模式且没有基线数据，重新加载
  if (chartMode.value === 'compare' && (!chartData.value.baseline || chartData.value.baseline.length === 0)) {
    const cRes = await getPositionChart(code.value, period.value, baselineCode.value)
    chartData.value = {
      prices: cRes.data.data || [],
      markers: cRes.data.trades || [],
      baseline: cRes.data.baseline || [],
      avg_cost: cRes.data.avg_cost
    }
  }
}

// 关联ETF相关方法
const loadSuggestions = async () => {
  suggestLoading.value = true
  try {
    const res = await suggestLinkedEtf(code.value)
    suggestions.value = res.data.suggestions || []
  } catch (e) {
    suggestions.value = []
  } finally {
    suggestLoading.value = false
  }
}

const selectSuggestion = (row) => {
  linkCode.value = row.code
  linkName.value = row.name
}

const confirmLink = async () => {
  if (!linkCode.value) return
  try {
    // 从建议列表或用户输入中提取名称
    let shortName = ''
    const suggestion = suggestions.value.find(s => s.code === linkCode.value)
    if (suggestion) {
      shortName = suggestion.name
    }
    await updatePositionLinkedCode(code.value, linkCode.value, linkName.value || shortName, shortName)
    showLinkDialog.value = false
    linkCode.value = ''
    linkName.value = ''
    suggestions.value = []
    await loadData()
  } catch (e) {
    console.error('关联失败', e)
  }
}

const clearLinked = async () => {
  try {
    await updatePositionLinkedCode(code.value, null)
    await loadData()
  } catch (e) {
    console.error('取消关联失败', e)
  }
}

// 监听图表缩放事件，更新视图范围
const onDataZoom = (params) => {
  // ECharts dataZoom事件可能包含batch数组
  const batch = params.batch || [params]
  if (batch.length > 0) {
    const zoom = batch[0]
    if (zoom && zoom.start !== undefined && zoom.end !== undefined) {
      viewRange.value = { start: zoom.start, end: zoom.end }
      saveViewRange() // 持久化视图范围
      
      // 计算并保存当前显示的K线数量
      const prices = chartData.value.prices
      if (prices && prices.length > 0) {
        const startIdx = Math.floor(prices.length * zoom.start / 100)
        const endIdx = Math.ceil(prices.length * zoom.end / 100)
        visibleBarCount.value = endIdx - startIdx
        saveVisibleBarCount()
      }
    }
  }
}

// 监听图例选择变化
const onLegendSelectChanged = (params) => {
  legendSelected.value = params.selected || {}
  saveLegendSelected()
}

// 监听图表模式变化
const onChartModeChangeWithSave = () => {
  saveChartMode()
  // 调用原有的模式切换逻辑
  onChartModeChange()
}

// 获取止盈线配置
const loadStopLossConfigs = async () => {
  try {
    const res = await axios.get('/api/config/stop-loss')
    stopLossConfigs.value = res.data
  } catch (e) {
    console.error('获取止盈线配置失败', e)
    stopLossConfigs.value = [
      { level_name: '浅厚利润', pnl_min: 50, pnl_max: 100, use_profit_based: 1, profit_retention_half: 0.5, profit_retention_clear: 0.3 },
      { level_name: '中厚利润', pnl_min: 100, pnl_max: 200, use_profit_based: 0, half_position_ratio: 0.82, clear_position_ratio: 0.70 },
      { level_name: '极厚利润', pnl_min: 200, pnl_max: null, use_profit_based: 0, half_position_ratio: 0.78, clear_position_ratio: 0.65 }
    ]
  }
}

const loadProfitLevels = async () => {
  try {
    const res = await axios.get('/api/config/profit-levels')
    profitLevels.value = res.data
  } catch (e) {
    console.error('获取利润等级配置失败', e)
    profitLevels.value = []
  }
}

onMounted(async () => {
  // 加载持久化状态（在加载数据之前）
  loadPersistedState()
  
  // 首屏关键数据并行加载
  await Promise.all([
    loadStopLossConfigs(),
    loadProfitLevels(),
    loadData(),
  ])
  
  // 延迟加载所有持仓列表（用于前后导航，非首屏必需）
  loadAllPositions()
})
</script>

<style scoped>
.stat-label { color: #909399; font-size: 13px; margin-bottom: 4px; }
.stat-value { font-size: 20px; font-weight: bold; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
