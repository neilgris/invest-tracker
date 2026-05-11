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
    short_name = Column(String(30), nullable=True)  # 简化名称
    category = Column(String(20), nullable=True)  # 分类标签
    linked_code = Column(String(10), nullable=True)  # 关联场内ETF代码
    total_cost = Column(Float, default=0.0)
    quantity = Column(Float, default=0.0)
    avg_cost = Column(Float, default=0.0)
    current_price = Column(Float, default=0.0)
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


class BaselineConfig(Base):
    __tablename__ = "baseline_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    etf_code = Column(String(10), nullable=False, index=True)
    baseline_code = Column(String(10), nullable=False)
    baseline_name = Column(String(50), nullable=False)


class AssetMeta(Base):
    """资产元数据表：所有标的的档案信息"""
    __tablename__ = "asset_meta"

    code = Column(String(10), primary_key=True)
    name = Column(String(50), nullable=False)
    asset_type = Column(String(20), nullable=False)  # index / sector_industry / sector_concept / etf / stock / fund
    category = Column(String(30), nullable=True)       # 细分分类（ETF: 宽基/行业/主题/跨境/商品/债券; 行业: 金融/科技/消费...）
    benchmark_index = Column(String(10), nullable=True)  # 关联基准指数
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


class AssetSectorMapping(Base):
    """个股-板块映射表"""
    __tablename__ = "asset_sector_mapping"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, index=True)
    sector_code = Column(String(10), nullable=False, index=True)
    sector_type = Column(String(20), nullable=False)  # industry / concept
