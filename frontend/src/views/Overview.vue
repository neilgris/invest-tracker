<template>
  <div>
    <!-- 骨架屏 -->
    <el-row v-if="loading" :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6" v-for="i in 4" :key="i">
        <el-card shadow="hover">
          <el-skeleton :rows="1" animated />
        </el-card>
      </el-col>
    </el-row>

    <el-row v-else :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">总成本</div>
          <div class="stat-value">¥{{ overview.total_cost?.toLocaleString() }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">总市值</div>
          <div class="stat-value">¥{{ overview.total_market_value?.toLocaleString() }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">总收益</div>
          <div class="stat-value" :class="overview.total_pnl >= 0 ? 'profit' : 'loss'">
            {{ overview.total_pnl >= 0 ? '+' : '' }}¥{{ overview.total_pnl?.toLocaleString() }}
          </div>
          <div class="stat-sub" :class="overview.total_pnl >= 0 ? 'profit' : 'loss'">
            {{ overview.total_pnl_pct >= 0 ? '+' : '' }}{{ overview.total_pnl_pct }}%
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">今日盈亏</div>
          <div class="stat-value" :class="overview.daily_pnl >= 0 ? 'profit' : 'loss'">
            {{ overview.daily_pnl >= 0 ? '+' : '' }}¥{{ overview.daily_pnl?.toLocaleString() }}
          </div>
          <div class="stat-sub" :class="overview.daily_pnl >= 0 ? 'profit' : 'loss'">
            {{ overview.daily_pnl_pct >= 0 ? '+' : '' }}{{ overview.daily_pnl_pct }}%
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>持仓列表</span>
              <el-button type="primary" size="small" @click="syncQuotes" :loading="syncing">同步行情</el-button>
            </div>
          </template>
          <el-table :data="sortedPositions" stripe style="width: 100%" @row-click="goDetail" @sort-change="handleSort" :default-sort="{ prop: 'total_pnl', order: 'descending' }" v-loading="loading">
            <el-table-column prop="code" label="代码" width="100" />
            <el-table-column prop="name" label="名称" width="120">
              <template #default="{ row }">{{ row.short_name || row.name }}</template>
            </el-table-column>
            <el-table-column label="持仓数量" width="100">
              <template #default="{ row }">{{ row.quantity?.toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="成本价" width="100">
              <template #default="{ row }">{{ row.avg_cost?.toFixed(4) }}</template>
            </el-table-column>
            <el-table-column label="现价" width="100">
              <template #default="{ row }">{{ row.current_price?.toFixed(4) }}</template>
            </el-table-column>
            <el-table-column label="市值" width="120" sortable="custom" prop="market_value">
              <template #default="{ row }">¥{{ row.market_value?.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="总收益" width="140" sortable="custom" prop="total_pnl">
              <template #default="{ row }">
                <span :class="row.total_pnl >= 0 ? 'profit' : 'loss'">
                  {{ row.total_pnl >= 0 ? '+' : '' }}¥{{ row.total_pnl?.toLocaleString() }}
                  ({{ row.total_pnl_pct >= 0 ? '+' : '' }}{{ row.total_pnl_pct }}%)
                </span>
              </template>
            </el-table-column>
            <el-table-column label="今日盈亏" width="120" sortable="custom" prop="daily_pnl">
              <template #default="{ row }">
                <span :class="row.daily_pnl >= 0 ? 'profit' : 'loss'">
                  {{ row.daily_pnl >= 0 ? '+' : '' }}¥{{ row.daily_pnl?.toLocaleString() }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="分类" width="120">
              <template #default="{ row }">
                <div @click.stop>
                  <el-select 
                    v-model="row.category" 
                    placeholder="选择分类" 
                    size="small" 
                    clearable
                    @change="(val) => handleCategoryChange(row, val)"
                  >
                    <el-option 
                      v-for="cat in categoryOptions" 
                      :key="cat" 
                      :label="cat" 
                      :value="cat" 
                    />
                  </el-select>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>持仓分布</span>
              <el-radio-group v-model="pieMode" size="small">
                <el-radio-button label="position">按持仓</el-radio-button>
                <el-radio-button label="category">按分类</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <v-chart :option="pieOption" style="height: 300px" autoresize />
        </el-card>
        
        <!-- 分类统计 -->
        <el-card shadow="hover" style="margin-top: 20px">
          <template #header><span>分类统计</span></template>
          <el-table :data="sortedCategoryStats" stripe size="small">
            <el-table-column prop="category" label="分类" width="80" />
            <el-table-column prop="count" label="数量" width="50" />
            <el-table-column label="市值" width="90">
              <template #default="{ row }">¥{{ row.market_value?.toLocaleString() }}</template>
            </el-table-column>
            <el-table-column label="占比" width="70">
              <template #default="{ row }">{{ row.pct }}%</template>
            </el-table-column>
            <el-table-column label="盈亏" width="80">
              <template #default="{ row }">
                <span :class="row.pnl >= 0 ? 'profit' : 'loss'">
                  {{ row.pnl >= 0 ? '+' : '' }}{{ row.pnl_pct }}%
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import VChart from 'vue-echarts'
import { getPositions, getOverview, syncQuotes as syncApi, updatePositionCategory, getCategoryStats } from '../api'

const router = useRouter()
const positions = ref([])
const overview = ref({})
const syncing = ref(false)
const loading = ref(false)
const categoryStats = ref([])
const categoryOptions = ['主线成长', '主动混合', '现金防御', '对冲压舱', '固收缓冲', '宽基', '主题']
const pieMode = ref('category')  // 'position' | 'category'

// 排序配置：默认按总收益降序
const sortConfig = ref({ prop: 'total_pnl', order: 'descending' })

// 排序后的持仓列表
const sortedPositions = computed(() => {
  const list = [...positions.value]
  const { prop, order } = sortConfig.value
  if (!prop || !order) return list
  
  return list.sort((a, b) => {
    let valA = a[prop] || 0
    let valB = b[prop] || 0
    return order === 'ascending' ? valA - valB : valB - valA
  })
})

// 计算总市值用于占比
const totalMarketValue = computed(() => {
  return positions.value.reduce((sum, p) => sum + (p.market_value || 0), 0)
})

// 带占比的分类统计，保持后端按盈亏率排序
const sortedCategoryStats = computed(() => {
  const total = totalMarketValue.value
  return categoryStats.value
    .map(c => ({
      ...c,
      pct: total > 0 ? ((c.market_value || 0) / total * 100).toFixed(1) : '0.0'
    }))
  // 不重新排序，保持后端按pnl_pct降序
})

const pieOption = computed(() => {
  let data = []
  if (pieMode.value === 'position') {
    data = positions.value
      .map(p => ({
        name: `${p.short_name || p.name}(${p.code})`,
        value: p.market_value || 0,
      }))
      .sort((a, b) => b.value - a.value)
  } else {
    data = sortedCategoryStats.value
      .map(c => ({
        name: c.category || '未分类',
        value: c.market_value || 0,
      }))
  }
  return {
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      data,
      label: { show: true, formatter: '{b}\n{d}%' },
    }],
  }
})

const loadData = async () => {
  loading.value = true
  try {
    // 分块加载：先加载总览（最快）
    const ovRes = await getOverview()
    overview.value = ovRes.data

    // 再加载持仓列表（用户最关注）
    const posRes = await getPositions()
    positions.value = posRes.data
    loading.value = false  // 持仓加载完成，表格显示

    // 最后加载分类统计（饼图数据）
    const catRes = await getCategoryStats()
    categoryStats.value = catRes.data
  } catch (e) {
    console.error('加载数据失败', e)
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleCategoryChange = async (row, category) => {
  try {
    await updatePositionCategory(row.code, category)
    ElMessage.success('分类已更新')
    loadData()
  } catch (e) {
    ElMessage.error('更新失败: ' + (e.response?.data?.detail || e.message))
  }
}

const syncQuotes = async () => {
  syncing.value = true
  try {
    await syncApi()
    await loadData()
  } finally {
    syncing.value = false
  }
}

const goDetail = (row) => {
  router.push(`/position/${row.code}`)
}

const handleSort = ({ prop, order }) => {
  sortConfig.value = { prop, order }
}

onMounted(loadData)
</script>

<style scoped>
.stat-label { color: #909399; font-size: 14px; margin-bottom: 8px; }
.stat-value { font-size: 24px; font-weight: bold; }
.stat-sub { font-size: 14px; margin-top: 4px; }
.profit { color: #f56c6c; }
.loss { color: #67c23a; }
</style>
