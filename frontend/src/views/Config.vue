<template>
  <div class="config-page">
    <el-page-header title="系统配置" @back="$router.back()" />
    
    <!-- 利润等级配置 -->
    <el-card class="config-card" style="margin-top: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div style="display: flex; align-items: center; gap: 8px">
            <span>利润等级配置</span>
            <el-tooltip placement="right" :show-after="200">
              <template #content>
                <div style="max-width: 400px; line-height: 1.8">
                  <p><strong>PnL_peak</strong> = (Pmax - Pcost) / Pcost × 100%</p>
                  <p><strong>PnL_now</strong> = (Pnow - Pcost) / Pcost × 100%</p>
                  <p><strong>Hold_days</strong> = 持仓天数</p>
                  <p style="margin-top: 8px"><strong>档位编码</strong>：F=利润档, L=亏损档</p>
                  <p><strong>判断方式</strong>：F档基于 PnL_peak，L档基于 PnL_now</p>
                  <p><strong>匹配规则</strong>：按优先级从高到低依次匹配</p>
                </div>
              </template>
              <el-icon :size="16" style="cursor: pointer; color: #909399"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
          <el-button type="warning" size="small" @click="resetProfitLevels">重置为默认</el-button>
        </div>
      </template>
      
      <el-table :data="profitLevels" v-loading="profitLoading" border>
        <el-table-column prop="sort_order" label="优先级" width="70" />
        <el-table-column prop="level_code" label="编码" width="70" />
        <el-table-column prop="level_name" label="等级名称" width="120" />
        <el-table-column label="阈值范围" width="220">
          <template #default="{ row }">
            <span v-if="row.pnl_threshold_max !== null && row.pnl_threshold_max !== undefined">
              {{ row.pnl_threshold }}% ≤ {{ row.use_peak_pnl ? 'PnL_peak' : 'PnL_now' }} < {{ row.pnl_threshold_max }}%
            </span>
            <span v-else>
              {{ row.use_peak_pnl ? 'PnL_peak' : 'PnL_now' }} ≥ {{ row.pnl_threshold }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="持仓天数" width="150">
          <template #default="{ row }">
            <span v-if="row.hold_days_min !== null && row.hold_days_max !== null">
              {{ row.hold_days_min }} ≤ 持仓 < {{ row.hold_days_max }}天
            </span>
            <span v-else-if="row.hold_days_min !== null">
              持仓 ≥ {{ row.hold_days_min }}天
            </span>
            <span v-else-if="row.hold_days_max !== null">
              持仓 < {{ row.hold_days_max }}天
            </span>
            <span v-else style="color: #909399">-</span>
          </template>
        </el-table-column>
        <el-table-column label="显示颜色" width="90">
          <template #default="{ row }">
            <el-tag :type="row.display_color" size="small">{{ row.display_color }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="editProfitLevel(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 止盈/损线配置 -->
    <el-card class="config-card" style="margin-top: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div style="display: flex; align-items: center; gap: 8px">
            <span>止盈/损线配置</span>
            <el-tooltip placement="right" :show-after="200">
              <template #content>
                <div style="max-width: 400px; line-height: 1.8">
                  <p><strong>关联机制</strong>：止盈线与利润等级通过 level_key 关联</p>
                  <p><strong>F档(利润)</strong>：F1.3/F1.2/F1.1/F2/F3 各有独立止盈策略</p>
                  <p><strong>L档(亏损)</strong>：L1/L2 共用薄利润配置，L3/L4 不设止盈线</p>
                  <p style="margin-top: 8px"><strong>Profit_max</strong> = Pmax - Pcost（最高浮盈金额）</p>
                  <p><strong>基于Pmax回撤</strong>：减半仓线 = Pmax × 系数（厚利润）</p>
                  <p><strong>基于Profit_max保留</strong>：减半仓线 = Pcost + Profit_max × 保留比例（中/浅厚利润）</p>
                  <p><strong>基于成本保护</strong>：减半仓线 = Pcost × 系数（薄利润/L1/L2）</p>
                </div>
              </template>
              <el-icon :size="16" style="cursor: pointer; color: #909399"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
          <el-button type="warning" size="small" @click="resetStopLoss">重置为默认</el-button>
        </div>
      </template>
      
      <el-table :data="stopLossConfigs" v-loading="stopLossLoading" border>
        <el-table-column prop="level_code" label="编码" width="70" />
        <el-table-column prop="level_name" label="利润等级" width="120" />
        <el-table-column label="利润范围" width="180">
          <template #default="{ row }">
            <span v-if="row.pnl_min !== null">
              {{ row.pnl_min }}% {{ row.pnl_max !== null ? '≤ PnL < ' + row.pnl_max + '%' : '以上' }}
            </span>
            <span v-else style="color: #909399">-</span>
          </template>
        </el-table-column>
        <el-table-column label="计算方式" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.calculation_mode === 'profit_retention'" type="success" size="small">保留浮盈</el-tag>
            <el-tag v-else-if="row.calculation_mode === 'cost_protection'" type="warning" size="small">成本保护</el-tag>
            <el-tag v-else type="primary" size="small">Pmax回撤</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="减半仓线" min-width="160">
          <template #default="{ row }">
            <div v-if="row.calculation_mode === 'profit_retention' && row.profit_retention_half !== null">
              保留 {{ formatPercent(row.profit_retention_half) }} 浮盈
            </div>
            <div v-else-if="row.half_position_ratio !== null">
              <span v-if="row.calculation_mode === 'cost_protection'">
                Pcost × {{ row.half_position_ratio }} (跌破 {{ ((1 - row.half_position_ratio) * 100).toFixed(0) }}%)
              </span>
              <span v-else>
                Pmax × {{ row.half_position_ratio }} (回撤 {{ ((1 - row.half_position_ratio) * 100).toFixed(0) }}%)
              </span>
            </div>
            <span v-else style="color: #909399">-</span>
          </template>
        </el-table-column>
        <el-table-column label="清仓线" min-width="160">
          <template #default="{ row }">
            <div v-if="row.calculation_mode === 'profit_retention' && row.profit_retention_clear !== null">
              保留 {{ formatPercent(row.profit_retention_clear) }} 浮盈
            </div>
            <div v-else-if="row.clear_position_ratio !== null">
              <span v-if="row.calculation_mode === 'cost_protection'">
                Pcost × {{ row.clear_position_ratio }} (跌破 {{ ((1 - row.clear_position_ratio) * 100).toFixed(0) }}%)
              </span>
              <span v-else>
                Pmax × {{ row.clear_position_ratio }} (回撤 {{ ((1 - row.clear_position_ratio) * 100).toFixed(0) }}%)
              </span>
            </div>
            <span v-else style="color: #909399">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="editStopLoss(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑利润等级对话框 -->
    <el-dialog v-model="profitDialogVisible" title="编辑利润等级配置" width="500px">
      <el-form :model="profitEditForm" label-width="140px" v-if="profitEditForm">
        <el-form-item label="等级名称">
          <el-input v-model="profitEditForm.level_name" />
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="profitEditForm.level_code" />
        </el-form-item>
        <el-form-item label="标识">
          <el-input v-model="profitEditForm.level_key" disabled />
        </el-form-item>
        <el-form-item label="利润阈值下限(%)">
          <el-input-number v-model="profitEditForm.pnl_threshold" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="利润阈值上限(%)">
          <el-input-number v-model="profitEditForm.pnl_threshold_max" :precision="1" style="width: 100%" />
          <div style="font-size: 12px; color: #909399">留空表示无上限</div>
        </el-form-item>
        <el-form-item label="判断依据">
          <el-radio-group v-model="profitEditForm.use_peak_pnl">
            <el-radio :label="1">PnL_peak (历史最高)</el-radio>
            <el-radio :label="0">PnL_now (当前)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="持仓天数下限(天)">
          <el-input-number v-model="profitEditForm.hold_days_min" :min="0" :precision="0" style="width: 100%" />
          <div style="font-size: 12px; color: #909399">留空表示无限制</div>
        </el-form-item>
        <el-form-item label="持仓天数上限(天)">
          <el-input-number v-model="profitEditForm.hold_days_max" :min="0" :precision="0" style="width: 100%" />
          <div style="font-size: 12px; color: #909399">留空表示无限制，匹配规则：min ≤ 持仓 < max</div>
        </el-form-item>
        <el-form-item label="显示颜色">
          <el-select v-model="profitEditForm.display_color" style="width: 100%">
            <el-option label="success (绿色)" value="success" />
            <el-option label="warning (黄色)" value="warning" />
            <el-option label="danger (红色)" value="danger" />
            <el-option label="info (灰色)" value="info" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="profitDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProfitLevel" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 编辑止盈线对话框 -->
    <el-dialog v-model="stopLossDialogVisible" title="编辑止盈/损线配置" width="500px">
      <el-form :model="stopLossEditForm" label-width="140px" v-if="stopLossEditForm">
        <el-form-item label="编码">
          <el-input v-model="stopLossEditForm.level_code" disabled />
        </el-form-item>
        <el-form-item label="利润等级">
          <el-input v-model="stopLossEditForm.level_name" disabled />
        </el-form-item>
        <el-form-item label="利润范围">
          <el-input :value="stopLossEditForm.pnl_min + '%' + (stopLossEditForm.pnl_max !== null ? ' ≤ PnL < ' + stopLossEditForm.pnl_max + '%' : ' 以上')" disabled />
        </el-form-item>
        <el-form-item label="计算方式">
          <el-radio-group v-model="stopLossEditForm.calculation_mode">
            <el-radio label="pmax_drawdown">基于Pmax回撤</el-radio>
            <el-radio label="profit_retention">基于Profit_max保留</el-radio>
            <el-radio label="cost_protection">基于成本保护</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="stopLossEditForm.calculation_mode === 'profit_retention'">
          <el-form-item label="减半仓保留比例">
            <el-slider v-model="stopLossEditForm.profit_retention_half" :min="0" :max="1" :step="0.05" show-stops />
            <div style="text-align: center; font-size: 12px; color: #606266">
              {{ formatPercent(stopLossEditForm.profit_retention_half) }}
            </div>
          </el-form-item>
          <el-form-item label="清仓保留比例">
            <el-slider v-model="stopLossEditForm.profit_retention_clear" :min="0" :max="1" :step="0.05" show-stops />
            <div style="text-align: center; font-size: 12px; color: #606266">
              {{ formatPercent(stopLossEditForm.profit_retention_clear) }}
            </div>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="减半仓系数">
            <el-slider v-model="stopLossEditForm.half_position_ratio" :min="0.5" :max="1" :step="0.01" show-stops />
            <div style="text-align: center; font-size: 12px; color: #606266">
              {{ stopLossEditForm.half_position_ratio }} (回撤 {{ ((1 - stopLossEditForm.half_position_ratio) * 100).toFixed(0) }}%)
            </div>
          </el-form-item>
          <el-form-item label="清仓系数">
            <el-slider v-model="stopLossEditForm.clear_position_ratio" :min="0.5" :max="1" :step="0.01" show-stops />
            <div style="text-align: center; font-size: 12px; color: #606266">
              {{ stopLossEditForm.clear_position_ratio }} (回撤 {{ ((1 - stopLossEditForm.clear_position_ratio) * 100).toFixed(0) }}%)
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="stopLossDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStopLoss" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import axios from 'axios'

// 利润等级配置
const profitLevels = ref([])
const profitLoading = ref(false)
const profitDialogVisible = ref(false)
const profitEditForm = ref(null)

// 止盈/损线配置
const stopLossConfigs = ref([])
const stopLossLoading = ref(false)
const stopLossDialogVisible = ref(false)
const stopLossEditForm = ref(null)

const saving = ref(false)

// 获取利润等级配置
const fetchProfitLevels = async () => {
  profitLoading.value = true
  try {
    const res = await axios.get('/api/config/profit-levels')
    profitLevels.value = res.data
  } catch (err) {
    ElMessage.error('获取利润等级配置失败: ' + err.message)
  } finally {
    profitLoading.value = false
  }
}

// 获取止盈/损线配置
const fetchStopLossConfigs = async () => {
  stopLossLoading.value = true
  try {
    const res = await axios.get('/api/config/stop-loss')
    stopLossConfigs.value = res.data
  } catch (err) {
    ElMessage.error('获取止盈/损线配置失败: ' + err.message)
  } finally {
    stopLossLoading.value = false
  }
}

const formatPercent = (val) => {
  if (val === null || val === undefined) return '-'
  return (val * 100).toFixed(0) + '%'
}

// 利润等级编辑
const editProfitLevel = (row) => {
  profitEditForm.value = { ...row }
  profitDialogVisible.value = true
}

const saveProfitLevel = async () => {
  saving.value = true
  try {
    await axios.put(`/api/config/profit-levels/${profitEditForm.value.id}`, profitEditForm.value)
    ElMessage.success('保存成功')
    profitDialogVisible.value = false
    fetchProfitLevels()
  } catch (err) {
    ElMessage.error('保存失败: ' + err.message)
  } finally {
    saving.value = false
  }
}

const resetProfitLevels = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要重置利润等级为默认配置吗？当前配置将被覆盖。',
      '确认重置',
      { type: 'warning' }
    )
    await axios.post('/api/config/profit-levels/reset')
    ElMessage.success('已重置为默认配置')
    fetchProfitLevels()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error('重置失败: ' + err.message)
    }
  }
}

