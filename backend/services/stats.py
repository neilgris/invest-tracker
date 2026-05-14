from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Trade, Position, DailySnapshot
from datetime import date, datetime, timedelta


def get_overview(db: Session) -> dict:
    """获取总览数据"""
    positions = db.query(Position).all()

    total_cost = 0.0
    total_market_value = 0.0
    latest_pnl = 0.0
    latest_date = None

    for pos in positions:
        mv = pos.quantity * pos.current_price if pos.current_price else pos.total_cost
        total_cost += pos.total_cost
        total_market_value += mv

        # 获取最新有数据日期的盈亏
        snap = db.query(DailySnapshot).filter(
            DailySnapshot.code == pos.code
        ).order_by(DailySnapshot.date.desc()).first()
        if snap and snap.daily_pnl is not None:
            latest_pnl += snap.daily_pnl
            if latest_date is None or snap.date > latest_date:
                latest_date = snap.date

    total_pnl = total_market_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    latest_pnl_pct = (latest_pnl / total_cost * 100) if total_cost > 0 else 0

    return {
        "total_cost": round(total_cost, 2),
        "total_market_value": round(total_market_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "daily_pnl": round(latest_pnl, 2),
        "daily_pnl_pct": round(latest_pnl_pct, 2),
        "latest_date": latest_date.isoformat() if latest_date else None,
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
        # 月末市值 = 月末成本 + 当月累计盈亏（从年初到月末的总盈亏）
        # 需要计算该月末的累计盈亏
        month_dates = [d for d in sorted_dates if d.strftime("%Y-%m") == month_key]
        if month_dates:
            last_date = month_dates[-1]
            day_snaps = snaps_by_date.get(last_date, [])
            end_market_value = sum(s.market_value or 0 for s in day_snaps)
        else:
            end_market_value = 0
        result.append({
            "month": month_key,
            "pnl": round(pnl, 2),
            "cost_start": round(cost_start, 2),
            "cost_end": round(cost_end, 2),
            "end_market_value": round(end_market_value, 2),
            "pnl_pct": round(pnl / avg_cost * 100, 2) if avg_cost > 0 else 0,
        })
    return result


def get_yearly_stats(db: Session) -> list[dict]:
    """年度收益统计"""
    snapshots = db.query(DailySnapshot).all()
    year_set = sorted(set(s.date.year for s in snapshots))
    
    # 按日期索引快照
    snaps_by_date: dict[date, list] = {}
    for snap in snapshots:
        snaps_by_date.setdefault(snap.date, []).append(snap)
    sorted_dates = sorted(snaps_by_date.keys())
    
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
        
        # 计算年末市值（该年最后一天的market_value之和）
        year_dates = [d for d in sorted_dates if d.year == year]
        if year_dates:
            last_date = year_dates[-1]
            day_snaps = snaps_by_date.get(last_date, [])
            end_market_value = sum(s.market_value or 0 for s in day_snaps)
        else:
            end_market_value = 0
        
        result.append({
            "year": year,
            "pnl": round(year_pnl, 2),
            "cost": round(avg_cost, 2),
            "end_market_value": round(end_market_value, 2),
            "pnl_pct": round(year_pnl / avg_cost * 100, 2) if avg_cost > 0 else 0,
        })
    return result


def get_monthly_position_details(db: Session, year: int, month: int) -> dict:
    """获取某月各持仓的收益明细
    
    返回该月有持仓的所有标的，包含：
    - 持仓明细列表
    - 汇总数据（总盈亏、总收益率等）
    """
    from models import Position
    
    # 获取该月的起始和结束日期
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)
    
    # 获取该月所有快照
    snapshots = db.query(DailySnapshot).filter(
        DailySnapshot.date >= start_date,
        DailySnapshot.date <= end_date
    ).all()
    
    if not snapshots:
        return {"positions": [], "summary": {}}
    
    # 按代码分组，获取每个代码的月初和月末数据
    snaps_by_code: dict[str, list] = {}
    for snap in snapshots:
        snaps_by_code.setdefault(snap.code, []).append(snap)
    
    positions = []
    total_start_cost = 0.0
    total_end_cost = 0.0
    
    for code, code_snaps in snaps_by_code.items():
        # 按日期排序
        code_snaps.sort(key=lambda x: x.date)
        
        first_snap = code_snaps[0]
        last_snap = code_snaps[-1]
        
        # 月初/月末市值
        start_market_value = first_snap.market_value or 0
        end_market_value = last_snap.market_value or 0
        
        # 月初/月末累计盈亏
        start_total_pnl = first_snap.total_pnl or 0
        end_total_pnl = last_snap.total_pnl or 0
        
        # 计算当月总盈亏（所有daily_pnl之和）
        month_pnl = sum(s.daily_pnl or 0 for s in code_snaps)
        
        # 过滤掉当月无盈亏的（市值为0且没有产生盈亏）
        if start_market_value == 0 and end_market_value == 0 and abs(month_pnl) < 0.01:
            continue
        
        # 获取持仓名称
        position = db.query(Position).filter(Position.code == code).first()
        name = position.name if position else code
        
        # 月初/月末投入成本 = 市值 - 累计盈亏
        start_cost = start_market_value - start_total_pnl
        end_cost = end_market_value - end_total_pnl
        
        # 对于月中买入的情况（月初无持仓，月末有持仓），期初成本显示为买入当日的投入成本
        display_start_cost = start_cost if start_cost > 0 else end_cost
        
        total_start_cost += start_cost
        total_end_cost += end_cost
        
        # 计算收益率：如果月初无持仓，按月末投入成本计算；否则按月初投入成本计算
        if start_cost > 0:
            pnl_pct = round(month_pnl / start_cost * 100, 2)
        elif end_cost > 0:
            # 月中买入的情况：按实际投入成本（月末成本）计算
            pnl_pct = round(month_pnl / end_cost * 100, 2)
        else:
            pnl_pct = 0
        
        positions.append({
            "code": code,
            "name": name,
            "start_market_value": round(start_market_value, 2),
            "end_market_value": round(end_market_value, 2),
            "start_cost": round(display_start_cost, 2),  # 期初投入成本（月中买入时显示买入成本）
            "pnl": round(month_pnl, 2),
            "pnl_pct": pnl_pct,
        })
    
    # 按盈亏金额降序排列
    positions.sort(key=lambda x: x["pnl"], reverse=True)
    
    # 计算汇总数据
    total_start_market_value = sum(p["start_market_value"] for p in positions)
    total_end_market_value = sum(p["end_market_value"] for p in positions)
    total_pnl = sum(p["pnl"] for p in positions)
    
    # 平均投入成本 = (月初成本 + 月末成本) / 2，用于计算月度收益率（与月度统计一致）
    avg_cost = (total_start_cost + total_end_cost) / 2
    total_pnl_pct = round(total_pnl / avg_cost * 100, 2) if avg_cost > 0 else 0
    
    summary = {
        "total_start_market_value": round(total_start_market_value, 2),
        "total_end_market_value": round(total_end_market_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": total_pnl_pct,
        "position_count": len(positions),
    }
    
    return {"positions": positions, "summary": summary}


def get_yearly_position_details(db: Session, year: int) -> dict:
    """获取某年度各持仓的收益明细
    
    返回该年有持仓的所有标的，包含：
    - 持仓明细列表
    - 汇总数据（总盈亏、总收益率等）
    """
    from models import Position
    
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    
    # 获取该年所有快照
    snapshots = db.query(DailySnapshot).filter(
        DailySnapshot.date >= start_date,
        DailySnapshot.date <= end_date
    ).all()
    
    if not snapshots:
        return {"positions": [], "summary": {}}
    
    # 按代码分组，获取每个代码的年初和年末数据
    snaps_by_code: dict[str, list] = {}
    for snap in snapshots:
        snaps_by_code.setdefault(snap.code, []).append(snap)
    
    positions = []
    total_start_cost = 0.0
    total_end_cost = 0.0
    
    for code, code_snaps in snaps_by_code.items():
        # 按日期排序
        code_snaps.sort(key=lambda x: x.date)
        
        first_snap = code_snaps[0]
        last_snap = code_snaps[-1]
        
        # 年初/年末市值
        start_market_value = first_snap.market_value or 0
        end_market_value = last_snap.market_value or 0
        
        # 年初/年末累计盈亏
        start_total_pnl = first_snap.total_pnl or 0
        end_total_pnl = last_snap.total_pnl or 0
        
        # 计算当年总盈亏（所有daily_pnl之和）
        year_pnl = sum(s.daily_pnl or 0 for s in code_snaps)
        
        # 过滤掉当年无盈亏的（市值为0且没有产生盈亏）
        if start_market_value == 0 and end_market_value == 0 and abs(year_pnl) < 0.01:
            continue
        
        # 获取持仓名称
        position = db.query(Position).filter(Position.code == code).first()
        name = position.name if position else code
        
        # 年初/年末投入成本 = 市值 - 累计盈亏
        start_cost = start_market_value - start_total_pnl
        end_cost = end_market_value - end_total_pnl
        
        # 对于年中买入的情况（年初无持仓，年末有持仓），期初成本显示为买入当日的投入成本
        display_start_cost = start_cost if start_cost > 0 else end_cost
        
        total_start_cost += start_cost
        total_end_cost += end_cost
        
        # 计算收益率：如果年初无持仓，按年末投入成本计算；否则按年初投入成本计算
        if start_cost > 0:
            pnl_pct = round(year_pnl / start_cost * 100, 2)
        elif end_cost > 0:
            pnl_pct = round(year_pnl / end_cost * 100, 2)
        else:
            pnl_pct = 0
        
        positions.append({
            "code": code,
            "name": name,
            "start_market_value": round(start_market_value, 2),
            "end_market_value": round(end_market_value, 2),
            "start_cost": round(display_start_cost, 2),
            "pnl": round(year_pnl, 2),
            "pnl_pct": pnl_pct,
        })
    
    # 按盈亏金额降序排列
    positions.sort(key=lambda x: x["pnl"], reverse=True)
    
    # 计算汇总数据
    total_start_market_value = sum(p["start_market_value"] for p in positions)
    total_end_market_value = sum(p["end_market_value"] for p in positions)
    total_pnl = sum(p["pnl"] for p in positions)
    
    # 平均投入成本 = (年初成本 + 年末成本) / 2，用于计算年度收益率
    avg_cost = (total_start_cost + total_end_cost) / 2
    total_pnl_pct = round(total_pnl / avg_cost * 100, 2) if avg_cost > 0 else 0
    
    summary = {
        "total_start_market_value": round(total_start_market_value, 2),
        "total_end_market_value": round(total_end_market_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": total_pnl_pct,
        "position_count": len(positions),
    }
    
    return {"positions": positions, "summary": summary}
