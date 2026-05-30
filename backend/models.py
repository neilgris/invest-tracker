from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Index
from database import Base
from datetime import datetime


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    direction = Column(String(10), nullable=False)  # buy / sell / dividend
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    quantity = Column(Float, nullable=True)
    trade_date = Column(Date, nullable=False)
    fee = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(10), nullable=False, unique=True, index=True)
    name = Column(String(50), nullable=False)

    category = Column(String(20), nullable=True)  # 分类标签
    linked_code = Column(String(10), nullable=True)  # 关联场内ETF代码
    linked_name = Column(String(50), nullable=True)  # 关联ETF名称
    linked_short_name = Column(String(30), nullable=True)  # 关联ETF短名称
    benchmark_index = Column(String(10), nullable=True)  # 关联指数代码（用于PE查询）
    total_cost = Column(Float, default=0.0)
    quantity = Column(Float, default=0.0)
    avg_cost = Column(Float, default=0.0)
    current_price = Column(Float, default=0.0)
    is_closed = Column(Integer, default=0)  # 0=当前持仓, 1=已清仓
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DailySnapshot(Base):
    __tablename__ = "daily_snapshots"
    __table_args__ = (
        Index('ix_snapshots_code_date', 'code', 'date', unique=True),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False)
    open = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    market_value = Column(Float, nullable=True)
    daily_pnl = Column(Float, nullable=True)
    total_pnl = Column(Float, nullable=True)


class AssetMeta(Base):
    """资产元数据表：存储指数/行业等基础信息"""
    __tablename__ = "asset_meta"

    code = Column(String(10), primary_key=True)
    name = Column(String(50), nullable=False)
    asset_type = Column(String(20), nullable=False)  # index / sector_industry / sector_concept / etf / stock / fund
    category = Column(String(30), nullable=True)       # 细分分类
    source = Column(String(20), nullable=True)       # 数据来源（sw=申万, csi=中证, wind=Wind等）
    list_date = Column(Date, nullable=True)
    is_cached = Column(Integer, default=0)  # 是否已缓存历史数据
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class HistQuotesCache(Base):
    """历史行情缓存表：通用，不区分持仓/非持仓"""
    __tablename__ = "hist_quotes_cache"
    __table_args__ = (
        Index('ix_hist_quotes_code_date', 'code', 'date', unique=True),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False)
    open = Column(Float, nullable=True)
    close = Column(Float, nullable=False)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)      # 成交量
    turnover = Column(Float, nullable=True)    # 成交额
    pct_change = Column(Float, nullable=True)  # 涨跌幅%


class SyncLog(Base):
    """同步日志表：记录上次行情同步时间"""
    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sync_type = Column(String(20), nullable=False, default="daily")  # daily / history
    synced_at = Column(DateTime, default=datetime.now)
    record_count = Column(Integer, default=0)


class StopLossConfig(Base):
    """止盈线配置表：与利润等级关联，存储各等级对应的止盈线参数"""
    __tablename__ = "stop_loss_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    profit_level_key = Column(String(20), nullable=False, unique=True)  # 关联 profit_level_config.level_key
    # 止盈线计算参数
    half_position_ratio = Column(Float, nullable=True)  # 减半仓线系数 (Pmax回撤或成本保护时用)
    clear_position_ratio = Column(Float, nullable=True)  # 清仓线系数 (Pmax回撤或成本保护时用)
    calculation_mode = Column(String(20), default="pmax_drawdown")  # pmax_drawdown=基于Pmax回撤, profit_retention=基于Profit_max保留比例, cost_protection=基于成本保护
    profit_retention_half = Column(Float, nullable=True)  # 保留浮盈比例(减半仓，基于Profit_max时用)
    profit_retention_clear = Column(Float, nullable=True)  # 保留浮盈比例(清仓，基于Profit_max时用)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ProfitLevelConfig(Base):
    """利润等级配置表：存储利润状态分级的阈值"""
    __tablename__ = "profit_level_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    level_name = Column(String(20), nullable=False, unique=True)  # 极厚利润/中厚利润/浅厚利润/中利润/薄利润/新建仓宽容/薄亏损观察/中亏损决策/厚亏损清仓
    level_key = Column(String(20), nullable=False, unique=True)   # thick_profit_3/thick_profit_2/thick_profit_1/medium_profit/thin_profit/thin_loss_new/thin_loss_watch/medium_loss/thick_loss
    level_code = Column(String(10), nullable=False, unique=True)  # F1.3/F1.2/F1.1/F2/F3/L1/L2/L3/L4
    pnl_threshold = Column(Float, nullable=False)  # 利润阈值下限(%), 基于pnlPeak或pnlNow
    pnl_threshold_max = Column(Float, nullable=True)  # 利润阈值上限(%), None表示无上限
    use_peak_pnl = Column(Integer, default=1)  # 1=使用pnlPeak判断, 0=使用pnlNow判断
    sort_order = Column(Integer, nullable=False)  # 排序顺序(从高到低)
    display_color = Column(String(10), nullable=False)  # 显示颜色: success/warning/danger
    hold_days_min = Column(Integer, nullable=True)  # 持仓天数最小值(≥), None表示无限制
    hold_days_max = Column(Integer, nullable=True)  # 持仓天数最大值(<), None表示无限制
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class IndexPEHistory(Base):
    """指数PE历史数据表：存储指数估值历史，用于PE走势分析"""
    __tablename__ = "index_pe_history"
    __table_args__ = (
        Index('ix_index_pe_code_date', 'code', 'date', unique=True),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)  # 指数代码
    date = Column(Date, nullable=False)  # 日期
    pe1 = Column(Float, nullable=True)   # 市盈率1（中证指数提供）
    pe2 = Column(Float, nullable=True)   # 市盈率2（中证指数提供，通常为滚动PE）
    dividend_yield1 = Column(Float, nullable=True)  # 股息率1
    dividend_yield2 = Column(Float, nullable=True)  # 股息率2
    source = Column(String(20), default='csindex')  # 数据来源：csindex=中证指数
    created_at = Column(DateTime, default=datetime.now)
