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
          :label="`${pos.name} (${pos.code})`" 
          :value="pos.code" 
        />
      </el-select>
      
      <el-button circle size="small" @click="goNext" :disabled="!canGoNext">
        <el-icon><Arrow-Right /></el-icon>
      </el-button>
      
      <el-button text @click="$router.push('/')">返回总览</el-button>
    </div>

    <!-- 持仓统计与关联ETF整合 -->
    <el-card shadow="hover" style="margin-bottom: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>持仓统计</span>
          <div v-if="detail.linked_info" style="display: flex; align-items: center; gap: 12px; font-size: 13px">
            <span style="color: #909399">关联: {{ detail.linked_info.code }} {{ detail.linked_info.name }}</span>
            <el-button size="small" type="danger" text @click="clearLinked" style="margin-left: 8px">取消关联</el-button>
          </div>
          <div v-else-if="!isEtf" style="display: flex; align-items: center; gap: 12px">
            <span style="color: #909399; font-size: 13px">未关联场内ETF</span>
            <el-button size="small" type="primary" @click="showLinkDialog = true">关联</el-button>
          </div>
        </div>
      </template>
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-label">持仓数量</div>
          <div class="stat-value">{{ detail.quantity?.toFixed(2) }}</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">平均成本</div>
          <div class="stat-value">{{ detail.avg_cost?.toFixed(4) }}</div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">总收益</div>
          <div class="stat-value" :class="detail.total_pnl >= 0 ? 'profit' : 'loss'">
            {{ detail.total_pnl >= 0 ? '+' : '' }}¥{{ detail.total_pnl?.toLocaleString() }}
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-label">收益率</div>
          <div class="stat-value" :class="detail.total_pnl_pct >= 0 ? 'profit' : 'loss'">
            {{ detail.total_pnl_pct >= 0 ? '+' : '' }}{{ detail.total_pnl_pct }}%
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="hover" style="margin-bottom: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px">
          <div style="display: flex; align-items: center; gap: 16px">
            <span>价格走势</span>
            <el-radio-group v-model="period" size="small" @change="onPeriodChange">
              <el-radio-button value="daily">日K</el-radio-button>
              <el-radio-button value="weekly">周K</el-radio-button>
              <el-radio-button value="monthly">月K</el-radio-button>
            </el-radio-group>
          </div>
          <div style="display: flex; align-items: center; gap: 10px">
            <span style="font-size: 14px; color: #909399">基线:</span>
            <el-select v-model="baselineCode" size="small" style="width: 160px" @change="onBaselineChange">
              <el-option label="沪深300" value="000300" />
              <el-option label="中证500" value="000905" />
              <el-option label="中证1000" value="000852" />
              <el-option label="上证50" value="000016" />
            </el-select>
          </div>
        </div>
      </template>
      <v-chart :option="chartOption" style="height: 450px" autoresize @dataZoom="onDataZoom" />
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

const route = useRoute()
const router = useRouter()
const code = computed(() => route.params.code)
const selectedCode = ref(route.params.code)
const allPositions = ref([])
const detail = ref({})
const chartData = ref({ prices: [], markers: [], baseline: [] })
const period = ref('daily')
const baselineCode = ref('000300')

// 当前图表视图范围（响应dataZoom事件）
const viewRange = ref({ start: 0, end: 100 })

// 关联ETF相关状态
const showLinkDialog = ref(false)
const linkCode = ref('')
const linkName = ref('')
const suggestions = ref([])
const suggestLoading = ref(false)

const isEtf = computed(() => code.value?.startsWith('5') || code.value?.startsWith('15'))

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

  // 以视图第一天为基准，计算归一化百分比 (基准=100)
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
  const buyMarkers = markers.filter(m => m.direction === 'buy').map(m => {
    const idx = findClosestIdx(m.date)
    const normalizedPrice = etfNormalized[idx]  // 使用归一化后的值
    return {
      coord: [dates[idx], normalizedPrice],
      symbol: 'triangle',
      symbolSize: 12,
      itemStyle: { color: '#67c23a' },
      label: { show: true, formatter: `买 ¥${m.amount.toFixed(2)}`, position: 'bottom', fontSize: 10 },
    }
  })
  const sellMarkers = markers.filter(m => m.direction === 'sell').map(m => {
    const idx = findClosestIdx(m.date)
    const normalizedPrice = etfNormalized[idx]
    return {
      coord: [dates[idx], normalizedPrice],
      symbol: 'triangle',
      symbolRotate: 180,
      symbolSize: 12,
      itemStyle: { color: '#f56c6c' },
      label: { show: true, formatter: `卖 ¥${m.amount.toFixed(2)}`, position: 'top', fontSize: 10 },
    }
  })
  const divMarkers = markers.filter(m => m.direction === 'dividend').map(m => {
    const idx = findClosestIdx(m.date)
    const normalizedPrice = etfNormalized[idx]
    return {
      coord: [dates[idx], normalizedPrice],
      symbol: 'diamond',
      symbolSize: 10,
      itemStyle: { color: '#e6a23c' },
      label: { show: true, formatter: `分红 ¥${m.amount.toFixed(2)}`, position: 'top', fontSize: 10 },
    }
  })

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
    legend: { data: [etfName, '基线'], top: 10 },
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
  chartData.value = cRes.data
  // 数据加载完成后，初始化 viewRange（只在首次加载或切换周期时重置）
  viewRange.value = calculateInitialRange()
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
  const cRes = await getPositionChart(code.value, period.value, baselineCode.value)
  chartData.value = cRes.data
}

const onBaselineChange = async () => {
  const cRes = await getPositionChart(code.value, period.value, baselineCode.value)
  chartData.value = cRes.data
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
  console.log('dataZoom event triggered:', params)
  // ECharts dataZoom事件可能包含batch数组
  const batch = params.batch || [params]
  if (batch.length > 0) {
    const zoom = batch[0]
    if (zoom && zoom.start !== undefined && zoom.end !== undefined) {
      viewRange.value = { start: zoom.start, end: zoom.end }
    }
  }
}

onMounted(async () => {
  await loadAllPositions()
  await loadData()
})
</script>

<style scoped>
.stat-label { color: #909399; font-size: 13px; margin-bottom: 4px; }
.stat-value { font-size: 20px; font-weight: bold; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
