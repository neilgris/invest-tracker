<template>
  <!-- 列表卡片 -->
  <el-card shadow="hover" style="margin-bottom: 20px">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>{{ title }}</span>
        <el-date-picker
          v-if="showYearPicker"
          :model-value="yearValue"
          type="year" value-format="YYYY" placeholder="选择年份" style="width: 120px"
          @update:model-value="$emit('yearChange', $event)"
        />
      </div>
    </template>

    <el-table
      :data="data" stripe style="width: 100%"
      @row-click="$emit('select', $event)"
      class="clickable-table" highlight-current-row
      :row-class-name="({ row }) => row[periodField] === currentPeriod ? 'current-row' : ''"
    >
      <el-table-column :prop="periodField" :label="colLabel" width="90" />
      <el-table-column label="持仓收益" width="115" sortable>
        <template #default="{ row }">
          <span :class="row.unrealized_pnl >= 0 ? 'profit' : 'loss'">
            {{ row.unrealized_pnl >= 0 ? '+' : '' }}¥{{ row.unrealized_pnl?.toLocaleString() }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="总收益" width="120" sortable>
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
      <el-icon><InfoFilled /></el-icon> 点击{{ colLabel }}查看持仓明细
    </div>
  </el-card>

  <!-- 趋势图卡片（双轴：柱状收益金额 + 折线收益率） -->
  <el-card shadow="hover">
    <template #header><span>{{ title }}趋势</span></template>
    <v-chart :option="chartOption" style="height: 280px" autoresize />
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { InfoFilled } from '@element-plus/icons-vue'

const props = defineProps({
  title:         { type: String, required: true },
  periodField:   { type: String, required: true },   // 'month' | 'year'
  data:          { type: Array,  default: () => [] },
  currentPeriod: { default: null },
  showYearPicker:{ type: Boolean, default: false },
  yearValue:     { type: String, default: '' },
})

defineEmits(['select', 'yearChange'])

const colLabel = computed(() => props.periodField === 'month' ? '月份' : '年份')

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
  legend: { data: ['收益金额', '收益率'] },
  xAxis: { type: 'category', data: props.data.map(r => r[props.periodField]) },
  yAxis: [
    { type: 'value', name: '收益(¥)', position: 'left' },
    { type: 'value', name: '收益率(%)', position: 'right', axisLabel: { formatter: '{value}%' } },
  ],
  series: [
    {
      name: '收益金额', type: 'bar',
      data: props.data.map(r => ({
        value: r.pnl,
        itemStyle: {
          color: r.pnl >= 0 ? '#f56c6c' : '#67c23a',
          opacity: props.currentPeriod === r[props.periodField] ? 1 : 0.7,
        },
      })),
    },
    {
      name: '收益率', type: 'line', yAxisIndex: 1,
      data: props.data.map(r => r.pnl_pct),
      smooth: true, lineStyle: { width: 3 }, itemStyle: { color: '#409eff' },
    },
  ],
  grid: { left: '3%', right: '8%', bottom: '3%', containLabel: true },
}))
</script>

<style scoped>
.profit { color: #f56c6c; }
.loss   { color: #67c23a; }
.clickable-table :deep(.el-table__row) { cursor: pointer; }
.clickable-table :deep(.el-table__row:hover) { background-color: #f5f7fa; }
.clickable-table :deep(.el-table__row.current-row) { background-color: #ecf5ff; }
</style>
