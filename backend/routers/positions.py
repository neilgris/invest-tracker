from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Position, DailySnapshot, Trade, HistQuotesCache
from schemas import PositionOut, OverviewOut, TradeMarker, PositionCategoryUpdate, PositionLinkedCodeUpdate
from services.stats import get_overview
from services.market import get_hist_prices
from datetime import date, timedelta, datetime
import math

router = APIRouter(prefix="/api/positions", tags=["持仓管理"])


def enrich_position(pos: Position, db: Session, latest_snaps: dict = None, latest_date: date = None) -> dict:
    """计算持仓的衍生字段"""
    # 从快照获取最新价格（T-1收盘价），而不是 pos.current_price
    if latest_snaps is not None:
        snap = latest_snaps.get(pos.code)
    else:
        # 获取该持仓最新有数据的日期
        snap = db.query(DailySnapshot).filter(
            DailySnapshot.code == pos.code
        ).order_by(DailySnapshot.date.desc()).first()
    
    # 使用快照的收盘价作为当前价格（T-1）
    current_price = snap.close if snap and snap.close else pos.current_price
    
    mv = pos.quantity * current_price if current_price else pos.total_cost
    total_pnl = mv - pos.total_cost
    total_pnl_pct = (total_pnl / pos.total_cost * 100) if pos.total_cost > 0 else 0

    daily_pnl = snap.daily_pnl if snap and snap.daily_pnl else 0
    daily_pnl_pct = (daily_pnl / pos.total_cost * 100) if pos.total_cost > 0 else 0

    # 关联ETF信息
    linked_info = None
    if pos.linked_code:
        # 从快照获取关联ETF的最新价格
        linked_snap = db.query(DailySnapshot).filter(
            DailySnapshot.code == pos.linked_code
        ).order_by(DailySnapshot.date.desc()).first()
        linked_price = linked_snap.close if linked_snap and linked_snap.close else None
        linked_info = {
            "code": pos.linked_code,
            "name": pos.linked_name,
            "short_name": pos.linked_short_name or pos.linked_name,
            "current_price": round(linked_price, 4) if linked_price else None,
        }
    
    # 止盈线价格计算（由前端根据配置动态计算，后端只返回必要的基础数据）
    stop_loss_prices = None
    
    return {
        "code": pos.code,
        "name": pos.name,
        "short_name": pos.linked_short_name if pos.linked_short_name else pos.name,
        "category": pos.category,
        "linked_code": pos.linked_code,
        "linked_name": pos.linked_name,
        "linked_short_name": pos.linked_short_name,
        "quantity": pos.quantity,
        "avg_cost": round(pos.avg_cost, 4),
        "current_price": round(current_price, 4) if current_price else None,
        "market_value": round(mv, 2),
        "total_cost": round(pos.total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "daily_pnl": round(daily_pnl, 2),
        "daily_pnl_pct": round(daily_pnl_pct, 2),
        "is_closed": pos.is_closed,
        "updated_at": pos.updated_at,
        "linked_info": linked_info,
        "benchmark_index": pos.benchmark_index,
    }


@router.get("")
def list_positions(db: Session = Depends(get_db)):
    """获取所有持仓列表"""
    positions = db.query(Position).filter(Position.is_closed == 0).all()
    
    # 批量获取最新快照日期
    latest_date = db.query(func.max(DailySnapshot.date)).scalar()
    
    # 批量获取所有持仓的最新快照
    latest_snaps = {}
    if latest_date:
        snaps = db.query(DailySnapshot).filter(DailySnapshot.date == latest_date).all()
        latest_snaps = {s.code: s for s in snaps}
    
    # 计算总市值用于权重计算
    total_mv = 0
    enriched = []
    for pos in positions:
        data = enrich_position(pos, db, latest_snaps, latest_date)
        enriched.append(data)
        total_mv += data.get("market_value", 0)
    
    # 添加权重字段
    result = []
    for data in enriched:
        data["weight"] = round(data.get("market_value", 0) / total_mv * 100, 2) if total_mv > 0 else 0
        result.append(data)
    
    return result


@router.get("/overview", response_model=OverviewOut)
def overview(db: Session = Depends(get_db)):
    return get_overview(db)


@router.get("/categories/stats")
def get_category_stats(db: Session = Depends(get_db)):
    """获取按分类汇总的持仓统计数据"""
    positions = db.query(Position).filter(Position.is_closed == 0).all()
    
    # 批量获取最新快照日期
    latest_date = db.query(func.max(DailySnapshot.date)).scalar()
    
    # 批量获取所有持仓的最新快照
    latest_snaps = {}
    if latest_date:
        snaps = db.query(DailySnapshot).filter(DailySnapshot.date == latest_date).all()
        latest_snaps = {s.code: s for s in snaps}
    
    # 按分类汇总
    category_stats = {}
    for pos in positions:
        category = pos.category or "未分类"
        
        # 计算市值和盈亏
        snap = latest_snaps.get(pos.code)
        current_price = snap.close if snap and snap.close else pos.current_price
        mv = pos.quantity * current_price if current_price else pos.total_cost
        total_pnl = mv - pos.total_cost
        total_pnl_pct = (total_pnl / pos.total_cost * 100) if pos.total_cost > 0 else 0
        
        if category not in category_stats:
            category_stats[category] = {
                "category": category,
                "market_value": 0,
                "total_cost": 0,
                "total_pnl": 0,
                "position_count": 0,
            }
        
        category_stats[category]["market_value"] += mv
        category_stats[category]["total_cost"] += pos.total_cost
        category_stats[category]["total_pnl"] += total_pnl
        category_stats[category]["position_count"] += 1
    
    # 转换为列表并计算盈亏率
    result = []
    for cat, data in category_stats.items():
        data["market_value"] = round(data["market_value"], 2)
        data["total_cost"] = round(data["total_cost"], 2)
        data["total_pnl"] = round(data["total_pnl"], 2)
        data["pnl_pct"] = round((data["total_pnl"] / data["total_cost"] * 100), 2) if data["total_cost"] > 0 else 0
        result.append(data)
    
    # 按盈亏率降序排列
    return sorted(result, key=lambda x: x["pnl_pct"], reverse=True)


@router.get("/closed-positions")
def get_closed_positions(db: Session = Depends(get_db)):
    """获取已清仓标的的历史收益"""
    result = []
    
    # 只处理 is_closed=1 的持仓记录
    closed_positions = db.query(Position).filter(Position.is_closed == 1).all()
    for position in closed_positions:
        code = position.code
        trades = db.query(Trade).filter(Trade.code == code).order_by(Trade.trade_date).all()
        if not trades:
            continue
        
        # 已清仓标的：优先使用关联ETF短名
        name = position.linked_short_name if position.linked_short_name else position.name
        
        # 计算总买入、总卖出、总分红
        total_buy = 0
        total_sell = 0
        total_dividend = 0
        
        for t in trades:
            if t.direction == "buy":
                total_buy += t.amount
            elif t.direction == "sell":
                total_sell += (t.amount - t.fee)
            elif t.direction == "dividend":
                total_dividend += (t.quantity or 0)
        
        # 清仓收益 = 卖出总金额 - 买入总金额 + 分红金额
        total_pnl = total_sell - total_buy + total_dividend
        pnl_pct = (total_pnl / total_buy * 100) if total_buy > 0 else 0
        
        # 获取第一笔和最后一笔交易日期
        first_trade = trades[0].trade_date
        last_trade = trades[-1].trade_date
        
        result.append({
            "code": code,
            "name": name,
            "total_buy": round(total_buy, 2),
            "total_sell": round(total_sell, 2),
            "total_dividend": round(total_dividend, 2),
            "total_pnl": round(total_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "first_trade": first_trade.strftime("%Y-%m-%d"),
            "last_trade": last_trade.strftime("%Y-%m-%d"),
            "trade_count": len(trades),
        })
    
    # 按盈亏额降序排列
    return sorted(result, key=lambda x: x["total_pnl"], reverse=True)


@router.get("/{code}")
def get_position_detail(code: str, db: Session = Depends(get_db)):
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")
    return enrich_position(pos, db)


def _aggregate_weekly(snaps: list) -> list[dict]:
    """将日线数据聚合为周线：按ISO周分组"""
    from itertools import groupby

    if not snaps:
        return []
    result = []
    for key, group in groupby(snaps, key=lambda s: s.date.isocalendar()[:2]):
        items = list(group)
        result.append({
            "date": items[-1].date.strftime("%Y-%m-%d"),  # 用周五日期
            "open": items[0].open,
            "close": items[-1].close,
            "high": max(s.high or s.close for s in items),
            "low": min(s.low or s.close for s in items),
        })
    return result


def _aggregate_monthly(snaps: list) -> list[dict]:
    """将日线数据聚合为月线：按年月分组"""
    from itertools import groupby

    if not snaps:
        return []
    result = []
    for key, group in groupby(snaps, key=lambda s: (s.date.year, s.date.month)):
        items = list(group)
        result.append({
            "date": items[-1].date.strftime("%Y-%m-%d"),  # 用月末日期
            "open": items[0].open,
            "close": items[-1].close,
            "high": max(s.high or s.close for s in items),
            "low": min(s.low or s.close for s in items),
        })
    return result


@router.get("/{code}/chart")
def get_position_chart(
    code: str,
    period: str = Query("daily", enum=["daily", "weekly", "monthly"]),
    baseline: str = Query(None, description="基线代码，如000300"),
    db: Session = Depends(get_db)
):
    """获取持仓走势图数据"""
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")
    
    # 获取历史快照数据
    snaps = db.query(DailySnapshot).filter(
        DailySnapshot.code == code
    ).order_by(DailySnapshot.date).all()
    
    if not snaps:
        return {"data": [], "trades": [], "baseline": None}
    
    # 根据周期聚合数据
    if period == "weekly":
        price_data = _aggregate_weekly(snaps)
    elif period == "monthly":
        price_data = _aggregate_monthly(snaps)
    else:
        price_data = [{
            "date": s.date.strftime("%Y-%m-%d"),
            "open": s.open,
            "close": s.close,
            "high": s.high,
            "low": s.low,
        } for s in snaps]
    
    # 获取交易记录（用于标记买卖点）
    trades = db.query(Trade).filter(Trade.code == code).order_by(Trade.trade_date).all()
    trade_markers = []
    for t in trades:
        trade_markers.append({
            "date": t.trade_date.strftime("%Y-%m-%d"),
            "direction": t.direction,
            "price": t.price,
            "amount": t.amount,
            "quantity": t.quantity,
        })
    
    # 获取基线数据（从 hist_quotes_cache 读取，不走 daily_snapshots）
    baseline_data = None
    if baseline:
        baseline_quotes = db.query(HistQuotesCache).filter(
            HistQuotesCache.code == baseline
        ).order_by(HistQuotesCache.date).all()
        if baseline_quotes:
            if period == "weekly":
                baseline_data = _aggregate_weekly(baseline_quotes)
            elif period == "monthly":
                baseline_data = _aggregate_monthly(baseline_quotes)
            else:
                baseline_data = [{
                    "date": q.date.strftime("%Y-%m-%d"),
                    "close": q.close,
                } for q in baseline_quotes]
    
    return {
        "data": price_data,
        "trades": trade_markers,
        "baseline": baseline_data,
        "avg_cost": pos.avg_cost,
    }


@router.get("/{code}/trades")
def get_position_trades(code: str, db: Session = Depends(get_db)):
    """获取持仓的交易记录"""
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")
    
    trades = db.query(Trade).filter(Trade.code == code).order_by(Trade.trade_date.desc()).all()
    return [{
        "id": t.id,
        "trade_date": t.trade_date.strftime("%Y-%m-%d"),
        "direction": t.direction,
        "price": t.price,
        "quantity": t.quantity,
        "amount": t.amount,
        "fee": t.fee,
        "name": t.name,
    } for t in trades]


@router.put("/{code}/category")
def update_position_category(
    code: str,
    update: PositionCategoryUpdate,
    db: Session = Depends(get_db)
):
    """更新持仓分类"""
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")
    
    pos.category = update.category
    db.commit()
    return {"message": "分类更新成功"}


@router.put("/{code}/linked-code")
def update_position_linked_code(
    code: str,
    update: PositionLinkedCodeUpdate,
    db: Session = Depends(get_db)
):
    """更新持仓关联的ETF代码"""
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")
    
    # 如果提供了关联代码，验证它是否存在
    if update.linked_code:
        linked_pos = db.query(Position).filter(Position.code == update.linked_code).first()
        if not linked_pos:
            raise HTTPException(status_code=404, detail=f"关联ETF {update.linked_code} 不存在")
        pos.linked_name = linked_pos.name
        pos.linked_short_name = linked_pos.linked_short_name or linked_pos.name
    else:
        pos.linked_name = None
        pos.linked_short_name = None
    
    pos.linked_code = update.linked_code
    db.commit()
    
    return {
        "message": "关联ETF更新成功",
        "linked_code": pos.linked_code,
        "linked_name": pos.linked_name,
        "linked_short_name": pos.linked_short_name,
    }


@router.get("/{code}/pnl-history")
def get_pnl_history(
    code: str,
    start_date: date = Query(None),
    end_date: date = Query(None),
    db: Session = Depends(get_db)
):
    """获取持仓收益历史"""
    pos = db.query(Position).filter(Position.code == code).first()
    if not pos:
        raise HTTPException(status_code=404, detail="持仓不存在")
    
    query = db.query(DailySnapshot).filter(DailySnapshot.code == code)
    if start_date:
        query = query.filter(DailySnapshot.date >= start_date)
    if end_date:
        query = query.filter(DailySnapshot.date <= end_date)
    
    snaps = query.order_by(DailySnapshot.date).all()
    
    return [{
        "date": s.date.strftime("%Y-%m-%d"),
        "close": s.close,
        "daily_pnl": s.daily_pnl,
        "cumulative_pnl": s.cumulative_pnl,
    } for s in snaps]


@router.get("/{code}/dividends")
def get_position_dividends(code: str, db: Session = Depends(get_db)):
    """获取持仓的分红记录"""
    dividends = db.query(Trade).filter(
        Trade.code == code,
        Trade.direction == "dividend"
    ).order_by(Trade.trade_date.desc()).all()
    
    return [{
        "id": d.id,
        "trade_date": d.trade_date.strftime("%Y-%m-%d"),
        "amount": d.amount,
        "quantity": d.quantity,
        "name": d.name,
    } for d in dividends]
