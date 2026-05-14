from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


# --- Trade ---
class TradeCreate(BaseModel):
    code: str
    name: str
    direction: str  # buy / sell / dividend
    price: float
    amount: float
    quantity: Optional[float] = None
    trade_date: date
    fee: Optional[float] = 0.0


class TradeUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    direction: Optional[str] = None
    price: Optional[float] = None
    amount: Optional[float] = None
    quantity: Optional[float] = None
    trade_date: Optional[date] = None
    fee: Optional[float] = None


class TradeOut(TradeCreate):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Position ---
class PositionOut(BaseModel):
    id: int
    code: str
    name: str
    short_name: Optional[str] = None
    category: Optional[str] = None
    linked_code: Optional[str] = None
    linked_name: Optional[str] = None
    linked_price: Optional[float] = None
    linked_change_pct: Optional[float] = None
    total_cost: float
    quantity: float
    avg_cost: float
    current_price: float
    market_value: Optional[float] = None
    total_pnl: Optional[float] = None
    total_pnl_pct: Optional[float] = None
    daily_pnl: Optional[float] = None
    daily_pnl_pct: Optional[float] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PositionCategoryUpdate(BaseModel):
    category: Optional[str] = None  # 允许清空分类


class PositionLinkedCodeUpdate(BaseModel):
    linked_code: Optional[str] = None  # 允许清空关联


# --- Overview ---
class OverviewOut(BaseModel):
    total_cost: float
    total_market_value: float
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    latest_date: Optional[str] = None  # 最新有数据日期
    position_count: int


# --- DailySnapshot ---
class SnapshotOut(BaseModel):
    id: int
    code: str
    date: date
    open: Optional[float] = None
    close: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    market_value: Optional[float] = None
    daily_pnl: Optional[float] = None
    total_pnl: Optional[float] = None

    class Config:
        from_attributes = True


# --- BaselineConfig ---
class BaselineConfigCreate(BaseModel):
    etf_code: str
    baseline_code: str
    baseline_name: str


class BaselineConfigOut(BaselineConfigCreate):
    id: int

    class Config:
        from_attributes = True


# --- Monthly Stats ---
class MonthlyStat(BaseModel):
    month: str  # YYYY-MM
    pnl: float
    cost: float
    pnl_pct: float


# --- Chart Data ---
class ChartPoint(BaseModel):
    date: str
    value: float


class TradeMarker(BaseModel):
    date: str
    price: float
    direction: str  # buy / sell / dividend
