
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

class CorrelationRequest(BaseModel):
    code_a: str
    code_b: str
    field: str = "pct_change"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class CorrelationMatrixRequest(BaseModel):
    codes: list[str]
    field: str = "pct_change"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class RollingCorrelationRequest(BaseModel):
    code_a: str
    code_b: str
    window: int = 60
    field: str = "pct_change"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class CrossCorrelationRequest(BaseModel):
    code_a: str
    code_b: str
    max_lag: int = 20
    field: str = "pct_change"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class GrangerRequest(BaseModel):
    code_a: str
    code_b: str
    max_lag: int = 5
    field: str = "pct_change"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ClusteringRequest(BaseModel):
    codes: list[str]
    field: str = "pct_change"
    n_clusters: int = 4
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class PatternRequest(BaseModel):
    code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


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


@router.post("/cache/sync-l2-em")
def sync_l2_industry_em():
    """同步 L2 行业板块（东方财富）- 已废弃，请使用THS版本"""
    from services.analysis.data_fetcher import sync_l2_industry_em as _sync
    return _sync()


@router.post("/cache/sync-l2-ths")
def sync_l2_industry_ths():
    """同步 L2 行业板块（同花顺）- 分页获取，每5秒一次"""
    from services.analysis.data_fetcher import sync_l2_industry_ths as _sync
    return _sync()


@router.post("/cache/sync-l3")
def sync_l3_concept():
    """同步 L3 概念板块"""
    from services.analysis.data_fetcher import sync_l3_concept as _sync
    return _sync()


@router.post("/cache/sync-l2-em")
def sync_l2_em():
    """同步 L2 行业板块（东方财富源）"""
    from services.analysis.data_fetcher import sync_l2_industry_em as _sync
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
# 相关性分析 API
# ══════════════════════════════════════════════════════

@router.post("/correlation/pearson")
def calc_pearson(req: CorrelationRequest):
    """两两皮尔逊相关系数"""
    from services.analysis.correlation import pearson_correlation
    return pearson_correlation(
        req.code_a, req.code_b, _parse_date(req.start_date), _parse_date(req.end_date), req.field
    )


@router.post("/correlation/matrix")
def calc_matrix(req: CorrelationMatrixRequest):
    """多标的的相关系数矩阵"""
    from services.analysis.correlation import correlation_matrix
    return correlation_matrix(
        req.codes, _parse_date(req.start_date), _parse_date(req.end_date), req.field
    )


@router.post("/correlation/rolling")
def calc_rolling(req: RollingCorrelationRequest):
    """滚动窗口相关性"""
    from services.analysis.correlation import rolling_correlation
    return rolling_correlation(
        req.code_a, req.code_b, req.window, _parse_date(req.start_date), _parse_date(req.end_date), req.field
    )


@router.post("/correlation/ccf")
def calc_ccf(req: CrossCorrelationRequest):
    """交叉相关函数（领先滞后分析）"""
    from services.analysis.correlation import cross_correlation
    return cross_correlation(
        req.code_a, req.code_b, req.max_lag, _parse_date(req.start_date), _parse_date(req.end_date), req.field
    )


@router.post("/correlation/granger")
def calc_granger(req: GrangerRequest):
    """Granger 因果检验"""
    from services.analysis.correlation import granger_causality
    return granger_causality(
        req.code_a, req.code_b, req.max_lag, _parse_date(req.start_date), _parse_date(req.end_date), req.field
    )


# ══════════════════════════════════════════════════════
# 特征规律挖掘 API
# ══════════════════════════════════════════════════════

@router.post("/pattern/seasonality-monthly")
def pattern_monthly(req: PatternRequest):
    """月度季节效应"""
    from services.analysis.pattern import seasonality_monthly
    return seasonality_monthly(req.code, _parse_date(req.start_date), _parse_date(req.end_date))


