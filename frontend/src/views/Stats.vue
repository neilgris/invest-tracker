<template>
  <div>
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 月度收益 Tab -->
      <el-tab-pane label="月度收益统计" name="monthly">
        <el-card shadow="hover" style="margin-bottom: 20px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>月度收益统计</span>
              <el-date-picker v-model="year" type="year" value-format="YYYY" placeholder="选择年份" style="width: 120px" @change="loadMonthly" />
            </div>
          </template>
          <el-table :data="monthly" stripe style="width: 100%">
            <el-table-column prop="month" label="月份" width="100" />
            <el-table-column label="月初投入" width="130">
              <template #default="{ row }">¥{{ row.cost_start?.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="月末投入" width="130">
              <template #default="{ row }">¥{{ row.cost_end?.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="月度收益" width="130">
              <template #default="{ row }">
                <span :class="row.pnl >= 0 ? 'profit' : 'loss'">
                  {{ row.pnl >= 0 ? '+' : '' }}¥{{ row.pnl?.toLocaleString() }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="收益率" width="120">
              <template #default="{ row }">
                <span :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">
                  {{ row.pnl_pct >= 0 ? '+' : '' }}{{ row.pnl_pct }}%
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="hover">
          <template #header><span>月度收益曲线</span></template>
          <v-chart :option="chartOption" style="height: 350px" autoresize />
        </el-card>
      </el-tab-pane>

      <!-- 年度收益 Tab -->
      <el-tab-pane label="年度收益汇总" name="yearly">
        <el-row :gutter="20" style="margin-bottom: 20px">
          <el-col :span="6" v-for="(item, index) in yearlySummaryCards" :key="index">
            <el-card shadow="hover">
              <div style="color: #909399; font-size: 14px; margin-bottom: 8px">{{ item.label }}</div>
              <div style="font-size: 24px; font-weight: bold" :class="item.valueClass">{{ item.value }}</div>
            </el-card>
          </el-col>
        </el-row>

        <el-card shadow="hover" style="margin-bottom: 20px">
          <template #header><span>年度收益统计</span></template>
          <el-table :data="yearly" stripe style="width: 100%">
            <el-table-column prop="year" label="年份" width="100" />
            <el-table-column label="平均投入" width="130">
              <template #default="{ row }">¥{{ row.cost?.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="年度收益" width="140">
              <template #default="{ row }">
                <span :class="row.pnl >= 0 ? 'profit' : 'loss'">
                  {{ row.pnl >= 0 ? '+' : '' }}¥{{ row.pnl?.toLocaleString() }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="收益率" width="120">
              <template #default="{ row }">
                <span :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">
                  {{ row.pnl_pct >= 0 ? '+' : '' }}{{ row.pnl_pct }}%
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="hover">
          <template #header><span>年度收益趋势</span></template>
          <v-chart :option="yearlyChartOption" style="height: 300px" autoresize />
        </el-card>
      </el-tab-pane>

      <!-- 历史收益 Tab -->
      <el-tab-pane label="历史投资收益" name="history">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>已清仓标的收益统计</span>
              <span style="color: #909399; font-size: 12px">共 {{ closedPositions.length }} 只</span>
            </div>
          </template>
          <el-table :data="closedPositions" stripe style="width: 100%">
            <el-table-column prop="code" label="代码" width="90" />
            <el-table-column prop="name" label="名称" width="160" />
            <el-table-column label="买入金额" width="110">
              <template #default="{ row }">¥{{ row.total_buy?.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="卖出金额" width="110">
              <template #default="{ row }">¥{{ row.total_sell?.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="分红" width="90">
              <template #default="{ row }">¥{{ row.total_dividend?.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="总收益" width="120">
              <template #default="{ row }">
                <span :class="row.total_pnl >= 0 ? 'profit' : 'loss'">
                  {{ row.total_pnl >= 0 ? '+' : '' }}¥{{ row.total_pnl?.toLocaleString() }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="收益率" width="90">
              <template #default="{ row }">
                <span :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">
                  {{ row.pnl_pct >= 0 ? '+' : '' }}{{ row.pnl_pct }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column label="持仓周期" width="120">
              <template #default="{ row }">{{ row.first_trade }} ~ {{ row.last_trade }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { getMonthlyStats, getClosedPositions, getYearlyStats } from '../api'

const activeTab = ref('monthly')
const year = ref(new Date().getFullYear().toString())
const monthly = ref([])
const closedPositions = ref([])
const yearly = ref([])

const chartOption = computed(() => {
  const months = monthly.value.map(m => m.month)
  const pnls = monthly.value.map(m => m.pnl)

  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: months },
    yAxis: { type: 'value', name: '收益(¥)' },
    series: [{
      type: 'bar',
      data: pnls.map(v => ({
        value: v,
        itemStyle: { color: v >= 0 ? '#f56c6c' : '#67c23a' },
      })),
    }],
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  }
})

// 年度汇总卡片数据
const yearlySummaryCards = computed(() => {
  const totalPnl = yearly.value.reduce((sum, y) => sum + (y.pnl || 0), 0)
  const avgCost = yearly.value.length > 0
    ? yearly.value.reduce((sum, y) => sum + (y.cost || 0), 0) / yearly.value.length
    : 0
  const avgReturn = yearly.value.length > 0
    ? totalPnl / avgCost * 100
    : 0
  const bestYear = yearly.value.length > 0
    ? yearly.value.reduce((max, y) => y.pnl_pct > max.pnl_pct ? y : max, yearly.value[0])
    : null
  const worstYear = yearly.value.length > 0
    ? yearly.value.reduce((min, y) => y.pnl_pct < min.pnl_pct ? y : min, yearly.value[0])
    : null

  return [
    {
      label: '累计收益',
      value: (totalPnl >= 0 ? '+' : '') + '¥' + Math.round(totalPnl).toLocaleString(),
      valueClass: totalPnl >= 0 ? 'profit' : 'loss'
    },
    {
      label: '平均年化收益',
      value: (avgReturn >= 0 ? '+' : '') + avgReturn.toFixed(2) + '%',
      valueClass: avgReturn >= 0 ? 'profit' : 'loss'
    },
    {
      label: '最佳年份' + (bestYear ? ` (${bestYear.year})` : ''),
      value: bestYear ? '+' + bestYear.pnl_pct + '%' : '-',
      valueClass: 'profit'
    },
    {
      label: '最差年份' + (worstYear ? ` (${worstYear.year})` : ''),
      value: worstYear ? worstYear.pnl_pct + '%' : '-',
      valueClass: worstYear && worstYear.pnl_pct < 0 ? 'loss' : 'profit'
    },
  ]
})

// 年度收益趋势图
const yearlyChartOption = computed(() => {
  const years = yearly.value.map(y => y.year)
  const pnls = yearly.value.map(y => y.pnl)
  const pnlPcts = yearly.value.map(y => y.pnl_pct)

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: { data: ['收益金额', '收益率'] },
    xAxis: { type: 'category', data: years },
    yAxis: [
      { type: 'value', name: '收益(¥)', position: 'left' },
      { type: 'value', name: '收益率(%)', position: 'right', axisLabel: { formatter: '{value}%' } }
    ],
    series: [
      {
        name: '收益金额',
        type: 'bar',
        data: pnls.map(v => ({
          value: v,
          itemStyle: { color: v >= 0 ? '#f56c6c' : '#67c23a' },
        })),
      },
      {
        name: '收益率',
        type: 'line',
        yAxisIndex: 1,
        data: pnlPcts,
        smooth: true,
        lineStyle: { width: 3 },
        itemStyle: { color: '#409eff' },
      }
    ],
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  }
})

const loadMonthly = async () => {
  const res = await getMonthlyStats(parseInt(year.value))
  monthly.value = res.data
}

const loadClosedPositions = async () => {
  const res = await getClosedPositions()
  closedPositions.value = res.data
}

const loadYearly = async () => {
  const res = await getYearlyStats()
  yearly.value = res.data
}

onMounted(() => {
  loadMonthly()
  loadClosedPositions()
  loadYearly()
})
</script>

<style scoped>
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