// 止盈线编辑
const editStopLoss = (row) => {
  stopLossEditForm.value = { ...row }
  stopLossDialogVisible.value = true
}

const saveStopLoss = async () => {
  saving.value = true
  try {
    // 只提交可编辑的字段
    const payload = {
      half_position_ratio: stopLossEditForm.value.half_position_ratio,
      clear_position_ratio: stopLossEditForm.value.clear_position_ratio,
      calculation_mode: stopLossEditForm.value.calculation_mode,
      profit_retention_half: stopLossEditForm.value.profit_retention_half,
      profit_retention_clear: stopLossEditForm.value.profit_retention_clear
    }
    await axios.put(`/api/config/stop-loss/${stopLossEditForm.value.id}`, payload)
    ElMessage.success('保存成功')
    stopLossDialogVisible.value = false
    fetchStopLossConfigs()
  } catch (err) {
    ElMessage.error('保存失败: ' + err.message)
  } finally {
    saving.value = false
  }
}

const resetStopLoss = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要重置止盈线为默认配置吗？当前配置将被覆盖。',
      '确认重置',
      { type: 'warning' }
    )
    await axios.post('/api/config/stop-loss/reset', { confirm: true })
    ElMessage.success('已重置为默认配置')
    fetchStopLossConfigs()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error('重置失败: ' + err.message)
    }
  }
}

onMounted(() => {
  fetchProfitLevels()
  fetchStopLossConfigs()
})
</script>

<style scoped>
.config-page {
  padding: 20px;
}

.config-card {
  max-width: 1200px;
}
</style>