@router.post("/pattern/seasonality-weekday")
def pattern_weekday(req: PatternRequest):
    """周几效应"""
    from services.analysis.pattern import seasonality_weekday
    return seasonality_weekday(req.code, _parse_date(req.start_date), _parse_date(req.end_date))


@router.post("/pattern/momentum-reversal")
def pattern_momentum(req: PatternRequest):
    """动量反转分析"""
    from services.analysis.pattern import momentum_reversal
    return momentum_reversal(req.code, 20, 5, _parse_date(req.start_date), _parse_date(req.end_date))


@router.post("/pattern/mean-reversion")
def pattern_mean_reversion(req: PatternRequest):
    """均值回归分析"""
    from services.analysis.pattern import mean_reversion
    return mean_reversion(req.code, 60, _parse_date(req.start_date), _parse_date(req.end_date))


@router.post("/pattern/clustering")
def pattern_clustering(req: ClusteringRequest):
    """层次聚类"""
    from services.analysis.pattern import hierarchical_clustering
    return hierarchical_clustering(
        req.codes, _parse_date(req.start_date), _parse_date(req.end_date), req.field, req.n_clusters
    )


# ══════════════════════════════════════════════════════
# 报告 API
# ══════════════════════════════════════════════════════

@router.post("/report/quick")
def report_quick(req: PatternRequest):
    """单标的快速诊断报告"""
    from services.analysis.report import quick_report
    return quick_report(req.code, _parse_date(req.start_date), _parse_date(req.end_date))


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


@router.get("/data/distribution")
def data_distribution(
    code: str = Query(..., description="资产代码"),
    field: str = Query("pct_change", description="字段: pct_change/close/volume"),
    bins: int = Query(20, description="分箱数"),
    db: Session = Depends(get_db)
):
    """获取数据分布（用于直方图）"""
    import numpy as np
    from sqlalchemy import func
    
    # 获取数据
    query = db.query(getattr(HistQuotesCache, field)).filter(
        getattr(HistQuotesCache, field).isnot(None),
        HistQuotesCache.code == code
    )
    values = [v[0] for v in query.all() if v[0] is not None]
    
    if not values:
        return {"code": code, "field": field, "count": 0, "bins": [], "freq": []}
    
    # 计算分箱
    hist, bin_edges = np.histogram(values, bins=bins)
    
    return {
        "code": code,
        "field": field,
        "count": len(values),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "bins": [float(b) for b in bin_edges[:-1]],  # 左边界
        "freq": [int(h) for h in hist]
    }


@router.get("/data/volume-analysis")
def volume_analysis(
    code: str = Query(..., description="资产代码"),
    limit: int = Query(252, description="返回条数"),
    db: Session = Depends(get_db)
):
    """成交量分析"""
    rows = db.query(HistQuotesCache).filter(
        HistQuotesCache.code == code,
        HistQuotesCache.volume.isnot(None)
    ).order_by(HistQuotesCache.date.desc()).limit(limit).all()
    
    if not rows:
        return {"code": code, "count": 0}
    
    volumes = [r.volume for r in rows]
    turnovers = [r.turnover for r in rows if r.turnover]
    
    return {
        "code": code,
        "count": len(rows),
        "volume": {
            "avg": sum(volumes) / len(volumes),
            "max": max(volumes),
            "min": min(volumes)
        },
        "turnover": {
            "avg": sum(turnovers) / len(turnovers) if turnovers else None,
            "max": max(turnovers) if turnovers else None,
            "min": min(turnovers) if turnovers else None
        } if turnovers else None,
        "data": [
            {"date": r.date.isoformat(), "volume": r.volume, "turnover": r.turnover, "close": r.close}
            for r in reversed(rows)
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


@router.post("/report/pair")
def report_pair(req: CorrelationRequest):
    """两两关系报告"""
    from services.analysis.report import pair_report
    return pair_report(
        req.code_a, req.code_b, _parse_date(req.start_date), _parse_date(req.end_date)
    )
