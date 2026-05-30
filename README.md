# Invest Tracker - 投资追踪平台

## 版本记录

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.4 | 2026-05-31 | PE估值分析、回测模块、统计重构、数据库清理 |
| v1.3 | 2026-05-28 | 新增配置管理模块，数据库迁移支持，持仓统计优化 |
| v1.2 | 2026-05-24 | 功能优化：改进持仓统计、数据分析逻辑，优化前端UI交互 |
| v1.1 | 2026-05-14 | 清理仓库：移除构建产物、缓存文件和临时测试文件 |
| v1.0 | 2026-05-09 | 初始版本，完成基础功能设计 |

## 项目概述

个人投资追踪可视化平台，支持A股、场内基金(ETF)、联接基金的投资记录、持仓管理、收益统计，以及历史行情数据分析。

## 技术栈

### 后端 (Python)
- **FastAPI** - Web框架
- **SQLAlchemy** - ORM
- **SQLite** - 数据库
- **akshare** - A股/ETF/基金行情数据
- **APScheduler** - 定时任务（每日收盘后拉取行情）
- **uvicorn** - ASGI服务器
- **numpy/pandas** - 数据分析

### 前端 (Vue 3)
- **Vue 3** + **Vite** - 前端框架+构建
- **Element Plus** - UI组件库
- **ECharts** - 图表（K线、折线、饼图、热力图）
- 打包后由FastAPI静态文件托管，单进程运行

## 核心功能

### 1. 交易管理
- 录入买卖交易：股票/ETF代码、方向(买/卖/分红)、价格、金额、日期
- 支持联接基金交易记录
- 自动检测并确认分红再投资
- 交易列表筛选（代码、方向、日期范围）

### 2. 持仓管理
- 实时持仓总览：总市值、总成本、总收益、收益率
- 每日盈亏计算（基于T-1收盘价）
- 持仓分类标签管理
- 关联场内ETF（用于联接基金跟踪）
- 已清仓标的归档查看

### 3. 持仓详情
- 价格走势图（日K线/折线图）：净值/趋势/对比/PE 四种模式
- 买卖点标记（绿色▲买入/红色▼卖出）
- PE 估值走势图（需配置 benchmark_index）
- 细分统计：平均成本、最高最低价、持仓天数
- 关联ETF对比（联接基金vs场内ETF）

### 4. 收益统计
- 月度收益表：每月盈亏金额、收益率（已实现+浮动盈亏）
- 年度收益汇总
- 收益曲线图（按月/按年）
- 月度/年度持仓收益明细

### 7. 回测（新增）
- 持仓标的历史区间回测
- 买入持有、定投等策略对比

### 5. 行情同步
- 自动同步：APScheduler每日15:30拉取收盘价
- 手动同步：支持后台任务进度查询
- 增量补全：自动检测缺失数据并补全
- 分红检测：自动识别持仓分红记录

### 6. 历史行情分析（新增）
支持多层级资产数据缓存和分析：

#### 数据层级
- **L1 大盘指数**：沪深300、中证500等宽基指数
- **L2 行业板块**：申万/同花顺行业分类
- **L3 概念板块**：热门概念追踪
- **L6 大宗商品**：黄金、原油、白银等国际商品

#### 分析功能
- **相关性分析**：皮尔逊相关系数、相关系数矩阵、滚动窗口相关
- **领先滞后**：交叉相关函数(CCF)、Granger因果检验
- **特征挖掘**：月度季节效应、周几效应、动量反转、均值回归
- **聚类分析**：多标的层次聚类
- **快速诊断**：单标的综合报告、两两关系报告

## 数据库设计

### 核心表

#### trades 交易记录表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| code | TEXT | 标的代码 |
| name | TEXT | 标的名称 |
| direction | TEXT | buy/sell/dividend |
| price | REAL | 成交价格 |
| amount | REAL | 总金额 |
| quantity | REAL | 数量 |
| trade_date | DATE | 交易日期 |
| fee | REAL | 手续费 |
| created_at | DATETIME | 创建时间 |

#### positions 持仓表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| code | TEXT | 标的代码（唯一） |
| name | TEXT | 名称 |
| category | TEXT | 分类标签 |
| linked_code | TEXT | 关联场内ETF代码 |
| linked_name | TEXT | 关联ETF名称 |
| benchmark_index | TEXT | 关联指数代码（用于PE查询） |
| total_cost | REAL | 总成本 |
| quantity | REAL | 持有数量 |
| avg_cost | REAL | 平均成本 |
| current_price | REAL | 最新价格 |
| is_closed | INTEGER | 0=持仓,1=清仓 |

#### daily_snapshots 每日快照表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| code | TEXT | 标的代码 |
| date | DATE | 日期 |
| open/high/low/close | REAL | OHLC价格 |
| market_value | REAL | 持仓市值 |
| daily_pnl | REAL | 当日盈亏 |
| total_pnl | REAL | 累计盈亏 |

### 分析相关表

#### asset_meta 资产元数据表
| 字段 | 类型 | 说明 |
|------|------|------|
| code | TEXT PK | 资产代码 |
| name | TEXT | 名称 |
| asset_type | TEXT | 类型(index/etf/stock/sector_*) |
| category | TEXT | 细分分类 |
| source | TEXT | 数据来源 |
| is_cached | INTEGER | 是否已缓存历史数据 |

