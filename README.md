# Invest Tracker - 投资追踪平台

## 版本记录

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.5 | 2026-06-02 | 策略参数寻优回测模块、历史记录、死代码清理 |
| v1.4 | 2026-05-31 | PE估值分析、统计重构、数据库清理 |
| v1.3 | 2026-05-28 | 配置管理模块、数据库迁移支持 |
| v1.2 | 2026-05-24 | 持仓统计优化、数据分析逻辑改进 |
| v1.1 | 2026-05-14 | 仓库清理 |
| v1.0 | 2026-05-09 | 初始版本 |

## 项目概述

个人投资追踪可视化平台，支持 A股、ETF、联接基金的投资记录、持仓管理、收益统计，以及历史行情分析和策略参数寻优。

## 技术栈

### 后端 (Python)
- **FastAPI** — Web 框架
- **SQLAlchemy** — ORM
- **SQLite** — 数据库
- **akshare** — A股/ETF/基金行情数据
- **APScheduler** — 定时任务（每日收盘后拉取行情）
- **uvicorn** — ASGI 服务器
- **numpy** — 策略回测数值计算

### 前端 (Vue 3)
- **Vue 3 + Vite** — 前端框架 + 构建
- **Element Plus** — UI 组件库
- **ECharts** — 图表（K线、折线、热力图）
- 打包后由 FastAPI 静态文件托管，单端口 (8000) 运行

---

## 核心功能

### 1. 交易管理（/trades）
- 录入买卖交易：代码、方向（买/卖/分红）、价格、金额、日期
- 支持联接基金交易记录
- 自动检测并确认分红再投资
- 交易列表筛选（代码、方向、日期范围）

### 2. 持仓管理（/）
- 实时持仓总览：总市值、总成本、总收益、收益率
- 每日盈亏（基于 T-1 收盘价）
- 持仓分类标签管理、关联场内 ETF
- 已清仓标的归档查看

### 3. 持仓详情（/position/:code）
- 价格走势图：净值 / 趋势 / 对比 / PE 四种模式
- 买卖点标记、止盈/损线展示
- PE 估值走势图（需配置关联指数）
- 关联 ETF 对比

### 4. 收益统计（/stats）
- 月度/年度收益汇总（已实现 + 浮动盈亏）
- 收益曲线图
- 月度/年度持仓收益明细

### 5. 行情同步（/analysis → 数据缓存 Tab）
- APScheduler 每日 15:30 自动拉取收盘价
- 手动触发：L1宽基/L2行业/L3主题/L6大宗商品批量同步
- 增量补全缺失数据
- 分红检测与确认

### 6. 历史行情分析（/analysis）
行情页包含四个 Tab：
- **数据缓存**：管理各层级行情数据的同步与状态
- **数据查看**：K线图浏览（支持资产类型筛选）
- **主题指数**：持仓关联中证/恒生系列指数走势 + PE/股息率趋势
- **大宗商品**：国际/国内大宗商品价格走势

### 7. 策略参数寻优（/backtest）— v1.5 新增

#### 退出策略（5 种）
| 模式 | 关键参数 | 适用场景 |
|---|---|---|
| 固定止盈止损 (simple) | stop_loss + take_profit | 简单基准策略 |
| 移动止损 Pmax (pmax_drawdown) | stop_loss + pmax_drawdown | 趋势跟踪、锁住利润 |
| 浮盈保留 (profit_retention) | stop_loss + trigger + retention | 两阶段保护，激活后保留浮盈比例 |
| 成本保护 (cost_protection) | stop_loss + trigger + floor | 两阶段保护，激活后拉高止损至成本线 |
| MA 均线穿越 (ma_cross) | stop_loss + ma_period | 趋势跟踪，价格跌破均线出场 |

#### 通用参数
- `stop_loss_pct`：兜底止损（所有模式）
- `reentry_cooldown`：出场后冷静期（所有模式）
- `reentry_pullback_pct`：回撤入场阈值（可选，非 MA 模式，默认关闭）
- `ma_entry_period`：MA 入场过滤（可选，MA 模式自动开启）

#### 网格搜索
- 对参数笛卡尔积扫描（无组合数上限）
- 5-cohort 中位数评估，避免单一入场点偏差
- 样本内寻优 + 可选样本外（OOS）验证
- 支持热力图（2维扫描时）

#### 评分指标
- **得分（Calmar）= 年化收益% ÷ 最大回撤%**（主评分，消除测试区间偏差）
- Profit Factor = 总盈利 ÷ 总亏损
- Sortino Ratio = 年化收益 ÷ 下行标准差
- Whipsaw 率 = 止损后价格回到入场价以上的比例（以入场价为基准）
- 最大连续亏损次数、回撤恢复期

#### 历史记录
- 每次寻优完成后自动保存最优解（BacktestRecord 表）
- 历史 Tab 按标的筛选，支持点击「查看」恢复完整展示
- 所有列含 Tooltip 指标说明

---

## 数据库表

| 表名 | 说明 |
|---|---|
| `trades` | 交易记录 |
| `positions` | 持仓（含清仓归档） |
| `hist_quotes_cache` | 历史行情缓存（OHLCV） |
| `asset_meta` | 行情资产元数据 |
| `index_pe_history` | 指数 PE/股息率历史 |
| `profit_level_config` | 利润等级配置 |
| `stop_loss_config` | 止盈/损线配置 |
| `backtest_record` | 回测历史记录（v1.5 新增） |

---

## API 概览

### 交易 `/api/trades`
`GET / POST / PUT /{id} / DELETE /{id}`

### 持仓 `/api/positions`
`GET / /{code} /{code}/chart /{code}/suggest-linked`
`PATCH /{code}/category /{code}/linked-code`
`GET /categories/stats /closed-positions`

### 行情 `/api/quotes`
`POST /sync` · `GET /sync-progress/{taskId} /last-sync /validate/{code}`
`GET /fund-info/{code} /dividends /pe/{code} /pe/index/{code}`
`POST /dividends/confirm`

### 统计 `/api/stats`
`GET /monthly /yearly /monthly/{y}/{m}/positions /yearly/{y}/positions`

### 历史行情分析 `/api/analysis`
**数据缓存**：`POST /cache/sync /cache/sync-batch /cache/sync-l1 /cache/sync-l2 /cache/sync-l3-theme /cache/sync-l6 /cache/sync-l6c`
`GET /cache/status /cache/progress`

**数据查看**：`GET /data/ohlcv /data/stats`

**策略参数寻优**：`POST /backtest/grid-search`

### 回测历史 `/api/backtest-records`
`GET / /codes` · `POST /` · `PATCH /{id}/notes` · `DELETE /{id}`

### 系统配置 `/api/config`
`GET/PUT /profit-levels /stop-loss`

---

## 开发说明

### 启动方式
```bash
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端构建（修改后必须执行）
```bash
cd frontend
npm run build
# 产物自动输出到 backend/static/
```

### 后端重启（改后端代码后执行）
```bash
lsof -ti:8000 | xargs kill -9 2>/dev/null; sleep 1
find backend -name "*.pyc" -delete
find backend -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
cd backend && nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/uvicorn.log 2>&1 &
sleep 4 && curl -s http://localhost:8000/api/analysis/cache/status | python3 -c "import sys,json; print('OK')"
```

### 数据约束（红线）
- **禁止直接删除数据库**，必须备份 → 迁移
- **清仓用软删除**（is_closed=1），禁止物理删除
- **行情数据必须先同步到 HistQuotesCache**，不允许前端实时调 akshare
