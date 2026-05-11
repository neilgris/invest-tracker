# Invest Tracker - 投资追踪平台

## 项目概述
个人投资追踪可视化平台，支持A股和场内基金(ETF)的投资记录、持仓管理、收益统计。

## 技术栈

### 后端 (Python)
- **FastAPI** - Web框架
- **SQLAlchemy** - ORM
- **SQLite** - 数据库
- **akshare** - A股/ETF行情数据
- **APScheduler** - 定时任务（每日收盘后拉取行情）
- **uvicorn** - ASGI服务器

### 前端 (Vue 3)
- **Vue 3** + **Vite** - 前端框架+构建
- **Element Plus** - UI组件库
- **ECharts** - 图表（K线、折线、饼图）
- 打包后由FastAPI静态文件托管，单进程运行

## 功能需求

### 1. 交易管理
- 手动录入买卖信息：股票/ETF代码、买卖方向(买/卖)、点位(价格)、总金额、日期
- 交易列表展示，支持筛选和分页
- 编辑和删除交易记录

### 2. 持仓统计
- 当前持仓总览：总市值、总成本、总收益、总收益率
- 每日收益：今日盈亏金额和比例
- 持仓列表：每个持仓的当前市值、成本、浮盈浮亏、收益率
- 持仓分布饼图（按股票/ETF）

### 3. 持仓详情
- 点击某个持仓进入详情页
- 价格走势图（日K线或折线图）
- 在走势图上标注买入点位（绿色▲）和卖出点位（红色▼）
- 细分统计：平均成本、最高价、最低价、持仓天数、分段收益
- **可选功能**：ETF基线对比 - 如果是ETF，可以选择对标基线（如沪深300），展示ETF走势与基线走势的对比图

### 4. 每日快照
- APScheduler每日15:30自动触发
- 通过akshare拉取持仓股票/ETF的收盘价
- 计算当日盈亏，存入daily_snapshots表
- 支持手动触发拉取

### 5. 月度/年度收益统计
- 月度收益表：每月收益金额、收益率
- 年度收益汇总
- 收益曲线图（按月/按周）

## 数据库设计

### trades 交易记录表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| code | TEXT | 股票/ETF代码（如 600519, 510300） |
| name | TEXT | 股票/ETF名称 |
| direction | TEXT | 买卖方向：buy/sell |
| price | REAL | 成交价格（点位） |
| amount | REAL | 总金额 |
| quantity | INTEGER | 可选，股数（由金额/价格推算） |
| trade_date | DATE | 交易日期 |
| fee | REAL | 手续费（可选，默认0） |
| created_at | DATETIME | 创建时间 |

### positions 持仓表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| code | TEXT | 股票/ETF代码 |
| name | TEXT | 名称 |
| total_cost | REAL | 总成本 |
| total_amount | REAL | 总金额（卖出时减少） |
| quantity | INTEGER | 当前持有数量 |
| avg_cost | REAL | 平均成本价 |
| current_price | REAL | 最新价格 |
| updated_at | DATETIME | 更新时间 |

### daily_snapshots 每日快照表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| code | TEXT | 股票/ETF代码 |
| date | DATE | 日期 |
| open | REAL | 开盘价 |
| close | REAL | 收盘价 |
| high | REAL | 最高价 |
| low | REAL | 最低价 |
| market_value | REAL | 持仓市值 |
| daily_pnl | REAL | 当日盈亏 |
| total_pnl | REAL | 累计盈亏 |

### baseline_config 基线配置表（可选功能）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| etf_code | TEXT | ETF代码 |
| baseline_code | TEXT | 基线指数代码（如 000300） |
| baseline_name | TEXT | 基线名称 |

## API设计

- `POST /api/trades` - 新增交易
- `GET /api/trades` - 交易列表（支持筛选）
- `PUT /api/trades/{id}` - 编辑交易
- `DELETE /api/trades/{id}` - 删除交易
- `GET /api/positions` - 持仓列表
- `GET /api/positions/{code}` - 持仓详情
- `GET /api/positions/{code}/chart` - 持仓走势图数据（含买卖标记）
- `GET /api/positions/{code}/baseline` - ETF基线对比数据
- `POST /api/quotes/sync` - 手动触发行情同步
- `GET /api/stats/monthly` - 月度收益统计
- `GET /api/stats/yearly` - 年度收益统计
- `GET /api/stats/overview` - 总览数据

## 前端页面

1. **总览页** (`/`) - 持仓概览 + 今日盈亏 + 持仓分布图
2. **交易记录页** (`/trades`) - 交易列表 + 新增/编辑
3. **持仓详情页** (`/position/:code`) - 走势图 + 买卖标记 + 统计 + 基线对比
4. **收益统计页** (`/stats`) - 月度/年度收益表 + 收益曲线

## 项目结构

```
invest-tracker/
├── backend/
│   ├── main.py               # FastAPI入口，挂载静态文件+路由+定时任务
│   ├── database.py           # SQLite连接+会话
│   ├── models.py             # SQLAlchemy模型
│   ├── schemas.py            # Pydantic模型
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── trades.py         # 交易API
│   │   ├── positions.py      # 持仓API
│   │   ├── quotes.py         # 行情API
│   │   └── stats.py          # 统计API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── market.py         # akshare行情拉取
│   │   ├── tracker.py        # 持仓计算+每日盈亏
│   │   └── stats.py          # 统计分析
│   ├── scheduler.py          # APScheduler配置
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── api/
│   │   │   └── index.js      # axios封装+API调用
│   │   ├── views/
│   │   │   ├── Overview.vue   # 总览
│   │   │   ├── Trades.vue     # 交易记录
│   │   │   ├── PositionDetail.vue  # 持仓详情
│   │   │   └── Stats.vue      # 收益统计
│   │   ├── components/
│   │   │   ├── TradeForm.vue       # 交易表单
│   │   │   ├── PositionTable.vue   # 持仓表格
│   │   │   ├── PriceChart.vue      # 价格走势+买卖标记
│   │   │   ├── BaselineChart.vue   # 基线对比图
│   │   │   ├── PnlChart.vue        # 收益曲线
│   │   │   └── DistributionPie.vue # 持仓分布饼图
│   │   └── router/
│   │       └── index.js
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── PRD.md
└── README.md
```

## 部署方式

单进程运行：
1. 前端 `npm run build` 打包到 `backend/static/`
2. FastAPI 启动时挂载 `StaticFiles` 托管前端
3. 启动命令：`cd backend && uvicorn main:app --host 0.0.0.0 --port 8000`
4. 访问 `http://localhost:8000`

## 注意事项

- akshare获取行情时注意频率限制，加适当延时
- ETF代码格式：510300（沪市ETF），159919（深市ETF）
- 股票代码格式：600519（沪市），000001（深市）
- 基线指数：000300（沪深300），000905（中证500），000852（中证1000）
- 日期格式统一用 YYYY-MM-DD
- 前端界面用中文
