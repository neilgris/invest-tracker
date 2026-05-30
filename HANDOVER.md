# Invest Tracker 项目交接文档

> 创建时间：2026-05-28 / 最后更新：2026-05-31（v1.4）
> 项目路径：`/Users/neilgris/Documents/python/qclaw/invest-tracker/`

---

## 1. 项目概述

**Invest Tracker** 是一个个人投资追踪可视化平台，支持 A股、场内基金(ETF)、联接基金的投资记录、持仓管理、收益统计，以及历史行情数据分析。

### 核心功能
- 交易管理：录入买卖交易、分红再投资
- 持仓管理：实时持仓总览、每日盈亏、分类标签
- 持仓详情：价格走势图、买卖点标记、止盈线配置
- 收益统计：月度/年度收益表、收益曲线
- 行情同步：自动/手动同步历史行情数据
- 历史行情分析：相关性分析、特征规律挖掘、聚类分析

---

## 2. 技术栈

### 后端
| 组件 | 用途 |
|------|------|
| FastAPI | Web 框架 |
| SQLAlchemy | ORM |
| SQLite | 数据库 |
| akshare | A股/ETF/基金行情数据 |
| APScheduler | 定时任务 |
| uvicorn | ASGI 服务器 |

### 前端
| 组件 | 用途 |
|------|------|
| Vue 3 + Vite | 前端框架+构建 |
| Element Plus | UI 组件库 |
| ECharts | 图表（K线、折线、饼图）|

---

## 3. 项目结构

```
invest-tracker/
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── database.py             # 数据库连接
│   ├── models.py               # SQLAlchemy 模型
│   ├── schemas.py              # Pydantic 模型
│   ├── scheduler.py            # 定时任务配置
│   ├── migrations/             # 数据库迁移脚本
│   ├── routers/                # API 路由
│   │   ├── trades.py           # 交易 API
│   │   ├── positions.py        # 持仓 API
│   │   ├── quotes.py           # 行情同步 + PE API
│   │   ├── stats.py            # 统计 API
│   │   ├── analysis.py         # 历史行情分析 API
│   │   └── config.py           # 配置 API
│   └── services/               # 业务逻辑
│       ├── market.py           # 行情数据获取
│       ├── tracker.py          # 持仓计算
│       ├── stats.py            # 统计分析
│       └── analysis/           # 分析模块
│           ├── data_fetcher.py # 数据获取与缓存
│           ├── backtest.py     # 回测服务
│           ├── correlation.py  # 相关性分析
│           ├── pattern.py      # 特征规律挖掘
│           └── report.py       # 报告生成
├── frontend/
│   └── src/
│       ├── components/         # 可复用组件
│       │   ├── PeriodListCard.vue    # 收益期列表卡片
│       │   └── PeriodDetailPanel.vue # 期内明细面板
│       ├── views/              # 页面组件
│       │   ├── Overview.vue    # 总览
│       │   ├── Trades.vue      # 交易记录
│       │   ├── PositionDetail.vue # 持仓详情（含PE模式）
│       │   ├── Stats.vue       # 收益统计
│       │   ├── Analysis.vue    # 历史行情分析
│       │   ├── Backtest.vue    # 回测
│       │   └── Config.vue      # 配置管理
│       └── api/index.js        # API 封装
└── README.md                   # 项目文档
```

---

## 4. 数据库模型

### 核心表

#### trades（交易记录）
| 字段 | 说明 |
|------|------|
| id | 主键 |
| code | 标的代码 |
| name | 标的名称 |
| direction | buy/sell/dividend |
| price | 成交价格 |
| amount | 总金额（含手续费）|
| quantity | 数量（自动计算）|
| trade_date | 交易日期 |
| fee | 手续费 |

#### positions（持仓）
| 字段 | 说明 |
|------|------|
| id | 主键 |
| code | 标的代码（唯一）|
| name | 名称 |
| category | 分类标签 |
| linked_code | 关联场内ETF代码 |
| linked_name | 关联ETF名称 |
| linked_short_name | 关联ETF短名称 |
| **benchmark_index** | **关联指数代码（用于PE查询）** |
| total_cost | 总成本 |
| quantity | 持有数量 |
| avg_cost | 平均成本 |
| current_price | 最新价格 |
| **is_closed** | **0=持仓, 1=清仓（软删除）** |

#### daily_snapshots（每日快照）
| 字段 | 说明 |
|------|------|
| id | 主键 |
| code | 标的代码 |
| date | 日期 |
| open/high/low/close | OHLC 价格 |
| market_value | 持仓市值 |
| daily_pnl | 当日盈亏 |
| total_pnl | 累计盈亏 |

