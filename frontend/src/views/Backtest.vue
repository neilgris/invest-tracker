<template>
  <div>
    <el-tabs v-model="activeTab" type="border-card">

      <!-- ── Tab 1: 参数寻优 ─────────────────────────── -->
      <el-tab-pane label="参数寻优" name="search">
    <el-row :gutter="20">
      <!-- 左侧：网格定义 -->
      <el-col :span="8">
        <el-card shadow="hover" style="margin-bottom:14px">
          <template #header><span>搜索设置</span></template>
          <el-form label-width="90px" size="small">
            <el-form-item label="标的">
              <el-select v-model="gridForm.code" filterable clearable placeholder="搜索代码或名称" style="width:100%" :loading="loadingAssets">
                <el-option v-for="a in cacheAssets" :key="a.code" :label="`${a.name}（${a.code}）`" :value="a.code" />
              </el-select>
            </el-form-item>
            <el-form-item label="退出模式">
              <el-select v-model="gridForm.exit_mode" style="width:100%">
                <el-option label="固定止盈止损" value="simple" />
                <el-option label="移动止损 Pmax" value="pmax_drawdown" />
                <el-option label="浮盈保留" value="profit_retention" />
                <el-option label="成本保护" value="cost_protection" />
                <el-option label="MA均线穿越" value="ma_cross" />
              </el-select>
            </el-form-item>
            <div v-if="EXIT_MODE_DESC[gridForm.exit_mode]" class="mode-desc-box">
              <b>{{ EXIT_MODE_DESC[gridForm.exit_mode].title }}</b><br/>{{ EXIT_MODE_DESC[gridForm.exit_mode].body }}
            </div>
            <el-form-item label="排序目标">
              <el-select v-model="gridForm.objective" style="width:100%">
                <el-option label="综合得分(收益/回撤·推荐)" value="calmar" />
                <el-option label="总收益" value="total_return" />
                <el-option label="收益捕获率" value="capture" />
                <el-option label="回撤削减率" value="dd_reduction" />
              </el-select>
            </el-form-item>
            <div v-if="OBJECTIVE_DESC[gridForm.objective]" class="objective-desc-box">
              <div class="objective-formula">{{ OBJECTIVE_DESC[gridForm.objective].formula }}</div>
              <div style="margin-top:4px">{{ OBJECTIVE_DESC[gridForm.objective].body }}</div>
            </div>
            <el-divider style="margin:10px 0" />
            <el-form-item label="回撤入场回看">
              <el-input-number
                v-model="gridForm.reentry_lookback"
                :min="10" :max="250" :step="10" :precision="0"
                style="width:100%"
              />
              <div class="param-desc">回撤入场判断"近N日高点"的时间窗口（交易日）。默认60日≈3个月，参与扫描的回撤阈值在下方参数区间设置。</div>
            </el-form-item>
            <el-form-item label="样本外起始">
              <el-date-picker
                v-model="gridForm.train_end"
                type="date"
                placeholder="不填=全历史，不做OOS"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                style="width:100%"
              />
              <el-text type="info" size="small">此日期前=样本内寻优，之后=样本外验证</el-text>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="hover" style="margin-bottom:14px">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>参数区间 / 步长</span>
              <el-tag size="small" type="success">
                {{ gridComboCount }} 组合
              </el-tag>
            </div>
          </template>
          <div v-for="p in gridVisibleParams" :key="p.key" style="margin-bottom:16px">
            <div style="font-size:13px;color:#606266;margin-bottom:4px">
              <b>{{ p.label }}</b>
              <el-text type="info" size="small" style="margin-left:6px">（{{ gridSteps(p.key) }} 档）</el-text>
            </div>
            <div v-if="PARAM_DESC[p.key]" class="param-desc" style="margin-bottom:6px">{{ PARAM_DESC[p.key] }}</div>
            <div style="display:flex;gap:6px;align-items:center">
              <el-input-number v-model="gridForm.grid[p.key].min" :min="p.min" :max="p.max" :step="p.step" :precision="p.precision" size="small" controls-position="right" style="width:33%" />
              <span style="color:#C0C4CC">~</span>
              <el-input-number v-model="gridForm.grid[p.key].max" :min="p.min" :max="p.max" :step="p.step" :precision="p.precision" size="small" controls-position="right" style="width:33%" />
              <span style="color:#C0C4CC">步</span>
              <el-input-number v-model="gridForm.grid[p.key].step" :min="0" :max="p.max" :step="p.step" :precision="p.precision" size="small" controls-position="right" style="width:33%" />
            </div>
          </div>
          <el-text type="info" size="small">步长=0 或 起=止 表示该参数固定不扫</el-text>
        </el-card>

        <el-button type="primary" style="width:100%" :loading="loading"
          :disabled="!gridForm.code" @click="runGridSearch">
          开始寻优（{{ gridComboCount }} 组合）
        </el-button>
      </el-col>

      <!-- 右侧：结果 -->
      <el-col :span="16">
        <el-empty v-if="!gridResult && !loading"
          description="配置参数区间后点击「开始寻优」" style="margin-top:80px" />
        <div v-if="loading" style="text-align:center;margin-top:80px">
          <el-text type="info">搜索中，{{ gridComboCount }} 个组合 × 全历史，请稍候...</el-text>
        </div>

        <template v-if="gridResult">
          <!-- 最优结果横幅 -->
          <el-alert type="success" :closable="false" show-icon style="margin-bottom:14px">
            <template #title>
              最优组合（按{{ gridObjectiveLabel }}）：{{ gridBestParamsText }}
            </template>
            <!-- 一行核心指标 -->
            <el-tooltip effect="dark" placement="bottom" :show-after="200">
              <template #content>
                <b>年化收益</b>（已按252交易日/年折算）<br/>
                消除测试区间长短的影响，才能跨标的/跨时段比较。<br/>
                同期 B&H 括号内参考。
              </template>
              <span class="best-metric">年化 <b>{{ gridResult.best.ann_return_pct }}%</b>（总收益 {{ gridResult.best.total_return_pct }}%）</span>
            </el-tooltip>
            &nbsp;·&nbsp;
            <el-tooltip effect="dark" placement="bottom" :show-after="200">
              <template #content>
                <b>最大回撤</b><br/>
                持仓期净值从最高点到最低点的最大跌幅（5 cohorts 均值）。<br/>
                ETF 实盘中超过 30% 通常需要评估是否符合自身风险承受能力。
              </template>
              <span class="best-metric" :style="gridResult.best.max_drawdown > 40 ? 'color:#e6a23c' : ''">
                最大回撤 <b>{{ gridResult.best.max_drawdown }}%</b>
              </span>
            </el-tooltip>
            &nbsp;·&nbsp;
            <el-tooltip effect="dark" placement="bottom" :show-after="200">
              <template #content>
                <b>Calmar（年化） = 年化收益% ÷ 最大回撤%</b><br/>
                当前排序目标「综合得分」使用此公式。<br/>
                代表每承受1%最大回撤能换来多少%年化收益，越高越好。
              </template>
              <span class="best-metric">Calmar <b>{{ gridResult.best.max_drawdown > 0 ? (gridResult.best.ann_return_pct / gridResult.best.max_drawdown).toFixed(2) : '-' }}</b></span>
            </el-tooltip>
            &nbsp;·&nbsp;
            <el-tooltip effect="dark" placement="bottom" :show-after="200">
              <template #content>
                <b>盈亏比（Profit Factor）= 全部盈利之和 ÷ 全部亏损之和</b><br/>
                直白解读：每亏1元，能赚回多少元。<br/>
                · &gt;2.0：优秀&nbsp; · 1.5–2.0：良好&nbsp; · &lt;1.5：需改进<br/>
                与胜率结合判断：胜率低但盈亏比高，同样可行。
              </template>
              <span class="best-metric" :style="gridResult.best.profit_factor < 1.5 ? 'color:#e6a23c' : 'color:#67c23a'">
                盈亏比 <b>{{ gridResult.best.profit_factor }}</b>
              </span>
            </el-tooltip>
            &nbsp;·&nbsp;
            <el-tooltip effect="dark" placement="bottom" :show-after="200">
              <template #content>
                <b>Sortino = 年化收益 ÷ 下行年化标准差</b><br/>
                只惩罚下行波动，比 Sharpe 更适合止损策略。<br/>
                · &gt;1.0：良好&nbsp; · 0.5–1.0：可接受&nbsp; · &lt;0.5：风险偏高
              </template>
              <span class="best-metric">Sortino <b>{{ gridResult.best.sortino }}</b></span>
            </el-tooltip>
            &nbsp;·&nbsp;
            <el-tooltip effect="dark" placement="bottom" :show-after="200">
              <template #content>
                <b>Whipsaw 率</b> = 止损出场后 N 个交易日内价格回到<b>入场价</b>以上的比例<br/>
                含义：这笔止损是"冤枉"的——持有不动本可盈利<br/>
                · &lt;30%：止损质量较好&nbsp; · 30–60%：噪声与信号参半&nbsp; · &gt;60%：参数过紧
              </template>
              <span class="best-metric" :style="gridResult.best.whipsaw_rate_pct > 60 ? 'color:#e6a23c' : ''">
                Whipsaw <b>{{ gridResult.best.whipsaw_rate_pct }}%</b>
              </span>
            </el-tooltip>

            <!-- 第二行：心理承受力指标 -->
            <div style="margin-top:8px;padding-top:6px;border-top:1px solid rgba(0,0,0,0.08);font-size:12px;color:#606266">
              <el-tooltip effect="dark" placement="bottom" :show-after="200">
                <template #content>
                  <b>最大连续亏损次数</b><br/>
                  策略历史上最多连续亏损多少笔。<br/>
                  即使策略长期盈利，实战中连亏时能否坚持执行是关键。<br/>
                  超过5笔建议评估自己是否能接受。
                </template>
                <span style="cursor:help;margin-right:12px">
                  最大连亏 <b :style="gridResult.best.max_consec_loss >= 5 ? 'color:#e6a23c' : ''">{{ gridResult.best.max_consec_loss }} 笔</b>
                </span>
              </el-tooltip>
              <el-tooltip effect="dark" placement="bottom" :show-after="200">
                <template #content>
                  <b>最大回撤恢复期</b><br/>
                  从最大回撤的最低点，恢复到前高需要多少个交易日。<br/>
                  恢复期越长，意味着持有体验越痛苦。<br/>
                  超过2年（504交易日）需要有足够的心理预期。
                </template>
                <span style="cursor:help;margin-right:12px">
                  回撤恢复期 <b :style="gridResult.best.recovery_days > 504 ? 'color:#e6a23c' : ''">
                    {{ gridResult.best.recovery_days }} 日（{{ (gridResult.best.recovery_days / 21).toFixed(1) }} 个月）
                  </b>
                </span>
              </el-tooltip>
              <el-tooltip effect="dark" placement="bottom" :show-after="200">
                <template #content>
                  <b>均盈 / 均亏</b><br/>
                  每笔盈利交易的平均收益 vs 每笔亏损交易的平均亏损。<br/>
                  均盈 &gt; 均亏：即使胜率不高也能整体盈利（好策略的特征）。<br/>
                  均盈 &lt; 均亏：需要靠高胜率来弥补，更脆弱。
                </template>
                <span style="cursor:help">
                  均盈 <b style="color:#f56c6c">{{ gridResult.best.avg_win > 0 ? '+' : '' }}{{ gridResult.best.avg_win }}%</b>
                  &nbsp;/&nbsp;均亏 <b style="color:#67c23a">{{ gridResult.best.avg_loss }}%</b>
                </span>
              </el-tooltip>
            </div>
          </el-alert>

          <!-- 最优组合：价格走势 / 净值对比 / 收益分布（合并卡片，可切换） -->
          <el-card v-if="(gridResult.price_series && gridResult.best_trades) || (gridResult.best_equity_curve && gridResult.best_equity_curve.length)" shadow="hover" style="margin-bottom:14px">
            <template #header>
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">
                <div style="display:flex;align-items:center;gap:8px">
                  <el-radio-group v-model="gridBestChartView" size="small">
                    <el-radio-button value="trade">价格走势 + 持仓区间</el-radio-button>
                    <el-radio-button value="curve">策略净值 vs B&amp;H</el-radio-button>
                    <el-radio-button value="dist">单笔收益分布</el-radio-button>
                  </el-radio-group>
                  <el-tag v-if="gridBestChartView === 'trade' && gridResult.exit_mode === 'pmax_drawdown'" size="small" type="warning">
                    移动止损模式无止盈出口，全部为止损退出
                  </el-tag>
                </div>
                <el-text type="info" size="small">
                  <template v-if="gridBestChartView === 'trade'">
                    <span style="color:#67c23a">▲</span>&nbsp;买入&nbsp;
                    <span style="color:#67c23a">●</span>&nbsp;盈利退出&nbsp;
                    <span style="color:#e6a23c">▼</span>&nbsp;亏损退出&nbsp;
                    <span style="color:#909399">■</span>&nbsp;时间止损&nbsp;
                    <span style="color:#409eff">◆</span>&nbsp;持有中&nbsp;&nbsp;
                    <span style="background:rgba(103,194,58,0.28);padding:0 4px;border-radius:2px">盈利持仓</span>&nbsp;
                    <span style="background:rgba(245,108,108,0.28);padding:0 4px;border-radius:2px">亏损持仓</span>
                  </template>
                  <template v-else-if="gridBestChartView === 'curve'">
                    <span style="color:#409eff">━</span>&nbsp;策略净值&nbsp;
                    <span style="color:#c0c4cc">┄</span>&nbsp;B&amp;H&nbsp;
                    <template v-if="gridResult.test_period">
                      &nbsp;<span style="background:#fef0f0;padding:0 4px">粉色区=样本外（未见过的行情）</span>
                    </template>
                  </template>
                  <template v-else>
                    <template v-if="gridResult.test_period">
                      <span style="color:#409eff">■</span>&nbsp;样本内&nbsp;
                      <span style="color:#e6a23c">■</span>&nbsp;样本外&nbsp;
                    </template>
                    5 cohort 所有已完结交易 · P10/P25/P50/P75/P90 分位数
                  </template>
                </el-text>
              </div>
            </template>
            <v-chart v-if="gridBestChartView === 'trade'" :option="gridBestTradeOption" style="height:380px" autoresize />
            <v-chart v-else-if="gridBestChartView === 'curve'" :option="gridBestCurveOption" style="height:380px" autoresize />
            <v-chart v-else :option="gridBestDistOption" style="height:320px" autoresize />
          </el-card>

          <!-- 热力图（恰好2维时） -->
          <el-card v-if="gridResult.heatmap" shadow="hover" style="margin-bottom:14px">
            <template #header>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span>参数热力图（{{ gridObjectiveLabel }}得分）</span>
                <el-text type="info" size="small">看「连成片的亮区」而非孤立尖峰，才是稳健参数</el-text>
              </div>
            </template>
            <v-chart :option="gridHeatmapOption" style="height:340px" autoresize />
          </el-card>

          <!-- 样本内/样本外期间说明 -->
          <el-row :gutter="12" style="margin-bottom:14px">
            <el-col :span="12">
              <el-card shadow="never" style="background:#f0f9eb;border-color:#b3e19d">
                <div style="font-size:12px;color:#67c23a;font-weight:bold;margin-bottom:4px">📊 样本内（寻优）</div>
                <div style="font-size:13px">{{ gridResult.train_period.start }} ~ {{ gridResult.train_period.end }}</div>
                <div style="font-size:12px;color:#909399">{{ gridResult.train_period.days }} 个交易日 · B&H {{ gridResult.benchmark_total_return_pct }}%</div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card v-if="gridResult.test_period" shadow="never" style="background:#fef0f0;border-color:#fbc4c4">
                <div style="font-size:12px;color:#f56c6c;font-weight:bold;margin-bottom:4px">🔬 样本外（验证）</div>
                <div style="font-size:13px">{{ gridResult.test_period.start }} ~ {{ gridResult.test_period.end }}</div>
                <div style="font-size:12px;color:#909399">{{ gridResult.test_period.days }} 个交易日 · B&H {{ gridResult.oos_benchmark_total_return_pct }}%</div>
              </el-card>
              <el-card v-else shadow="never" style="background:#f5f7fa;border-color:#dcdfe6">
                <div style="font-size:12px;color:#909399;font-weight:bold;margin-bottom:4px">🔬 样本外（验证）</div>
                <div style="font-size:13px;color:#c0c4cc">未设置样本外切割日期</div>
                <div style="font-size:12px;color:#c0c4cc">在左侧「样本外起始」选择日期后重新运行</div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 样本外对比表 -->
          <el-card v-if="gridResult.oos && gridResult.oos.length" shadow="hover" style="margin-bottom:14px">
            <template #header>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span>样本外验证（Top {{ gridResult.oos.length }} 样本内组合）</span>
                <el-text type="info" size="small">保留率 ≥ 70% 稳健 · 30-70% 一般 · &lt; 30% 过拟合警告</el-text>
              </div>
            </template>
            <el-table :data="gridResult.oos" size="small" border stripe :row-class-name="oosRowClass">
              <el-table-column v-for="p in gridResult.sweep_params" :key="p" min-width="80">
                <template #header>
                  <el-tooltip :content="PARAM_DESC[p] || gridParamLabel(p)" placement="top" :show-after="300" effect="dark">
                    <span class="col-tip">{{ gridParamLabel(p) }}</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">{{ row.params[p] }}</template>
              </el-table-column>
              <el-table-column width="90">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>样本内总收益</b><br/>该参数组合在寻优区间内的策略累计收益<br/>（连续再入场，5 cohorts 中位数）。</template>
                    <span class="col-tip">IS收益</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">
                  <span :class="row.is_total_return_pct >= 0 ? 'profit' : 'loss'">{{ row.is_total_return_pct }}%</span>
                </template>
              </el-table-column>
              <el-table-column width="80">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>样本内最大回撤</b><br/>寻优区间内持仓期净值从高点到低点的最大跌幅。<br/>越小说明策略回撤控制越好。</template>
                    <span class="col-tip">IS回撤</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }"><span style="color:#e6a23c">{{ row.is_max_drawdown }}%</span></template>
              </el-table-column>
              <el-table-column width="90">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>样本外总收益</b><br/>同一参数组合在验证期内的实际表现。<br/>与 IS收益 对比：差距越小，参数越稳健；差距悬殊则可能过拟合。</template>
                    <span class="col-tip">OOS收益</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">
                  <span :class="row.oos_total_return_pct >= 0 ? 'profit' : 'loss'">{{ row.oos_total_return_pct }}%</span>
                </template>
              </el-table-column>
              <el-table-column width="80">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>样本外最大回撤</b><br/>验证期内的最大净值回撤。<br/>应与 IS回撤 量级相近；差距过大说明风险特征发生漂移。</template>
                    <span class="col-tip">OOS回撤</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }"><span style="color:#e6a23c">{{ row.oos_max_drawdown }}%</span></template>
              </el-table-column>
              <el-table-column width="82">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>样本外收益捕获率</b><br/>= 策略OOS收益 ÷ B&H OOS收益<br/>&gt;100% = 跑赢大盘；&lt;0% = 大盘正收益但策略亏损。</template>
                    <span class="col-tip">OOS捕获</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">{{ ((row.oos_capture_rate || 0) * 100).toFixed(0) }}%</template>
              </el-table-column>
              <el-table-column width="88">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content>
                      <b>得分保留率</b><br/>= OOS得分 ÷ IS得分 × 100%<br/>衡量参数在样本外的稳健性：<br/>
                      🟢 ≥ 70% — 稳健，可信<br/>🟡 30–70% — 一般，谨慎使用<br/>🔴 &lt; 30% — 过拟合警告，不建议实盘
                    </template>
                    <span class="col-tip">保留率</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">
                  <span v-if="row.score_keep_pct != null" :style="oosKeepColor(row.score_keep_pct)">{{ row.score_keep_pct }}%</span>
                  <span v-else>-</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- 排行榜 -->
          <el-card shadow="hover">
            <template #header>
              <span>样本内排行榜 Top {{ gridResult.top.length }} / 共 {{ gridResult.total_combos }} 组合</span>
            </template>
            <el-table :data="gridResult.top" size="small" border stripe max-height="420"
              :row-class-name="gridRowClass">
              <el-table-column label="#" type="index" width="44" />
              <el-table-column v-for="p in gridResult.sweep_params" :key="p" min-width="78">
                <template #header>
                  <el-tooltip :content="PARAM_DESC[p] || gridParamLabel(p)" placement="top" :show-after="300" effect="dark">
                    <span class="col-tip">{{ gridParamLabel(p) }}</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">{{ row.params[p] }}</template>
              </el-table-column>
              <el-table-column width="80" prop="score" sortable>
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content>
                      <b>排序得分</b><br/>由所选「排序目标」决定：<br/>· 综合得分 = 总收益 ÷ 最大回撤（Calmar 类）<br/>· 总收益 / 捕获率 / 回撤削减 各取对应值<br/>同一目标下越高越好，可点击列头排序。
                    </template>
                    <span class="col-tip">得分</span>
                  </el-tooltip>
                </template>
              </el-table-column>
              <el-table-column width="90">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>样本内总收益</b><br/>连续再入场策略在整个样本内区间的累计收益<br/>（5 cohorts 中位数）。<br/>参考同期 B&H 收益判断是否跑赢大盘。</template>
                    <span class="col-tip">总收益</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">
                  <span :class="row.total_return_pct >= 0 ? 'profit' : 'loss'">{{ row.total_return_pct }}%</span>
                </template>
              </el-table-column>
              <el-table-column width="78">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>最大回撤</b><br/>持仓期间净值从高点到低点的最大跌幅（5 cohorts 均值）。<br/>越小说明策略对下行风险控制越好。<br/>与 B&H 回撤对比可评估回撤削减效果。</template>
                    <span class="col-tip">回撤</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }"><span style="color:#e6a23c">{{ row.max_drawdown }}%</span></template>
              </el-table-column>
              <el-table-column width="80">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>收益捕获率</b><br/>= 策略总收益 ÷ B&H 总收益<br/>代表持仓期间"拿到了大盘涨幅的几成"。<br/>100% = 完全跟上；&gt;100% = 跑赢大盘；<br/>注意：若 B&H 为负，此值无实际意义。</template>
                    <span class="col-tip">捕获率</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">{{ ((row.capture_rate || 0) * 100).toFixed(0) }}%</template>
              </el-table-column>
              <el-table-column width="86">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>回撤削减</b><br/>= (B&H最大回撤 − 策略最大回撤) ÷ B&H最大回撤 × 100%<br/>表示策略相对"买入持有"减少了多少回撤。<br/>正值 = 保护有效；负值 = 策略回撤反而更大。</template>
                    <span class="col-tip">回撤削减</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">{{ row.dd_reduction_pct }}%</template>
              </el-table-column>
              <el-table-column width="86">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>Whipsaw 率</b> = 止损出场后 N 日内价格回到<b>入场价</b>以上的比例<br/>即"这笔止损是冤枉的——持有不动本可盈利"<br/>&gt;60% 说明参数过紧，止损多为噪声触发，建议放宽阈值或延长冷静期</template>
                    <span class="col-tip">Whipsaw</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">
                  <span :style="row.whipsaw_rate_pct > 60 ? 'color:#e6a23c' : ''">{{ row.whipsaw_rate_pct }}%</span>
                </template>
              </el-table-column>
              <el-table-column width="70">
                <template #header>
                  <el-tooltip placement="top" :show-after="300" effect="dark">
                    <template #content><b>在市时间</b><br/>持仓天数 ÷ 总观测天数。<br/>过低（&lt;50%）说明策略频繁止损、大量时间空仓，<br/>摩擦成本和踏空风险会在实盘中放大。</template>
                    <span class="col-tip">在市</span>
                  </el-tooltip>
                </template>
                <template #default="{ row }">{{ row.time_in_market_pct }}%</template>
              </el-table-column>
            </el-table>
          </el-card>
        </template>
      </el-col>
    </el-row>
      </el-tab-pane>

      <!-- ── Tab 2: 历史记录 ─────────────────────────── -->
      <el-tab-pane label="历史记录" name="history">
        <el-row style="margin-bottom:14px" :gutter="12" align="middle">
          <el-col :span="6">
            <el-select
              v-model="historyCode"
              clearable
              placeholder="按标的筛选（全部）"
              style="width:100%"
              @change="loadHistory"
            >
              <el-option
                v-for="c in historyCodes"
                :key="c.code"
                :label="`${c.name || c.code}（${c.code}）`"
                :value="c.code"
              />
            </el-select>
          </el-col>
          <el-col :span="2">
            <el-button @click="loadHistory" :loading="historyLoading">刷新</el-button>
          </el-col>
          <el-col :span="16" style="text-align:right;color:#909399;font-size:13px">
            共 {{ historyRecords.length }} 条记录
          </el-col>
        </el-row>

        <el-table
          :data="historyRecords"
          v-loading="historyLoading"
          border
          size="small"
          row-key="id"
          :default-sort="{ prop: 'created_at', order: 'descending' }"
        >
          <!-- 时间 -->
          <!-- 标的 -->
          <el-table-column width="130">
            <template #header>
              <el-tooltip content="标的代码和名称" placement="top" :show-after="300">
                <span class="col-tip">标的</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <div style="font-weight:bold">{{ row.asset_name || row.code }}</div>
              <div style="color:#909399;font-size:11px">{{ row.code }}</div>
            </template>
          </el-table-column>

          <!-- 退出模式 -->
          <el-table-column width="105">
            <template #header>
              <el-tooltip content="使用的退出策略模式" placement="top" :show-after="300">
                <span class="col-tip">退出模式</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <el-tag size="small" :type="exitModeTagType(row.exit_mode)">{{ exitModeLabel(row.exit_mode) }}</el-tag>
            </template>
          </el-table-column>

          <!-- 最优参数 -->
          <el-table-column min-width="170" show-overflow-tooltip>
            <template #header>
              <el-tooltip content="本次寻优找到的最优参数组合" placement="top" :show-after="300">
                <span class="col-tip">最优参数</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span style="font-size:12px;font-family:monospace">{{ formatParams(row) }}</span>
            </template>
          </el-table-column>

          <!-- 得分 -->
          <el-table-column width="78" sortable prop="calmar">
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>综合得分（寻优排序依据）</b><br/>
                  排序目标为 Calmar 时：得分 = 年化收益% ÷ 最大回撤%<br/>
                  排序目标为总收益时：得分 = 年化收益%<br/>
                  同一标的可横向比较不同策略的得分。<br/>
                  ⭐ 越高越好，建议以此为主要筛选依据。
                </template>
                <span class="col-tip" style="color:#409eff;font-weight:bold">得分</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span :style="scoreColor(row)" style="font-weight:bold">
                {{ computeScore(row)?.toFixed(2) ?? '-' }}
              </span>
              <div style="font-size:10px;color:#909399">{{ scoreObjectiveLabel(row) }}</div>
            </template>
          </el-table-column>

          <!-- 年化收益 -->
          <el-table-column width="80" sortable prop="ann_return_pct">
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>年化收益率</b><br/>
                  按 252 交易日/年折算，消除测试区间长短的影响。<br/>
                  与总收益不同：14年100%总收益 ≈ 年化5%，远低于看起来的直觉值。
                </template>
                <span class="col-tip">年化%</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span :class="row.ann_return_pct >= 0 ? 'profit' : 'loss'">
                {{ row.ann_return_pct != null ? (row.ann_return_pct >= 0 ? '+' : '') + row.ann_return_pct + '%' : '-' }}
              </span>
            </template>
          </el-table-column>

          <!-- 最大回撤 -->
          <el-table-column width="82" sortable prop="max_drawdown">
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>最大回撤</b><br/>
                  样本内持仓净值从最高点到最低点的最大跌幅。<br/>
                  越小越好。ETF 策略建议控制在 30% 以内；超过 50% 极难坚持执行。
                </template>
                <span class="col-tip">最大回撤</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span :style="row.max_drawdown > 40 ? 'color:#f56c6c' : 'color:#e6a23c'">
                {{ row.max_drawdown != null ? row.max_drawdown + '%' : '-' }}
              </span>
            </template>
          </el-table-column>

          <!-- Calmar -->
          <el-table-column width="75" sortable prop="calmar">
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>Calmar Ratio = 年化收益% ÷ 最大回撤%</b><br/>
                  标准风险调整收益指标。<br/>
                  · ≥ 0.5：良好&nbsp; · ≥ 1.0：优秀&nbsp; · &lt; 0.3：偏弱
                </template>
                <span class="col-tip">Calmar</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span :style="row.calmar >= 1 ? 'color:#67c23a' : row.calmar >= 0.5 ? '' : 'color:#e6a23c'">
                {{ row.calmar?.toFixed(2) ?? '-' }}
              </span>
            </template>
          </el-table-column>

          <!-- 盈亏比 -->
          <el-table-column width="75" sortable prop="profit_factor">
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>盈亏比（Profit Factor）= 总盈利之和 ÷ 总亏损之和</b><br/>
                  每亏1元能换回多少元收益。<br/>
                  · ≥ 2.0：优秀&nbsp; · 1.5–2.0：良好&nbsp; · &lt; 1.5：需改进
                </template>
                <span class="col-tip">盈亏比</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span :style="row.profit_factor >= 2 ? 'color:#67c23a' : row.profit_factor >= 1.5 ? '' : 'color:#e6a23c'">
                {{ row.profit_factor?.toFixed(2) ?? '-' }}
              </span>
            </template>
          </el-table-column>

          <!-- Sortino -->
          <el-table-column width="72" sortable prop="sortino">
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>Sortino Ratio = 年化收益 ÷ 下行标准差</b><br/>
                  只惩罚下行波动，比 Sharpe 更适合止损策略。<br/>
                  · ≥ 1.0：良好&nbsp; · 0.5–1.0：可接受&nbsp; · &lt; 0.5：风险偏高
                </template>
                <span class="col-tip">Sortino</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span :style="row.sortino >= 1 ? 'color:#67c23a' : row.sortino >= 0.5 ? '' : 'color:#e6a23c'">
                {{ row.sortino?.toFixed(2) ?? '-' }}
              </span>
            </template>
          </el-table-column>

          <!-- Whipsaw -->
          <el-table-column width="80" sortable prop="whipsaw_rate_pct">
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>Whipsaw 率</b><br/>
                  止损出场后价格在 N 日内回到入场价以上的比例。<br/>
                  即"止损是冤枉的"的比例。<br/>
                  · &lt; 30%：止损质量好&nbsp; · &gt; 60%：参数过紧，噪声过多
                </template>
                <span class="col-tip">Whipsaw</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span :style="row.whipsaw_rate_pct > 60 ? 'color:#e6a23c' : row.whipsaw_rate_pct != null && row.whipsaw_rate_pct < 30 ? 'color:#67c23a' : ''">
                {{ row.whipsaw_rate_pct != null ? row.whipsaw_rate_pct + '%' : '-' }}
              </span>
            </template>
          </el-table-column>

          <!-- 连亏 -->
          <el-table-column width="68" sortable prop="max_consec_loss">
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>最大连续亏损次数</b><br/>
                  策略历史上最多连续亏损多少笔。<br/>
                  即使长期盈利，连亏期也需要能坚持执行。超过 5 笔需评估心理承受力。
                </template>
                <span class="col-tip">最大连亏</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span :style="row.max_consec_loss >= 5 ? 'color:#e6a23c' : ''">
                {{ row.max_consec_loss ?? '-' }}
              </span>
            </template>
          </el-table-column>

          <!-- 恢复期 -->
          <el-table-column width="78" sortable prop="recovery_days">
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>最大回撤恢复期（交易日）</b><br/>
                  从最大回撤的底部恢复到前高需要多少交易日。<br/>
                  超过 2 年（504日）意味着极长的"水下"体验。
                </template>
                <span class="col-tip">恢复期(日)</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <el-tooltip v-if="row.recovery_days" :content="`约 ${(row.recovery_days/21).toFixed(1)} 个月`" placement="top">
                <span :style="row.recovery_days > 504 ? 'color:#e6a23c' : ''">
                  {{ row.recovery_days ?? '-' }}
                </span>
              </el-tooltip>
              <span v-else>-</span>
            </template>
          </el-table-column>

          <!-- 测试区间 -->
          <el-table-column min-width="130" show-overflow-tooltip>
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>测试区间</b><br/>
                  样本内寻优区间（含 OOS 标注说明有样本外验证）。<br/>
                  区间越长、含 OOS 验证的结果更可信。
                </template>
                <span class="col-tip">区间</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span style="font-size:11px">
                {{ row.train_start?.slice(0,7) }} ~ {{ row.train_end?.slice(0,7) }}
                <el-tag v-if="row.oos_start" size="small" type="danger" style="margin-left:4px">含OOS</el-tag>
              </span>
            </template>
          </el-table-column>

          <!-- B&H -->
          <el-table-column width="72" sortable prop="bh_return">
            <template #header>
              <el-tooltip placement="top" :show-after="300" effect="dark">
                <template #content>
                  <b>同期 B&H 总收益</b><br/>
                  在相同区间内买入持有不做任何操作的总收益。<br/>
                  参考基准：策略年化 > B&H 年化才有意义。
                </template>
                <span class="col-tip">B&H%</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span style="color:#909399">{{ row.bh_return != null ? row.bh_return + '%' : '-' }}</span>
            </template>
          </el-table-column>

          <!-- 备注 -->
          <el-table-column min-width="120">
            <template #header>备注</template>
            <template #default="{ row }">
              <el-input
                v-model="row.notes"
                size="small"
                placeholder="添加备注..."
                @blur="saveNotes(row)"
                @keyup.enter="saveNotes(row)"
              />
            </template>
          </el-table-column>

          <!-- 时间（最后展示，聚焦指标优先） -->
          <el-table-column prop="created_at" width="150" sortable>
            <template #header>
              <el-tooltip content="寻优执行时间" placement="top" :show-after="300">
                <span class="col-tip">时间</span>
              </el-tooltip>
            </template>
            <template #default="{ row }">
              <span style="font-size:12px">{{ row.created_at?.slice(0,16).replace('T',' ') }}</span>
            </template>
          </el-table-column>

          <!-- 操作 -->
          <el-table-column width="110" fixed="right">
            <template #header>操作</template>
            <template #default="{ row }">
              <el-button
                type="primary" size="small"
                :loading="restoringRecord"
                @click="restoreFromRecord(row)"
                style="margin-right:4px"
              >查看</el-button>
              <el-button type="danger" size="small" @click="deleteRecord(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import VChart from 'vue-echarts'
