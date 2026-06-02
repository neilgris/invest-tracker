
"""
历史行情分析 API
================
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

from database import get_db
from models import AssetMeta, HistQuotesCache

router = APIRouter(prefix="/api/analysis", tags=["历史行情分析"])

# ── 请求模型 ──────────────────────────────────────────

class SyncRequest(BaseModel):
    code: str
    asset_type: str = "stock"  # index / sector_industry / sector_concept / etf / stock / fund

class SyncBatchRequest(BaseModel):
    codes: list[str]
    asset_type: str = "stock"

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()

# ══════════════════════════════════════════════════════
# 数据缓存 API
# ══════════════════════════════════════════════════════

@router.post("/cache/sync")
def sync_single(req: SyncRequest):
    """拉取指定标的行情并缓存"""
    from services.analysis.data_fetcher import sync_single as _sync
    return _sync(req.code, req.asset_type)

@router.post("/cache/sync-batch")
def sync_batch(req: SyncBatchRequest):
    """批量拉取多个标的行情"""
    from services.analysis.data_fetcher import sync_batch as _sync
    return _sync(req.codes, req.asset_type)

@router.post("/cache/sync-l1")
def sync_l1_indexes():
    """同步 L1 大盘指数（7个宽基）"""
    from services.analysis.data_fetcher import sync_l1_indexes as _sync
    return _sync()

@router.post("/cache/sync-l2")
def sync_l2_industry():
    """同步 L2 行业板块（申万指数）"""
    from services.analysis.data_fetcher import sync_l2_industry as _sync
    return _sync()

@router.post("/cache/sync-l3-theme")
def sync_l3_theme_indexes():
    """同步 L3 主题指数（持仓关联的中证/恒生系列指数）"""
    from services.analysis.data_fetcher import sync_l3_theme_indexes as _sync
    return _sync()

@router.post("/cache/sync-l6")
def sync_l6_commodity():
    """同步 L6 国际大宗商品（黄金/原油/白银等）"""
    from services.analysis.data_fetcher import sync_l6_commodity as _sync
    return _sync()

@router.post("/cache/sync-l6c")
def sync_l6c_domestic_commodity():
    """同步 L6C 国内大宗商品（焦炭/焦煤等期货连续合约）"""
    from services.analysis.data_fetcher import sync_l6c_domestic_commodity as _sync
    return _sync()

@router.get("/cache/status")
def cache_status():
    """查看缓存概况"""
    from services.analysis.data_fetcher import get_cache_status
    return get_cache_status()

@router.get("/cache/progress")
def sync_progress():
    """获取当前同步进度"""
    from services.analysis.data_fetcher import get_sync_progress
    return get_sync_progress()

# ══════════════════════════════════════════════════════
# 基础数据查看 API
# ══════════════════════════════════════════════════════

@router.get("/data/ohlcv")
def data_ohlcv(
    code: str = Query(..., description="资产代码"),
    limit: int = Query(100, description="返回条数"),
    db: Session = Depends(get_db)
):
    """获取K线数据（OHLCV）"""
    rows = db.query(HistQuotesCache).filter(
        HistQuotesCache.code == code
    ).order_by(HistQuotesCache.date.desc()).limit(limit).all()
    
    return {
        "code": code,
        "count": len(rows),
        "data": [
            {
                "date": r.date.isoformat(),
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "turnover": r.turnover,
                "pct_change": r.pct_change
            }
            for r in reversed(rows)  # 按日期正序
        ]
    }

@router.get("/data/stats")
def data_stats(
    code: str = Query(..., description="资产代码"),
    db: Session = Depends(get_db)
):
    """基础统计信息"""
    from sqlalchemy import func
    
    # 基础统计
    row = db.query(
        func.min(HistQuotesCache.date).label("min_date"),
        func.max(HistQuotesCache.date).label("max_date"),
        func.count(HistQuotesCache.id).label("count"),
        func.avg(HistQuotesCache.pct_change).label("avg_return"),
        func.min(HistQuotesCache.pct_change).label("min_return"),
        func.max(HistQuotesCache.pct_change).label("max_return"),
        func.avg(HistQuotesCache.volume).label("avg_volume"),
        func.avg(HistQuotesCache.close).label("avg_close")
    ).filter(HistQuotesCache.code == code).first()
    
    if not row or row.count == 0:
        return {"code": code, "exists": False}
    
    # 计算波动率（标准差）
    returns = db.query(HistQuotesCache.pct_change).filter(
        HistQuotesCache.code == code,
        HistQuotesCache.pct_change.isnot(None)
    ).all()
    returns = [r[0] for r in returns if r[0] is not None]
    
    import numpy as np
    volatility = float(np.std(returns)) if len(returns) > 1 else None
    
    # 年化收益
    total_return = None
    if row.count > 1:
        first_close = db.query(HistQuotesCache.close).filter(
            HistQuotesCache.code == code
        ).order_by(HistQuotesCache.date.asc()).first()
        last_close = db.query(HistQuotesCache.close).filter(
            HistQuotesCache.code == code
        ).order_by(HistQuotesCache.date.desc()).first()
        if first_close and last_close and first_close[0] and last_close[0]:
            total_return = (last_close[0] - first_close[0]) / first_close[0]
    
    return {
        "code": code,
        "exists": True,
        "date_range": {"start": row.min_date.isoformat(), "end": row.max_date.isoformat()},
        "total_days": row.count,
        "returns": {
            "total": round(total_return * 100, 2) if total_return else None,
            "avg_daily": round(row.avg_return, 4) if row.avg_return else None,
            "min": round(row.min_return, 2) if row.min_return else None,
            "max": round(row.max_return, 2) if row.max_return else None,
            "volatility": round(volatility, 4) if volatility else None
        },
        "price": {
            "avg": round(row.avg_close, 2) if row.avg_close else None
        },
        "volume": {
            "avg": int(row.avg_volume) if row.avg_volume else None
        }
    }

class GridSearchRequest(BaseModel):
    code: str
    exit_mode: str = "pmax_drawdown"
    grid: dict
    objective: str = "calmar"
    entry_freq: int = 5
    whipsaw_window: int = 20
    max_combos: int = 100000
    top_n: int = 30
    train_end: Optional[str] = None
    oos_top_n: int = 5
    reentry_lookback: int = 60   # 回撤入场高点回看窗口（交易日）

@router.post("/backtest/grid-search")
def grid_search(req: GridSearchRequest, db: Session = Depends(get_db)):
    """
    参数网格搜索：对单一退出模式扫描参数笛卡尔积，按目标排序输出 top 组合 + 热力图。
    """
    from services.analysis.backtest import run_grid_search
    return run_grid_search(
        db=db,
        code=req.code,
        exit_mode=req.exit_mode,
        grid=req.grid,
        objective=req.objective,
        entry_freq=req.entry_freq,
        whipsaw_window=req.whipsaw_window,
        max_combos=req.max_combos,
        top_n=req.top_n,
        train_end=req.train_end,
        oos_top_n=req.oos_top_n,
        reentry_lookback=req.reentry_lookback,
    )

