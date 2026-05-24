from sqlalchemy.orm import Session
from datetime import date

def get_yearly_stats(db: Session) -> list[dict]:
    from models import DailySnapshot, Trade
    """年度收益统计
    
    计算逻辑：
    - 年度总收益 = 本年末市值 - 上年末市值（跨年市值变化）
    - 当年已实现收益 = 当年卖出交易的盈亏总和（移动平均成本法）
    - 当年持仓收益 = 年度总收益 - 当年已实现收益
    """
    from models import Trade
    
    snapshots = db.query(DailySnapshot).all()
    year_set = sorted(set(s.date.year for s in snapshots))
    
    # 按日期索引快照
    snaps_by_date: dict[date, list] = {}
    for snap in snapshots:
        snaps_by_date.setdefault(snap.date, []).append(snap)
    sorted_dates = sorted(snaps_by_date.keys())
    
    result = []
    prev_year_end_market_value = 0.0
    
    for year in year_set:
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        
        # 获取当年所有交易
        year_trades = db.query(Trade).filter(
            Trade.trade_date >= year_start,
            Trade.trade_date <= year_end
        ).all()
        
        # 获取当年日期范围
        year_dates = [d for d in sorted_dates if d.year == year]
        if not year_dates:
            continue
            
        first_date = year_dates[0]
        last_date = year_dates[-1]
        
        first_snaps = {s.code: s for s in snaps_by_date.get(first_date, [])}
        last_snaps = {s.code: s for s in snaps_by_date.get(last_date, [])}
        
        # 计算本年末市值
        current_year_end_market_value = sum(
            s.market_value or 0 for s in snaps_by_date.get(last_date, [])
        )
        
        # 计算上年末市值（用于跨年比较）
        if year == min(year_set):
            # 第一年，上年末市值为0
            prev_year_end_market_value = 0.0
        else:
            # 获取上一年最后一个交易日
            prev_year = year - 1
            prev_year_dates = [d for d in sorted_dates if d.year == prev_year]
            if prev_year_dates:
                prev_last_date = prev_year_dates[-1]
                prev_year_end_market_value = sum(
                    s.market_value or 0 for s in snaps_by_date.get(prev_last_date, [])
                )
            else:
                prev_year_end_market_value = 0.0
        
        # 按代码分组计算
        codes = set(s.code for s in snapshots if s.date.year == year)
        total_realized_pnl = 0.0  # 当年已实现收益
        total_cost_start = 0.0  # 年初总成本
        total_cost_end = 0.0  # 年末总成本
        
        for code in codes:
            first_snap = first_snaps.get(code)
            last_snap = last_snaps.get(code)
            
            # 年初成本
            if first_snap:
                start_total_pnl = first_snap.total_pnl or 0
                start_market_value = first_snap.market_value or 0
                start_cost = start_market_value - start_total_pnl
                total_cost_start += start_cost
            
            # 年末成本
            if last_snap:
                end_total_pnl = last_snap.total_pnl or 0
                end_market_value = last_snap.market_value or 0
                end_cost = end_market_value - end_total_pnl
                total_cost_end += end_cost
            
            # 当年交易
            code_trades = [t for t in year_trades if t.code == code]
            
            # 遍历交易计算已实现收益
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
                        total_realized_pnl += realized
                        running_cost -= sell_cost
                        running_qty -= (t.quantity or 0)
        
        # 处理当年有交易但无快照的标的（已清仓标的）
        codes_with_snaps = codes
        traded_codes = set(t.code for t in year_trades)
        codes_without_snaps = traded_codes - codes_with_snaps
        
        for code in codes_without_snaps:
            code_trades = [t for t in year_trades if t.code == code]
            
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
                total_realized_pnl += code_realized_pnl
                total_cost_start += total_buy_amount
        
        # 年度总收益 = 本年末市值 - 上年末市值
        total_pnl = current_year_end_market_value - prev_year_end_market_value
        
        # 当年持仓收益 = 年度总收益 - 当年已实现收益
        total_unrealized_pnl = total_pnl - total_realized_pnl
        
        # 年度收益率 = 总收益 / 平均投入成本
        avg_cost = (total_cost_start + total_cost_end) / 2
        
        result.append({
            "year": year,
            "realized_pnl": round(total_realized_pnl, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "pnl": round(total_pnl, 2),
            "cost": round(total_cost_end, 2),
            "end_market_value": round(current_year_end_market_value, 2),
            "pnl_pct": round(total_pnl / avg_cost * 100, 2) if avg_cost > 0 else 0,
        })
    return result
