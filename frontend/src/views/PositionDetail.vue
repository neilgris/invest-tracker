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
          :label="`${pos.short_name || pos.name} (${pos.code})`" 
          :value="pos.code" 
        />
      </el-select>
      
      <el-button circle size="small" @click="goNext" :disabled="!canGoNext">
        <el-icon><Arrow-Right /></el-icon>
      </el-button>
      
      <el-button text @click="$router.push('/')">返回总览</el-button>
    </div>

    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">持仓数量</div>
          <div class="stat-value">{{ detail.quantity?.toFixed(2) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">平均成本</div>
          <div class="stat-value">{{ detail.avg_cost?.toFixed(4) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">总收益</div>
          <div class="stat-value" :class="detail.total_pnl >= 0 ? 'profit' : 'loss'">
            {{ detail.total_pnl >= 0 ? '+' : '' }}¥{{ detail.total_pnl?.toLocaleString() }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">收益率</div>
          <div class="stat-value" :class="detail.total_pnl_pct >= 0 ? 'profit' : 'loss'">
            {{ detail.total_pnl_pct >= 0 ? '+' : '' }}{{ detail.total_pnl_pct }}%
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 关联ETF信息 -->
    <el-card v-if="detail.linked_info" shadow="hover" style="margin-bottom: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>关联场内ETF</span>
          <el-button size="small" type="danger" text @click="clearLinked">取消关联</el-button>
        </div>
      </template>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="代码">
          <router-link :to="`/position/${detail.linked_info.code}`" style="color: #409eff; text-decoration: none">
            {{ detail.linked_info.code }}
          </router-link>
        </el-descriptions-item>
        <el-descriptions-item label="名称">{{ detail.linked_info.name }}</el-descriptions-item>
        <el-descriptions-item label="短名称">{{ detail.linked_info.short_name }}</el-descriptions-item>
        <el-descriptions-item label="现价">{{ detail.linked_info.current_price }}</el-descriptions-item>
        <el-descriptions-item label="市值" v-if="detail.linked_info.market_value">¥{{ detail.linked_info.market_value?.toLocaleString() }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 无关联时显示关联按钮 -->
    <el-card v-if="!detail.linked_info && !detail.linked_code" shadow="hover" style="margin-bottom: 20px">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span style="color: #909399">尚未关联场内ETF</span>
        <el-button size="small" type="primary" @click="showLinkDialog = true">关联ETF</el-button>
      </div>
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
          <div v-if="isEtf" style="display: flex; align-items: center; gap: 10px">
            <span style="font-size: 14px; color: #909399">基线对比:</span>
            <el-select v-model="baselineCode" size="small" style="width: 160px" @change="loadBaseline">
              <el-option label="沪深300" value="000300" />
              <el-option label="中证500" value="000905" />
              <el-option label="中证1000" value="000852" />
              <el-option label="上证50" value="000016" />
            </el-select>
          </div>
        </div>
      </template>
      <v-chart :option="chartOption" style="height: 450px" autoresize />
    </el-card>

    <el-card v-if="baselineData.etf.length" shadow="hover">
      <template #header><span>基线对比（归一化）</span></template>
      <v-chart :option="baselineOption" style="height: 300px" autoresize />
    </el-card>

    <!-- 关联ETF对话框 -->
    <el-dialog v-model="showLinkDialog" title="关联场内ETF" width="600px">
      <div style="margin-bottom: 16px">
        <el-button size="small" @click="loadSuggestions" :loading="suggestLoading">自动推荐</el-button>
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
import { getPositionDetail, getPositionChart, getBaselineComparison, updatePositionLinkedCode, suggestLinkedEtf, getPositions } from '../api'

const route = useRoute()
const router = useRouter()
const code = computed(() => route.params.code)
const selectedCode = ref(route.params.code)
const allPositions = ref([])
const detail = ref({})
const chartData = ref({ prices: [], markers: [] })
const period = ref('daily')
const baselineCode = ref('000300')
const baselineData = ref({ etf: [], baseline: [] })

// 关联ETF相关状态
const showLinkDialog = ref(false)
const linkCode = ref('')
const suggestions = ref([])
const suggestLoading = ref(false)

const isEtf = computed(() => code.value?.startsWith('5') || code.value?.startsWith('15'))

// 计算 dataZoom 范围：日视图默认显示近1年，周/月视图全部显示
const dataZoomRange = computed(() => {
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
})

const chartOption = computed(() => {
  const prices = chartData.value.prices
  const markers = chartData.value.markers

  const dates = prices.map(p => p.date)
  const closes = prices.map(p => p.close)

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

  const buyMarkers = markers.filter(m => m.direction === 'buy').map(m => ({
    coord: [dates[findClosestIdx(m.date)], m.price],
    symbol: 'triangle',
    symbolSize: 12,
    itemStyle: { color: '#67c23a' },
    label: { show: true, formatter: `买 ¥${m.amount}`, position: 'bottom', fontSize: 10 },
  }))
  const sellMarkers = markers.filter(m => m.direction === 'sell').map(m => ({
    coord: [dates[findClosestIdx(m.date)], m.price],
    symbol: 'triangle',
    symbolRotate: 180,
    symbolSize: 12,
    itemStyle: { color: '#f56c6c' },
    label: { show: true, formatter: `卖 ¥${m.amount}`, position: 'top', fontSize: 10 },
  }))
  const divMarkers = markers.filter(m => m.direction === 'dividend').map(m => ({
    coord: [dates[findClosestIdx(m.date)], m.price],
    symbol: 'diamond',
    symbolSize: 10,
    itemStyle: { color: '#e6a23c' },
    label: { show: true, formatter: `分红 +${m.quantity}`, position: 'top', fontSize: 10 },
  }))

  const zoom = dataZoomRange.value

  return {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        rotate: dates.length > 30 ? 30 : 0,
        fontSize: 11,
      },
    },
    yAxis: { type: 'value', scale: true },
    dataZoom: [
      {
        type: 'inside',      // 鼠标滚轮缩放
        start: zoom.start,
        end: zoom.end,
      },
      {
        type: 'slider',      // 底部拖拽条
        start: zoom.start,
        end: zoom.end,
        height: 20,
        bottom: 5,
      },
    ],
    series: [{
      type: 'line',
      data: closes,
      smooth: true,
      lineStyle: { width: 2 },
      markPoint: { data: [...buyMarkers, ...sellMarkers, ...divMarkers] },
    }],
    grid: { left: '3%', right: '4%', top: '3%', bottom: 60, containLabel: true },
  }
})

const baselineOption = computed(() => {
  const allDates = [...new Set([
    ...baselineData.value.etf.map(d => d.date),
    ...baselineData.value.baseline.map(d => d.date),
  ])].sort()

  const etfMap = Object.fromEntries(baselineData.value.etf.map(d => [d.date, d.value]))
  const baseMap = Object.fromEntries(baselineData.value.baseline.map(d => [d.date, d.value]))

  const len = allDates.length
  const zoomEnd = len <= 60 ? 100 : Math.round(60 / len * 100)

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: [detail.value.short_name || detail.value.name || code.value, '基线'] },
    xAxis: { type: 'category', data: allDates },
    yAxis: { type: 'value', name: '归一化' },
    dataZoom: [
      { type: 'inside', start: 0, end: zoomEnd },
      { type: 'slider', start: 0, end: zoomEnd, height: 20, bottom: 5 },
    ],
    series: [
      {
        name: detail.value.short_name || detail.value.name || code.value,
        type: 'line',
        data: allDates.map(d => etfMap[d] ?? null),
        smooth: true,
        connectNulls: true,
      },
      {
        name: '基线',
        type: 'line',
        data: allDates.map(d => baseMap[d] ?? null),
        smooth: true,
        connectNulls: true,
        lineStyle: { type: 'dashed' },
      },
    ],
    grid: { left: '3%', right: '4%', top: 40, bottom: 60, containLabel: true },
  }
})

const loadData = async () => {
  const [dRes, cRes] = await Promise.all([
    getPositionDetail(code.value),
    getPositionChart(code.value, period.value),
  ])
  detail.value = dRes.data
  chartData.value = cRes.data
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
    if (isEtf.value) loadBaseline()
  }
})

const loadBaseline = async () => {
  if (!isEtf.value) return
  try {
    const res = await getBaselineComparison(code.value, baselineCode.value, period.value)
    baselineData.value = res.data
  } catch {
    baselineData.value = { etf: [], baseline: [] }
  }
}

const onPeriodChange = async () => {
  const cRes = await getPositionChart(code.value, period.value)
  chartData.value = cRes.data
  if (isEtf.value) loadBaseline()
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
}

const confirmLink = async () => {
  if (!linkCode.value) return
  try {
    await updatePositionLinkedCode(code.value, linkCode.value)
    showLinkDialog.value = false
    linkCode.value = ''
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

onMounted(async () => {
  await loadAllPositions()
  await loadData()
  if (isEtf.value) loadBaseline()
})
</script>

<style scoped>
.stat-label { color: #909399; font-size: 14px; margin-bottom: 8px; }
.stat-value { font-size: 22px; font-weight: bold; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
