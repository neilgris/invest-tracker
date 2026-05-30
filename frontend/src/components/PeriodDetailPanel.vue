<template>
  <el-card shadow="hover" v-loading="loading" style="height: 100%">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>{{ title || '请选择' + periodLabel }}</span>
        <span v-if="data.length > 0" style="color: #909399; font-size: 12px">
          共 {{ data.length }} 只持仓
        </span>
      </div>
    </template>

    <!-- 汇总 mini-card -->
    <el-row :gutter="10" v-if="summary.position_count > 0" style="margin-bottom: 15px">
      <el-col :span="5">
        <div class="summary-card">
          <div class="summary-label">已实现收益</div>
          <div class="summary-value" :class="summary.total_realized_pnl >= 0 ? 'profit' : 'loss'">
            {{ summary.total_realized_pnl >= 0 ? '+' : '' }}¥{{ summary.total_realized_pnl?.toLocaleString() }}
          </div>
        </div>
      </el-col>
      <el-col :span="5">
        <div class="summary-card">
          <div class="summary-label">持仓收益</div>
          <div class="summary-value" :class="summary.total_unrealized_pnl >= 0 ? 'profit' : 'loss'">
            {{ summary.total_unrealized_pnl >= 0 ? '+' : '' }}¥{{ summary.total_unrealized_pnl?.toLocaleString() }}
          </div>
        </div>
      </el-col>
      <el-col :span="5">
        <div class="summary-card">
          <div class="summary-label">总收益</div>
          <div class="summary-value" :class="summary.total_pnl >= 0 ? 'profit' : 'loss'">
            {{ summary.total_pnl >= 0 ? '+' : '' }}¥{{ summary.total_pnl?.toLocaleString() }}
          </div>
        </div>
      </el-col>
      <el-col :span="5">
        <div class="summary-card">
          <div class="summary-label">持仓市值</div>
          <div class="summary-value">¥{{ summary.total_end_market_value?.toLocaleString() }}</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="summary-card">
          <div class="summary-label">收益率</div>
          <div class="summary-value" :class="summary.total_pnl_pct >= 0 ? 'profit' : 'loss'">
            {{ summary.total_pnl_pct >= 0 ? '+' : '' }}{{ summary.total_pnl_pct }}%
          </div>
        </div>
      </el-col>
    </el-row>

    <el-table
      :data="data"
      stripe
      style="width: 100%"
      v-if="data.length > 0"
      show-summary
      :summary-method="summaryMethod"
      :default-sort="{ prop: 'pnl', order: 'descending' }"
    >
      <el-table-column prop="code" label="代码" width="80" sortable />
      <el-table-column label="名称" width="130" show-overflow-tooltip>
        <template #default="{ row }">{{ row.linked_short_name || row.name }}</template>
      </el-table-column>
      <el-table-column prop="end_market_value" label="持仓市值" width="110" sortable>
        <template #default="{ row }">¥{{ row.end_market_value?.toLocaleString() }}</template>
      </el-table-column>
      <el-table-column prop="realized_pnl" label="实现收益" width="105" sortable>
        <template #default="{ row }">
          <span :class="row.realized_pnl >= 0 ? 'profit' : 'loss'">
            {{ row.realized_pnl >= 0 ? '+' : '' }}¥{{ row.realized_pnl?.toLocaleString() }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="unrealized_pnl" label="持仓收益" width="105" sortable>
        <template #default="{ row }">
          <span :class="row.unrealized_pnl >= 0 ? 'profit' : 'loss'">
            {{ row.unrealized_pnl >= 0 ? '+' : '' }}¥{{ row.unrealized_pnl?.toLocaleString() }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="pnl" label="总收益" width="105" sortable>
        <template #default="{ row }">
          <span :class="row.pnl >= 0 ? 'profit' : 'loss'">
            {{ row.pnl >= 0 ? '+' : '' }}¥{{ row.pnl?.toLocaleString() }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="pnl_pct" label="收益率" width="90" sortable>
        <template #default="{ row }">
          <span :class="row.pnl_pct >= 0 ? 'profit' : 'loss'">
            {{ row.pnl_pct >= 0 ? '+' : '' }}{{ row.pnl_pct }}%
          </span>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-else :description="'点击左侧' + periodLabel + '查看持仓明细'" style="padding: 100px 0" />
  </el-card>
</template>

<script setup>
const props = defineProps({
  loading: Boolean,
  title: String,
  periodLabel: { type: String, default: '月份' }, // '月份' | '年份'
  data: { type: Array, default: () => [] },
  summary: { type: Object, default: () => ({}) },
})

const summaryMethod = ({ columns, data }) => {
  const s = props.summary
  return columns.map((col, i) => {
    if (i === 0) return '合计'
    if (i === 1) return `${data.length} 只`
    const fmt = (v) => v == null ? '' : (v >= 0 ? '+' : '') + '¥' + v?.toLocaleString()
    if (col.property === 'end_market_value')  return '¥' + s.total_end_market_value?.toLocaleString()
    if (col.property === 'realized_pnl')      return fmt(s.total_realized_pnl)
    if (col.property === 'unrealized_pnl')    return fmt(s.total_unrealized_pnl)
    if (col.property === 'pnl')               return fmt(s.total_pnl)
    if (col.property === 'pnl_pct')           return (s.total_pnl_pct >= 0 ? '+' : '') + s.total_pnl_pct + '%'
    return ''
  })
}
</script>

<style scoped>
.profit { color: #f56c6c; }
.loss   { color: #67c23a; }
.summary-card {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  text-align: center;
}
.summary-label {
  color: #909399;
  font-size: 11px;
  margin-bottom: 4px;
}
.summary-value {
  font-size: 14px;
  font-weight: bold;
}
</style>