#### hist_quotes_cache 历史行情缓存表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| code | TEXT | 标的代码 |
| date | DATE | 日期 |
| open/high/low/close | REAL | OHLC |
| volume | REAL | 成交量 |
| turnover | REAL | 成交额 |
| pct_change | REAL | 涨跌幅% |

#### index_pe_history 指数PE历史表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| code | TEXT | 指数代码 |
| date | DATE | 日期 |
| pe1 / pe2 | REAL | 市盈率（中证指数提供） |
| dividend_yield1/2 | REAL | 股息率 |
| source | TEXT | 数据来源（csindex） |

## API 概览

### 交易管理 `/api/trades`
- `POST /` - 新增交易
- `GET /` - 交易列表（支持筛选）
- `PUT /{id}` - 编辑交易
- `DELETE /{id}` - 删除交易

### 持仓管理 `/api/positions`
- `GET /` - 持仓列表
- `GET /{code}` - 持仓详情
- `GET /{code}/chart` - 走势图数据
- `PUT /{code}/category` - 更新分类
- `PUT /{code}/linked` - 更新关联ETF

### 行情同步 `/api/quotes`
- `POST /sync` - 手动触发同步（后台任务）
- `GET /sync-progress/{task_id}` - 查询同步进度
- `GET /validate/{code}` - 校验代码有效性
- `GET /fund-info/{code}` - 获取联接基金信息
- `GET /dividends` - 检测分红记录
- `POST /dividends/confirm` - 确认分红再投资
- `GET /last-sync` - 上次同步时间
- `GET /pe/{etf_code}` - 获取ETF关联指数PE历史
- `GET /pe/index/{index_code}` - 直接查询指数PE历史

### 收益统计 `/api/stats`
- `GET /monthly` - 月度统计
- `GET /yearly` - 年度统计
- `GET /monthly/{year}/{month}/positions` - 月度持仓明细
- `GET /yearly/{year}/positions` - 年度持仓明细

### 历史行情分析 `/api/analysis`

#### 数据缓存
- `POST /cache/sync` - 同步单个标的
- `POST /cache/sync-batch` - 批量同步
- `POST /cache/sync-l1` - 同步大盘指数
- `POST /cache/sync-l2` - 同步行业板块
- `POST /cache/sync-l3` - 同步概念板块
- `POST /cache/sync-l6` - 同步大宗商品
- `GET /cache/status` - 缓存概况
- `GET /cache/progress` - 同步进度

#### 相关性分析
- `POST /correlation/pearson` - 皮尔逊相关系数
- `POST /correlation/matrix` - 相关系数矩阵
- `POST /correlation/rolling` - 滚动窗口相关
- `POST /correlation/ccf` - 交叉相关函数
- `POST /correlation/granger` - Granger因果检验

#### 特征规律
- `POST /pattern/seasonality-monthly` - 月度季节效应
- `POST /pattern/seasonality-weekday` - 周几效应
- `POST /pattern/momentum-reversal` - 动量反转
- `POST /pattern/mean-reversion` - 均值回归
- `POST /pattern/clustering` - 层次聚类

#### 数据查看
- `GET /data/ohlcv` - K线数据
- `GET /data/distribution` - 数据分布
- `GET /data/volume-analysis` - 成交量分析
- `GET /data/stats` - 基础统计

#### 报告
- `POST /report/quick` - 单标的快速诊断
- `POST /report/pair` - 两两关系报告

## 项目结构

```
invest-tracker/
├── backend/
│   ├── main.py                 # FastAPI入口
│   ├── database.py             # 数据库连接
│   ├── models.py               # SQLAlchemy模型
│   ├── schemas.py              # Pydantic模型
│   ├── scheduler.py            # 定时任务配置
│   ├── migrations/             # 数据库迁移脚本
│   ├── routers/
│   │   ├── trades.py           # 交易API
│   │   ├── positions.py        # 持仓API
│   │   ├── quotes.py           # 行情同步+PE API
│   │   ├── stats.py            # 统计API
│   │   ├── analysis.py         # 历史行情分析API
│   │   └── config.py           # 配置管理API
│   └── services/
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
│       │   ├── PeriodListCard.vue   # 收益期列表卡片
│       │   └── PeriodDetailPanel.vue # 期内明细面板
│       ├── views/              # 页面组件
│       │   ├── Overview.vue    # 总览
│       │   ├── Trades.vue      # 交易记录
│       │   ├── PositionDetail.vue # 持仓详情（含PE模式）
│       │   ├── Stats.vue       # 收益统计
│       │   ├── Analysis.vue    # 历史行情分析
│       │   ├── Backtest.vue    # 回测
│       │   └── Config.vue      # 配置管理
│       └── api/index.js        # API封装
├── tests/                      # 测试文件
└── README.md                   # 项目文档
```

## 部署方式

1. 安装依赖
```bash
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

2. 构建前端
```bash
cd frontend && npm run build
```

3. 启动服务
```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000
```

4. 访问
```
http://localhost:8000
```

## 注意事项

- akshare获取行情时注意频率限制，已内置延时控制
- ETF代码格式：510300（沪市ETF），159919（深市ETF）
- 股票代码格式：600519（沪市），000001（深市）
- 联接基金代码格式：160119（场外基金）
- 日期格式统一用 YYYY-MM-DD
- 数据库文件较大，已加入.gitignore不提交到仓库