#### hist_quotes_cache（历史行情缓存）
| 字段 | 说明 |
|------|------|
| id | 主键 |
| code | 标的代码 |
| date | 日期 |
| open/high/low/close | OHLC 价格 |
| volume | 成交量 |
| turnover | 成交额 |
| pct_change | 涨跌幅% |

#### asset_meta（资产元数据）
| 字段 | 说明 |
|------|------|
| code | 资产代码（PK）|
| name | 名称 |
| asset_type | index/etf/stock/sector_industry/sector_concept/fund/commodity |
| category | 细分分类 |
| source | 数据来源 |
| is_cached | 是否已缓存历史数据 |

#### ProfitLevelConfig（利润等级配置）
| 字段 | 说明 |
|------|------|
| level_key | thick_profit_3/thick_profit_2/... |
| level_code | F1.3/F1.2/F1.1/F2/F3/L1/L2/L3/L4 |
| pnl_threshold | 利润阈值下限(%) |
| pnl_threshold_max | 利润阈值上限(%) |
| use_peak_pnl | 1=使用pnlPeak判断, 0=使用pnlNow判断 |
| hold_days_min/max | 持仓天数区间 |

#### StopLossConfig（止盈线配置）
| 字段 | 说明 |
|------|------|
| profit_level_key | 关联 profit_level_config.level_key |
| calculation_mode | pmax_drawdown/profit_retention/cost_protection |
| half_position_ratio | 减半仓线系数 |
| clear_position_ratio | 清仓线系数 |
| profit_retention_half/clear | 保留浮盈比例 |

#### IndexPEHistory（指数PE历史）
| 字段 | 说明 |
|------|------|
| code | 指数代码 |
| date | 日期 |
| pe1/pe2 | 市盈率 |
| dividend_yield1/2 | 股息率 |

---

## 5. 核心计算逻辑

### 5.1 数量计算
```python
quantity = (amount - fee) / price  # 保留2位小数
```

### 5.2 成本计算（移动平均成本法）
- **买入**：`total_cost += amount`（实际花了多少钱）
- **卖出**：按当前成本单价减少成本，保持单价不变
- **分红再投资**：`total_cost` 不变，`quantity` 增加

### 5.3 收益计算
| 指标 | 计算方法 |
|------|----------|
| 已实现收益 | 卖出交易盈亏（移动平均成本法）|
| 持仓收益 | 累计盈亏差（年末-年初）|
| 月度/年度收益 | 明细汇总：各标的 realized_pnl + unrealized_pnl |
| 收益率 | total_pnl / total_end_market_value（市值基准）|
| 平均年化 | CAGR: (∏(1+ri))^(1/n)-1 |

### 5.4 利润等级判断
| 等级 | 代码 | 核心条件 |
|------|------|----------|
| 极厚利润 | F1.3 | PnL_peak ≥ 200% |
| 中厚利润 | F1.2 | PnL_peak ≥ 100% |
| 浅厚利润 | F1.1 | PnL_peak ≥ 50% |
| 中利润 | F2 | PnL_peak ≥ 25% |
| 薄利润 | F3 | PnL_now ≥ 0 |
| 新建仓宽容 | L1 | PnL_now ≥ -10% 且持仓<60天 |
| 薄亏损观察 | L2 | 持仓≥60天 |
| 中亏损决策 | L3 | PnL_now ≥ -30% |
| 厚亏损清仓 | L4 | PnL_now < -30% |

**关键变量**：
- `pmax`：首个买入后最高净值
- `pnlPeak` = (Pmax - Pcost) / Pcost × 100
- `pnlNow` = (Pnow - Pcost) / Pcost × 100

---

## 6. 数据层级（L1-L6）

| 层级 | 类型 | 说明 |
|------|------|------|
| L1 | 大盘指数 | 沪深300、中证500等7个宽基 |
| L2 | 行业板块 | 申万一级行业（~90个）|
| L3 | 概念板块 | 热门概念追踪（~400个）|
| L4 | ETF | 宽基+行业（按需）|
| L5 | 个股 | 纯按需 |
| L6 | 国际大宗商品 | 黄金、原油、白银等 |
| L6C | 国内期货 | 焦炭、焦煤等 |

---

## 7. 关键代码位置

### 7.1 行情数据获取
**文件**：`services/analysis/data_fetcher.py`

指数数据获取逻辑：
- 000/399 开头：先尝试 `stock_zh_index_daily`，失败则回退到 `stock_zh_index_hist_csindex`
- 其他（931xxx, 932xxx, Hxxxxx）：走 `stock_zh_index_hist_csindex`

