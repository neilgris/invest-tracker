from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Trade, Position, DailySnapshot
from datetime import date, datetime, timedelta


def get_overview(db: Session) -> dict:
    """获取总览数据"""
    positions = db.query(Position).all()

    total_cost = 0.0
    total_market_value = 0.0
    daily_pnl = 0.0

    for pos in positions:
        mv = pos.quantity * pos.current_price if pos.current_price else pos.total_cost
        total_cost += pos.total_cost
        total_market_value += mv

        # 每日盈亏从快照取
        today = date.today()
        snap = db.query(DailySnapshot).filter(
            DailySnapshot.code == pos.code,
            DailySnapshot.date == today
        ).first()
        if snap and snap.daily_pnl is not None:
            daily_pnl += snap.daily_pnl

    total_pnl = total_market_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    daily_pnl_pct = (daily_pnl / total_cost * 100) if total_cost > 0 else 0

    return {
        "total_cost": round(total_cost, 2),
        "total_market_value": round(total_market_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "daily_pnl": round(daily_pnl, 2),
        "daily_pnl_pct": round(daily_pnl_pct, 2),
        "position_count": len(positions),
    }


def _get_cost_on_date(snaps_by_date: dict, target_date: date) -> float:
    """计算某天所有持仓的投入成本 = sum(market_value - total_pnl)"""
    day_snaps = snaps_by_date.get(target_date, [])
    return sum(
        (s.market_value or 0) - (s.total_pnl or 0)
        for s in day_snaps
        if s.market_value and s.market_value > 0
    )


def get_monthly_stats(db: Session, year: int | None = None) -> list[dict]:
    """月度收益统计"""
    if not year:
        year = date.today().year

    snapshots = db.query(DailySnapshot).filter(
        DailySnapshot.date >= date(year, 1, 1),
        DailySnapshot.date <= date(year, 12, 31)
    ).all()

    # 按日期索引快照
    snaps_by_date: dict[date, list] = {}
    for snap in snapshots:
        snaps_by_date.setdefault(snap.date, []).append(snap)

    # 按月聚合
    monthly = {}
    for snap in snapshots:
        month_key = snap.date.strftime("%Y-%m")
        if month_key not in monthly:
            monthly[month_key] = {"pnl": 0.0}
        monthly[month_key]["pnl"] += snap.daily_pnl or 0

    # 按月计算月初/月末持仓成本
    sorted_dates = sorted(snaps_by_date.keys())
    for month_key in monthly:
        month_dates = [d for d in sorted_dates if d.strftime("%Y-%m") == month_key]
        if not month_dates:
            monthly[month_key]["cost_start"] = 0.0
            monthly[month_key]["cost_end"] = 0.0
            continue

        # 月初成本：本月第一个交易日的持仓成本
        cost_start = _get_cost_on_date(snaps_by_date, month_dates[0])

        # 月末成本：本月最后一个交易日的持仓成本
        cost_end = _get_cost_on_date(snaps_by_date, month_dates[-1])

        monthly[month_key]["cost_start"] = round(cost_start, 2)
        monthly[month_key]["cost_end"] = round(cost_end, 2)

    result = []
    for month_key in sorted(monthly.keys()):
        pnl = monthly[month_key]["pnl"]
        cost_start = monthly[month_key]["cost_start"]
        cost_end = monthly[month_key]["cost_end"]
        # 平均投入成本 = (月初 + 月末) / 2，用于计算月度收益率
        avg_cost = (cost_start + cost_end) / 2
        result.append({
            "month": month_key,
            "pnl": round(pnl, 2),
            "cost_start": round(cost_start, 2),
            "cost_end": round(cost_end, 2),
            "pnl_pct": round(pnl / avg_cost * 100, 2) if avg_cost > 0 else 0,
        })
    return result


def get_yearly_stats(db: Session) -> list[dict]:
    """年度收益统计"""
    snapshots = db.query(DailySnapshot).all()
    year_set = sorted(set(s.date.year for s in snapshots))
    result = []
    for year in year_set:
        monthly = get_monthly_stats(db, year)
        year_pnl = sum(m["pnl"] for m in monthly)
        # 年度成本：取第一个有持仓月份的月初成本和最后一个月的月末成本
        months_with_cost = [m for m in monthly if m["cost_end"] > 0]
        if months_with_cost:
            cost_start = months_with_cost[0]["cost_start"]
            cost_end = months_with_cost[-1]["cost_end"]
            avg_cost = (cost_start + cost_end) / 2
        else:
            avg_cost = 0
        result.append({
            "year": year,
            "pnl": round(year_pnl, 2),
            "cost": round(avg_cost, 2),
            "pnl_pct": round(year_pnl / avg_cost * 100, 2) if avg_cost > 0 else 0,
        })
    return result