import {
  analysisCacheStatus, analysisGridSearch,
  saveBacktestRecord, listBacktestRecords, listBacktestCodes,
  updateBacktestNotes, deleteBacktestRecord
} from '../api'

// ── 排序目标说明 ──────────────────────────────────────
const OBJECTIVE_DESC = {
  calmar: {
    formula: '得分 = 年化收益% ÷ 最大回撤%',
    body: '标准 Calmar Ratio，同时衡量收益与风险。\n用年化收益而非总收益，避免测试区间长短影响评分（14年数据不能和5年数据的总收益直接比）。\n示例：年化收益6%、最大回撤20% → Calmar=0.30',
  },
  total_return: {
    formula: '得分 = 策略总收益%',
    body: '只看绝对收益，完全不考虑持仓期间的下行风险。适合对回撤有独立判断、纯粹追求最大收益的场景。',
  },
  capture: {
    formula: '得分 = 策略总收益 ÷ B&H总收益',
    body: '衡量策略捕获了大盘涨幅的几成。\n>100% = 跑赢大盘；100% = 完全跟上；<100% = 跑输大盘；负值 = 大盘正收益但策略亏损。\n注意：B&H为负时此值无实际意义。',
  },
  dd_reduction: {
    formula: '得分 = (B&H最大回撤 - 策略最大回撤) ÷ B&H最大回撤 × 100%',
    body: '衡量止损策略相对"买入持有"减少了多少下行风险。\n正值 = 止损有效保护了资金；负值 = 止损后在更低价再入场，回撤反而更大。\n适合重点想评估"止损到底有没有用"的场景。',
  },
}

