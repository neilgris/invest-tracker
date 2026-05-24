from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Trade, Position, DailySnapshot
from datetime import date, datetime, timedelta


def get_overview(db: Session) -> dict:
    """获取总览数据"""
    positions = db.query(Position).filter(Position.is_closed == 0).all()

    total_cost = 0.0
    total_market_value = 0.0
    latest_pnl = 0.0
    latest_date = None

    for pos in positions:
        # 从快照获取最新价格（T-1收盘价）
        snap = db.query(DailySnapshot).filter(
            DailySnapshot.code == pos.code
        ).order_by(DailySnapshot.date.desc()).first()
        
        price = snap.close if snap and snap.close else pos.current_price
        mv = pos.quantity * price if price else pos.total_cost
        total_cost += pos.total_cost
        total_market_value += mv

        # 获取最新有数据日期的盈亏
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
    """月度收益统计
    
    计算逻辑：
    直接调用 get_monthly_position_details 汇总各标的明细收益，确保口径完全一致。
    月度总收益 = sum(各标的 realized_pnl + unrealized_pnl)
    """
    if not year:
        year = date.today().year

    # 获取当年所有交易，用于确定哪些月份有数据
    all_year_trades = db.query(Trade).filter(
        Trade.trade_date >= date(year, 1, 1),
        Trade.trade_date <= date(year, 12, 31)
    ).all()

    # 获取当年及上一年12月的快照（用于计算成本）
    snapshots = db.query(DailySnapshot).filter(
        DailySnapshot.date >= date(year - 1, 12, 1),
        DailySnapshot.date <= date(year, 12, 31)
    ).all()

    # 按日期索引快照
    snaps_by_date: dict[date, list] = {}
    for snap in snapshots:
        snaps_by_date.setdefault(snap.date, []).append(snap)

    sorted_dates = sorted(snaps_by_date.keys())

    # 按月聚合
    monthly = {}
    for snap in snapshots:
        month_key = snap.date.strftime("%Y-%m")
        if snap.date.year == year and month_key not in monthly:
            monthly[month_key] = {}

    # 补充：检查当年有卖出交易的月份（已清仓标的可能导致该月无快照）
    for t in all_year_trades:
        if t.direction == 'sell':
            month_key = t.trade_date.strftime("%Y-%m")
            if month_key not in monthly:
                monthly[month_key] = {}

    result = []

    for month_key in sorted(monthly.keys()):
        # 跳过上一年12月的数据
        if month_key.startswith(str(year - 1)):
            continue

        # 解析年月
        year_num, month_num = map(int, month_key.split("-"))
        
        # 直接调用 get_monthly_position_details 获取明细
        details = get_monthly_position_details(db, year_num, month_num)
        summary = details.get("summary", {})
        
        # 从明细汇总数据
        total_realized_pnl = summary.get("total_realized_pnl", 0)
        total_unrealized_pnl = summary.get("total_unrealized_pnl", 0)
        total_pnl = summary.get("total_pnl", 0)
        
        # 从明细汇总获取成本和市值数据（确保与明细汇总口径一致）
        details_summary = details.get("summary", {})
        total_start_cost = details_summary.get("total_start_cost", 0)
        total_end_cost = details_summary.get("total_end_cost", 0)
        total_end_market_value = details_summary.get("total_end_market_value", 0)
        total_pnl_pct = details_summary.get("total_pnl_pct", 0)
        
        result.append({
            "month": month_key,
            "realized_pnl": round(total_realized_pnl, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "pnl": round(total_pnl, 2),
            "cost_start": round(total_start_cost, 2),
            "cost_end": round(total_end_cost, 2),
            "holding_market_value": round(total_end_market_value, 2),
            "pnl_pct": total_pnl_pct,
        })

    return result


from sqlalchemy.orm import Session
from datetime import date

def get_yearly_stats(db: Session) -> list[dict]:
    """年度收益统计
    
    计算逻辑：直接调用 get_yearly_position_details 汇总各标的明细收益，确保口径完全一致。
    年度总收益 = sum(各标的 realized_pnl + unrealized_pnl)
    """
    from models import DailySnapshot
    
    snapshots = db.query(DailySnapshot).all()
    year_set = sorted(set(s.date.year for s in snapshots))
    
    result = []
    
    for year in year_set:
        # 直接调用 get_yearly_position_details 获取明细
        details = get_yearly_position_details(db, year)
        summary = details.get("summary", {})
        
        # 从明细汇总数据
        total_realized_pnl = summary.get("total_realized_pnl", 0)
        total_unrealized_pnl = summary.get("total_unrealized_pnl", 0)
        total_pnl = summary.get("total_pnl", 0)
        
        # 从明细汇总获取成本和市值数据
        total_start_cost = summary.get("total_start_cost", 0)
        total_end_cost = summary.get("total_end_cost", 0)
        total_end_market_value = summary.get("total_end_market_value", 0)
        total_pnl_pct = summary.get("total_pnl_pct", 0)
        
        result.append({
            "year": year,
            "realized_pnl": round(total_realized_pnl, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "pnl": round(total_pnl, 2),
            "cost": round(total_end_cost, 2),
            "end_market_value": round(total_end_market_value, 2),
            "pnl_pct": total_pnl_pct,
        })
    return result



def get_monthly_position_details(db: Session, year: int, month: int) -> dict:
    """获取某月各持仓的收益明细
    
    返回该月有持仓的所有标的，包含：
    - 持仓明细列表（含已实现收益和持仓收益）
    - 汇总数据（总盈亏、总收益率等）
    
    计算逻辑（纯收益口径，不含新增投入）：
    - 当月总收益 = 本月末累计盈亏 - 上月末累计盈亏
    - 当月已实现收益 = 当月卖出交易的盈亏总和（移动平均成本法）
    - 当月持仓收益 = 当月总收益 - 当月已实现收益
    """
    from models import Position, Trade
    
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
    
    # 获取当月所有交易
    month_trades = db.query(Trade).filter(
        Trade.trade_date >= start_date,
        Trade.trade_date <= end_date
    ).all()
    
    # 获取上月最后一个交易日的市值（用于跨月比较）
    # 查询当月第一个快照日期的前一天的数据
    first_snap_date = min(s.date for s in snapshots)
    prev_day = first_snap_date - __import__('datetime').timedelta(days=1)
    
    # 查询该日期之前的最后一个快照
    prev_month_snap = db.query(DailySnapshot).filter(
        DailySnapshot.date <= prev_day
    ).order_by(DailySnapshot.date.desc()).first()
    
    if prev_month_snap:
        # 获取该日期的所有快照
        prev_month_snaps_list = db.query(DailySnapshot).filter(
            DailySnapshot.date == prev_month_snap.date
        ).all()
        prev_month_snaps = {s.code: s for s in prev_month_snaps_list}
    else:
        prev_month_snaps = {}
    
    positions = []
    total_start_cost = 0.0
    total_end_cost = 0.0
    total_realized_pnl = 0.0
    total_unrealized_pnl = 0.0
    
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
        
        # 过滤掉当月无持仓变化的
        if start_market_value == 0 and end_market_value == 0:
            continue
        
        # 获取持仓名称（有关联ETF短名则优先使用）
        position = db.query(Position).filter(Position.code == code).first()
        if position:
            name = position.linked_short_name if position.linked_short_name else position.name
        else:
            name = code
        
        # 月初/月末投入成本 = 市值 - 累计盈亏
        start_cost = start_market_value - start_total_pnl
        end_cost = end_market_value - end_total_pnl
        
        # 对于月中买入的情况（月初无持仓，月末有持仓），期初成本显示为买入当日的投入成本
        display_start_cost = start_cost if start_cost > 0 else end_cost
        
        total_start_cost += start_cost
        total_end_cost += end_cost
        
        # 计算该标的当月已实现收益（通过交易记录）
        code_trades = [t for t in month_trades if t.code == code]
        code_realized_pnl = 0.0
        running_cost = 0.0
        running_qty = 0.0
        
        for t in sorted(code_trades, key=lambda x: x.trade_date):
            if t.direction == 'buy':
                running_cost += t.amount
                running_qty += t.quantity or 0
            elif t.direction == 'sell':
                if running_qty > 0:
                    avg_cost = running_cost / running_qty
                    sell_cost = (t.quantity or 0) * avg_cost
                    realized = (t.amount - t.fee) - sell_cost
                    code_realized_pnl += realized
                    running_cost -= sell_cost
                    running_qty -= (t.quantity or 0)
        
        # 获取上月末累计盈亏（用于计算纯收益）
        prev_snap = prev_month_snaps.get(code)
        prev_month_total_pnl = prev_snap.total_pnl or 0 if prev_snap else 0
        
        # 当月纯收益 = 本月末累计盈亏 - 上月末累计盈亏（不含新增投入）
        code_pnl = end_total_pnl - prev_month_total_pnl
        
        # 当月持仓收益 = 当月纯收益 - 当月已实现收益
        code_unrealized_pnl = code_pnl - code_realized_pnl
        
        total_realized_pnl += code_realized_pnl
        total_unrealized_pnl += code_unrealized_pnl
        
        # 计算收益率（基于月初成本）
        if start_cost > 0:
            pnl_pct = round(code_pnl / start_cost * 100, 2)
        elif end_cost > 0:
            pnl_pct = round(code_pnl / end_cost * 100, 2)
        else:
            pnl_pct = 0
        
        positions.append({
            "code": code,
            "name": name,
            "start_market_value": round(start_market_value, 2),
            "end_market_value": round(end_market_value, 2),
            "start_cost": round(display_start_cost, 2),
            "realized_pnl": round(code_realized_pnl, 2),
            "unrealized_pnl": round(code_unrealized_pnl, 2),
            "pnl": round(code_pnl, 2),
            "pnl_pct": pnl_pct,
        })
    
    # 处理当月有交易但无快照的标的（已清仓标的）
    codes_with_snaps = set(snaps_by_code.keys())
    processed_codes = set()
    
    for trade in month_trades:
        if trade.code in codes_with_snaps or trade.code in processed_codes:
            continue
        processed_codes.add(trade.code)
        
        # 已清仓标的需要查询所有历史交易（买入可能在之前月份）
        code_trades = db.query(Trade).filter(
            Trade.code == trade.code,
            Trade.trade_date <= end_date
        ).all()
        
        # 计算已实现收益
        code_realized_pnl = 0.0
        running_cost = 0.0
        running_qty = 0.0
        total_buy_amount = 0.0
        
        for t in sorted(code_trades, key=lambda x: x.trade_date):
            if t.direction == 'buy':
                running_cost += t.amount
                running_qty += t.quantity or 0
                total_buy_amount += t.amount
            elif t.direction == 'sell':
                if running_qty > 0:
                    avg_cost = running_cost / running_qty
                    sell_cost = (t.quantity or 0) * avg_cost
                    realized = (t.amount - t.fee) - sell_cost
                    code_realized_pnl += realized
                    running_cost -= sell_cost
                    running_qty -= (t.quantity or 0)
        
        if abs(code_realized_pnl) >= 0.01:
            position = db.query(Position).filter(Position.code == trade.code).first()
            if position:
                name = position.linked_short_name if position.linked_short_name else position.name
            else:
                name = trade.name or trade.code
            
            positions.append({
                "code": trade.code,
                "name": name,
                "start_market_value": 0,
                "end_market_value": 0,
                "start_cost": round(total_buy_amount, 2) if total_buy_amount > 0 else 0,
                "realized_pnl": round(code_realized_pnl, 2),
                "unrealized_pnl": 0,
                "pnl": round(code_realized_pnl, 2),
                "pnl_pct": round(code_realized_pnl / total_buy_amount * 100, 2) if total_buy_amount > 0 else 0,
            })
            
            total_realized_pnl += code_realized_pnl
            total_start_cost += total_buy_amount
    
    # 按盈亏金额降序排列
    positions.sort(key=lambda x: x["pnl"], reverse=True)
    
    # 计算汇总数据
    total_start_market_value = sum(p["start_market_value"] for p in positions)
    total_end_market_value = sum(p["end_market_value"] for p in positions)
    total_pnl = total_realized_pnl + total_unrealized_pnl
    
    # 月度收益率 = 总收益 / 月末市值 × 100%
    total_pnl_pct = round(total_pnl / total_end_market_value * 100, 2) if total_end_market_value > 0 else 0
    
    summary = {
        "total_start_market_value": round(total_start_market_value, 2),
        "total_end_market_value": round(total_end_market_value, 2),
        "total_realized_pnl": round(total_realized_pnl, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": total_pnl_pct,
        "position_count": len(positions),
    }
    
    return {"positions": positions, "summary": summary}


def get_yearly_position_details(db: Session, year: int) -> dict:
    """获取某年度各持仓的收益明细
    
    返回该年有持仓的所有标的，包含：
    - 持仓明细列表（含已实现收益和持仓收益）
    - 汇总数据（总盈亏、总收益率等）
    """
    from models import Position, Trade
    
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
    
    # 获取当年所有交易
    year_trades = db.query(Trade).filter(
        Trade.trade_date >= start_date,
        Trade.trade_date <= end_date
    ).all()
    
    positions = []
    total_start_cost = 0.0
    total_end_cost = 0.0
    total_realized_pnl = 0.0
    total_unrealized_pnl = 0.0
    
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
        
        # 过滤掉当年无持仓且无盈亏的
        year_pnl = sum(s.daily_pnl or 0 for s in code_snaps)
        if start_market_value == 0 and end_market_value == 0 and abs(year_pnl) < 0.01:
            continue
        
        # 获取持仓名称（有关联ETF短名则优先使用）
        position = db.query(Position).filter(Position.code == code).first()
        if position:
            name = position.linked_short_name if position.linked_short_name else position.name
        else:
            name = code
        
        # 年初/年末投入成本 = 市值 - 累计盈亏
        start_cost = start_market_value - start_total_pnl
        end_cost = end_market_value - end_total_pnl
        
        # 对于年中买入的情况（年初无持仓，年末有持仓），期初成本显示为买入当日的投入成本
        display_start_cost = start_cost if start_cost > 0 else end_cost
        
        total_start_cost += start_cost
        total_end_cost += end_cost
        
        # 计算该标的当年已实现收益（通过交易记录）
        code_trades = [t for t in year_trades if t.code == code]
        code_realized_pnl = 0.0
        running_cost = 0.0
        running_qty = 0.0
        
        for t in sorted(code_trades, key=lambda x: x.trade_date):
            if t.direction == 'buy':
                running_cost += t.amount
                running_qty += t.quantity or 0
            elif t.direction == 'sell':
                if running_qty > 0:
                    avg_cost = running_cost / running_qty
                    sell_cost = (t.quantity or 0) * avg_cost
                    realized = (t.amount - t.fee) - sell_cost
                    code_realized_pnl += realized
                    running_cost -= sell_cost
                    running_qty -= (t.quantity or 0)
        
        # 获取上年末累计盈亏（用于计算纯收益）
        prev_year_snap = db.query(DailySnapshot).filter(
            DailySnapshot.date < start_date
        ).order_by(DailySnapshot.date.desc()).first()
        
        if prev_year_snap:
            prev_year_snaps_list = db.query(DailySnapshot).filter(
                DailySnapshot.date == prev_year_snap.date
            ).all()
            prev_year_snaps = {s.code: s for s in prev_year_snaps_list}
        else:
            prev_year_snaps = {}
        
        prev_snap = prev_year_snaps.get(code)
        
        # 如果没有上年末数据，使用本年年初（首个快照）的累计盈亏作为基准
        if prev_snap:
            prev_year_total_pnl = prev_snap.total_pnl or 0
        else:
            # 无上年末数据，使用本年首个快照的累计盈亏
            prev_year_total_pnl = start_total_pnl
        
        # 年度纯收益 = 本年末累计盈亏 - 上年末累计盈亏（不含新增投入）
        code_pnl = end_total_pnl - prev_year_total_pnl
        
        # 年度持仓收益 = 年度纯收益 - 年度已实现收益
        code_unrealized_pnl = code_pnl - code_realized_pnl
        
        total_realized_pnl += code_realized_pnl
        total_unrealized_pnl += code_unrealized_pnl
        
        # 计算收益率
        if start_cost > 0:
            pnl_pct = round(code_pnl / start_cost * 100, 2)
        elif end_cost > 0:
            pnl_pct = round(code_pnl / end_cost * 100, 2)
        else:
            pnl_pct = 0
        
        positions.append({
            "code": code,
            "name": name,
            "start_market_value": round(start_market_value, 2),
            "end_market_value": round(end_market_value, 2),
            "start_cost": round(display_start_cost, 2),
            "realized_pnl": round(code_realized_pnl, 2),
            "unrealized_pnl": round(code_unrealized_pnl, 2),
            "pnl": round(code_pnl, 2),
            "pnl_pct": pnl_pct,
        })
    
    # 处理当年有交易但无快照的标的（已清仓标的）
    # 获取所有有快照的标的代码
    codes_with_snaps = set(snaps_by_code.keys())
    
    # 检查当年有交易但不在快照中的标的
    processed_codes = set()
    for trade in year_trades:
        if trade.code in codes_with_snaps or trade.code in processed_codes:
            continue
        processed_codes.add(trade.code)
        
        # 获取该标的当年所有交易
        code_trades = [t for t in year_trades if t.code == trade.code]
        
        # 计算已实现收益
        code_realized_pnl = 0.0
        running_cost = 0.0
        running_qty = 0.0
        total_buy_amount = 0.0
        
        for t in sorted(code_trades, key=lambda x: x.trade_date):
            if t.direction == 'buy':
                running_cost += t.amount
                running_qty += t.quantity or 0
                total_buy_amount += t.amount
            elif t.direction == 'sell':
                if running_qty > 0:
                    avg_cost = running_cost / running_qty
                    sell_cost = (t.quantity or 0) * avg_cost
                    realized = (t.amount - t.fee) - sell_cost
                    code_realized_pnl += realized
                    running_cost -= sell_cost
                    running_qty -= (t.quantity or 0)
        
        # 只添加有盈亏的已清仓标的
        if abs(code_realized_pnl) >= 0.01:
            # 获取标的名称（有关联ETF短名则优先使用）
            position = db.query(Position).filter(Position.code == trade.code).first()
            if position:
                name = position.linked_short_name if position.linked_short_name else position.name
            else:
                name = trade.name or trade.code
            
            # 已清仓标的无持仓收益
            code_unrealized_pnl = 0.0
            
            positions.append({
                "code": trade.code,
                "name": name,
                "start_market_value": 0,
                "end_market_value": 0,
                "start_cost": round(total_buy_amount, 2) if total_buy_amount > 0 else 0,
                "realized_pnl": round(code_realized_pnl, 2),
                "unrealized_pnl": 0,
                "pnl": round(code_realized_pnl, 2),
                "pnl_pct": round(code_realized_pnl / total_buy_amount * 100, 2) if total_buy_amount > 0 else 0,
            })
            
            total_realized_pnl += code_realized_pnl
            total_start_cost += total_buy_amount
            # 已清仓标的年末成本为0
    
    # 按盈亏金额降序排列
    positions.sort(key=lambda x: x["pnl"], reverse=True)
    
    # 计算汇总数据
    total_start_market_value = sum(p["start_market_value"] for p in positions)
    total_end_market_value = sum(p["end_market_value"] for p in positions)
    total_pnl = total_realized_pnl + total_unrealized_pnl
    
    # 年度收益率 = 总收益 / 年末总市值（市值口径）
    total_pnl_pct = round(total_pnl / total_end_market_value * 100, 2) if total_end_market_value > 0 else 0
    
    summary = {
        "total_start_market_value": round(total_start_market_value, 2),
        "total_end_market_value": round(total_end_market_value, 2),
        "total_start_cost": round(total_start_cost, 2),
        "total_end_cost": round(total_end_cost, 2),
        "total_realized_pnl": round(total_realized_pnl, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": total_pnl_pct,
        "position_count": len(positions),
    }
    
    return {"positions": positions, "summary": summary}
