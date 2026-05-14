<template>
  <div>
    <el-card shadow="hover">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>交易记录</span>
          <div style="display: flex; gap: 8px">
            <el-button type="warning" @click="detectDivs" :loading="detectingDivs">检测分红</el-button>
            <el-button type="primary" @click="showDialog = true">新增交易</el-button>
          </div>
        </div>
      </template>

      <!-- 筛选条件 -->
      <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; align-items: center">
        <el-input v-model="filters.code" placeholder="代码" clearable style="width: 120px" @clear="loadTrades" @keyup.enter="loadTrades" />
        <el-select v-model="filters.direction" placeholder="方向" clearable style="width: 100px" @change="loadTrades">
          <el-option label="买入" value="buy" />
          <el-option label="卖出" value="sell" />
          <el-option label="分红" value="dividend" />
        </el-select>
        <el-date-picker v-model="filters.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 260px" @change="loadTrades" />
        <el-button type="primary" @click="loadTrades" :icon="Search">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>

      <el-table :data="pagedTrades" stripe style="width: 100%">
        <el-table-column prop="trade_date" label="日期" width="120" />
        <el-table-column prop="code" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="160" />
        <el-table-column prop="direction" label="方向" width="80">
          <template #default="{ row }">
            <el-tag :type="row.direction === 'buy' ? 'danger' : row.direction === 'sell' ? 'success' : 'warning'" size="small">
              {{ row.direction === 'buy' ? '买入' : row.direction === 'sell' ? '卖出' : '分红' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="100">
          <template #default="{ row }">{{ row.price?.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column label="数量" width="100">
          <template #default="{ row }">{{ row.quantity?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="金额" width="120">
          <template #default="{ row }">¥{{ row.amount?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="手续费" width="90">
          <template #default="{ row }">¥{{ (row.fee || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="费率" width="80">
          <template #default="{ row }">
            <span v-if="row.fee && row.amount">{{ (row.fee / row.amount * 100).toFixed(3) }}%</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="editTrade(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="removeTrade(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="trades.length"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="showDialog" :title="isEdit ? '编辑交易' : '新增交易'" width="500px">
      <!-- 新增交易时显示模式切换 -->
      <div v-if="!isEdit" style="margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #e4e7ed">
        <el-radio-group v-model="quickMode">
          <el-radio-button :value="false">标准模式</el-radio-button>
          <el-radio-button :value="true">联接基金快速模式</el-radio-button>
        </el-radio-group>
        <div v-if="quickMode" style="margin-top: 8px; font-size: 12px; color: #909399">
          联接基金只需输入代码、日期、金额，自动获取当日净值，手续费默认为0
        </div>
      </div>

      <el-form :model="form" label-width="80px">
        <el-form-item label="代码">
          <div style="display: flex; gap: 8px; width: 100%">
            <el-input v-model="form.code" placeholder="如 600519, 510300" :disabled="isEdit" style="flex: 1" />
            <el-button v-if="!quickMode || isEdit" type="primary" :loading="validating" @click="validateCode" :disabled="!form.code || isEdit">校验</el-button>
            <el-button v-if="quickMode && !isEdit" type="success" :loading="fetchingFund" @click="fetchFundInfo" :disabled="!form.code || !form.trade_date">获取净值</el-button>
          </div>
        </el-form-item>
        
        <!-- 标准模式显示名称输入 -->
        <el-form-item v-if="!quickMode || isEdit" label="名称">
          <el-input v-model="form.name" placeholder="如 贵州茅台, 沪深300ETF" />
        </el-form-item>
        
        <!-- 快速模式显示获取到的名称 -->
        <el-form-item v-if="quickMode && !isEdit" label="名称">
          <el-input v-model="form.name" disabled placeholder="自动获取" />
        </el-form-item>

        <el-form-item v-if="!quickMode || isEdit" label="方向">
          <el-radio-group v-model="form.direction">
            <el-radio value="buy">买入</el-radio>
            <el-radio value="sell">卖出</el-radio>
            <el-radio value="dividend">分红</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 快速模式方向选择 -->
        <el-form-item v-if="quickMode && !isEdit" label="方向">
          <el-radio-group v-model="form.direction">
            <el-radio value="buy">买入</el-radio>
            <el-radio value="sell">卖出</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="日期">
          <el-date-picker v-model="form.trade_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>

        <!-- 标准模式价格输入 -->
        <el-form-item v-if="!quickMode || isEdit" label="价格">
          <el-input-number v-model="form.price" :precision="4" :min="0" style="width: 100%" />
        </el-form-item>
        
        <!-- 快速模式价格显示（自动获取） -->
        <el-form-item v-if="quickMode && !isEdit" :label="form.direction === 'buy' ? '净值' : '赎回净值'">
          <el-input-number v-model="form.price" :precision="4" :min="0" style="width: 100%" disabled />
          <div v-if="form.price > 0" style="font-size: 12px; color: #67c23a; margin-top: 4px">
            已获取{{ form.direction === 'buy' ? '净值' : '赎回净值' }}: {{ form.price.toFixed(4) }}
          </div>
        </el-form-item>

        <!-- 买入/卖出：输入份数，自动计算总金额 -->
        <el-form-item v-if="form.direction === 'buy' || form.direction === 'sell'" label="份数">
          <el-input-number v-model="form.quantity" :precision="2" :min="0" style="width: 100%" />
          <div v-if="form.price > 0 && form.quantity > 0" class="el-form-item__tip" style="font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px">
            <template v-if="form.direction === 'buy'">
              预估金额：{{ (form.price * form.quantity).toFixed(2) }} 元 + 手续费 = {{ (form.price * form.quantity + (form.fee || 0)).toFixed(2) }} 元
            </template>
            <template v-else>
              卖出总额：{{ (form.price * form.quantity).toFixed(2) }} 元，手续费 {{ (form.fee || 0).toFixed(2) }} 元，到账 {{ (form.price * form.quantity - (form.fee || 0)).toFixed(2) }} 元
            </template>
          </div>
        </el-form-item>

        <!-- 分红：输入份数（分红再投资） -->
        <el-form-item v-if="form.direction === 'dividend'" label="份数">
          <el-input-number v-model="form.quantity" :precision="2" :min="0" style="width: 100%" />
          <div v-if="form.price > 0 && form.quantity > 0" class="el-form-item__tip" style="font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px">
            分红金额：{{ (form.price * form.quantity).toFixed(2) }} 元（再投资）
          </div>
        </el-form-item>

        <!-- 标准模式手续费输入 -->
        <el-form-item v-if="!quickMode || isEdit" label="手续费">
          <el-input-number v-model="form.fee" :precision="2" :min="0" style="width: 100%" />
        </el-form-item>
        
        <!-- 快速模式手续费显示（默认为0） -->
        <el-form-item v-if="quickMode && !isEdit" label="手续费">
          <el-input-number v-model="form.fee" :precision="2" :min="0" style="width: 100%" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px">
            {{ form.direction === 'buy' ? '联接基金申购费通常为0或很低，默认0可修改' : '赎回费根据持有期限计算，默认0可修改' }}
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="submitTrade" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 分红确认对话框 -->
    <el-dialog v-model="divDialog" title="检测到分红记录" width="700px">
      <div v-if="divList.length === 0" style="text-align: center; color: #909399; padding: 20px">
        未检测到新的分红记录
      </div>
      <el-table v-else :data="divList" stripe>
        <el-table-column prop="code" label="代码" width="80" />
        <el-table-column label="名称" width="140">
          <template #default="{ row }">{{ row.short_name || row.name }}</template>
        </el-table-column>
        <el-table-column prop="date" label="分红日" width="110" />
        <el-table-column label="每份分红" width="100">
          <template #default="{ row }">{{ row.dividend_per_unit?.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column label="持仓量" width="80">
          <template #default="{ row }">{{ row.quantity?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="分红金额" width="100">
          <template #default="{ row }">¥{{ row.dividend_amount?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="再投资价" width="100">
          <template #default="{ row }">{{ row.price?.toFixed(4) }}</template>
        </el-table-column>
        <el-table-column label="再投资份额" width="100">
          <template #default="{ row }">{{ row.reinvest_qty?.toFixed(2) }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="divDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmDivs" :loading="confirmingDivs" :disabled="divList.length === 0">
          确认全部再投资
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { getTrades, createTrade, updateTrade, deleteTrade, validateCode as validateCodeApi, getFundInfo, detectDividends, confirmDividends } from '../api'

const trades = ref([])
const showDialog = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const submitting = ref(false)
const validating = ref(false)
const detectingDivs = ref(false)
const divDialog = ref(false)
const divList = ref([])
const confirmingDivs = ref(false)

// 联接基金快速模式
const quickMode = ref(false)
const fetchingFund = ref(false)

// 分页配置
const pagination = ref({
  page: 1,
  pageSize: 20
})

// 分页后的交易数据
const pagedTrades = computed(() => {
  const start = (pagination.value.page - 1) * pagination.value.pageSize
  const end = start + pagination.value.pageSize
  return trades.value.slice(start, end)
})

const handlePageChange = (page) => {
  pagination.value.page = page
}

const handleSizeChange = (size) => {
  pagination.value.pageSize = size
  pagination.value.page = 1
}

const filters = ref({
  code: '',
  direction: '',
  dateRange: null,
})

const defaultForm = () => ({
  code: '',
  name: '',
  direction: 'buy',
  price: 0,
  quantity: 0,  // 买入时输入份数
  amount: 0,    // 卖出/分红时输入金额
  trade_date: new Date().toISOString().slice(0, 10),
  fee: 0,
})

const form = ref(defaultForm())

const validateCode = async () => {
  if (!form.value.code) return
  validating.value = true
  try {
    const res = await validateCodeApi(form.value.code)
    const data = res.data
    if (data.valid) {
      form.value.name = data.name
      ElMessage.success(`校验通过：${data.name}`)
    } else {
      ElMessage.warning('代码无效，未找到对应股票/ETF')
    }
  } catch {
    ElMessage.error('校验失败，请检查网络')
  } finally {
    validating.value = false
  }
}

const fetchFundInfo = async () => {
  if (!form.value.code || !form.value.trade_date) {
    ElMessage.warning('请输入代码和日期')
    return
  }
  fetchingFund.value = true
  try {
    const res = await getFundInfo(form.value.code, form.value.trade_date)
    const data = res.data
    if (data.valid) {
      form.value.name = data.name
      form.value.price = data.nav
      form.value.direction = 'buy'
      form.value.fee = 0
      ElMessage.success(`已获取 ${data.name} ${form.value.trade_date} 净值: ${data.nav.toFixed(4)}`)
    } else {
      ElMessage.warning(data.message || '获取基金信息失败')
    }
  } catch (e) {
    ElMessage.error('获取基金信息失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    fetchingFund.value = false
  }
}

const loadTrades = async () => {
  const params = { limit: 200 }
  if (filters.value.code) params.code = filters.value.code
  if (filters.value.direction) params.direction = filters.value.direction
  if (filters.value.dateRange && filters.value.dateRange.length === 2) {
    params.start_date = filters.value.dateRange[0]
    params.end_date = filters.value.dateRange[1]
  }
  const res = await getTrades(params)
  trades.value = res.data
}

const resetFilters = () => {
  filters.value = { code: '', direction: '', dateRange: null }
  loadTrades()
}

const editTrade = (row) => {
  isEdit.value = true
  quickMode.value = false
  editId.value = row.id
  form.value = { ...row, trade_date: row.trade_date }
  
  // 买入/卖出/分红：从 amount 反推 quantity（用于编辑时显示）
  if (row.price > 0) {
    if (row.direction === 'buy') {
      // 买入：amount = price * qty + fee
      form.value.quantity = (row.amount - (row.fee || 0)) / row.price
    } else if (row.direction === 'sell') {
      // 卖出：amount = price * qty
      form.value.quantity = row.amount / row.price
    } else if (row.direction === 'dividend') {
      // 分红：amount = 0，从数据库的 quantity 直接显示
      form.value.quantity = row.quantity || 0
    }
  }
  
  showDialog.value = true
}

const removeTrade = async (id) => {
  await ElMessageBox.confirm('确认删除该交易记录？', '提示', { type: 'warning' })
  await deleteTrade(id)
  ElMessage.success('已删除')
  loadTrades()
}

const submitTrade = async () => {
  submitting.value = true
  try {
    const payload = { ...form.value }
    
    // 买入/卖出/分红：根据单价、份数计算总金额
    if (payload.direction === 'buy') {
      // 买入：总金额 = 单价 × 份数 + 手续费
      payload.amount = payload.price * payload.quantity + (payload.fee || 0)
    } else if (payload.direction === 'sell') {
      // 卖出：总金额 = 单价 × 份数（卖出总额，不含手续费）
      payload.amount = payload.price * payload.quantity
    } else if (payload.direction === 'dividend') {
      // 分红：总金额 = 0（分红再投资不增加成本）
      payload.amount = 0
    }
    
    if (isEdit.value) {
      await updateTrade(editId.value, payload)
    } else {
      await createTrade(payload)
    }
    ElMessage.success(isEdit.value ? '已更新' : '已添加')
    showDialog.value = false
    form.value = defaultForm()
    isEdit.value = false
    quickMode.value = false
    loadTrades()
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    submitting.value = false
  }
}

const detectDivs = async () => {
  detectingDivs.value = true
  try {
    const res = await detectDividends()
    divList.value = res.data.dividends || []
    divDialog.value = true
    if (divList.value.length === 0) {
      ElMessage.info('未检测到新的分红记录')
    }
  } catch {
    ElMessage.error('检测分红失败')
  } finally {
    detectingDivs.value = false
  }
}

const confirmDivs = async () => {
  confirmingDivs.value = true
  try {
    await confirmDividends(divList.value)
    ElMessage.success('分红再投资已记录')
    divDialog.value = false
    divList.value = []
    loadTrades()
  } catch (e) {
    ElMessage.error('确认失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    confirmingDivs.value = false
  }
}

onMounted(loadTrades)
</script>