// ── 退出模式说明 & 参数说明 ──────────────────────────
const EXIT_MODE_DESC = {
  simple: {
    title: '固定止盈止损',
    body: '设两条固定价格线：浮盈 ≥ 止盈阈值时卖出；浮亏 ≥ 止损阈值时离场。逻辑最简单，参数最少，建议作为基准对比其他模式。',
  },
  ma_cross: {
    title: 'MA 均线穿越（趋势跟踪）',
    body: '价格跌破 MA(N) 时出场（盈利=止盈，亏损=止损），兜底止损作安全网。\n持仓期间只要价格在 MA 上方就继续持有，跌破即离场，自动跟随趋势。\n建议：MA60（3个月）适合中线，MA120（半年）减少噪声，MA200（年线）趋势信号强。\n⚡ 再入场：将「MA入场过滤」设为与 MA均线周期相同，可实现"跌破出场、重回才入场"的完整双向穿越策略。',
  },
  pmax_drawdown: {
    title: '移动止损（Trailing Stop）',
    body: '持续追踪持仓期最高价，价格从该高点回落超过 Pmax% 时卖出。止损位随价格上涨自动抬升，能锁住大段利润同时承受日常波动。兜底止损始终有效。',
  },
  profit_retention: {
    title: '浮盈保留（两阶段）',
    body: '① 浮盈先须达到「激活阈值%」；\n② 激活后止损线 = 历史最高浮盈 × 保留比，跌破即卖出。\n示例：激活20%、保留比0.6 → 若最高涨至30%，止损线 = 30%×0.6 = +18%，确保至少以+18%离场。激活前兜底止损仍有效。',
  },
  cost_protection: {
    title: '成本保护（两阶段）',
    body: '① 浮盈先须达到「激活阈值%」；\n② 激活后止损线抬至 买入成本×(1+保护底线%) 处，跌破即卖出（0=保本，2=锁成本+2%，负值=允许小亏）。激活前兜底止损仍有效。',
  },
}

