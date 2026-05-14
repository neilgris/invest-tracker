<template>
  <div>
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 月度收益 Tab -->
      <el-tab-pane label="月度收益统计" name="monthly">
        <el-row :gutter="20">
          <!-- 左侧：月度列表 + 曲线图 -->
          <el-col :span="10">
            <el-card shadow="hover" style="margin-bottom: 20px">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>月度收益统计</span>
                  <el-date-picker v-model="year" type="year" value-format="YYYY" placeholder="选择年份" style="width: 120px" @change="loadMonthly" />
                </div>
              </template>
              <el-table 
                :data="monthly" 
                stripe 
                style="width: 100%" 
                @row-click="openMonthDetail" 
                class="clickable-table"
                highlight-current-row
                :row-class-name="getRowClassName"
              >
                <el-table-column prop="month" label="月份" width="90" />
                <el-table-column label="期末市值" width="110" sortable>
                  <template #default="{ row }">¥{{ row.end_market_value?.toLocaleString() }}</template>
                </el-table-column>
                <el-table-column label="月度收益" width="120" sortable>
                  <template #default="{ row }">
                    <span :class="row.pnl >= 0 ? 'profit' : 'loss'">
                      {{ row.pnl >= 0 ? '+' : '' }}¥{{ row.pnl?.toLocaleString() }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="收益率" width="90" sortable>
                  <template #default="{ row }">
                    <span :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">
                      {{ row.pnl_pct >= 0 ? '+' : '' }}{{ row.pnl_pct }}%
                    </span>
                  </template>
                </el-table-column>
              </el-table>
              <div style="margin-top: 10px; color: #909399; font-size: 12px;">
                <el-icon><InfoFilled /></el-icon> 点击月份查看持仓明细
              </div>
            </el-card>

            <el-card shadow="hover">
              <template #header><span>月度收益曲线</span></template>
              <v-chart :option="chartOption" style="height: 280px" autoresize />
            </el-card>
          </el-col>

          <!-- 右侧：持仓明细 -->
          <el-col :span="14">
            <el-card shadow="hover" v-loading="monthDetailLoading" style="height: 100%">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>{{ monthDetailTitle || '请选择月份' }}</span>
                  <span v-if="monthDetailData.length > 0" style="color: #909399; font-size: 12px">
                    共 {{ monthDetailData.length }} 只持仓
                  </span>
                </div>
              </template>
              
              <!-- 汇总数据卡片 -->
              <el-row :gutter="15" v-if="monthDetailSummary.position_count > 0" style="margin-bottom: 15px">
                <el-col :span="6">
                  <div style="background: #f5f7fa; padding: 12px; border-radius: 4px; text-align: center">
                    <div style="color: #909399; font-size: 12px; margin-bottom: 4px">期初市值</div>
                    <div style="font-size: 16px; font-weight: bold">¥{{ monthDetailSummary.total_start_market_value?.toLocaleString() }}</div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div style="background: #f5f7fa; padding: 12px; border-radius: 4px; text-align: center">
                    <div style="color: #909399; font-size: 12px; margin-bottom: 4px">月末市值</div>
                    <div style="font-size: 16px; font-weight: bold">¥{{ monthDetailSummary.total_end_market_value?.toLocaleString() }}</div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div style="background: #f5f7fa; padding: 12px; border-radius: 4px; text-align: center">
                    <div style="color: #909399; font-size: 12px; margin-bottom: 4px">当月盈亏</div>
                    <div style="font-size: 16px; font-weight: bold" :class="monthDetailSummary.total_pnl >= 0 ? 'profit' : 'loss'">
                      {{ monthDetailSummary.total_pnl >= 0 ? '+' : '' }}¥{{ monthDetailSummary.total_pnl?.toLocaleString() }}
                    </div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div style="background: #f5f7fa; padding: 12px; border-radius: 4px; text-align: center">
                    <div style="color: #909399; font-size: 12px; margin-bottom: 4px">收益率</div>
                    <div style="font-size: 16px; font-weight: bold" :class="monthDetailSummary.total_pnl_pct >= 0 ? 'profit' : 'loss'">
                      {{ monthDetailSummary.total_pnl_pct >= 0 ? '+' : '' }}{{ monthDetailSummary.total_pnl_pct }}%
                    </div>
                  </div>
                </el-col>
              </el-row>
              
              <el-table 
                :data="monthDetailData" 
                stripe 
                style="width: 100%" 
                v-if="monthDetailData.length > 0"
                max-height="480"
                show-summary
                :summary-method="getMonthDetailSummary"
                :default-sort="{ prop: 'pnl', order: 'descending' }"
              >
                <el-table-column prop="code" label="代码" width="85" sortable />
                <el-table-column prop="name" label="名称" width="130" show-overflow-tooltip />
                <el-table-column label="期初市值" width="110" sortable :sort-by="['start_cost', 'start_market_value']">
                  <template #default="{ row }">¥{{ (row.start_cost || row.start_market_value)?.toLocaleString() }}</template>
                </el-table-column>
                <el-table-column prop="end_market_value" label="月末市值" width="110" sortable>
                  <template #default="{ row }">¥{{ row.end_market_value?.toLocaleString() }}</template>
                </el-table-column>
                <el-table-column prop="pnl" label="当月盈亏" width="110" sortable>
                  <template #default="{ row }">
                    <span :class="row.pnl >= 0 ? 'profit' : 'loss'">
                      {{ row.pnl >= 0 ? '+' : '' }}¥{{ row.pnl?.toLocaleString() }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="pnl_pct" label="收益率" width="100" sortable>
                  <template #default="{ row }">
                    <span :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">
                      {{ row.pnl_pct >= 0 ? '+' : '' }}{{ row.pnl_pct }}%
                    </span>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="点击左侧月份查看持仓明细" style="padding: 100px 0" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 年度收益 Tab -->
      <el-tab-pane label="年度收益汇总" name="yearly">
        <!-- 整体统计卡片 -->
        <el-row :gutter="20" style="margin-bottom: 20px">
          <el-col :span="6" v-for="(item, index) in yearlySummaryCards" :key="index">
            <el-card shadow="hover">
              <div style="color: #909399; font-size: 14px; margin-bottom: 8px">{{ item.label }}</div>
              <div style="font-size: 24px; font-weight: bold" :class="item.valueClass">{{ item.value }}</div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <!-- 左侧：年度列表 + 曲线图 -->
          <el-col :span="10">
            <el-card shadow="hover" style="margin-bottom: 20px">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>年度收益统计</span>
                </div>
              </template>
              <el-table 
                :data="yearly" 
                stripe 
                style="width: 100%" 
                @row-click="openYearDetail" 
                class="clickable-table"
                highlight-current-row
                :row-class-name="getYearRowClassName"
              >
                <el-table-column prop="year" label="年份" width="60" />
                <el-table-column label="期末市值" width="110" sortable>
                  <template #default="{ row }">¥{{ row.end_market_value?.toLocaleString() }}</template>
                </el-table-column>
                <el-table-column label="年度收益" width="120" sortable>
                  <template #default="{ row }">
                    <span :class="row.pnl >= 0 ? 'profit' : 'loss'">
                      {{ row.pnl >= 0 ? '+' : '' }}¥{{ row.pnl?.toLocaleString() }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="收益率" width="90" sortable>
                  <template #default="{ row }">
                    <span :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">
                      {{ row.pnl_pct >= 0 ? '+' : '' }}{{ row.pnl_pct }}%
                    </span>
                  </template>
                </el-table-column>
              </el-table>
              <div style="margin-top: 10px; color: #909399; font-size: 12px;">
                <el-icon><InfoFilled /></el-icon> 点击年份查看持仓明细
              </div>
            </el-card>

            <el-card shadow="hover">
              <template #header><span>年度收益趋势</span></template>
              <v-chart :option="yearlyChartOption" style="height: 280px" autoresize />
            </el-card>
          </el-col>

          <!-- 右侧：年度持仓明细 -->
          <el-col :span="14">
            <el-card shadow="hover" v-loading="yearDetailLoading" style="height: 100%">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center">
                  <span>{{ yearDetailTitle || '请选择年份' }}</span>
                  <span v-if="yearDetailData.length > 0" style="color: #909399; font-size: 12px">
                    共 {{ yearDetailData.length }} 只持仓
                  </span>
                </div>
              </template>
              
              <!-- 汇总数据卡片 -->
              <el-row :gutter="15" v-if="yearDetailSummary.position_count > 0" style="margin-bottom: 15px">
                <el-col :span="6">
                  <div style="background: #f5f7fa; padding: 12px; border-radius: 4px; text-align: center">
                    <div style="color: #909399; font-size: 12px; margin-bottom: 4px">期初市值</div>
                    <div style="font-size: 16px; font-weight: bold">¥{{ yearDetailSummary.total_start_market_value?.toLocaleString() }}</div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div style="background: #f5f7fa; padding: 12px; border-radius: 4px; text-align: center">
                    <div style="color: #909399; font-size: 12px; margin-bottom: 4px">年末市值</div>
                    <div style="font-size: 16px; font-weight: bold">¥{{ yearDetailSummary.total_end_market_value?.toLocaleString() }}</div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div style="background: #f5f7fa; padding: 12px; border-radius: 4px; text-align: center">
                    <div style="color: #909399; font-size: 12px; margin-bottom: 4px">年度盈亏</div>
                    <div style="font-size: 16px; font-weight: bold" :class="yearDetailSummary.total_pnl >= 0 ? 'profit' : 'loss'">
                      {{ yearDetailSummary.total_pnl >= 0 ? '+' : '' }}¥{{ yearDetailSummary.total_pnl?.toLocaleString() }}
                    </div>
                  </div>
                </el-col>
                <el-col :span="6">
                  <div style="background: #f5f7fa; padding: 12px; border-radius: 4px; text-align: center">
                    <div style="color: #909399; font-size: 12px; margin-bottom: 4px">收益率</div>
                    <div style="font-size: 16px; font-weight: bold" :class="yearDetailSummary.total_pnl_pct >= 0 ? 'profit' : 'loss'">
                      {{ yearDetailSummary.total_pnl_pct >= 0 ? '+' : '' }}{{ yearDetailSummary.total_pnl_pct }}%
                    </div>
                  </div>
                </el-col>
              </el-row>
              
              <el-table 
                :data="yearDetailData" 
                stripe 
                style="width: 100%" 
                v-if="yearDetailData.length > 0"
                max-height="480"
                show-summary
                :summary-method="getYearDetailSummary"
                :default-sort="{ prop: 'pnl', order: 'descending' }"
              >
                <el-table-column prop="code" label="代码" width="85" sortable />
                <el-table-column prop="name" label="名称" width="130" show-overflow-tooltip />
                <el-table-column label="期初市值" width="110" sortable :sort-by="['start_cost', 'start_market_value']">
                  <template #default="{ row }">¥{{ (row.start_cost || row.start_market_value)?.toLocaleString() }}</template>
                </el-table-column>
                <el-table-column prop="end_market_value" label="年末市值" width="110" sortable>
                  <template #default="{ row }">¥{{ row.end_market_value?.toLocaleString() }}</template>
                </el-table-column>
                <el-table-column prop="pnl" label="年度盈亏" width="110" sortable>
                  <template #default="{ row }">
                    <span :class="row.pnl >= 0 ? 'profit' : 'loss'">
                      {{ row.pnl >= 0 ? '+' : '' }}¥{{ row.pnl?.toLocaleString() }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="pnl_pct" label="收益率" width="100" sortable>
                  <template #default="{ row }">
                    <span :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">
                      {{ row.pnl_pct >= 0 ? '+' : '' }}{{ row.pnl_pct }}%
                    </span>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-else description="点击左侧年份查看持仓明细" style="padding: 100px 0" />
            </el-card>
          </el-col>
        </el-row>
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
import { InfoFilled } from '@element-plus/icons-vue'
import { getMonthlyStats, getClosedPositions, getYearlyStats, getMonthlyPositionDetails, getYearlyPositionDetails } from '../api'

const activeTab = ref('monthly')
const year = ref(new Date().getFullYear().toString())
const monthly = ref([])
const closedPositions = ref([])
const yearly = ref([])

// 月度持仓明细
const monthDetailLoading = ref(false)
const monthDetailTitle = ref('')
const monthDetailData = ref([])
const monthDetailSummary = ref({})
const currentMonth = ref(null)

// 年度持仓明细
const yearDetailLoading = ref(false)
const yearDetailTitle = ref('')
const yearDetailData = ref([])
const yearDetailSummary = ref({})
const currentYear = ref(null)

const chartOption = computed(() => {
  const months = monthly.value.map(m => m.month)
  const pnls = monthly.value.map(m => m.pnl)

  return {
    tooltip: { 
      trigger: 'axis',
      formatter: (params) => {
        const data = params[0]
        const monthData = monthly.value[data.dataIndex]
        return `${data.name}<br/>
                收益: ${data.value >= 0 ? '+' : ''}¥${data.value?.toLocaleString()}<br/>
                收益率: ${monthData?.pnl_pct >= 0 ? '+' : ''}${monthData?.pnl_pct}%`
      }
    },
    xAxis: { type: 'category', data: months },
    yAxis: { type: 'value', name: '收益(¥)' },
    series: [{
      type: 'bar',
      data: pnls.map((v, index) => ({
        value: v,
        itemStyle: { 
          color: v >= 0 ? '#f56c6c' : '#67c23a',
          opacity: currentMonth.value === months[index] ? 1 : 0.7
        },
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
        data: pnls.map((v, index) => ({
          value: v,
          itemStyle: { 
            color: v >= 0 ? '#f56c6c' : '#67c23a',
            opacity: currentYear.value === years[index] ? 1 : 0.7
          },
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
  
  // 默认选中当前月（如果有数据）
  const currentMonthStr = new Date().toISOString().slice(0, 7) // YYYY-MM
  const currentMonthData = res.data.find(m => m.month === currentMonthStr)
  if (currentMonthData) {
    openMonthDetail(currentMonthData)
  } else if (res.data.length > 0) {
    // 没有当前月数据，选中最后一个月
    openMonthDetail(res.data[res.data.length - 1])
  } else {
    // 清空右侧明细
    monthDetailData.value = []
    monthDetailSummary.value = {}
    monthDetailTitle.value = ''
    currentMonth.value = null
  }
}

// 行样式：高亮当前选中的月份
const getRowClassName = ({ row }) => {
  return row.month === currentMonth.value ? 'current-row' : ''
}

// 打开月度持仓明细
const openMonthDetail = async (row) => {
  const [y, m] = row.month.split('-')
  currentMonth.value = row.month
  monthDetailTitle.value = `${row.month} 持仓收益明细`
  monthDetailLoading.value = true
  monthDetailData.value = []
  monthDetailSummary.value = {}
  
  try {
    const res = await getMonthlyPositionDetails(parseInt(y), parseInt(m))
    monthDetailData.value = res.data.positions || []
    monthDetailSummary.value = res.data.summary || {}
  } finally {
    monthDetailLoading.value = false
  }
}

// 表格汇总行
const getMonthDetailSummary = (param) => {
  const { columns, data } = param
  const sums = []
  columns.forEach((column, index) => {
    if (index === 0) {
      sums[index] = '合计'
      return
    }
    if (index === 1) {
      sums[index] = `${data.length} 只`
      return
    }
    if (column.property === 'start_market_value') {
      sums[index] = '¥' + monthDetailSummary.value.total_start_market_value?.toLocaleString()
      return
    }
    if (column.property === 'end_market_value') {
      sums[index] = '¥' + monthDetailSummary.value.total_end_market_value?.toLocaleString()
      return
    }
    if (column.property === 'pnl') {
      const pnl = monthDetailSummary.value.total_pnl
      sums[index] = (pnl >= 0 ? '+' : '') + '¥' + pnl?.toLocaleString()
      return
    }
    if (column.property === 'pnl_pct') {
      sums[index] = (monthDetailSummary.value.total_pnl_pct >= 0 ? '+' : '') + monthDetailSummary.value.total_pnl_pct + '%'
      return
    }
    sums[index] = ''
  })
  return sums
}

// 行样式：高亮当前选中的年份
const getYearRowClassName = ({ row }) => {
  return row.year === currentYear.value ? 'current-row' : ''
}

// 打开年度持仓明细
const openYearDetail = async (row) => {
  currentYear.value = row.year
  yearDetailTitle.value = `${row.year}年 持仓收益明细`
  yearDetailLoading.value = true
  yearDetailData.value = []
  yearDetailSummary.value = {}
  
  try {
    const res = await getYearlyPositionDetails(row.year)
    yearDetailData.value = res.data.positions || []
    yearDetailSummary.value = res.data.summary || {}
  } finally {
    yearDetailLoading.value = false
  }
}

// 年度持仓明细表格汇总行
const getYearDetailSummary = (param) => {
  const { columns, data } = param
  const sums = []
  columns.forEach((column, index) => {
    if (index === 0) {
      sums[index] = '合计'
      return
    }
    if (index === 1) {
      sums[index] = `${data.length} 只`
      return
    }
    if (column.property === 'start_market_value') {
      sums[index] = '¥' + yearDetailSummary.value.total_start_market_value?.toLocaleString()
      return
    }
    if (column.property === 'end_market_value') {
      sums[index] = '¥' + yearDetailSummary.value.total_end_market_value?.toLocaleString()
      return
    }
    if (column.property === 'pnl') {
      const pnl = yearDetailSummary.value.total_pnl
      sums[index] = (pnl >= 0 ? '+' : '') + '¥' + pnl?.toLocaleString()
      return
    }
    if (column.property === 'pnl_pct') {
      sums[index] = (yearDetailSummary.value.total_pnl_pct >= 0 ? '+' : '') + yearDetailSummary.value.total_pnl_pct + '%'
      return
    }
    sums[index] = ''
  })
  return sums
}

const loadClosedPositions = async () => {
  const res = await getClosedPositions()
  closedPositions.value = res.data
}

const loadYearly = async () => {
  const res = await getYearlyStats()
  yearly.value = res.data
  
  // 默认选中最新的年份
  if (res.data.length > 0) {
    openYearDetail(res.data[res.data.length - 1])
  }
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
.clickable-table :deep(.el-table__row) {
  cursor: pointer;
}
.clickable-table :deep(.el-table__row:hover) {
  background-color: #f5f7fa;
}
.clickable-table :deep(.el-table__row.current-row) {
  background-color: #ecf5ff;
}
</style>
