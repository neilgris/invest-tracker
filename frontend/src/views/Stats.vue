<template>
  <div>
    <el-tabs v-model="activeTab" type="border-card">

      <!-- ── 月度收益 Tab ─────────────────────────────────── -->
      <el-tab-pane label="月度收益统计" name="monthly">
        <el-row :gutter="20">
          <el-col :span="9">
            <PeriodListCard
              title="月度收益统计"
              period-field="month"
              :data="monthly"
              :current-period="currentMonth"
              :show-year-picker="true"
              :year-value="year"
              @select="openMonthDetail"
              @year-change="onYearChange"
            />
          </el-col>
          <el-col :span="15">
            <PeriodDetailPanel
              period-label="月份"
              :title="monthDetail.title"
              :loading="monthDetail.loading"
              :data="monthDetail.data"
              :summary="monthDetail.summary"
            />
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- ── 年度收益 Tab ─────────────────────────────────── -->
      <el-tab-pane label="年度收益汇总" name="yearly">
        <!-- 顶部汇总卡片 -->
        <el-row :gutter="20" style="margin-bottom: 20px">
          <el-col :span="6" v-for="(item, index) in yearlySummaryCards" :key="index">
            <el-card shadow="hover">
              <div style="color: #909399; font-size: 14px; margin-bottom: 8px">{{ item.label }}</div>
              <div style="font-size: 24px; font-weight: bold" :class="item.valueClass">{{ item.value }}</div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="10">
            <PeriodListCard
              title="年度收益统计"
              period-field="year"
              :data="yearly"
              :current-period="currentYear"
              @select="openYearDetail"
            />
          </el-col>
          <el-col :span="14">
            <PeriodDetailPanel
              period-label="年份"
              :title="yearDetail.title"
              :loading="yearDetail.loading"
              :data="yearDetail.data"
              :summary="yearDetail.summary"
            />
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- ── 历史投资收益 Tab ──────────────────────────────── -->
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
import { ref, reactive, computed, onMounted } from 'vue'
import { getMonthlyStats, getClosedPositions, getYearlyStats, getMonthlyPositionDetails, getYearlyPositionDetails } from '../api'
import PeriodListCard    from '../components/PeriodListCard.vue'
import PeriodDetailPanel from '../components/PeriodDetailPanel.vue'

const activeTab = ref('monthly')
const year = ref(new Date().getFullYear().toString())

const monthly         = ref([])
const yearly          = ref([])
const closedPositions = ref([])
const currentMonth    = ref(null)
const currentYear     = ref(null)

const monthDetail = reactive({ loading: false, title: '', data: [], summary: {} })
const yearDetail  = reactive({ loading: false, title: '', data: [], summary: {} })

// ── 年度顶部汇总卡片 ────────────────────────────────────────
const yearlySummaryCards = computed(() => {
  const totalPnl  = yearly.value.reduce((s, y) => s + (y.pnl || 0), 0)
  const n         = yearly.value.length
  const product   = yearly.value.reduce((p, y) => p * (1 + (y.pnl_pct || 0) / 100), 1)
  const avgReturn = n > 0 ? (Math.pow(product, 1 / n) - 1) * 100 : 0
  const best  = n ? yearly.value.reduce((a, b) => b.pnl_pct > a.pnl_pct ? b : a) : null
  const worst = n ? yearly.value.reduce((a, b) => b.pnl_pct < a.pnl_pct ? b : a) : null
  return [
    { label: '累计收益',    value: (totalPnl  >= 0 ? '+' : '') + '¥' + Math.round(totalPnl).toLocaleString(), valueClass: totalPnl  >= 0 ? 'profit' : 'loss' },
    { label: '平均年化收益', value: (avgReturn >= 0 ? '+' : '') + avgReturn.toFixed(2) + '%',                  valueClass: avgReturn >= 0 ? 'profit' : 'loss' },
    { label: '最佳年份' + (best  ? ` (${best.year})`  : ''), value: best  ? '+' + best.pnl_pct  + '%' : '-', valueClass: 'profit' },
    { label: '最差年份' + (worst ? ` (${worst.year})` : ''), value: worst ? worst.pnl_pct + '%' : '-',        valueClass: worst?.pnl_pct < 0 ? 'loss' : 'profit' },
  ]
})

// ── 数据加载 ────────────────────────────────────────────────
const loadMonthly = async () => {
  const res = await getMonthlyStats(parseInt(year.value))
  monthly.value = res.data
  const todayMonth = new Date().toISOString().slice(0, 7)
  const target = res.data.find(m => m.month === todayMonth) || res.data[res.data.length - 1]
  if (target) openMonthDetail(target)
  else Object.assign(monthDetail, { data: [], summary: {}, title: '', loading: false })
}

const onYearChange = (val) => {
  year.value = val
  loadMonthly()
}

const openMonthDetail = async (row) => {
  const [y, m] = row.month.split('-')
  currentMonth.value = row.month
  Object.assign(monthDetail, { title: `${row.month} 持仓收益明细`, loading: true, data: [], summary: {} })
  try {
    const res = await getMonthlyPositionDetails(parseInt(y), parseInt(m))
    monthDetail.data    = res.data.positions || []
    monthDetail.summary = res.data.summary   || {}
  } finally {
    monthDetail.loading = false
  }
}

const loadYearly = async () => {
  const res = await getYearlyStats()
  yearly.value = res.data
  if (res.data.length) openYearDetail(res.data[res.data.length - 1])
}

const openYearDetail = async (row) => {
  currentYear.value = row.year
  Object.assign(yearDetail, { title: `${row.year}年 持仓收益明细`, loading: true, data: [], summary: {} })
  try {
    const res = await getYearlyPositionDetails(row.year)
    yearDetail.data    = res.data.positions || []
    yearDetail.summary = res.data.summary   || {}
  } finally {
    yearDetail.loading = false
  }
}

const loadClosedPositions = async () => {
  closedPositions.value = (await getClosedPositions()).data
}

onMounted(() => {
  loadMonthly()
  loadYearly()
  loadClosedPositions()
})
</script>

<style scoped>
.profit { color: #f56c6c; }
.loss   { color: #67c23a; }
</style>
