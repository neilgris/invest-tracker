from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List


class TradeCreate(BaseModel):
    code: str
    name: str
    direction: str  # buy / sell / dividend
    price: float
    amount: float
    quantity: Optional[float] = None
    trade_date: date
    fee: float = 0.0


class TradeUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    direction: Optional[str] = None
    price: Optional[float] = None
    amount: Optional[float] = None
    quantity: Optional[float] = None
    trade_date: Optional[date] = None
    fee: Optional[float] = None


class TradeOut(BaseModel):
    id: int
    code: str
    name: str
    direction: str
    price: float
    amount: float
    quantity: Optional[float]
    trade_date: date
    fee: float
    created_at: datetime

    class Config:
        from_attributes = True


class PositionOut(BaseModel):
    id: int
    code: str
    name: str
    category: Optional[str]
    linked_code: Optional[str]
    linked_name: Optional[str]
    linked_short_name: Optional[str]
    total_cost: float
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    weight: float
    is_closed: int
    updated_at: datetime
    linked_info: Optional[dict] = None

    class Config:
        from_attributes = True


class PositionDetailOut(BaseModel):
    code: str
    name: str
    short_name: Optional[str]
    category: Optional[str]
    linked_code: Optional[str]
    linked_name: Optional[str]
    linked_short_name: Optional[str]
    total_cost: float
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    total_pnl: float
    total_pnl_pct: float
    is_closed: int

    class Config:
        from_attributes = True


class DailySnapshotOut(BaseModel):
    id: int
    code: str
    date: date
    close: float
    market_value: Optional[float]
    daily_pnl: Optional[float]
    total_pnl: Optional[float]

    class Config:
        from_attributes = True


class OverviewOut(BaseModel):
    total_cost: float
    total_market_value: float
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    position_count: int
    latest_date: str | None = None


class YearlyStats(BaseModel):
    year: int
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    return_pct: float


class MonthlyStats(BaseModel):
    year: int
    month: int
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    return_pct: float


class AssetMetaOut(BaseModel):
    code: str
    name: str
    asset_type: str
    category: Optional[str]
    source: Optional[str]
    benchmark_index: Optional[str]
    list_date: Optional[date]
    is_cached: int

    class Config:
        from_attributes = True


class QuoteOut(BaseModel):
    code: str
    date: date
    close: float

    class Config:
        from_attributes = True


class StopLossConfigOut(BaseModel):
    id: int
    profit_level_key: str
    # 关联的利润等级信息
    level_name: Optional[str] = None
    level_code: Optional[str] = None
    pnl_min: Optional[float] = None
    pnl_max: Optional[float] = None
    # 止盈线参数
    half_position_ratio: Optional[float]
    clear_position_ratio: Optional[float]
    calculation_mode: str  # pmax_drawdown, profit_retention, cost_protection
    profit_retention_half: Optional[float]
    profit_retention_clear: Optional[float]
    updated_at: datetime

    class Config:
        from_attributes = True


class StopLossConfigUpdate(BaseModel):
    half_position_ratio: Optional[float] = None
    clear_position_ratio: Optional[float] = None
    calculation_mode: str = "pmax_drawdown"
    profit_retention_half: Optional[float] = None
    profit_retention_clear: Optional[float] = None


class StopLossConfigReset(BaseModel):
    confirm: bool = False


# Profit Level Config schemas
class ProfitLevelConfigOut(BaseModel):
    id: int
    level_name: str
    level_key: str
    level_code: str
    pnl_threshold: float
    pnl_threshold_max: Optional[float]
    use_peak_pnl: int
    sort_order: int
    display_color: str
    hold_days_min: Optional[int] = None
    hold_days_max: Optional[int] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class ProfitLevelConfigUpdate(BaseModel):
    level_name: str
    level_code: str
    pnl_threshold: float
    pnl_threshold_max: Optional[float] = None
    use_peak_pnl: int = 1
    display_color: str
    hold_days_min: Optional[int] = None
    hold_days_max: Optional[int] = None


# Baseline Config schemas
class BaselineConfigCreate(BaseModel):
    code: str
    baseline_code: str


class BaselineConfigOut(BaseModel):
    id: int
    code: str
    baseline_code: str
    created_at: datetime

    class Config:
        from_attributes = True


# Trade marker for position detail chart
class TradeMarker(BaseModel):
    date: date
    type: str  # buy, sell, dividend
    price: float
    amount: float


# Position update schemas
class PositionCategoryUpdate(BaseModel):
    category: Optional[str] = None


class PositionLinkedCodeUpdate(BaseModel):
    linked_code: Optional[str] = None