const PARAM_DESC = {
  stop_loss_pct:        '兜底止损：浮亏达此%强制卖出，无论使用哪种退出模式都生效。宽基ETF建议10-20%；过小频繁止损，过大单次亏损过重。',
  max_hold_days:        '时间止损：持仓超过此天数无论盈亏强制平仓，防止资金长期被套。0=不限制。常设365天（1年）或730天（2年）。',
  take_profit_pct:      '止盈线：浮盈涨到此%时卖出锁利。过低会频繁止盈、错失后续上涨；建议参考标的历史平均涨幅周期设定。',
  pmax_drawdown_pct:    '回撤容忍度：从持仓最高点回落超过此%触发卖出。宽基ETF日均波幅~1%，10%≈约10个交易日正常波动，可视个人风险偏好适度放宽。',
  profit_trigger_pct:   '激活阈值：浮盈须先达到此%，保护机制才生效。激活前只有兜底止损保护，建议设在你认为"已有可观盈利"的水平（如ETF涨幅15-30%）。',
  profit_retention_pct: '浮盈保留比（0～1）：激活后，止损线 = 历史最高浮盈 × 此比例。0.5=保留50%浮盈，0.8=保留80%（保护更激进，但容易提前触发）。',
  cost_trigger_pct:     '激活阈值：浮盈须先达到此%后保本保护才生效。建议至少5-10%，给策略一定获利空间再锁仓位。',
  cost_floor_pct:       '保护底线：激活后止损线 = 成本价×(1+此值/100)。0=保本，2=成本+2%，-1=允许亏1%才触发（负值通常不推荐）。',
  reentry_cooldown:     '冷静期（交易日）：止损/止盈后等待此天数再重新入场，避免震荡市频繁进出被"锯齿"消耗。宽基ETF建议20-30天。',
  reentry_pullback_pct: '回撤入场阈值（%）：冷静期满后，还需从近N日高点回撤此%才触发买入；0=冷静期满立即入场（原始行为）。\n作用：避免追高，等市场回调到相对低位再买入。建议范围5-10%。',
  ma_entry_period:      'MA入场过滤（交易日）：仅在 close > MA(N) 时允许入场，作为趋势过滤器，避免在熊市中买入。\n0=不过滤（任何时候都可买入）。\n常用：MA200=年线过滤，只在长期趋势向上时参与。',
  ma_period:            'MA均线周期（交易日）：ma_cross 模式下，价格跌破此均线时出场。\n常用：60≈3个月（中线），120≈半年（减少噪声），200≈年线（趋势信号最强）。',
  whipsaw_window:       'Whipsaw判定窗口（交易日）：止损出场后，若此日内价格回到入场价以上则判为假止损（冤枉单）。此参数只影响统计分析，不影响实际交易逻辑。',
}