**注意**：中证指数接口只提供收盘价，需用收盘价填充 open/high/low 的 NaN 值。

### 7.2 持仓计算
**文件**：`services/tracker.py`

核心函数：
- `recalc_position(db, code)` - 根据交易记录重新计算持仓
- `create_trade()` - 创建交易，自动触发持仓重算和历史数据同步

### 7.3 行情同步
**文件**：`services/market.py`

核心函数：
- `get_hist_prices()` - 获取历史价格
- `sync_single_position_history()` - 同步单个持仓历史
- `recalc_snapshots_pnl()` - 重算快照收益

### 7.4 持仓详情页
**文件**：`frontend/src/views/PositionDetail.vue`

走势图三模式：
- **净值模式**：显示价格K线+买卖点标记
- **趋势模式**：显示MA/ADX技术指标
- **对比模式**：与基线指数（沪深300等）归一化对比

---

## 8. 重要约束与红线

### 8.1 数据库操作红线
**绝对禁止直接删除或清空数据库！**

如果因结构调整等原因必须操作数据库：
1. **先备份** - 复制 `.db` 文件到安全位置
2. **调整结构** - 修改 models/schema
3. **数据迁移** - 在新结构上恢复数据

### 8.2 软删除机制
- 清仓标记 `is_closed = 1`，**禁止物理删除**
- 历史教训：物理删除导致收益缺失、历史追溯困难

### 8.3 数据访问原则
- **禁止实时连接 akshare**，必须先同步到数据库
- 判断逻辑优先从 `HistQuotesCache` 读取，akshare 实时拉取作回退

### 8.4 前端构建
- 修改后必须 `npm run build` 验证
- 构建产物在 `backend/static/` 目录

---

## 9. 已知问题与注意事项

### 9.1 指数数据问题
- 中证指数接口（931xxx, 932xxx, Hxxxxx）只返回收盘价
- 解决方案：用收盘价填充 open/high/low 的 NaN 值

### 9.2 字段映射
- 后端用 `level_key`（如 thick_profit_3）
- 前端用 `level_code`（如 F1.3）
- 需通过 `profitStatus.levelKey` 桥接

### 9.3 日期格式
- 统一使用 `YYYY-MM-DD`
- akshare 部分接口返回中文列名，需映射为英文

### 9.4 持仓天数判断
```python
hold_days_min <= hold_days < hold_days_max  # None 表示无限制
```

---

## 10. 启动与部署

### 开发环境启动
```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd frontend
npm install
npm run dev
```

### 生产构建
```bash
cd frontend
npm run build  # 输出到 backend/static/
```

### 访问
```
http://localhost:8000
```

---

## 11. 常用 API 速查

### 持仓管理
- `GET /api/positions` - 持仓列表
- `GET /api/positions/{code}` - 持仓详情
- `GET /api/positions/{code}/chart` - 走势图数据
- `PUT /api/positions/{code}/category` - 更新分类
- `PUT /api/positions/{code}/linked-code` - 更新关联ETF

### 交易管理
- `POST /api/trades` - 新增交易
- `GET /api/trades` - 交易列表
- `PUT /api/trades/{id}` - 编辑交易
- `DELETE /api/trades/{id}` - 删除交易

### 行情同步
- `POST /api/quotes/sync` - 手动触发同步
- `GET /api/quotes/sync-progress/{task_id}` - 查询同步进度
- `GET /api/quotes/validate/{code}` - 校验代码有效性
- `GET /api/quotes/pe/{etf_code}` - 获取ETF关联指数PE历史
- `GET /api/quotes/pe/index/{index_code}` - 直接查询指数PE历史

### 历史行情分析
- `POST /api/analysis/cache/sync-l1` - 同步L1大盘指数
- `POST /api/analysis/cache/sync-l2` - 同步L2行业板块
- `POST /api/analysis/cache/sync-l3-theme` - 同步L3主题指数
- `POST /api/analysis/correlation/pearson` - 皮尔逊相关系数

---

## 12. 待办事项（已知）

- [x] 删除 BaselineConfig 和 AssetSectorMapping 表（v1.4 已完成）
- [ ] L3 主题指数同步失败（KeyError: 'date'）- 已修复，需验证
- [ ] PositionDetail.vue 调整日期范围后标记点不显示（findClosestIdx 索引问题）
- [ ] buildPriceModeChart 标记点变量重复定义
- [ ] 构建警告 chunk 体积过大
- [ ] Backtest.vue 功能完善（当前为初始版本）

---

## 13. 联系方式

如有问题，请查阅：
1. `README.md` - 项目基础文档
2. `backend/models.py` - 数据库模型定义
3. `backend/services/` - 业务逻辑实现