// ── 状态 ─────────────────────────────────────────────
const activeTab = ref('search')

const loading = ref(false)
const loadingAssets = ref(false)
const cacheAssets = ref([])
const gridResult = ref(null)
const gridBestChartView = ref('trade')

// ── 历史记录 ──────────────────────────────────────────
const historyLoading  = ref(false)
const historyRecords  = ref([])
const historyCodes    = ref([])
const historyCode     = ref('')

const loadHistory = async () => {
  historyLoading.value = true
  try {
    const [recs, codes] = await Promise.all([
      listBacktestRecords(historyCode.value || undefined),
      listBacktestCodes(),
    ])
    historyRecords.value = recs.data
    historyCodes.value   = codes.data
  } catch (e) {
    ElMessage.error('加载历史记录失败: ' + e.message)
  } finally {
    historyLoading.value = false
  }
}

const saveNotes = async (row) => {
  try {
    await updateBacktestNotes(row.id, row.notes)
  } catch (e) { /* 静默 */ }
}

const deleteRecord = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除「${row.asset_name || row.code}」的这条记录？`, '确认删除', { type: 'warning' })
    await deleteBacktestRecord(row.id)
    ElMessage.success('已删除')
    loadHistory()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// ── 从历史记录恢复寻优展示 ──────────────────────────
const restoringRecord = ref(false)

const restoreFromRecord = async (row) => {
  restoringRecord.value = true
  try {
    // 1. 切换到参数寻优 Tab
    activeTab.value = 'search'

    // 2. 恢复基础配置
    gridForm.value.code       = row.code
    gridForm.value.exit_mode  = row.exit_mode
    gridForm.value.objective  = row.objective || 'calmar'
    // 有 OOS 时恢复样本外起始（train_end 对应 IS 结束日）
    gridForm.value.train_end  = row.oos_start ? row.train_end : ''
    gridForm.value.reentry_lookback = row.best_params?.reentry_lookback || 60

    // 3. 把所有参数固定为历史最优值（单点网格，step=0）
    const saved = row.best_params || {}
    for (const k of Object.keys(GRID_PARAM_META)) {
      const v = saved[k]
      if (v != null) {
        gridForm.value.grid[k] = { min: v, max: v, step: 0 }
      }
    }

    // 4. 确保资产列表已加载
    if (!cacheAssets.value.length) await loadCacheAssets()

    // 5. 运行寻优（跳过自动保存，避免重复入库）
    suppressAutoSave.value = true
    await runGridSearch()
  } finally {
    suppressAutoSave.value = false
    restoringRecord.value  = false
  }
}

// 得分计算（基于 objective 重建）
const computeScore = (row) => {
  if (!row) return null
  const obj = row.objective || 'calmar'
  if (obj === 'calmar' || !obj) return row.calmar
  if (obj === 'total_return') return row.ann_return_pct
  return row.calmar   // capture / dd_reduction 回退到 calmar
}
const scoreObjectiveLabel = (row) => {
  const map = { calmar: 'Calmar', total_return: '年化%', capture: '捕获率', dd_reduction: '回撤削减' }
  return map[row.objective] || 'Calmar'
}
const scoreColor = (row) => {
  const s = computeScore(row)
  if (s == null) return ''
  const obj = row.objective || 'calmar'
  if (obj === 'calmar') return s >= 1 ? 'color:#67c23a' : s >= 0.5 ? 'color:#409eff' : 'color:#e6a23c'
  if (obj === 'total_return') return s >= 10 ? 'color:#67c23a' : s >= 5 ? 'color:#409eff' : 'color:#e6a23c'
  return ''
}

const exitModeLabel = (mode) => {
  const map = { simple: '固定止盈止损', pmax_drawdown: 'Pmax移动止损', profit_retention: '浮盈保留', cost_protection: '成本保护', ma_cross: 'MA穿越' }
  return map[mode] || mode
}
const exitModeTagType = (mode) => {
  const map = { simple: '', pmax_drawdown: 'warning', profit_retention: 'success', cost_protection: 'info', ma_cross: 'danger' }
  return map[mode] || ''
}
const formatParams = (row) => {
  if (!row.best_params || !row.sweep_params?.length) return '-'
  return row.sweep_params
    .map(k => `${GRID_PARAM_META[k]?.label ?? k}=${row.best_params[k]}`)
    .join('  ')
}

// ── 参数元数据 ────────────────────────────────────────
const GRID_PARAM_META = {
  stop_loss_pct:        { label: '止损阈值%',      min: 1,  max: 50,  step: 1,   precision: 1, def: { min: 10, max: 25,  step: 5    } },
  reentry_cooldown:     { label: '再入场等待(日)',  min: 0,  max: 120, step: 5,   precision: 0, def: { min: 5,  max: 20,  step: 5    } },
  reentry_pullback_pct: { label: '回撤入场阈值%',  min: 0,  max: 20,  step: 2,   precision: 1, def: { min: 0,  max: 10,  step: 2    } },
  ma_entry_period:      { label: 'MA入场过滤(日)',  min: 0,  max: 250, step: 20,  precision: 0, def: { min: 0,  max: 200, step: 100  } },
  ma_period:            { label: 'MA均线周期(日)',  min: 5,  max: 250, step: 20,  precision: 0, def: { min: 60, max: 200, step: 20   } },
  take_profit_pct:      { label: '止盈阈值%',     min: 1,  max: 200, step: 1,    precision: 1, def: { min: 10, max: 40,  step: 10   } },
  pmax_drawdown_pct:    { label: 'Pmax回撤%',     min: 1,  max: 50,  step: 1,    precision: 1, def: { min: 5,  max: 20,  step: 5    } },
  profit_trigger_pct:   { label: '激活阈值%',     min: 1,  max: 200, step: 1,    precision: 1, def: { min: 5, max: 30,  step: 5   } },
  profit_retention_pct: { label: '浮盈保留比',    min: 0,  max: 1,   step: 0.05, precision: 2, def: { min: 0.5, max: 0.8, step: 0.05 } },
  cost_trigger_pct:     { label: '激活阈值%',     min: 1,  max: 200, step: 1,    precision: 1, def: { min: 5,  max: 20,  step: 5    } },
  cost_floor_pct:       { label: '保护底线%',     min: 0,  max: 50,  step: 0.5,  precision: 1, def: { min: 0,  max: 5,   step: 2.5  } },
}

const MODE_SWEEP_PARAMS = {
  simple:           ['take_profit_pct'],
  pmax_drawdown:    ['pmax_drawdown_pct'],
  profit_retention: ['profit_trigger_pct', 'profit_retention_pct'],
  cost_protection:  ['cost_trigger_pct', 'cost_floor_pct'],
  ma_cross:         ['ma_period'],
}

const makeGridDefaults = () => {
  const grid = {}
  for (const k of Object.keys(GRID_PARAM_META)) {
    grid[k] = { ...GRID_PARAM_META[k].def }
  }
  return grid
}

const gridForm = ref({
  code: '',
  exit_mode: 'pmax_drawdown',
  objective: 'calmar',
  train_end: '',
  reentry_lookback: 60,   // 回撤入场的高点回看窗口（交易日），固定配置不参与扫描
  grid: makeGridDefaults(),
})

// ── 计算属性 ──────────────────────────────────────────
const gridVisibleParams = computed(() => {
  // ma_cross 模式用 ma_entry_period（重回均线再入场）替代回撤条件，两者逻辑冲突故排除
  const isMaCross = gridForm.value.exit_mode === 'ma_cross'
  const common = isMaCross
    ? ['stop_loss_pct', 'reentry_cooldown', 'ma_entry_period']
    : ['stop_loss_pct', 'reentry_cooldown', 'reentry_pullback_pct', 'ma_entry_period']
  const keys = [...common, ...(MODE_SWEEP_PARAMS[gridForm.value.exit_mode] || [])]
  return keys.map(k => ({ key: k, ...GRID_PARAM_META[k] }))
})

const gridSteps = (key) => {
  const g = gridForm.value.grid[key]
  if (!g || !g.step || g.step <= 0 || g.min >= g.max) return 1
  return Math.floor((g.max - g.min) / g.step + 1e-9) + 1
}

const gridComboCount = computed(() => {
  return gridVisibleParams.value.reduce((acc, p) => acc * gridSteps(p.key), 1)
})

const gridObjectiveLabel = computed(() => {
  const map = { calmar: '综合得分', total_return: '总收益', capture: '捕获率', dd_reduction: '回撤削减', win_rate: '胜率' }
  return map[gridForm.value.objective] || '得分'
})

const gridParamLabel = (key) => GRID_PARAM_META[key]?.label || key

const gridBestParamsText = computed(() => {
  if (!gridResult.value) return ''
  const p = gridResult.value.best.params
  return gridResult.value.sweep_params.map(k => `${gridParamLabel(k)}=${p[k]}`).join('  ')
})

// ── 数据加载 ──────────────────────────────────────────
const loadCacheAssets = async () => {
  loadingAssets.value = true
  try {
    const res = await analysisCacheStatus()
    cacheAssets.value = res.data.assets || []
  } catch (e) {
    ElMessage.error('加载资产列表失败: ' + e.message)
  } finally {
    loadingAssets.value = false
  }
}

// ── 保存记录（自动，寻优完成后静默执行）──────────────
const savingRecord      = ref(false)
const suppressAutoSave  = ref(false)   // 从历史恢复时跳过自动保存

const saveCurrentRecord = async () => {
  if (!gridResult.value || savingRecord.value || suppressAutoSave.value) return
  savingRecord.value = true
  try {
    const d = gridResult.value
    const b = d.best
    const asset = cacheAssets.value.find(a => a.code === gridForm.value.code)
    const calmar = b.max_drawdown > 0 ? +(b.ann_return_pct / b.max_drawdown).toFixed(3) : 0
    await saveBacktestRecord({
      code:           gridForm.value.code,
      asset_name:     asset?.name || gridForm.value.code,
      exit_mode:      d.exit_mode,
      objective:      gridForm.value.objective,
      best_params:    b.params || {},
      sweep_params:   d.sweep_params || [],
      train_start:    d.train_period?.start,
      train_end:      d.train_period?.end,
      train_days:     d.train_period?.days,
      oos_start:      d.test_period?.start,
      oos_end:        d.test_period?.end,
      ann_return_pct: b.ann_return_pct,
      max_drawdown:   b.max_drawdown,
      calmar:         calmar,
      profit_factor:  b.profit_factor,
      sortino:        b.sortino,
      win_rate:       null,
      whipsaw_rate_pct: b.whipsaw_rate_pct,
      max_consec_loss:  b.max_consec_loss,
      recovery_days:    b.recovery_days,
      avg_win:          b.avg_win,
      avg_loss:         b.avg_loss,
      total_combos:     d.total_combos,
      bh_return:        d.benchmark_total_return_pct,
    })
    listBacktestCodes().then(r => { historyCodes.value = r.data })  // 刷新标的列表
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally {
    savingRecord.value = false
  }
}

const runGridSearch = async () => {
  if (!gridForm.value.code) return ElMessage.warning('请选择标的')
  loading.value = true
  gridResult.value = null
  try {
    const grid = {}
    for (const p of gridVisibleParams.value) {
      grid[p.key] = { ...gridForm.value.grid[p.key] }
    }
    const res = await analysisGridSearch({
      code: gridForm.value.code,
      exit_mode: gridForm.value.exit_mode,
      objective: gridForm.value.objective,
      train_end: gridForm.value.train_end || null,
      reentry_lookback: gridForm.value.reentry_lookback || 60,
      grid,
    })
    if (!res.data.ok) return ElMessage.error(res.data.message || '寻优失败')
    gridResult.value = res.data
    gridBestChartView.value = 'trade'
    saveCurrentRecord()         // 自动保存最优解（后台静默执行）
  } catch (e) {
    ElMessage.error('寻优失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

// ── 工具函数 ──────────────────────────────────────────
const gridRowClass = ({ rowIndex }) => (rowIndex === 0 ? 'grid-best-row' : '')

const oosRowClass = ({ row }) => {
  const k = row.score_keep_pct
  if (k == null) return ''
  if (k >= 70) return 'oos-row-good'
  if (k >= 30) return 'oos-row-warn'
  return 'oos-row-bad'
}

const oosKeepColor = (pct) => {
  if (pct >= 70) return 'color:#67c23a;font-weight:bold'
  if (pct >= 30) return 'color:#e6a23c;font-weight:bold'
  return 'color:#f56c6c;font-weight:bold'
}

// ── 图表 ─────────────────────────────────────────────
const gridBestTradeOption = computed(() => {
  const g = gridResult.value
  if (!g?.price_series?.length || !g?.best_trades?.length) return {}

  const ps      = g.price_series
  const trades  = g.best_trades
  const dates   = ps.map(p => p[0])
  const closes  = ps.map(p => p[1])
  const dateIdx = Object.fromEntries(dates.map((d, i) => [d, i]))
  const lastDate = dates[dates.length - 1]

  const holdAreas = trades.map(t => {
    const endD = t.sell_date || lastDate
    let color
    if (t.sell_reason === '持有中')  color = 'rgba(64,158,255,0.22)'
    else if (t.pct > 0)             color = 'rgba(103,194,58,0.30)'
    else                            color = 'rgba(245,108,108,0.30)'
    return [{ xAxis: t.buy_date, itemStyle: { color } }, { xAxis: endD }]
  })

  const markPoints = []
  for (const t of trades) {
    const bi = dateIdx[t.buy_date]
    if (bi != null) {
      markPoints.push({
        coord: [bi, closes[bi]],
        symbol: 'triangle', symbolSize: 9, symbolRotate: 0,
        itemStyle: { color: '#67c23a' }, label: { show: false },
        name: `买入 ${t.buy_date}  @${t.buy_price}`,
      })
    }
    if (t.sell_date) {
      const si = dateIdx[t.sell_date]
      if (si != null) {
        let sym, sz, rot, col
        if (t.sell_reason?.includes('时间'))     { sym='rect';     sz=7; rot=0;   col='#909399' }
        else if (t.sell_reason === '持有中')      { sym='diamond';  sz=8; rot=0;   col='#409eff' }
        else if (t.pct > 0)                      { sym='circle';   sz=8; rot=0;   col='#67c23a' }
        else                                      { sym='triangle'; sz=9; rot=180; col='#e6a23c' }
        markPoints.push({
          coord: [si, closes[si]],
          symbol: sym, symbolSize: sz, symbolRotate: rot,
          itemStyle: { color: col }, label: { show: false },
          name: `${t.sell_reason}  ${t.sell_date}  @${t.sell_price}  ${t.pct >= 0 ? '+' : ''}${t.pct}%`,
        })
      }
    }
  }

  let splitDate = null
  if (g.test_period?.start) {
    splitDate = dates.find(d => d >= g.test_period.start) || null
  }

  return {
    tooltip: { trigger: 'axis', formatter: params => {
      const p = params[0]
      return `${p?.axisValue}<br/>价格: <b>${(+p?.value || 0).toFixed(3)}</b>`
    }},
    grid: { left: '6%', right: '2%', top: '8%', bottom: '20%' },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, height: 18, bottom: 6 },
    ],
    xAxis: { type: 'category', data: dates, boundaryGap: false,
             axisLabel: { formatter: v => v.slice(0, 7), fontSize: 11 } },
    yAxis: { type: 'value', scale: true, axisLabel: { formatter: v => v.toFixed(1) } },
    series: [{
      name: '收盘价', type: 'line', data: closes, symbol: 'none', z: 10,
      lineStyle: { color: '#409EFF', width: 1.5 },
      markArea: { silent: true, data: holdAreas },
      markPoint: { data: markPoints, tooltip: { formatter: p => p.name } },
      ...(splitDate ? {
        markLine: {
          symbol: ['none', 'none'], silent: true,
          lineStyle: { color: '#f56c6c', type: 'dashed', width: 2 },
          label: { show: true, formatter: '← 样本内 | 样本外 →',
                   color: '#f56c6c', fontSize: 11, position: 'insideEndTop' },
          data: [{ xAxis: splitDate }],
        }
      } : {}),
    }],
  }
})

const gridBestCurveOption = computed(() => {
  const g = gridResult.value
  if (!g?.best_equity_curve?.length) return {}
  const curve   = g.best_equity_curve
  const bhCurve = g.best_bh_curve || []
  const dates   = curve.map(p => p[0])
  const vals    = curve.map(p => +p[1].toFixed(4))
  const bhMap   = Object.fromEntries(bhCurve.map(p => [p[0], p[1]]))
  const bhVals  = dates.map(d => (bhMap[d] != null ? +bhMap[d].toFixed(4) : null))

  let splitName = null
  if (g.test_period && g.train_period) {
    splitName = dates.find(d => d > g.train_period.end) || null
  }

  const stratMark = {}
  if (splitName) {
    stratMark.markArea = {
      silent: true,
      itemStyle: { color: 'rgba(245,108,108,0.06)' },
      data: [[{ xAxis: splitName }, { xAxis: dates[dates.length - 1] }]],
    }
    stratMark.markLine = {
      symbol: 'none', silent: true,
      lineStyle: { color: '#f56c6c', type: 'dashed', width: 1 },
      label: { formatter: '样本外起点', position: 'insideEndTop', color: '#f56c6c', fontSize: 11 },
      data: [{ xAxis: splitName }],
    }
  }

  return {
    tooltip: { trigger: 'axis', formatter: params => {
      const lines = params.filter(p => p.value != null && p.seriesType === 'line')
        .map(p => `${p.marker}${p.seriesName}: <b>${(+p.value).toFixed(3)}</b>`).join('<br/>')
      return `${params[0]?.axisValue}<br/>${lines}`
    }},
    legend: { data: ['策略净值', 'B&H'], top: 4 },
    grid: { left: '6%', right: '3%', top: '12%', bottom: '12%' },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, height: 18, bottom: 6 },
    ],
    xAxis: { type: 'category', data: dates, boundaryGap: false,
             axisLabel: { formatter: v => v.slice(0, 7), fontSize: 11 } },
    yAxis: { type: 'value', scale: true, axisLabel: { formatter: v => v.toFixed(1) } },
    series: [
      { name: '策略净值', type: 'line', data: vals, symbol: 'none',
        lineStyle: { color: '#409EFF', width: 2 }, areaStyle: { color: 'rgba(64,158,255,0.06)' },
        z: 3, ...stratMark },
      { name: 'B&H', type: 'line', data: bhVals, symbol: 'none',
        lineStyle: { color: '#C0C4CC', width: 1.5, type: 'dashed' }, z: 2 },
    ],
  }
})

const gridBestDistOption = computed(() => {
  const g = gridResult.value
  if (!g?.best_trade_distribution) return {}
  const labels   = ['P10', 'P25', 'P50', 'P75', 'P90']
  const hasSplit = !!(g.test_period && g.best_is_trade_distribution && g.best_oos_trade_distribution)

  if (hasSplit) {
    const isVals  = [g.best_is_trade_distribution.p10,  g.best_is_trade_distribution.p25,  g.best_is_trade_distribution.p50,  g.best_is_trade_distribution.p75,  g.best_is_trade_distribution.p90]
    const oosVals = [g.best_oos_trade_distribution.p10, g.best_oos_trade_distribution.p25, g.best_oos_trade_distribution.p50, g.best_oos_trade_distribution.p75, g.best_oos_trade_distribution.p90]
    return {
      tooltip: { trigger: 'axis', formatter: params => {
        const lines = params.map(p => `${p.marker}${p.seriesName}: <b>${p.value >= 0 ? '+' : ''}${p.value}%</b>`).join('<br/>')
        return `${params[0].name}<br/>${lines}`
      }},
      legend: { data: ['样本内', '样本外'], top: 4 },
      grid: { left: '7%', right: '3%', top: '14%', bottom: '8%' },
      xAxis: { type: 'category', data: labels },
      yAxis: { type: 'value', axisLabel: { formatter: v => v + '%' } },
      series: [
        { name: '样本内', type: 'bar', barGap: '10%', itemStyle: { color: '#409EFF' }, data: isVals,
          label: { show: true, formatter: p => `${p.value >= 0 ? '+' : ''}${p.value}%`,
                   position: p => p.value >= 0 ? 'top' : 'bottom', fontSize: 11 } },
        { name: '样本外', type: 'bar', itemStyle: { color: '#e6a23c' }, data: oosVals,
          label: { show: true, formatter: p => `${p.value >= 0 ? '+' : ''}${p.value}%`,
                   position: p => p.value >= 0 ? 'top' : 'bottom', fontSize: 11 } },
      ],
    }
  }

  const d    = g.best_trade_distribution
  const vals = [d.p10, d.p25, d.p50, d.p75, d.p90]
  return {
    tooltip: { trigger: 'axis', formatter: params => `${params[0].name}: ${params[0].value >= 0 ? '+' : ''}${params[0].value}%` },
    grid: { left: '7%', right: '3%', top: '8%', bottom: '8%' },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value', axisLabel: { formatter: v => v + '%' } },
    series: [{ type: 'bar', itemStyle: { color: '#409EFF' }, data: vals,
      label: { show: true, formatter: p => `${p.value >= 0 ? '+' : ''}${p.value}%`,
               position: p => p.value >= 0 ? 'top' : 'bottom', fontSize: 11 } }],
  }
})

const gridHeatmapOption = computed(() => {
  const h = gridResult.value?.heatmap
  if (!h) return {}
  const scores = h.cells.map(c => c[2])
  let minS = Math.min(...scores)
  let maxS = Math.max(...scores)
  if (maxS === minS) { minS -= 1; maxS += 1 }

  return {
    tooltip: { position: 'top', formatter: p => {
      const v = p.value
      return `${gridParamLabel(h.x_param)} = <b>${h.x_vals[v[0]]}</b><br/>`
           + `${gridParamLabel(h.y_param)} = <b>${h.y_vals[v[1]]}</b><br/>`
           + `得分: <b>${v[2]}</b>`
    }},
    grid: { left: '14%', right: '6%', top: '10%', bottom: '22%' },
    xAxis: { type: 'category', data: h.x_vals.map(String),
             name: gridParamLabel(h.x_param), nameLocation: 'middle', nameGap: 32, splitArea: { show: true } },
    yAxis: { type: 'category', data: h.y_vals.map(String),
             name: gridParamLabel(h.y_param), nameLocation: 'middle', nameGap: 48, splitArea: { show: true } },
    visualMap: { min: minS, max: maxS, calculable: true, orient: 'horizontal',
                 left: 'center', bottom: 4, itemHeight: 120,
                 inRange: { color: ['#a8d8a8', '#ffffff', '#f56c6c'] } },
    series: [{ type: 'heatmap', data: h.cells,
      label: { show: true, formatter: params => String(params.value[2]), fontSize: 11, fontWeight: 'bold', color: '#303133' },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.4)' } } }],
  }
})

// ── 侦听 ─────────────────────────────────────────────
watch(() => gridForm.value.exit_mode, () => { gridResult.value = null })

watch(() => gridForm.value.code, (code) => {
  gridResult.value = null
  if (!code) { gridForm.value.train_end = ''; return }
  const asset = cacheAssets.value.find(a => a.code === code)
  if (!asset?.start || !asset?.end) { gridForm.value.train_end = ''; return }
  const t0 = new Date(asset.start).getTime()
  const t1 = new Date(asset.end).getTime()
  gridForm.value.train_end = new Date(t0 + (t1 - t0) * 2 / 3).toISOString().split('T')[0]
})

onMounted(() => {
  loadCacheAssets()
  loadHistory()
})

watch(activeTab, (tab) => {
  if (tab === 'history') loadHistory()
})
</script>

<style scoped>
.profit { color: #f56c6c; }
.loss   { color: #67c23a; }
.col-tip     { cursor: help; border-bottom: 1px dashed #909399; }
.best-metric { cursor: help; border-bottom: 1px dashed #67c23a; }
.mode-desc-box { background:#f0f9eb; border-left:3px solid #67c23a; border-radius:4px; padding:8px 10px; font-size:12px; color:#606266; line-height:1.7; margin-bottom:12px; white-space:pre-line; }
.objective-desc-box { background:#f0f4ff; border-left:3px solid #409eff; border-radius:4px; padding:8px 10px; font-size:12px; color:#606266; line-height:1.7; margin-bottom:12px; white-space:pre-line; }
.objective-formula  { font-weight:bold; color:#409eff; font-size:13px; margin-bottom:2px; font-family:monospace; }
.param-desc    { font-size:11px; color:#909399; line-height:1.6; margin-top:3px; }
:deep(.grid-best-row) { background: #f0f9eb !important; font-weight: bold; }
:deep(.oos-row-good)  { background: #f0f9eb !important; }
:deep(.oos-row-warn)  { background: #fdf6ec !important; }
:deep(.oos-row-bad)   { background: #fef0f0 !important; }
</style>
